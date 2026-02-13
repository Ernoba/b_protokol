import time
from bproto import BProto

def on_file_received(msg):
    # Callback khusus untuk UI Server
    print(f"✅ SERVER EVENT: {msg}")

def main():
    # Setup Server
    print("=== FILE SERVER STARTED ===")
    server = BProto(
        device_name="Ernoba-Server", 
        secret="rahasia123", 
        save_dir="./Storage_Server"
    )
    
    # Override event log agar lebih cantik
    server.events["log"] = on_file_received
    
    server.start()
    
    try:
        while True:
            # Server standby, bisa melakukan tugas lain di background
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping Server...")
        server.stop()

if __name__ == "__main__":
    main()