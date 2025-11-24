import time
import statistics
import threading
import sys
from typing import List, Dict, Type
from rate_limiter import TokenBucketMemory, LeakyBucketMemory, RateLimiter

# Try to import plotting libraries (optional)
try:
    import matplotlib.pyplot as plt
    import numpy as np
    PLOTTING_AVAILABLE = True
except ImportError:
    print("⚠️  Matplotlib/Numpy not found. Graphs will not be generated.")
    PLOTTING_AVAILABLE = False

# Check for Redis
try:
    import redis
    r = redis.Redis(host='localhost', port=6379)
    r.ping()
    REDIS_AVAILABLE = True
except:
    REDIS_AVAILABLE = False

def run_benchmark(limiter: RateLimiter, num_requests: int = 10000) -> Dict:
    """Run a performance test on a single limiter"""
    latencies = []
    
    start_total = time.time()
    
    for i in range(num_requests):
        start_req = time.time()
        # Use a rotating key to simulate different users
        key = f"user_{i % 100}"
        limiter.allow_request(key)
        end_req = time.time()
        latencies.append((end_req - start_req) * 1000) # Convert to ms

    end_total = time.time()
    duration = end_total - start_total
    
    return {
        "total_time": duration,
        "rps": num_requests / duration,
        "avg_latency": statistics.mean(latencies),
        "p95_latency": statistics.quantiles(latencies, n=20)[18], # 95th percentile
        "p99_latency": statistics.quantiles(latencies, n=100)[98], # 99th percentile
    }

def print_results(name: str, stats: Dict):
    print(f"\n--- {name} ---")
    print(f"Total Requests:      {stats['rps'] * stats['total_time']:.0f}")
    print(f"Requests Per Second: {stats['rps']:,.2f} req/s")
    print(f"Average Latency:     {stats['avg_latency']:.4f} ms")
    print(f"99th % Latency:      {stats['p99_latency']:.4f} ms")

def plot_results(results: Dict[str, Dict]):
    if not PLOTTING_AVAILABLE:
        return

    names = list(results.keys())
    rps_values = [results[n]['rps'] for n in names]
    latencies = [results[n]['avg_latency'] for n in names]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

    # RPS Chart
    ax1.bar(names, rps_values, color='green')
    ax1.set_title('Throughput (Higher is Better)')
    ax1.set_ylabel('Requests per Second')

    # Latency Chart
    ax2.bar(names, latencies, color='red')
    ax2.set_title('Latency (Lower is Better)')
    ax2.set_ylabel('Avg Latency (ms)')

    plt.tight_layout()
    plt.savefig('benchmark_results.png')
    print("\n[Graph] Performance chart saved to 'benchmark_results.png'")

def main():
    print(f"Starting Benchmark (Target: 10,000 requests)...")
    results = {}

    # 1. Test In-Memory Token Bucket
    print("Testing TokenBucketMemory...", end="", flush=True)
    tb = TokenBucketMemory(capacity=1000, refill_rate=1000)
    results['Memory Token'] = run_benchmark(tb)
    print(" Done.")

    # 2. Test In-Memory Leaky Bucket
    print("Testing LeakyBucketMemory...", end="", flush=True)
    lb = LeakyBucketMemory(capacity=1000, leak_rate=1000)
    results['Memory Leaky'] = run_benchmark(lb)
    print(" Done.")

    # 3. Test Redis (Only if available)
    if REDIS_AVAILABLE:
        print("Testing Redis TokenBucket...", end="", flush=True)
        r = redis.Redis(host='localhost', port=6379)
        # Clear previous keys
        r.flushdb()
        # Note: We do fewer requests for Redis because network calls are slower
        from rate_limiter import TokenBucketRedis
        tb_redis = TokenBucketRedis(capacity=1000, refill_rate=1000, redis_client=r)
        results['Redis Token'] = run_benchmark(tb_redis, num_requests=2000)
        print(" Done.")
    else:
        print("\n[Skipping Redis tests: Docker container not running]")

    # Print all stats
    for name, stats in results.items():
        print_results(name, stats)

    # Generate Graph
    plot_results(results)

if __name__ == "__main__":
    main()