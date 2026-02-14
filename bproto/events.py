# bproto/events.py

class EventManager:
    def __init__(self):
        self._listeners = {
            "log": [],
            "error": [],
            "progress": [],
            "message": [],    # Baru: Event chat masuk
            "clipboard": [],  # Baru: Event clipboard
            "peer_found": []  # Baru: Event peer ditemukan
        }

    def on(self, event_name, callback):
        """Mendaftarkan listener baru"""
        if event_name in self._listeners:
            self._listeners[event_name].append(callback)

    def emit(self, event_name, *args):
        """Memicu event"""
        if event_name in self._listeners:
            for callback in self._listeners[event_name]:
                try:
                    callback(*args)
                except Exception as e:
                    print(f"[EVENT ERROR] {event_name}: {e}")

    # Helper standar agar tidak merubah behavior lama
    def log(self, msg): self.emit("log", msg)
    def error(self, msg): self.emit("error", msg)
    def progress(self, filename, percent, speed): self.emit("progress", filename, percent, speed)