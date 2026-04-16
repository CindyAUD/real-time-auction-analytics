import asyncio
import json
import logging
import os
import time
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from .enrichment import parse_event, enrich
from .aggregator import WindowAggregator
from .sink import write_to_parquet
from .metrics import (
    events_consumed,
    events_failed,
    processing_latency,
    start_metrics_server,
)

logger = logging.getLogger(__name__)

BROKER = os.getenv("KAFKA_BROKER", "redpanda:9092")
BATCH_SIZE = 10  # small for quick feedback during testing


async def run():
    start_metrics_server(port=8001)
    aggregator = WindowAggregator()
    buffer: list[dict] = []

    logger.info("🚀 Auction Processor starting...")

    while True:
        consumer = None
        producer = None
        try:
            consumer = AIOKafkaConsumer(
                "raw_events",
                bootstrap_servers=BROKER,
                group_id="auction-processor",
                auto_offset_reset="earliest",
                enable_auto_commit=False,  # manual commit for control
                fetch_max_wait_ms=500,  # don't wait too long
                fetch_min_bytes=1,
                session_timeout_ms=45000,
                heartbeat_interval_ms=15000,
            )
            producer = AIOKafkaProducer(bootstrap_servers=BROKER, acks="all")

            logger.info("Starting Kafka consumer...")
            await consumer.start()
            logger.info("Consumer started successfully")
            logger.info("Starting Kafka producer...")
            await producer.start()
            logger.info("Producer started successfully")

            logger.info("✅ Successfully started consumer and joined group")
            logger.info("📥 Now polling for messages from raw_events...")

            async for msg in consumer:
                start_time = time.perf_counter()

                logger.info(f"📨 Received message from offset {msg.offset}")

                event = parse_event(msg.value)

                if event is None:
                    events_failed.inc()
                    dead_payload = {
                        "raw": msg.value.decode("utf-8", errors="replace"),
                        "error": "parse_failed",
                        "offset": msg.offset,
                    }
                    await producer.send_and_wait(
                        "dead_letter", value=json.dumps(dead_payload).encode()
                    )
                    await consumer.commit()
                    continue

                enriched = enrich(event)
                aggregator.update(enriched)
                buffer.append(enriched)

                # Forward enriched event
                await producer.send_and_wait(
                    "processed_events",
                    key=event.user_id.encode(),
                    value=json.dumps(enriched).encode(),
                )

                events_consumed.labels(event_type=event.event_type).inc()
                processing_latency.observe(time.perf_counter() - start_time)

                # Visible logging
                logger.info(
                    f"✅ Enriched & forwarded → {event.event_type} | item={event.item_id} | user={event.user_id}"
                )

                # Batch write to Parquet
                if len(buffer) >= BATCH_SIZE:
                    write_to_parquet(buffer)
                    buffer.clear()
                    await consumer.commit()  # commit after successful batch

        except Exception as e:
            logger.warning(f"⚠️ Error in processing loop: {type(e).__name__}: {e}")
            await asyncio.sleep(5)
        finally:
            if buffer:
                write_to_parquet(buffer)
                buffer.clear()
            if consumer is not None:
                await consumer.stop()
            if producer is not None:
                await producer.stop()


if __name__ == "__main__":
    asyncio.run(run())
