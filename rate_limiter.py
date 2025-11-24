"""
Rate Limiter Implementation
Supports Token Bucket and Leaky Bucket algorithms with In-Memory and Redis backends.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Dict
import time
import threading
import redis


@dataclass
class RateLimitResult:
    """Result of a rate limit check"""
    allowed: bool
    tokens_remaining: int
    retry_after: Optional[float] = None


class RateLimiter(ABC):
    """Abstract base class for rate limiters"""
    
    @abstractmethod
    def allow_request(self, key: str) -> RateLimitResult:
        """Check if a request should be allowed"""
        pass
    
    @abstractmethod
    def reset(self, key: str) -> None:
        """Reset rate limit for a key"""
        pass


class TokenBucketMemory(RateLimiter):
    """Token Bucket algorithm with in-memory storage"""
    
    def __init__(self, capacity: int, refill_rate: float):
        """
        Args:
            capacity: Maximum number of tokens in bucket
            refill_rate: Tokens added per second
        """
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.buckets: Dict[str, dict] = {}
        self.lock = threading.Lock()
    
    def _refill(self, bucket: dict) -> None:
        """Refill tokens based on elapsed time"""
        now = time.time()
        elapsed = now - bucket['last_refill']
        tokens_to_add = elapsed * self.refill_rate
        
        bucket['tokens'] = min(self.capacity, bucket['tokens'] + tokens_to_add)
        bucket['last_refill'] = now
    
    def allow_request(self, key: str) -> RateLimitResult:
        with self.lock:
            if key not in self.buckets:
                self.buckets[key] = {
                    'tokens': self.capacity,
                    'last_refill': time.time()
                }
            
            bucket = self.buckets[key]
            self._refill(bucket)
            
            if bucket['tokens'] >= 1:
                bucket['tokens'] -= 1
                return RateLimitResult(
                    allowed=True,
                    tokens_remaining=int(bucket['tokens'])
                )
            else:
                retry_after = (1 - bucket['tokens']) / self.refill_rate
                return RateLimitResult(
                    allowed=False,
                    tokens_remaining=0,
                    retry_after=retry_after
                )
    
    def reset(self, key: str) -> None:
        with self.lock:
            if key in self.buckets:
                del self.buckets[key]


class LeakyBucketMemory(RateLimiter):
    """Leaky Bucket algorithm with in-memory storage"""
    
    def __init__(self, capacity: int, leak_rate: float):
        """
        Args:
            capacity: Maximum queue size
            leak_rate: Requests processed per second
        """
        self.capacity = capacity
        self.leak_rate = leak_rate
        self.buckets: Dict[str, dict] = {}
        self.lock = threading.Lock()
    
    def _leak(self, bucket: dict) -> None:
        """Process requests based on leak rate"""
        now = time.time()
        elapsed = now - bucket['last_leak']
        leaked = elapsed * self.leak_rate
        
        bucket['level'] = max(0, bucket['level'] - leaked)
        bucket['last_leak'] = now
    
    def allow_request(self, key: str) -> RateLimitResult:
        with self.lock:
            if key not in self.buckets:
                self.buckets[key] = {
                    'level': 0,
                    'last_leak': time.time()
                }
            
            bucket = self.buckets[key]
            self._leak(bucket)
            
            if bucket['level'] < self.capacity:
                bucket['level'] += 1
                return RateLimitResult(
                    allowed=True,
                    tokens_remaining=int(self.capacity - bucket['level'])
                )
            else:
                retry_after = 1 / self.leak_rate
                return RateLimitResult(
                    allowed=False,
                    tokens_remaining=0,
                    retry_after=retry_after
                )
    
    def reset(self, key: str) -> None:
        with self.lock:
            if key in self.buckets:
                del self.buckets[key]


class TokenBucketRedis(RateLimiter):
    """Token Bucket algorithm with Redis storage"""
    
    def __init__(self, capacity: int, refill_rate: float, redis_client: redis.Redis):
        """
        Args:
            capacity: Maximum number of tokens in bucket
            refill_rate: Tokens added per second
            redis_client: Redis client instance
        """
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.redis = redis_client
        
        # Lua script for atomic token bucket operations
        self.lua_script = self.redis.register_script("""
            local key = KEYS[1]
            local capacity = tonumber(ARGV[1])
            local refill_rate = tonumber(ARGV[2])
            local now = tonumber(ARGV[3])
            
            local bucket = redis.call('HMGET', key, 'tokens', 'last_refill')
            local tokens = tonumber(bucket[1])
            local last_refill = tonumber(bucket[2])
            
            if tokens == nil then
                tokens = capacity
                last_refill = now
            end
            
            -- Refill tokens
            local elapsed = now - last_refill
            local tokens_to_add = elapsed * refill_rate
            tokens = math.min(capacity, tokens + tokens_to_add)
            
            -- Try to consume token
            if tokens >= 1 then
                tokens = tokens - 1
                redis.call('HMSET', key, 'tokens', tokens, 'last_refill', now)
                redis.call('EXPIRE', key, 3600)
                return {1, math.floor(tokens)}
            else
                redis.call('HMSET', key, 'tokens', tokens, 'last_refill', now)
                redis.call('EXPIRE', key, 3600)
                local retry_after = (1 - tokens) / refill_rate
                return {0, 0, retry_after}
            end
        """)
    
    def allow_request(self, key: str) -> RateLimitResult:
        result = self.lua_script(
            keys=[f"tb:{key}"],
            args=[self.capacity, self.refill_rate, time.time()]
        )
        
        if result[0] == 1:
            return RateLimitResult(allowed=True, tokens_remaining=result[1])
        else:
            return RateLimitResult(
                allowed=False,
                tokens_remaining=0,
                retry_after=result[2] if len(result) > 2 else None
            )
    
    def reset(self, key: str) -> None:
        self.redis.delete(f"tb:{key}")


class LeakyBucketRedis(RateLimiter):
    """Leaky Bucket algorithm with Redis storage"""
    
    def __init__(self, capacity: int, leak_rate: float, redis_client: redis.Redis):
        """
        Args:
            capacity: Maximum queue size
            leak_rate: Requests processed per second
            redis_client: Redis client instance
        """
        self.capacity = capacity
        self.leak_rate = leak_rate
        self.redis = redis_client
        
        # Lua script for atomic leaky bucket operations
        self.lua_script = self.redis.register_script("""
            local key = KEYS[1]
            local capacity = tonumber(ARGV[1])
            local leak_rate = tonumber(ARGV[2])
            local now = tonumber(ARGV[3])
            
            local bucket = redis.call('HMGET', key, 'level', 'last_leak')
            local level = tonumber(bucket[1])
            local last_leak = tonumber(bucket[2])
            
            if level == nil then
                level = 0
                last_leak = now
            end
            
            -- Leak water
            local elapsed = now - last_leak
            local leaked = elapsed * leak_rate
            level = math.max(0, level - leaked)
            
            -- Try to add request
            if level < capacity then
                level = level + 1
                redis.call('HMSET', key, 'level', level, 'last_leak', now)
                redis.call('EXPIRE', key, 3600)
                return {1, math.floor(capacity - level)}
            else
                redis.call('HMSET', key, 'level', level, 'last_leak', now)
                redis.call('EXPIRE', key, 3600)
                local retry_after = 1 / leak_rate
                return {0, 0, retry_after}
            end
        """)
    
    def allow_request(self, key: str) -> RateLimitResult:
        result = self.lua_script(
            keys=[f"lb:{key}"],
            args=[self.capacity, self.leak_rate, time.time()]
        )
        
        if result[0] == 1:
            return RateLimitResult(allowed=True, tokens_remaining=result[1])
        else:
            return RateLimitResult(
                allowed=False,
                tokens_remaining=0,
                retry_after=result[2] if len(result) > 2 else None
            )
    
    def reset(self, key: str) -> None:
        self.redis.delete(f"lb:{key}")