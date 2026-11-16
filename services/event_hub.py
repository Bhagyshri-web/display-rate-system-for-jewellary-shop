import threading


class EventHub:
    """Wakes every connected TV stream when rates or settings change."""

    def __init__(self):
        self._cv = threading.Condition()
        self.version = 0

    def publish(self):
        with self._cv:
            self.version += 1
            self._cv.notify_all()

    def wait(self, seen_version, timeout):
        with self._cv:
            self._cv.wait_for(lambda: self.version != seen_version, timeout=timeout)
            return self.version
