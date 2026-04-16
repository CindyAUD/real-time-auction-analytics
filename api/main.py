import duckdb
import time
from pathlib import Path
from typing import List
from fastapi import FastAPI, Query
from pydantic import BaseModel
import logging
import numpy as np

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Auction Analytics API",
    description="Real-time auction analytics from Parquet files",
    version="1.0.0",
)

PARQUET_PATH = Path("/data/processed")

# Simple in-memory cache with TTL
cache = {}
CACHE_TTL = 30  # seconds


def get_duckdb_connection():
    """Create fresh DuckDB connection"""
    con = duckdb.connect(":memory:")
    return con


# ====================== Response Models ======================


class HealthResponse(BaseModel):
    status: str
    parquet_path_exists: bool
    message: str


class TopItem(BaseModel):
    item_id: str
    bid_count: int
    total_bid_amount: float
    view_count: int
    conversion_rate: float


class RevenueHour(BaseModel):
    hour: str
    revenue: float
    purchase_count: int


class FunnelResponse(BaseModel):
    total_views: int
    total_bids: int
    total_purchases: int
    view_to_bid_rate: float
    bid_to_purchase_rate: float


class StatsResponse(BaseModel):
    total_events: int
    views: int
    bids: int
    purchases: int


# ====================== Endpoints ======================


@app.get("/health", response_model=HealthResponse)
async def health():
    path_exists = PARQUET_PATH.exists()
    return HealthResponse(
        status="healthy",
        parquet_path_exists=path_exists,
        message="API is running" if path_exists else "Waiting for Parquet data",
    )


@app.get("/api/top-items", response_model=List[TopItem])
async def top_items(limit: int = Query(10, ge=1, le=50)):
    """Top items by bid activity"""
    cache_key = f"top_items_{limit}"
    if cache_key in cache and time.time() - cache[cache_key]["timestamp"] < CACHE_TTL:
        return cache[cache_key]["data"]

    try:
        con = get_duckdb_connection()

        query = f"""
        SELECT
            item_id,
            COUNT_IF(event_type = 'bid_placed') AS bid_count,
            COALESCE(SUM(CASE WHEN event_type = 'bid_placed' THEN final_price ELSE 0 END), 0) AS total_bid_amount,
            COUNT_IF(event_type = 'item_view') AS view_count,
            ROUND(
                COUNT_IF(event_type = 'bid_placed') * 100.0 /
                NULLIF(COUNT_IF(event_type = 'item_view'), 0), 2
            ) AS conversion_rate
        FROM read_parquet('{PARQUET_PATH}/**/*.parquet')
        GROUP BY item_id
        HAVING bid_count > 0
        ORDER BY bid_count DESC
        LIMIT {limit}
        """

        result = con.execute(query).df()
        data = result.to_dict(orient="records")

        cache[cache_key] = {"data": data, "timestamp": time.time()}
        return data if data else []

    except Exception as e:
        logger.error(f"Top items query failed: {e}")
        return []


@app.get("/api/revenue", response_model=List[RevenueHour])
async def revenue_over_time(hours: int = Query(24, ge=1, le=168)):
    """Revenue over the last N hours"""
    try:
        con = get_duckdb_connection()

        query = f"""
        SELECT
            strftime(TRY_CAST(timestamp AS TIMESTAMP), '%Y-%m-%d %H:00') AS hour,
            COALESCE(SUM(final_price), 0) AS revenue,
            COUNT(*) AS purchase_count
        FROM read_parquet('{PARQUET_PATH}/**/*.parquet')
        WHERE event_type = 'purchase_completed'
          AND TRY_CAST(timestamp AS TIMESTAMP) >= CURRENT_TIMESTAMP - INTERVAL '{hours} hours'
        GROUP BY hour
        ORDER BY hour DESC
        """

        result = con.execute(query).df()
        return result.to_dict(orient="records") if not result.empty else []

    except Exception as e:
        logger.error(f"Revenue query failed: {e}")
        return []


@app.get("/api/funnel", response_model=FunnelResponse)
async def conversion_funnel():
    """Overall conversion funnel"""
    try:
        con = get_duckdb_connection()

        query = f"""
        SELECT
            COUNT_IF(event_type = 'item_view') AS total_views,
            COUNT_IF(event_type = 'bid_placed') AS total_bids,
            COUNT_IF(event_type = 'purchase_completed') AS total_purchases,
            ROUND(
                COUNT_IF(event_type = 'bid_placed') * 100.0 /
                NULLIF(COUNT_IF(event_type = 'item_view'), 0), 2
            ) AS view_to_bid_rate,
            ROUND(
                COUNT_IF(event_type = 'purchase_completed') * 100.0 /
                NULLIF(COUNT_IF(event_type = 'bid_placed'), 0), 2
            ) AS bid_to_purchase_rate
        FROM read_parquet('{PARQUET_PATH}/**/*.parquet')
        """

        row = con.execute(query).fetchone()

        return FunnelResponse(
            total_views=row[0] or 0,
            total_bids=row[1] or 0,
            total_purchases=row[2] or 0,
            view_to_bid_rate=row[3] or 0.0,
            bid_to_purchase_rate=row[4] or 0.0,
        )

    except Exception as e:
        logger.error(f"Funnel query failed: {e}")
        return FunnelResponse(
            total_views=0,
            total_bids=0,
            total_purchases=0,
            view_to_bid_rate=0.0,
            bid_to_purchase_rate=0.0,
        )


@app.get("/api/stats", response_model=StatsResponse)
async def overall_stats():
    """Overall statistics"""
    try:
        con = get_duckdb_connection()
        query = f"""
        SELECT
            COUNT(*) as total_events,
            COUNT_IF(event_type = 'item_view') as views,
            COUNT_IF(event_type = 'bid_placed') as bids,
            COUNT_IF(event_type = 'purchase_completed') as purchases
        FROM read_parquet('{PARQUET_PATH}/**/*.parquet')
        """
        row = con.execute(query).fetchone()

        return StatsResponse(
            total_events=row[0] or 0,
            views=row[1] or 0,
            bids=row[2] or 0,
            purchases=row[3] or 0,
        )
    except Exception as e:
        logger.error(f"Stats query failed: {e}")
        return StatsResponse(total_events=0, views=0, bids=0, purchases=0)


@app.get("/api/recent-events")
async def recent_events(limit: int = Query(10, ge=1, le=100)):
    """Show the most recent enriched events"""
    try:
        con = get_duckdb_connection()
        query = f"""
        SELECT *
        FROM read_parquet('{PARQUET_PATH}/**/*.parquet', union_by_name => true)
        ORDER BY timestamp DESC
        LIMIT {limit}
        """
        result = con.execute(query).df()
        # Replace NaN with None for JSON compatibility
        result = result.replace({np.nan: None})
        return result.to_dict(orient="records")
    except Exception as e:
        return {"error": "No data available yet", "message": str(e)}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
