import faust
from schemas.events import (
    AuctionEvent,
    BidPlacedEvent,
)
import pyarrow as pa
import pyarrow.parquet as pq
import pandas as pd
from pathlib import Path
import random

app = faust.App(
    "auction-processor",
    broker="kafka://redpanda:9092",
    value_serializer="json",
    table_cleanup_interval=60,  # clean old state
)

# Topics
raw_events_topic = app.topic("raw_events", value_type=AuctionEvent)
processed_events_topic = app.topic("processed_events", value_type=dict)

# Tables for stateful processing (lightweight)
bid_count_table = app.Table("bid_count", default=int)  # per item bid counter

# Output Parquet directory (will be mounted from host if needed later)
PARQUET_DIR = Path("/app/data/parquet")
PARQUET_DIR.mkdir(parents=True, exist_ok=True)


@app.agent(raw_events_topic)
async def enrich_events(stream):
    """Agent 1: Enrichment"""
    async for event in stream:
        enriched = event.model_dump()

        # --- Enrichment logic ---
        if isinstance(event, BidPlacedEvent):
            # Simple bid rank using table (stateful)
            current_count = bid_count_table[event.item_id] or 0
            enriched["bid_rank"] = current_count + 1
            bid_count_table[event.item_id] = current_count + 1

            # Simple session duration estimate (heuristic)
            enriched["estimated_session_duration"] = random.randint(30, 300)  # seconds

        # Add partitioning fields
        dt = event.timestamp
        enriched["event_date"] = dt.strftime("%Y-%m-%d")
        enriched["event_hour"] = dt.strftime("%H")

        # Forward to processed topic
        await processed_events_topic.send(key=event.item_id, value=enriched)

        print(f"Enriched → {enriched['event_type']} | item={enriched['item_id']}")


@app.agent(processed_events_topic)
async def aggregate_windows(stream):
    """Agent 2: Tumbling 1-minute window aggregation"""
    async for event in stream.group_by(
        lambda e: e["event_date"] + "_" + e["event_hour"]
    ):
        # Faust windowing example - tumbling 1 minute
        # window = app.window(60, 60)  # 60 seconds tumbling

        # Example aggregations (we'll expand this)
        # For now: simple count per window
        print(
            f"Windowed event in {event.get('event_date')} {event.get('event_hour')}: {event['event_type']}"
        )

        # TODO: Write to Parquet every window close (we'll improve in next iteration)


# Helper to write Parquet (we'll call this periodically)
def write_to_parquet(df: pd.DataFrame, date_str: str, hour_str: str):
    table = pa.Table.from_pandas(df)
    path = PARQUET_DIR / date_str / hour_str
    path.mkdir(parents=True, exist_ok=True)
    pq.write_to_dataset(
        table, root_path=str(path), partition_cols=["event_date", "event_hour"]
    )


if __name__ == "__main__":
    app.main()
