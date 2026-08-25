from __future__ import annotations

import json
import statistics
import time
from pathlib import Path

from src.agent.tools import document_search

OUTPUT_PATH = Path("artifacts/retrieval_benchmark.json")

QUERIES = [
    "observability in ML systems",
    "monitoring machine learning systems",
    "model drift and data quality",
    "latency and throughput",
    "production AI reliability",
    "deployment monitoring",
    "failure handling in ML systems",
    "structured logging",
    "Prometheus metrics",
    "applied AI engineering",
]


def percentile(
    values: list[float],
    percentile_value: float,
) -> float:
    ordered = sorted(values)

    index = (
        len(ordered) - 1
    ) * percentile_value

    lower = int(index)
    upper = min(
        lower + 1,
        len(ordered) - 1,
    )

    fraction = index - lower

    return (
        ordered[lower]
        + (
            ordered[upper]
            - ordered[lower]
        )
        * fraction
    )


def timed_search(
    query: str,
) -> tuple[dict, float]:
    start = time.perf_counter()

    result = document_search(
        query
    )

    latency_ms = (
        time.perf_counter()
        - start
    ) * 1000

    return result, latency_ms


def run_benchmark() -> dict:
    _, cold_latency_ms = timed_search(
        QUERIES[0]
    )

    warm_latencies = []

    for query in QUERIES:
        _, latency_ms = timed_search(
            query
        )

        warm_latencies.append(
            latency_ms
        )

    result = {
        "queries_tested": len(
            QUERIES
        ),
        "cold_start_ms": round(
            cold_latency_ms,
            3,
        ),
        "warm_latency_ms": {
            "average": round(
                statistics.mean(
                    warm_latencies
                ),
                3,
            ),
            "median": round(
                statistics.median(
                    warm_latencies
                ),
                3,
            ),
            "p95": round(
                percentile(
                    warm_latencies,
                    0.95,
                ),
                3,
            ),
            "min": round(
                min(warm_latencies),
                3,
            ),
            "max": round(
                max(warm_latencies),
                3,
            ),
        },
    }

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT_PATH.write_text(
        json.dumps(
            result,
            indent=2,
        ),
        encoding="utf-8",
    )

    return result


def main():
    result = run_benchmark()

    print(
        json.dumps(
            result,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()