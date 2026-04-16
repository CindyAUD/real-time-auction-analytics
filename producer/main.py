import time
import random
from confluent_kafka import Producer
from prometheus_client import start_http_server, Counter, Histogram
from schemas.events import (
    AuctionEvent,
    ItemViewEvent,
    BidPlacedEvent,
    PurchaseCompletedEvent,
)
from pydantic import ValidationError


# Prometheus metrics
EVENTS_PRODUCED = Counter(
    "events_produced_total", "Total events produced", ["event_type"]
)
EVENTS_FAILED = Counter(
    "events_failed_total", "Total events that failed validation", ["reason"]
)
PRODUCE_LATENCY = Histogram(
    "produce_latency_seconds", "Time to produce a message", ["event_type"]
)

# Producer configuration
producer_conf = {
    "bootstrap.servers": "localhost:19092",  # external port from docker-compose
    "client.id": "auction-producer",
    "acks": "all",  # wait for all replicas (strong durability)
    "linger.ms": 5,  # small batching for better throughput
}

producer = Producer(producer_conf)


def delivery_report(err, msg):
    """Callback called when message is delivered or fails."""
    if err is not None:
        print(f"Delivery failed: {err}")
        EVENTS_FAILED.labels(reason="delivery_error").inc()
    else:
        print(
            f"Delivered to {msg.topic()} [{msg.partition()}] at offset {msg.offset()}"
        )


def produce_event(event: AuctionEvent):
    """Produce a single validated event to raw_events topic."""
    start_time = time.time()

    try:
        # Serialize to JSON
        value = event.model_dump_json().encode("utf-8")
        key = event.user_id.encode("utf-8")  # use user_id as key for partitioning

        producer.produce(
            topic="raw_events", key=key, value=value, callback=delivery_report
        )

        # Trigger callbacks
        producer.poll(0)

        latency = time.time() - start_time
        PRODUCE_LATENCY.labels(event_type=event.event_type).observe(latency)
        EVENTS_PRODUCED.labels(event_type=event.event_type).inc()

        print(f"✅ Produced {event.event_type} for item {event.item_id}")

    except Exception as e:
        print(f"❌ Produce error: {e}")
        EVENTS_FAILED.labels(reason="produce_exception").inc()


def main(rate: int = 10):  # events per second
    """Run the simulator + producer together."""
    print(f"🚀 Starting producer at ~{rate} events/sec. Press Ctrl+C to stop.")
    print("Metrics available at http://localhost:8002/metrics")
    # Start Prometheus metrics server on port 8002
    start_http_server(8002)

    while True:
        try:
            # Reuse your simulator logic or generate directly
            event_type = random.choice(
                ["item_view", "bid_placed", "purchase_completed"]
            )

            base = {
                "user_id": f"user_{random.randint(1000, 9999)}",
                "item_id": f"item_{random.randint(100, 999)}",
                "session_id": f"session_{random.randint(10000, 99999)}",
            }

            if event_type == "item_view":
                event = ItemViewEvent(
                    **base,
                    category=random.choice(
                        ["electronics", "fashion", "home", "sports"]
                    ),
                    price=round(random.uniform(10, 500), 2),
                )
            elif event_type == "bid_placed":
                event = BidPlacedEvent(
                    **base,
                    bid_amount=round(random.uniform(50, 1000), 2),
                    previous_bid=round(random.uniform(40, 900), 2)
                    if random.random() > 0.3
                    else None,
                )
            else:
                event = PurchaseCompletedEvent(
                    **base,
                    final_price=round(random.uniform(100, 2000), 2),
                    payment_method=random.choice(["card", "paypal", "crypto"]),
                )

            produce_event(event)

            # Sleep to control rate (simple approximation)
            time.sleep(1.0 / rate)

        except KeyboardInterrupt:
            print("\nStopping producer...")
            producer.flush()  # wait for all messages to be delivered
            break
        except ValidationError as e:
            print(f"Validation failed: {e}")
            EVENTS_FAILED.labels(reason="validation_error").inc()


if __name__ == "__main__":
    import sys

    rate = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    print(f"Starting producer at {rate} events/sec")
    main(rate=rate)
