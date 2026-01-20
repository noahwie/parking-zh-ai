from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, List, Tuple
import time

import feedparser


FEED_URL = "https://www.pls-zh.ch/plsFeed/rss/"


# Datamodel class
@dataclass(frozen=True) # @dataclass adds methods like __init__ frozen=true means once created cant be changed
class ParkingLot:
    name: str
    link: str
    status: str               # "open", "closed", "unknown", etc.
    free_spaces: Optional[int] # this field is either an int or none
    updated_at: Optional[datetime] # this field is either a datetime object or none

# parses the description string
def _parse_description(desc: str) -> Tuple[str, Optional[int]]:
    """
    Examples:
      "open / 43"
      "???? / ???"
    """
    
    # if parsed feed description is empty return string unknown
    if not desc:
        return "unknown", None

    # turns input into two parts and removes white space ("open / 43" -> ["open", "43"])
    parts = [p.strip() for p in desc.split("/")]
    # if length of parts does not equal 2 return lowered and stripped or unkown
    if len(parts) != 2:
        return desc.strip().lower() or "unknown", None

    # takes first element of parts and stores in status_raw and second element of parts and stores in spaces_raw: ["open", "43"] -> status_raw: ["open"], spaces_raw: ["43"]
    status_raw, spaces_raw = parts[0], parts[1]

    # checks if "??" appears in status raw if so returns assigns status="unknown"
    status = status_raw.lower()
    if "??" in status_raw:
        status = "unknown"

    # trys to convert spaces_raw into int: "43" -> free=43 if that is not possible assigns free=none
    try:
        free = int(spaces_raw)
    except Exception:
        free = None

    # returns a tuple of newly assigned attributes status and free
    return status, free

# parses a entry into a timestamp
def _parse_dt(entry) -> Optional[datetime]:
    # feedparser often provides: entry.published_parsed (time.struct_time)
    t = getattr(entry, "published_parsed", None)
    if not t:
        return None
    return datetime.fromtimestamp(time.mktime(t), tz=timezone.utc)

# stores parsed data into TTL cache 
class FeedCache:
    # __init__ runs on object creation 
    def __init__(self, ttl_seconds: int = 15):
        self.ttl_seconds = ttl_seconds # saves the ttl to the object self
        self._expires_at: float = 0.0 # expiration timestamp starts at 0.0
        self._value: List[ParkingLot] = [] # holds the cached list of parking lots and starts empty 

    # get method to retrieve parking data which returns a list of ParkingLot objects
    def get(self) -> List[ParkingLot]:
        now = time.time()
        # if now is lower than expires_at and cached list isnt empty return cached value immediately
        if now < self._expires_at and self._value:
            return self._value

        # downloads and parses RSS feed (parsed contains .entries items)
        parsed = feedparser.parse(FEED_URL)

        #creates empty list called lots and will contain ParkingLot
        lots: List[ParkingLot] = []
        # for every entry in parsed
        for e in parsed.entries:
            # gets entry description, uses _parse_description to return status and free
            status, free = _parse_description(getattr(e, "description", ""))
            lots.append(
                # builds parkinglot object
                ParkingLot(
                    name=getattr(e, "title", "").strip(), # gets name from rss entry and strips
                    link=getattr(e, "link", "").strip(), # gets link from rss entry and strips
                    status=status, # assigns parsed status to status
                    free_spaces=free, # assigns free to free spaces
                    updated_at=_parse_dt(e), # calls parse dt for entry timestamp
                )
            )

        # Sort: open first, then by most free spaces
        def sort_key(x: ParkingLot):
            open_rank = 0 if x.status == "open" else 1 # open comes first
            free_rank = -(x.free_spaces if x.free_spaces is not None else -1) # then sorts by descending parking spaces
            return (open_rank, free_rank, x.name.lower())

        lots.sort(key=sort_key)

        self._value = lots
        self._expires_at = now + self.ttl_seconds
        return lots
