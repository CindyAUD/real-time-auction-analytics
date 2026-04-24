# ADR 001: Core Architecture Choices

## Status
Accepted (2026-04-14)

## Context
We needed to build a **real-time analytics pipeline** with end-to-end ownership, low operational complexity, and good performance for auction events (views, bids, purchases). The system must handle streaming ingestion, enrichment, aggregation, storage, and querying while remaining easy to develop and maintain on a single machine or small cluster.

Key requirements:
- True streaming with low latency
- Strong analytical query performance
- Full code ownership (no heavy managed services)
- Good observability
- Reasonable developer experience

## Decision

We chose the following stack:

| Layer              | Technology              | Reason |
|--------------------|-------------------------|--------|
| **Message Broker** | **Redpanda**            | Kafka-compatible, single binary, high performance, no ZooKeeper, lower resource usage than Kafka |
| **Stream Processor** | **aiokafka (Python)** | Better Python 3.12 compatibility than Faust. Full control, easier debugging, no framework magic |
| **Storage**        | **Parquet (partitioned)** | Columnar format, excellent compression, native support in DuckDB, future-proof for scale |
| **Analytics Engine** | **DuckDB**            | Extremely fast OLAP queries on Parquet with zero ETL. In-process, embedded, simple |
| **API Layer**      | **FastAPI**             | Modern, fast, automatic Swagger UI, excellent Pydantic integration |
| **Dashboard**      | **Streamlit**           | Rapid development of data apps with auto-refresh |
| **Observability**  | **Prometheus + Grafana** | Standard, lightweight, works well with our custom metrics |

### Why not other options?

- **Faust** → Abandoned main project, dependency hell with Python 3.12, complex Docker setup
- **Flink / Spark Streaming** → Heavy, complex, overkill for this scale
- **Kafka + Kafka Connect + ksqlDB** → More operational overhead
- **Managed services (Confluent, Materialize, etc.)** → Violates "end-to-end ownership" goal

## Consequences

### Positive
- Excellent performance for analytical workloads
- Full visibility and control over every component
- Easy local development (`docker compose up`)
- Strong learning value (real streaming concepts without framework hiding details)
- Cheap to run (can run on a single VM)
- Good foundation for future scaling (add ClickHouse, Flink, etc. later if needed)

### Negative / Trade-offs
- In-memory window aggregation (not persistent across restarts) — acceptable for this project
- Manual consumer management instead of high-level framework
- Parquet-based serving is slightly higher latency than a dedicated OLAP database (but still very fast)

## Alternatives Considered

1. **Faust + RocksDB** — Rejected due to repeated startup and dependency issues
2. **Quix Streams** — Good alternative, but aiokafka gave us more transparency
3. **ClickHouse** instead of DuckDB — Overkill for current scale and added complexity

## References
- Project GitHub: https://github.com/CindyAUD/real-time-auction-analytics.git
- Phase 3: Switched from Faust to aiokafka
- Phase 4: DuckDB + FastAPI query layer

---
**Date:** 2026-04-14
**Author:** Cindy Audrey
