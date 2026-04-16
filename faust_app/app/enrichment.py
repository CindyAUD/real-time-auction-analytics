from datetime import datetime, timezone
from typing import Optional
import json
from .models import AuctionEvent, BidPlacedEvent, ItemViewEvent, PurchaseCompletedEvent


def parse_event(raw: bytes) -> Optional[AuctionEvent]:
    try:
        data = json.loads(raw)
        event_type = data.get("event_type")
        if event_type == "item_view":
            return ItemViewEvent(**data)
        elif event_type == "bid_placed":
            return BidPlacedEvent(**data)
        elif event_type == "purchase_completed":
            return PurchaseCompletedEvent(**data)
        return None
    except Exception:
        return None


def enrich(event: AuctionEvent) -> dict:
    data = event.model_dump()
    data["timestamp"] = event.timestamp.isoformat()
    data["processed_at"] = datetime.now(timezone.utc).isoformat()

    if isinstance(event, BidPlacedEvent) and event.previous_bid:
        data["bid_increment"] = round(event.bid_amount - event.previous_bid, 2)
        data["bid_increment_pct"] = round(
            (event.bid_amount - event.previous_bid) / event.previous_bid * 100, 2
        )

    return data
