from prometheus_client import Counter, Histogram, start_http_server

events_consumed = Counter(
    "pipeline_events_consumed_total",
    "Total events consumed from raw_events",
    ["event_type"],
)
events_failed = Counter(
    "pipeline_events_failed_total",
    "Events that failed parsing or enrichment",
)
processing_latency = Histogram(
    "pipeline_processing_seconds",
    "Time to process a single event",
)


def start_metrics_server(port: int = 8001):
    start_http_server(port)
