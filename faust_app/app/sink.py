import pyarrow as pa
import pyarrow.parquet as pq
from pathlib import Path
from datetime import datetime

# Output directory inside the container (mounted via docker-compose)
OUTPUT_DIR = Path("/data/processed")


def write_to_parquet(events: list[dict]) -> None:
    """Write a batch of enriched events to partitioned Parquet files."""
    if not events:
        return

    try:
        # Ensure output directory exists
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        now = datetime.utcnow()
        # Partition by year/month/day/hour (Hive-style partitioning)
        partition_path = (
            OUTPUT_DIR
            / f"year={now.year}/month={now.month:02d}/day={now.day:02d}/hour={now.hour:02d}"
        )
        partition_path.mkdir(parents=True, exist_ok=True)

        # Convert to Arrow Table and write
        table = pa.Table.from_pylist(events)
        filename = f"batch_{now.strftime('%H%M%S_%f')}.parquet"
        filepath = partition_path / filename

        pq.write_table(table, filepath)
        print(f"💾 Wrote {len(events)} events to {filepath}")

    except Exception as e:
        print(f"❌ Failed to write Parquet: {e}")
