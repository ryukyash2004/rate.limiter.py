import pytest
import time
import threading
from unittest.mock import MagicMock, patch
from rate_limiter import TokenBucketMemory, LeakyBucketMemory, RateLimitResult

# --- Helper for Mocking Time ---
@pytest.fixture
def mock_time():
    with patch('time.time') as mock:
        yield mock

# --- Token Bucket Tests ---

def test_token_bucket_initialization():
    limiter = TokenBucketMemory(capacity=10, refill_rate=1)
    # First request should be allowed
    result = limiter.allow_request("user1")
    assert result.allowed is True
    assert result.tokens_remaining == 9

def test_token_bucket_depletion(mock_time):
    # Capacity 2, refill 1 per second
    limiter = TokenBucketMemory(capacity=2, refill_rate=1)
    mock_time.return_value = 1000
    
    # Consume all tokens
    assert limiter.allow_request("user1").allowed is True
    assert limiter.allow_request("user1").allowed is True
    
    # Next one should fail
    result = limiter.allow_request("user1")
    assert result.allowed is False
    assert result.retry_after > 0

def test_token_bucket_refill(mock_time):
    limiter = TokenBucketMemory(capacity=5, refill_rate=1)
    mock_time.return_value = 1000
    
    # Use all tokens
    for _ in range(5):
        limiter.allow_request("user1")
    
    assert limiter.allow_request("user1").allowed is False
    
    # "Wait" for 2 seconds
    mock_time.return_value = 1002
    
    # Should have 2 tokens now
    result = limiter.allow_request("user1")
    assert result.allowed is True
    assert result.tokens_remaining == 1 # 2 refreshed, 1 consumed

# --- Leaky Bucket Tests ---

def test_leaky_bucket_flow(mock_time):
    # Leak rate 1 request per second
    limiter = LeakyBucketMemory(capacity=5, leak_rate=1)
    mock_time.return_value = 1000
    
    # Fill the bucket
    for _ in range(5):
        assert limiter.allow_request("user1").allowed is True
        
    # Overflow
    assert limiter.allow_request("user1").allowed is False
    
    # Advance time by 1 second (1 request leaks out)
    mock_time.return_value = 1001
    
    # Should accept 1 more now
    assert limiter.allow_request("user1").allowed is True
    # And reject the next
    assert limiter.allow_request("user1").allowed is False

# --- Concurrency Tests ---

def test_thread_safety():
    """Test that multiple threads don't corrupt the counter"""
    limiter = TokenBucketMemory(capacity=100, refill_rate=0) # No refill
    
    def make_request():
        limiter.allow_request("shared_key")

    threads = []
    for _ in range(100):
        t = threading.Thread(target=make_request)
        threads.append(t)
        t.start()
        
    for t in threads:
        t.join()
        
    # If 100 threads hit it, tokens should be exactly 0
    # (assuming capacity was 100 and we hit it 100 times)
    assert limiter.buckets["shared_key"]['tokens'] == 0

# --- Redis Tests (Skipped if no Redis) ---

try:
    import redis
    redis_client = redis.Redis(host='localhost', port=6379)
    redis_client.ping()
    REDIS_AVAILABLE = True
except:
    REDIS_AVAILABLE = False

@pytest.mark.skipif(not REDIS_AVAILABLE, reason="Redis not available")
def test_redis_token_bucket():
    r = redis.Redis(host='localhost', port=6379)
    # Clean up before test
    r.delete("tb:test_user")
    
    limiter = TokenBucketRedis(capacity=5, refill_rate=1, redis_client=r)
    assert limiter.allow_request("test_user").allowed is True