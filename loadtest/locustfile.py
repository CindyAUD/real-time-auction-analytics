"""
Locust Load Test Script for Auction Analytics Pipeline

Simulates high load (up to 1,000 events/sec) to test:
- Event ingestion via Kafka/Redpanda
- Faust processor performance
- API endpoint throughput
- End-to-end pipeline latency

Usage:
    locust -f locustfile.py --host=http://localhost:8000 -u 100 -r 10
    # -u: number of users, -r: spawn rate per second
"""

from locust import HttpUser, task, between, events
from confluent_kafka import Producer
from faker import Faker
import json
import random
import uuid
from datetime import datetime
import threading

fake = Faker()

# Kafka configuration
KAFKA_BROKER = "localhost:19092"
TOPIC = "raw_events"

# Event type weights (realistic distribution)
EVENT_WEIGHTS = {
    "item_view": 70,  # 70% views
    "bid_placed": 25,  # 25% bids
    "purchase_completed": 5,  # 5% purchases
}

# Global producer pool for thread-safe Kafka access
_producer_pool: list = []
_pool_lock = threading.Lock()
_pool_size = 10  # Number of producers in pool


def create_producer():
    """Create a Kafka producer with optimized settings"""
    conf = {
        "bootstrap.servers": KAFKA_BROKER,
        "client.id": f"locust-loadtest-{uuid.uuid4().hex[:8]}",
        "acks": "1",  # Less strict for load testing
        "linger.ms": 5,
        "batch.num.messages": 10000,
        "queue.buffering.max.messages": 100000,
        "queue.buffering.max.ms": 10,
        "compression.type": "lz4",
        "max.in.flight.requests.per.connection": 5,
    }
    return Producer(conf)


def get_producer():
    """Get a producer from the pool (thread-safe)"""
    with _pool_lock:
        if _producer_pool:
            return _producer_pool.pop()
    # Create new producer if pool is empty
    return create_producer()


def return_producer(producer):
    """Return a producer to the pool"""
    with _pool_lock:
        if len(_producer_pool) < _pool_size:
            _producer_pool.append(producer)
        else:
            producer.close()


def delivery_callback(err, msg):
    """Handle delivery reports"""
    if err:
        print(f"Delivery failed: {err}")
        events.request.fire(
            request_type="Kafka", name="produce", response_time=0, exception=err
        )


class AuctionUser(HttpUser):
    """Simulates a user generating auction events"""

    # Fast wait time for high throughput
    wait_time = between(0.01, 0.05)  # 10-50ms between tasks

    def on_start(self):
        """Initialize user session"""
        self.event_types = list(EVENT_WEIGHTS.keys())
        self.producer = get_producer()
        self.events_produced = 0
        self.produce_errors = 0

    def on_stop(self):
        """Cleanup on user stop"""
        return_producer(self.producer)

    def _weighted_choice(self):
        """Select event type based on weights"""
        r = random.randint(1, 100)
        cumulative = 0
        for event_type, weight in EVENT_WEIGHTS.items():
            cumulative += weight
            if r <= cumulative:
                return event_type
        return "item_view"

    def generate_event(self):
        """Generate a random auction event"""
        event_type = self._weighted_choice()

        base = {
            "event_id": str(uuid.uuid4()),
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "user_id": f"user_{random.randint(1000, 9999)}",
            "item_id": f"item_{random.randint(100, 999)}",
            "session_id": str(uuid.uuid4()),
        }

        if event_type == "item_view":
            return {
                **base,
                "event_type": "item_view",
                "category": random.choice(["electronics", "fashion", "home", "sports"]),
                "price": round(random.uniform(10, 500), 2),
            }
        elif event_type == "bid_placed":
            bid_amount = round(random.uniform(50, 1000), 2)
            return {
                **base,
                "event_type": "bid_placed",
                "bid_amount": bid_amount,
                "previous_bid": round(bid_amount * random.uniform(0.7, 0.95), 2)
                if random.random() > 0.3
                else None,
            }
        else:  # purchase_completed
            return {
                **base,
                "event_type": "purchase_completed",
                "final_price": round(random.uniform(100, 2000), 2),
                "payment_method": random.choice(["card", "paypal", "crypto"]),
            }

    @task(10)
    def produce_event(self):
        """Produce an event to Kafka/Redpanda"""
        event = self.generate_event()

        try:
            # Serialize event
            value = json.dumps(event).encode("utf-8")
            key = event["user_id"].encode("utf-8")

            # Produce to Kafka
            self.producer.produce(
                topic=TOPIC, key=key, value=value, callback=delivery_callback
            )

            # Trigger callback processing
            self.producer.poll(0)

            self.events_produced += 1

        except Exception as e:
            self.produce_errors += 1
            print(f"Produce error: {e}")

    @task(3)
    def test_api_stats(self):
        """Test /api/stats endpoint"""
        self.client.get("/api/stats", name="/api/stats")

    @task(3)
    def test_api_funnel(self):
        """Test /api/funnel endpoint"""
        self.client.get("/api/funnel", name="/api/funnel")

    @task(2)
    def test_api_top_items(self):
        """Test /api/top-items endpoint"""
        self.client.get("/api/top-items?limit=10", name="/api/top-items")

    @task(1)
    def test_api_revenue(self):
        """Test /api/revenue endpoint"""
        self.client.get("/api/revenue?hours=6", name="/api/revenue")

    @task(1)
    def test_api_health(self):
        """Test health endpoint"""
        self.client.get("/health", name="/health")


class APILoadUser(HttpUser):
    """Dedicated user for API-only load testing (no Kafka)"""

    wait_time = between(0.05, 0.2)  # 50-200ms between requests

    @task(5)
    def stats(self):
        self.client.get("/api/stats", name="/api/stats")

    @task(5)
    def funnel(self):
        self.client.get("/api/funnel", name="/api/funnel")

    @task(3)
    def top_items(self):
        self.client.get("/api/top-items?limit=10", name="/api/top-items")

    @task(2)
    def revenue(self):
        self.client.get("/api/revenue?hours=6", name="/api/revenue")

    @task(1)
    def health(self):
        self.client.get("/health", name="/health")


# Initialize producer pool on module load
def on_init():
    """Initialize producer pool"""
    global _producer_pool
    print(f"Initializing {_pool_size} Kafka producers...")
    for _ in range(_pool_size):
        _producer_pool.append(create_producer())
    print("Producer pool ready")


# Initialize on module import (runs when Locust loads the file)
on_init()
