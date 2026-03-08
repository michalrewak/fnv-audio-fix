"""Simple logger that writes to both stdout and a log file."""

import time


class Logger:
    """Dual-output logger (console + file)."""

    def __init__(self, log_path=None):
        self.log_path = log_path
        self._file = None
        if log_path:
            self._file = open(log_path, "w", encoding="utf-8")
        self._start = time.time()

    def log(self, msg, level="INFO"):
        elapsed = time.time() - self._start
        line = f"[{elapsed:8.1f}s] [{level:5s}] {msg}"
        print(line)
        if self._file:
            self._file.write(line + "\n")
            self._file.flush()

    def close(self):
        if self._file:
            self._file.close()
            self._file = None
