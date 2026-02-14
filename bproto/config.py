# bproto/config.py

# Identitas Protokol
PROTOCOL_ID = b'BPROTO_V2' # Upgrade version tag
DISCOVERY_PORT = 7001
TCP_PORT = 7002

# Transfer Settings
CHUNK_SIZE = 1024 * 1024 * 4  # 4MB Buffer
SESSION_TIMEOUT = 3600       # 1 Jam
CONNECTION_TIMEOUT = 10      # 10 Detik

# Defaults
DEFAULT_SECRET = "ernoba-root"
DEFAULT_SAVE_DIR = "BProto_Received"

# Features Flags
ENABLE_ENCRYPTION = False    # <--- Ubah ini jadi False
ENABLE_COMPRESSION = False  # Siap untuk masa depan
VERIFY_INTEGRITY = True      # Fitur Baru: Cek Hash File