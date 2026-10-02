import time


def retry(fn, attempts: int = 3, delay_seconds: float = 1.0, default=None):
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except OSError:
            if attempt == attempts:
                return default
            time.sleep(delay_seconds)


def chunked(items: list, size: int) -> list[list]:
    return [items[i : i + size] for i in range(0, len(items), size)]
