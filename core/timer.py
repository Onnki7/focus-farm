import threading, time
from datetime import datetime

class SessionMonitor(threading.Thread):
    def __init__(self, interval=30):
        super().__init__(daemon=True)
        self.interval = interval
        self._stop_event = threading.Event()

    def run(self):
        from core import db
        while not self._stop_event.is_set():
            time.sleep(self.interval)
            try:
                db.expire_overdue_sessions(datetime.utcnow().isoformat())
            except Exception:
                pass

    def stop(self):
        self._stop_event.set()
