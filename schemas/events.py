from pydantic import BaseModel, Field
from datetime import datetime
from typing import Literal, Optional
import uuid

class BaseEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    user_id: str
    item_id: str
    session_id: Optional[str] = None

class ItemViewEvent(BaseEvent):
    event_type: Literal["item_view"] = "item_view"
    category: str
    price: Optional[float] = None  # current asking price

class BidPlacedEvent(BaseEvent):
    event_type: Literal["bid_placed"] = "bid_placed"
    bid_amount: float
    previous_bid: Optional[float] = None

class PurchaseCompletedEvent(BaseEvent):
    event_type: Literal["purchase_completed"] = "purchase_completed"
    final_price: float
    payment_method: str

# Union type for all events
AuctionEvent = ItemViewEvent | BidPlacedEvent | PurchaseCompletedEvent

# Example usage 
if __name__ == "__main__":
    event = BidPlacedEvent(user_id="user_123", item_id="item_456", bid_amount=150.0)
    print(event.model_dump_json(indent=2))

#test quickly: python -m schemas.events
#Why Pydantic v2? -Modern validation, fast serialization (model_dump_json), strict typing. We'll use it for producers (Phase 2) and API responses (Phase 4).
