# **PHASE 1 : PROJECT SETUP AND DATA MODEL**
1. Create GitHub repo with a clear README describing the project, architecture, and how to run it locally
2. Define your domain — e.g. e-commerce auction events (bids, views, purchases). Write a JSON schema for each event type
Why?
Strong schema = validation, documentation, and easier debugging. Pydantic will enforce it in Phase 2. This prevents garbage-in-garbage-out in the streaming layer.
Domain Choice (as you suggested): E-commerce auction events.
Main event types:

item_view — user views an auction item
bid_placed — user places a bid
purchase_completed — item is bought (auction ends or buy-it-now)
3. Set up Docker Compose with Redpanda, Prometheus, and Grafana containers
Why?

Redpanda: Lightweight Kafka-compatible broker (no ZooKeeper, faster for dev).
Prometheus: Scrapes metrics (we'll expose producer/consumer metrics later).
Grafana: Visualizes dashboards (consumer lag, events/sec, etc. in Phase 5).

4. Write a Python event simulator that generates realistic fake events at configurable rates
Configure pre-commit hooks (ruff, mypy, pytest) and a basic GitHub Actions CI workflow
Why?

Generates realistic fake events at configurable rates → easy testing without real web/API sources. We'll use it to feed the pipeline in later phases.
                Move up to the main project directory:bashcd ~/projects/real-time-auction-analytics/
                Use code with caution.Run the script as a module:bashpython3 -m simulator.main

5. Pre-commit Hooks + Basic GitHub Actions CI

Why?
Enforces code quality (formatting, types, tests) before commits. CI catches issues early.


# **PHASE 2 — EVENT INGESTION WITH REDPANDA**
1. Create Kafka topics via Redpanda's rpk CLI (raw_events, processed_events, dead_letter)

rpk topic create raw_events processed_events dead_letter --brokers localhost:19092
rpk topic list --brokers localhost:19092
NAME              PARTITIONS  REPLICAS
dead_letter       1           1
processed_events  1           1
raw_events        1           1

Why this design?

Pydantic validation happens before sending → bad events never reach Redpanda.
Dead-letter logic: For now, validation errors are counted in metrics (we can later produce them to dead_letter topic with extra error metadata).
Prometheus metrics: Exposes publish rate, error rate, and p99 latency (via histogram).
Uses confluent-kafka-python (fast, production-ready)


2. Write a Kafka producer using confluent-kafka-python with Pydantic v2 validation before publish
3. Implement dead-letter queue: events that fail validation go to a separate topic with error metadata
4. Write integration tests that produce events and assert they appear in the correct topic
5. Add producer metrics: publish rate, error rate, p99 latency — exposed to Prometheus

Phase 2 – Event Ingestion with Redpanda - what works here

                1. Installed rpk CLI inside WSL
                2. Created three Kafka-compatible topics:
                raw_events → where fresh events land
                processed_events → where Faust will write cleaned/enriched data (Phase 3)
                dead_letter → for events that fail validation or processing

                3. Built a production-style Kafka Producer using confluent-kafka-python:
                -Validates every event with Pydantic before sending
                -Uses user_id as partitioning key (good for future stateful processing)
                -Has delivery callbacks and proper flushing
                -Exposes real-time Prometheus metrics (events produced, failed, p99 latency)

                4. Tested end-to-end: Simulator → Producer → Redpanda topic (you saw the delivery confirmations)
Why Redpanda instead of Kafka? Lighter, faster, no ZooKeeper, single binary.
Why external port 19092? So your Python code running on Windows/WSL can reach the broker inside Docker.
Why Pydantic validation before produce? Prevents bad data from entering the pipeline early (fail fast).
Why Prometheus metrics? We’ll visualize them in Grafana in Phase 5 (events/sec, error rate, latency).
Why topics separation? Clear data flow: raw → processed → (later analytics).

# **## STUFF TO KNOW B4 PHASE 3**
## Faust : A library for building streaming applications in Python.
Faust only requires Kafka, the rest is just Python, so If you know Python you can already use Faust to do stream processing, and it can integrate with just about anything.

Agents
Process infinite streams in a straightforward manner using asynchronous generators. The concept of “agents” comes from the actor model, and means the stream processor can execute concurrently on many CPU cores, and on hundreds of machines at the same time.

Tables
Tables are sharded dictionaries that enable stream processors to be stateful with persistent and durable data.

Streams are partitioned to keep relevant data close, and can be easily repartitioned to achieve the topology you need.

## **Phase 3 Agents (What They Will Actually Do)**
Agent 1: Enrichment Agent

Consumes from raw_events
Adds derived / enriched fields:
bid_rank (how many bids have been placed on this item so far — we'll keep lightweight per-item state)
estimated_session_duration (simple heuristic based on time between view and bid in same session)
event_hour and event_date for partitioning
Possibly normalized price_bucket or is_first_bid

Forwards enriched event to processed_events topic (or directly to Parquet sink)

Agent 2: Aggregator Agent

Consumes from processed_events (or directly from raw if we want simpler)
Maintains tumbling 1-minute windows (non-overlapping)
Computes in real time:
Number of views, bids, purchases per window
Bids per item (top items by activity)
Conversion rate (bids / views)
Revenue per category
Total bid volume and average bid amount

Writes aggregated results as Parquet files, partitioned by date/hour (using PyArrow) — this becomes the source for DuckDB in Phase 4

This gives you both event-level enrichment (for detailed analysis) and real-time metrics (for dashboards).


# **Phase 4 : Query Layer with DuckDB + FastAPI**
Goal:
Expose analytical queries on top of the Parquet files using DuckDB (which reads Parquet natively and extremely fast) and serve them via a clean FastAPI REST API.
We will build:

A FastAPI app that can query the partitioned Parquet files directly
3–4 useful analytical endpoints:
Top items by bid volume / activity
Revenue over time (by hour/day)
Conversion rate (views → bids → purchases)
Event funnel summary

Typed Pydantic response models
Simple TTL-based caching (to avoid rescanning Parquet on every request)
/health endpoint + basic error handling
Integration tests

Plan

FastAPI service that queries the Parquet data via DuckDB
4 useful analytical endpoints
Typed Pydantic response models
Simple in-memory caching (TTL) for hot queries
Health check endpoint
Proper error handling

# **Phase 5 Plan**
will create:

A new dashboard/ service using Streamlit
Multiple pages/tabs: Overview, Top Items, Revenue Trends, Conversion Funnel, Recent Events
Auto-refresh every 5 seconds
Clean charts using Plotly
Connection to your existing FastAPI (http://api:8000)
Integration into docker-compose.yml
