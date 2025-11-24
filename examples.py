"""
Example usage patterns for the rate limiter library
"""

import time
import redis
from rate_limiter import (
    TokenBucketMemory, LeakyBucketMemory,
    TokenBucketRedis, LeakyBucketRedis
)


def example_basic_usage():
    """Basic rate limiting example"""
    print("\n=== Example 1: Basic Usage ===")
    
    limiter = TokenBucketMemory(capacity=5, refill_rate=1.0)
    
    for i in range(7):
        result = limiter.allow_request("user123")
        print(f"Request {i+1}: {'✓ Allowed' if result.allowed else '✗ Denied'} "
              f"(tokens: {result.tokens_remaining})")
        time.sleep(0.3)


def example_api_rate_limiting():
    """Simulate API rate limiting"""
    print("\n=== Example 2: API Rate Limiting ===")
    
    # 100 requests per minute = 100/60 = 1.67 req/sec
    limiter = TokenBucketMemory(capacity=100, refill_rate=1.67)
    
    def api_request(api_key: str, endpoint: str):
        result = limiter.allow_request(api_key)
        
        if result.allowed:
            print(f"✓ {endpoint}: Request processed")
            return {"status": "success"}
        else:
            print(f"✗ {endpoint}: Rate limited (retry in {result.retry_after:.1f}s)")
            return {"status": "rate_limited", "retry_after": result.retry_after}
    
    # Simulate API calls
    api_key = "sk_test_abc123"
    for i in range(5):
        api_request(api_key, f"/api/v1/users/{i}")


def example_burst_handling():
    """Demonstrate burst traffic handling"""
    print("\n=== Example 3: Burst Traffic Handling ===")
    
    limiter = TokenBucketMemory(capacity=5, refill_rate=2.0)
    
    print("Sending burst of 15 requests:")
    allowed = 0
    denied = 0
    
    for i in range(15):
        result = limiter.allow_request("burst_user")
        if result.allowed:
            allowed += 1
        else:
            denied += 1
    
    print(f"  Allowed: {allowed}, Denied: {denied}")
    print(f"\nWaiting 3 seconds for refill (2 tokens/sec)...")
    time.sleep(3)
    
    print("Sending 5 more requests:")
    for i in range(5):
        result = limiter.allow_request("burst_user")
        print(f"  Request {i+1}: {'✓' if result.allowed else '✗'}")


def example_multiple_users():
    """Rate limiting for multiple users"""
    print("\n=== Example 4: Multiple Users ===")
    
    limiter = LeakyBucketMemory(capacity=3, leak_rate=1.0)
    
    users = ["alice", "bob", "charlie"]
    
    for round in range(3):
        print(f"\nRound {round + 1}:")
        for user in users:
            result = limiter.allow_request(user)
            print(f"  {user}: {'✓' if result.allowed else '✗'} "
                  f"(capacity: {result.tokens_remaining})")
        time.sleep(0.5)


def example_distributed_redis():
    """Distributed rate limiting with Redis"""
    print("\n=== Example 5: Distributed Rate Limiting (Redis) ===")
    
    try:
        redis_client = redis.Redis(host='localhost', port=6379, decode_responses=True)
        redis_client.ping()
        
        limiter = TokenBucketRedis(
            capacity=10,
            refill_rate=5.0,
            redis_client=redis_client
        )
        
        print("Simulating requests from multiple servers:")
        
        # Simulate different application servers
        for server_id in range(3):
            result = limiter.allow_request("global_api_key")
            print(f"  Server {server_id + 1}: {'✓' if result.allowed else '✗'} "
                  f"(shared tokens: {result.tokens_remaining})")
        
        # Clean up
        limiter.reset("global_api_key")
        
    except (redis.ConnectionError, redis.RedisError) as e:
        print(f"  ⚠ Redis not available: {e}")
        print("  Install Redis: docker run -d -p 6379:6379 redis:7-alpine")


def example_graceful_degradation():
    """Handle rate limiting gracefully"""
    print("\n=== Example 6: Graceful Degradation ===")
    
    limiter = TokenBucketMemory(capacity=3, refill_rate=0.5)
    
    def make_request_with_retry(user_id: str, max_retries: int = 3):
        for attempt in range(max_retries):
            result = limiter.allow_request(user_id)
            
            if result.allowed:
                print(f"  ✓ Request succeeded on attempt {attempt + 1}")
                return True
            
            if attempt < max_retries - 1:
                wait_time = result.retry_after or 1.0
                print(f"  ⏳ Rate limited, waiting {wait_time:.1f}s...")
                time.sleep(wait_time)
        
        print(f"  ✗ Request failed after {max_retries} attempts")
        return False
    
    # Exhaust rate limit
    for _ in range(3):
        limiter.allow_request("user456")
    
    # Try with retry logic
    make_request_with_retry("user456")


def example_different_tiers():
    """Different rate limits for different user tiers"""
    print("\n=== Example 7: Tiered Rate Limiting ===")
    
    limiters = {
        "free": TokenBucketMemory(capacity=10, refill_rate=1.0),
        "pro": TokenBucketMemory(capacity=100, refill_rate=10.0),
        "enterprise": TokenBucketMemory(capacity=1000, refill_rate=100.0)
    }
    
    users = [
        ("user_free_1", "free"),
        ("user_pro_1", "pro"),
        ("user_ent_1", "enterprise")
    ]
    
    print("Making 15 requests per user:")
    for user_id, tier in users:
        limiter = limiters[tier]
        allowed = sum(1 for _ in range(15) 
                     if limiter.allow_request(user_id).allowed)
        print(f"  {tier:12} user: {allowed}/15 requests allowed")


def example_monitoring():
    """Monitor rate limiter behavior"""
    print("\n=== Example 8: Monitoring & Metrics ===")
    
    limiter = TokenBucketMemory(capacity=5, refill_rate=1.0)
    
    metrics = {
        "total_requests": 0,
        "allowed_requests": 0,
        "denied_requests": 0,
        "total_retry_time": 0.0
    }
    
    for i in range(10):
        result = limiter.allow_request("monitored_user")
        metrics["total_requests"] += 1
        
        if result.allowed:
            metrics["allowed_requests"] += 1
        else:
            metrics["denied_requests"] += 1
            if result.retry_after:
                metrics["total_retry_time"] += result.retry_after
        
        time.sleep(0.2)
    
    print(f"  Total Requests: {metrics['total_requests']}")
    print(f"  Allowed: {metrics['allowed_requests']} "
          f"({metrics['allowed_requests']/metrics['total_requests']*100:.1f}%)")
    print(f"  Denied: {metrics['denied_requests']} "
          f"({metrics['denied_requests']/metrics['total_requests']*100:.1f}%)")
    print(f"  Avg Retry Time: {metrics['total_retry_time']/max(metrics['denied_requests'], 1):.2f}s")


def run_all_examples():
    """Run all examples"""
    print("="*60)
    print("RATE LIMITER EXAMPLES")
    print("="*60)
    
    examples = [
        example_basic_usage,
        example_api_rate_limiting,
        example_burst_handling,
        example_multiple_users,
        example_distributed_redis,
        example_graceful_degradation,
        example_different_tiers,
        example_monitoring
    ]
    
    for example in examples:
        try:
            example()
        except KeyboardInterrupt:
            print("\n\nExamples interrupted by user")
            break
        except Exception as e:
            print(f"\n⚠ Error in {example.__name__}: {e}")
    
    print("\n" + "="*60)
    print("Examples completed!")
    print("="*60)


if __name__ == '__main__':
    run_all_examples()

     