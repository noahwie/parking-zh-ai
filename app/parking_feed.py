from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, List, Tuple
import time

import feedparser


FEED_URL = "https://www.pls-zh.ch/plsFeed/rss/"


@dataclass(frozen=True)
class ParkingLot:
    name: str
    link: str
    status: str               # "open", "closed", "unknown", etc.
    free_spaces: Optional[int]
    updated_at: Optional[datetime]


def _parse_description(desc: str) -> Tuple[str, Optional[int]]:
    """
    Examples:
      "open / 43"
      "???? / ???"
    """
    if not desc:
        return "unknown", None

    parts = [p.strip() for p in desc.split("/")]
    if len(parts) != 2:
        return desc.strip().lower() or "unknown", None

    status_raw, spaces_raw = parts[0], parts[1]

    status = status_raw.lower()
    if "??" in status_raw:
        status = "unknown"

    try:
        free = int(spaces_raw)
    except Exception:
        free = None

    return status, free


def _parse_dt(entry) -> Optional[datetime]:
    # feedparser often provides: entry.published_parsed (time.struct_time)
    t = getattr(entry, "published_parsed", None)
    if not t:
        return None
    return datetime.fromtimestamp(time.mktime(t), tz=timezone.utc)


class FeedCache:
    def __init__(self, ttl_seconds: int = 15):
        self.ttl_seconds = ttl_seconds
        self._expires_at: float = 0.0
        self._value: List[ParkingLot] = []

    def get(self) -> List[ParkingLot]:
        now = time.time()
        if now < self._expires_at and self._value:
            return self._value

        parsed = feedparser.parse(FEED_URL)

        lots: List[ParkingLot] = []
        for e in parsed.entries:
            status, free = _parse_description(getattr(e, "description", ""))
            lots.append(
                ParkingLot(
                    name=getattr(e, "title", "").strip(),
                    link=getattr(e, "link", "").strip(),
                    status=status,
                    free_spaces=free,
                    updated_at=_parse_dt(e),
                )
            )

        # Sort: open first, then by most free spaces
        def sort_key(x: ParkingLot):
            open_rank = 0 if x.status == "open" else 1
            free_rank = -(x.free_spaces if x.free_spaces is not None else -1)
            return (open_rank, free_rank, x.name.lower())

        lots.sort(key=sort_key)

        self._value = lots
        self._expires_at = now + self.ttl_seconds
        return lots
