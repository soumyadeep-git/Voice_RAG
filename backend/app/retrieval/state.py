import threading

_version = 0
_lock = threading.Lock()


def bump() -> None:
    global _version
    with _lock:
        _version += 1


def current() -> int:
    return _version
