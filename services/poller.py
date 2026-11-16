import logging
import threading
import time


class Poller(threading.Thread):
    """Background loop. The service itself decides whether a fetch is due, so nothing is fetched twice."""

    def __init__(self, service):
        super().__init__(daemon=True, name="rate-poller")
        self.service = service

    def run(self):
        while True:
            try:
                self.service.refresh_if_due()
            except Exception:
                logging.getLogger("rates").exception("Poller error")
            time.sleep(1)
