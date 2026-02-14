# bproto/protocol.py
from enum import Enum

class PacketType:
    """Tipe Paket Data untuk komunikasi"""
    PING = "PING"
    PONG = "PONG"
    FILE_INIT = "FILE_INIT"
    MESSAGE = "MESSAGE"           # Fitur Baru: Chat
    CLIPBOARD = "CLIPBOARD"       # Fitur Baru: Remote Clipboard
    AUTH_CHALLENGE = "CHALLENGE"
    AUTH_OK = "OK"
    AUTH_FAIL = "FAIL"

class AuthMode:
    TOKEN = "TOKEN"
    NEW_HANDSHAKE = "NEW_HANDSHAKE"