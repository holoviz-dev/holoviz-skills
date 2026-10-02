import re
from datetime import datetime

SCAN_TIME_RE = re.compile(r"(\d{8}_\d{6})")


def scan_time(filename: str) -> datetime | None:
    match = SCAN_TIME_RE.search(filename)
    return datetime.strptime(match.group(1), "%Y%m%d_%H%M%S") if match else None


class NexradSource:
    def __init__(self, base_url: str):
        self.base_url = base_url

    def url(self, filename: str) -> str:
        return f"{self.base_url}/{filename}"
