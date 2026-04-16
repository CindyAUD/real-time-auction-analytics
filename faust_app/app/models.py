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
    price: Optional[float] = None


class BidPlacedEvent(BaseEvent):
    event_type: Literal["bid_placed"] = "bid_placed"
    bid_amount: float
    previous_bid: Optional[float] = None


class PurchaseCompletedEvent(BaseEvent):
    event_type: Literal["purchase_completed"] = "purchase_completed"
    final_price: float
    payment_method: str


AuctionEvent = ItemViewEvent | BidPlacedEvent | PurchaseCompletedEvent
