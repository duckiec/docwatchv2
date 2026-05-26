from prometheus_client import Counter, Histogram, Gauge

CRASH_COUNT = Counter(
    "docwatch_crashes_total", 
    "Total number of container crashes processed"
)

AI_LATENCY = Histogram(
    "docwatch_ai_classification_latency_seconds",
    "Latency of AI classification requests in seconds",
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0]
)

MONITORED_CONTAINERS = Gauge(
    "docwatch_monitored_containers",
    "Estimated number of running containers (if available from docker socket)"
)
