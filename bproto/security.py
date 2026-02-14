# bproto/security.py
import hashlib
import uuid
import time
import base64
import os
from .config import SESSION_TIMEOUT, ENABLE_ENCRYPTION

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False

class SecurityManager:
    def __init__(self, secret):
        self.secret = secret
        self.authorized_sessions = {}
        self.client_tokens = {}
        
        # Buat Key AES 256-bit dari secret config
        if HAS_CRYPTO:
            key = hashlib.sha256(secret.encode()).digest()
            self.aes = AESGCM(key)
        else:
            print("[WARNING] Library 'cryptography' not found. Encryption disabled.")

    def encrypt_data(self, data: bytes) -> bytes:
        """Enkripsi data bytes dengan AES-GCM"""
        if not ENABLE_ENCRYPTION or not HAS_CRYPTO:
            return data
        
        nonce = os.urandom(12) # 12 bytes nonce rekomendasi untuk GCM
        ciphertext = self.aes.encrypt(nonce, data, None)
        return nonce + ciphertext

    def decrypt_data(self, data: bytes) -> bytes:
        """Dekripsi data bytes"""
        if not ENABLE_ENCRYPTION or not HAS_CRYPTO:
            return data
            
        try:
            nonce = data[:12]
            ciphertext = data[12:]
            return self.aes.decrypt(nonce, ciphertext, None)
        except Exception:
            raise ValueError("Decryption failed: Invalid Key or Corrupted Data")

    def generate_token(self):
        return uuid.uuid4().hex

    def create_session_for(self, ip):
        token = self.generate_token()
        self.authorized_sessions[ip] = {
            'token': token,
            'expires': time.time() + SESSION_TIMEOUT
        }
        return token

    def verify_token(self, ip, token):
        if ip in self.authorized_sessions:
            sess = self.authorized_sessions[ip]
            if sess['token'] == token and time.time() < sess['expires']:
                return True
        return False

    def get_outgoing_auth(self, target_ip):
        now = time.time()
        if target_ip in self.client_tokens:
            session = self.client_tokens[target_ip]
            if now < session['expires']:
                return {"auth_mode": "TOKEN", "data": session['token']}
        return {"auth_mode": "NEW_HANDSHAKE", "data": None}

    def save_client_token(self, target_ip, token):
        self.client_tokens[target_ip] = {
            'token': token,
            'expires': time.time() + SESSION_TIMEOUT
        }

    def verify_handshake(self, nonce, client_proof):
        # Simple SHA verification for handshake proof
        expected = hashlib.sha256((self.secret + nonce).encode()).hexdigest()
        return client_proof == expected

    def create_proof(self, nonce):
        return hashlib.sha256((self.secret + nonce).encode()).hexdigest()