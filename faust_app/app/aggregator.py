from collections import defaultdict
from datetime import datetime, timezone
from typing import Any


class WindowAggregator:
    """
    Tumbling 1-minute window aggregator.
    Keyed by (window_start_minute, dimension).
    In production you'd back this with Redis or a time-series DB.
    """

    def __init__(self):
        self.bids_per_item: dict = defaultdict(int)
        self.views_per_item: dict = defaultdict(int)
        self.revenue_per_category: dict = defaultdict(float)

    def _window_key(self, event_time: str, dimension: str) -> str:
        dt = datetime.fromisoformat(event_time)
        minute = dt.replace(second=0, microsecond=0).isoformat()
        return f"{minute}|{dimension}"

    def update(self, event: dict) -> None:
        event_type = event.get("event_type")
        item_id = event.get("item_id", "unknown")
        category = event.get("category", "unknown")
        timestamp = event.get("timestamp", datetime.now(timezone.utc).isoformat())

        if event_type == "item_view":
            self.views_per_item[self._window_key(timestamp, item_id)] += 1

        elif event_type == "bid_placed":
            self.bids_per_item[self._window_key(timestamp, item_id)] += 1

        elif event_type == "purchase_completed":
            self.revenue_per_category[self._window_key(timestamp, category)] += (
                event.get("final_price", 0.0)
            )

    def snapshot(self) -> dict[str, Any]:
        return {
            "bids_per_item": dict(self.bids_per_item),
            "views_per_item": dict(self.views_per_item),
            "revenue_per_category": dict(self.revenue_per_category),
        }
