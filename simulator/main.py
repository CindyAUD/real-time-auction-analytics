import time
import random
from faker import Faker
from schemas.events import ItemViewEvent, BidPlacedEvent, PurchaseCompletedEvent

fake = Faker()


def generate_event():
    event_type = random.choice(["item_view", "bid_placed", "purchase_completed"])
    user_id = fake.uuid4()
    item_id = f"item_{random.randint(100, 999)}"
    session_id = fake.uuid4()

    if event_type == "item_view":
        return ItemViewEvent(
            user_id=user_id,
            item_id=item_id,
            session_id=session_id,
            category=fake.word(),
            price=round(random.uniform(10, 500), 2),
        )
    elif event_type == "bid_placed":
        return BidPlacedEvent(
            user_id=user_id,
            item_id=item_id,
            session_id=session_id,
            bid_amount=round(random.uniform(50, 1000), 2),
            previous_bid=round(random.uniform(40, 900), 2)
            if random.random() > 0.3
            else None,
        )
    else:
        return PurchaseCompletedEvent(
            user_id=user_id,
            item_id=item_id,
            session_id=session_id,
            final_price=round(random.uniform(100, 2000), 2),
            payment_method=random.choice(["card", "paypal", "crypto"]),
        )


def run_simulator(rate: int = 10):  # events per second
    print(f"Starting simulator at {rate} events/sec. Press Ctrl+C to stop.")
    while True:
        event = generate_event()
        print(f"[{event.timestamp}] {event.event_type} for item {event.item_id}")
        # Later: we'll send this to Redpanda producer
        # For now: just print or write to file
        time.sleep(1.0 / rate)


if __name__ == "__main__":
    run_simulator(rate=5)  # start slow
