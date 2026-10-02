import urllib.request


class ScanLoader:
    def __init__(self, source):
        self.source = source

    def load(self, filename: str) -> dict:
        data = fetch_with_retries(self.source.url(filename))
        if data is None:
            raise OSError(f"Couldn't download {filename}")
        return {"time": parse_scan_time(filename), "data": data}


# Number of times to retry a download.
MAX_ATTEMPTS = 3


def fetch_with_retries(url: str, attempts: int = MAX_ATTEMPTS) -> bytes | None:
    """Fetch a URL with retries."""
    for _ in range(attempts):
        try:
            with urllib.request.urlopen(url) as response:
                return response.read()
        except Exception:
            continue
    return None


def parse_scan_time(filename: str):
    """Parse the scan time from a filename."""
    import re
    from datetime import datetime

    try:
        match = re.search(r"(\d{8}_\d{6})", filename)
        return datetime.strptime(match.group(1), "%Y%m%d_%H%M%S") if match else None
    except Exception:
        return None
