# Rate Limiter

A production-ready rate limiting library for Python with support for Token Bucket and Leaky Bucket algorithms, featuring both in-memory and Redis-backed storage.

## Features

- **Two algorithms**: Token Bucket and Leaky Bucket
- **Two storage backends**: In-Memory and Redis
- **Thread-safe**: Safe for concurrent access
- **Atomic operations**: Redis implementation uses Lua scripts for atomicity
- **Comprehensive tests**: Full unit test coverage
- **Performance benchmarks**: Detailed performance analysis tools

## Algorithms

### Token Bucket

The Token Bucket algorithm allows for bursts of traffic while maintaining an average rate limit.

```
┌─────────────────────────────────┐
│      Token Bucket               │
│                                 │
│  ┌─────────────────────────┐   │
│  │  🪙 🪙 🪙 🪙 🪙 🪙 🪙    │   │  Capacity: 10 tokens
│  │  🪙 🪙 🪙              │   │  Refill: 2 tokens/sec
│  └─────────────────────────┘   │
│           ▲         │           │
│           │         │           │
│      Refill      Consume        │
│     (2/sec)     (1/request)     │
└─────────────────────────────────┘

✓ Allows burst traffic up to capacity
✓ Tokens regenerate at fixed rate
✓ Good for APIs with occasional spikes
```

**Use cases:**
- API rate limiting with burst allowance
- Request throttling with flexibility
- Scenarios where brief traffic spikes are acceptable

### Leaky Bucket

The Leaky Bucket algorithm enforces a strict, smooth rate limit.

```
┌─────────────────────────────────┐
│      Leaky Bucket               │
│                                 │
│  ┌─────────────────────────┐   │
│  │  💧                      │   │  Capacity: 5 requests
│  │  💧 💧                   │   │  Leak: 2 requests/sec
│  │  💧 💧 💧                │   │
│  └──────────┬───────────────┘   │
│             │                   │
│             ▼                   │
│         Leak Out                │
│        (2/sec)                  │
└─────────────────────────────────┘

✓ Enforces smooth, predictable rate
✓ Requests processed at constant rate
✓ Good for protecting downstream services
```

**Use cases:**
- Protecting backend services from overload
- Enforcing strict, smooth rate limits
- Traffic shaping and flow control

## Installation

```bash
# Install dependencies
pip install redis

# For development and testing
pip install redis pytest
```

## Quick Start

### In-Memory Token Bucket

```python
from rate_limiter import TokenBucketMemory

# Create limiter: 10 tokens, refill at 2 tokens/second
limiter = TokenBucketMemory(capacity=10, refill_rate=2.0)

# Check if request is allowed
result = limiter.allow_request("user123")

if result.allowed:
    print(f"Request allowed! {result.tokens_remaining} tokens remaining")
    # Process request
else:
    print(f"Rate limited! Retry after {result.retry_after:.2f} seconds")
    # Return 429 Too Many Requests
```

### Redis Token Bucket

```python
import redis
from rate_limiter import TokenBucketRedis

# Connect to Redis
redis_client = redis.Redis(host='localhost', port=6379, decode_responses=True)

# Create distributed limiter
limiter = TokenBucketRedis(
    capacity=100,
    refill_rate=10.0,
    redis_client=redis_client
)

result = limiter.allow_request("user456")
```

### Leaky Bucket

```python
from rate_limiter import LeakyBucketMemory

# Create limiter: 5 request capacity, leak at 2 requests/second
limiter = LeakyBucketMemory(capacity=5, leak_rate=2.0)

result = limiter.allow_request("user789")
```

## API Reference

### RateLimitResult

```python
@dataclass
class RateLimitResult:
    allowed: bool              # Whether request should be allowed
    tokens_remaining: int      # Tokens/capacity remaining
    retry_after: float | None  # Seconds until retry (if denied)
```

### TokenBucketMemory

```python
TokenBucketMemory(capacity: int, refill_rate: float)
```

- `capacity`: Maximum number of tokens in bucket
- `refill_rate`: Tokens added per second

### LeakyBucketMemory

```python
LeakyBucketMemory(capacity: int, leak_rate: float)
```

- `capacity`: Maximum queue size (requests)
- `leak_rate`: Requests processed per second

### Redis Implementations

```python
TokenBucketRedis(capacity: int, refill_rate: float, redis_client: redis.Redis)
LeakyBucketRedis(capacity: int, leak_rate: float, redis_client: redis.Redis)
```

Same parameters plus `redis_client` for distributed storage.

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                   Rate Limiter                      │
│                 (Abstract Base)                     │
└────────────┬─────────────────────┬──────────────────┘
             │                     │
    ┌────────▼────────┐   ┌────────▼────────┐
    │  Token Bucket   │   │  Leaky Bucket   │
    └────────┬────────┘   └────────┬────────┘
             │                     │
    ┌────────┴────────┐   ┌────────┴────────┐
    │                 │   │                 │
┌───▼──────┐  ┌───────▼───┐  ┌──────▼───┐  ┌─────▼──────┐
│  Memory  │  │   Redis   │  │  Memory  │  │   Redis    │
│ Backend  │  │  Backend  │  │ Backend  │  │  Backend   │
└──────────┘  └───────────┘  └──────────┘  └────────────┘
   (Fast)      (Distributed)    (Fast)      (Distributed)
```

## Running Tests

```bash
# Run all tests
python -m pytest test_rate_limiter.py -v

# Run specific test class
python -m pytest test_rate_limiter.py::TestTokenBucketMemory -v

# Run with coverage
python -m pytest test_rate_limiter.py --cov=rate_limiter --cov-report=html
```

## Running Benchmarks

```bash
# Run full benchmark suite
python benchmark.py

# Expected output:
# - Single-threaded performance metrics
# - Redis backend performance (if available)
# - Concurrent access benchmarks
# - Comparative analysis
```

### Sample Benchmark Results

```
PERFORMANCE COMPARISON
============================================================
Implementation                      Mean (ms)    P99 (ms)     Throughput     
------------------------------------------------------------
Token Bucket (Memory)               0.004        0.012        250,000        
Leaky Bucket (Memory)               0.005        0.013        200,000        
Token Bucket (Redis)                0.145        0.289        6,900          
Leaky Bucket (Redis)                0.148        0.295        6,700          
Token Bucket (Memory) (Concurrent)  0.008        0.025        125,000        
============================================================

Key Insights:
- In-memory: ~0.004ms latency, 250K+ req/sec
- Redis: ~0.15ms latency, 6-7K req/sec
- Thread-safe with minimal overhead
- Redis overhead: ~35x latency (network + serialization)
```

## Implementation Details

### Thread Safety

In-memory implementations use threading locks to ensure atomic operations:

```python
with self.lock:
    # Atomic bucket operations
    self._refill(bucket)
    bucket['tokens'] -= 1
```

### Redis Atomicity

Redis implementations use Lua scripts for atomic operations, preventing race conditions in distributed environments:

```lua
-- Atomic token bucket operation
local tokens = tonumber(bucket[1])
-- Refill calculation
-- Token consumption
-- All in single atomic operation
```

### Key Features

1. **Precision timing**: Uses `time.time()` for sub-second accuracy
2. **Automatic cleanup**: Redis keys expire after 1 hour of inactivity
3. **Efficient refill**: On-demand calculation, not periodic polling
4. **Minimal overhead**: Optimized for high-throughput scenarios

## Use Cases

### API Gateway

```python
# Rate limit by API key
limiter = TokenBucketRedis(capacity=1000, refill_rate=100, redis_client=redis_client)

def api_middleware(request):
    api_key = request.headers.get('X-API-Key')
    result = limiter.allow_request(api_key)
    
    if not result.allowed:
        return Response(
            status=429,
            headers={'Retry-After': str(int(result.retry_after))}
        )
    
    return next_handler(request)
```

### User Actions

```python
# Limit user actions (e.g., posts, comments)
limiter = LeakyBucketMemory(capacity=10, leak_rate=1.0)  # 1 action per second

def create_post(user_id, content):
    result = limiter.allow_request(f"user:{user_id}:posts")
    
    if not result.allowed:
        raise RateLimitError(f"Please wait {result.retry_after:.0f} seconds")
    
    # Create post
    save_post(user_id, content)
```

### Distributed System

```python
# Rate limit across multiple application servers
redis_client = redis.Redis(host='redis.example.com', port=6379)
limiter = TokenBucketRedis(capacity=10000, refill_rate=1000, redis_client=redis_client)

# All app servers share same rate limit state
result = limiter.allow_request("global:api:limit")
```

## Choosing an Algorithm

| Scenario | Recommended Algorithm | Reason |
|----------|----------------------|---------|
| API with burst allowance | Token Bucket | Allows brief spikes while maintaining average rate |
| Strict rate enforcement | Leaky Bucket | Smooth, predictable rate limiting |
| Protecting backend | Leaky Bucket | Prevents downstream overload |
| User-facing features | Token Bucket | Better UX with burst tolerance |
| Single server | In-Memory | Lowest latency, highest throughput |
| Distributed system | Redis | Shared state across servers |

## Performance Considerations

### In-Memory
- **Pros**: Extremely fast (~0.004ms), no network overhead
- **Cons**: State not shared across processes/servers
- **Best for**: Single-server applications, high-throughput scenarios

### Redis
- **Pros**: Distributed state, survives restarts, scalable
- **Cons**: Network latency (~0.15ms), requires Redis infrastructure
- **Best for**: Multi-server deployments, microservices

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## License

MIT License - feel free to use in your projects!

## References

- [Token Bucket Algorithm](https://en.wikipedia.org/wiki/Token_bucket)
- [Leaky Bucket Algorithm](https://en.wikipedia.org/wiki/Leaky_bucket)
- [Redis Documentation](https://redis.io/docs/)
- [Rate Limiting Patterns](https://cloud.google.com/architecture/rate-limiting-strategies-techniques)

## Future Enhancements

- [ ] Sliding window algorithm
- [ ] Fixed window counter
- [ ] Dynamic rate adjustment
- [ ] Metrics and monitoring integration
- [ ] GraphQL/REST middleware decorators
- [ ] Admin dashboard for monitoring