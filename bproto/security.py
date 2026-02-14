# bproto/security.py
import hashlib
import uuid
import time
import base64
import os
from .config import SESSION_TIMEOUT

# Jika ingin enkripsi kuat, perlu 'pip install cryptography'
# Untuk sekarang kita pakai implementasi XOR sederhana atau 
# pure python AES jika library tidak ada, tapi demi kompatibilitas 
# tanpa dependensi berat, kita pakai logic Auth yang lama + Scrambling.

class SecurityManager:
    def __init__(self, secret):
        self.secret = secret
        self.authorized_sessions = {}  # IP -> {token, expires}
        self.client_tokens = {}        # IP -> {token, expires} (Outgoing)

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
        expected = hashlib.sha256((self.secret + nonce).encode()).hexdigest()
        return client_proof == expected

    def create_proof(self, nonce):
        return hashlib.sha256((self.secret + nonce).encode()).hexdigest()