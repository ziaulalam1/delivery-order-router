"""
Throughput and latency benchmark for the delivery order router.
Sends 1000 POST /orders requests, measures per-request latency,
then writes reports/benchmark.json and reports/benchmark.png.

Usage:
    python benchmark.py [--url http://localhost:8000] [--n 1000]

The server must be running before calling this script.
"""

import argparse
import json
import os
import sys
import time
import uuid
from statistics import mean, median, quantiles

import httpx
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


REPORTS_DIR = os.path.join(os.path.dirname(__file__), "reports")


def run_benchmark(base_url: str, n: int) -> dict:
    latencies_ms = []
    errors = 0

    payload_template = {
        "restaurant_id": "r-bench",
        "customer_id": "c-bench",
        "items": ["burger", "fries"],
        "priority": 1,
    }

    print(f"Sending {n} requests to {base_url}/orders ...")
    start_total = time.perf_counter()

    with httpx.Client(base_url=base_url, timeout=10.0) as client:
        for i in range(n):
            payload = {**payload_template, "customer_id": str(uuid.uuid4())}
            t0 = time.perf_counter()
            try:
                resp = client.post("/orders", json=payload)
                resp.raise_for_status()
            except Exception:
                errors += 1
            t1 = time.perf_counter()
            latencies_ms.append((t1 - t0) * 1000)

            if (i + 1) % 100 == 0:
                print(f"  {i + 1}/{n} done")

    elapsed_s = time.perf_counter() - start_total
    throughput = n / elapsed_s

    latencies_ms.sort()
    qs = quantiles(latencies_ms, n=100)  # percentiles
    p50 = qs[49]
    p95 = qs[94]
    p99 = qs[98]

    return {
        "total_requests": n,
        "errors": errors,
        "elapsed_seconds": round(elapsed_s, 3),
        "throughput_rps": round(throughput, 2),
        "latency_ms": {
            "min": round(min(latencies_ms), 3),
            "mean": round(mean(latencies_ms), 3),
            "p50": round(p50, 3),
            "p95": round(p95, 3),
            "p99": round(p99, 3),
            "max": round(max(latencies_ms), 3),
        },
    }, latencies_ms


def write_reports(results: dict, latencies_ms: list[float]) -> None:
    os.makedirs(REPORTS_DIR, exist_ok=True)

    json_path = os.path.join(REPORTS_DIR, "benchmark.json")
    with open(json_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"Wrote {json_path}")

    # Histogram
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.hist(latencies_ms, bins=60, color="#1a73e8", edgecolor="white", alpha=0.85)
    ax.axvline(results["latency_ms"]["p50"], color="#d93025", linestyle="--", linewidth=1.5,
               label=f"p50 = {results['latency_ms']['p50']} ms")
    ax.axvline(results["latency_ms"]["p95"], color="#f29900", linestyle="--", linewidth=1.5,
               label=f"p95 = {results['latency_ms']['p95']} ms")
    ax.set_xlabel("Latency (ms)")
    ax.set_ylabel("Request count")
    ax.set_title(
        f"Delivery Order Router — {results['total_requests']} requests "
        f"@ {results['throughput_rps']} req/s"
    )
    ax.legend()
    fig.tight_layout()

    png_path = os.path.join(REPORTS_DIR, "benchmark.png")
    fig.savefig(png_path, dpi=150)
    print(f"Wrote {png_path}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8000")
    parser.add_argument("--n", type=int, default=1000)
    args = parser.parse_args()

    results, latencies_ms = run_benchmark(args.url, args.n)

    print("\n--- Results ---")
    print(f"  Throughput : {results['throughput_rps']} req/s")
    print(f"  p50        : {results['latency_ms']['p50']} ms")
    print(f"  p95        : {results['latency_ms']['p95']} ms")
    print(f"  Errors     : {results['errors']}/{results['total_requests']}")

    write_reports(results, latencies_ms)


if __name__ == "__main__":
    main()
