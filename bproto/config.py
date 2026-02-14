# bproto/config.py

PROTOCOL_ID = b'BPROTO_V1'
DISCOVERY_PORT = 7001       # Port UDP untuk broadcast/discovery
TCP_PORT = 7002
CHUNK_SIZE = 1024 * 1024 * 4 # 4MB Buffer
SESSION_TIMEOUT = 3600      # 1 Jam
DEFAULT_SECRET = "ernoba-root"
DEFAULT_SAVE_DIR = "BProto_Received"