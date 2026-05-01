"""
Redis Cache Client - Cloud-Agnostic

Works with:
- AWS ElastiCache
- GCP Memorystore
- Azure Cache for Redis
- Redis (local Docker)

Usage:
    from app.services.cache import get_cache, Cache
    
    cache = get_cache()
    
    # Basic key-value
    cache.set("user:123", {"name": "John"}, ttl=3600)
    user = cache.get("user:123")
    
    # With JSON serialization
    cache.set_json("config", {"theme": "dark"})
    config = cache.get_json("config")
    
    # Caching decorator
    @cached(ttl=300)
    async def get_expensive_data():
        ...
"""

import json
from typing import Optional, Any, Callable
from functools import wraps

import redis
from redis import Redis

from ..core.config import get_settings
from ..core.logging import get_logger

logger = get_logger(__name__)


class Cache:
    """Redis cache client with JSON support."""
    
    def __init__(
        self,
        redis_url: str,
        max_connections: int = 10,
        default_ttl: int = 300,
    ):
        """
        Initialize Redis cache client.
        
        Args:
            redis_url: Redis connection URL (redis://host:port)
            max_connections: Connection pool size
            default_ttl: Default TTL in seconds (5 minutes)
        """
        self.default_ttl = default_ttl
        
        # Create connection pool
        self.pool = redis.ConnectionPool.from_url(
            redis_url,
            max_connections=max_connections,
            decode_responses=True,  # Auto-decode to strings
        )
        
        self.client = Redis(connection_pool=self.pool)
        
        logger.info("Cache client initialized", url=redis_url)
    
    def ping(self) -> bool:
        """Check if Redis is available."""
        try:
            return self.client.ping()
        except Exception as e:
            logger.error("Redis ping failed", error=str(e))
            return False
    
    # ==========================================================================
    # Basic Operations
    # ==========================================================================
    
    def get(self, key: str) -> Optional[str]:
        """Get a string value."""
        try:
            return self.client.get(key)
        except Exception as e:
            logger.error("Cache get failed", key=key, error=str(e))
            return None
    
    def set(
        self,
        key: str,
        value: str,
        ttl: Optional[int] = None,
    ) -> bool:
        """
        Set a string value.
        
        Args:
            key: Cache key
            value: String value
            ttl: TTL in seconds (None = use default)
        """
        try:
            self.client.set(key, value, ex=ttl or self.default_ttl)
            return True
        except Exception as e:
            logger.error("Cache set failed", key=key, error=str(e))
            return False
    
    def delete(self, key: str) -> bool:
        """Delete a key."""
        try:
            self.client.delete(key)
            return True
        except Exception as e:
            logger.error("Cache delete failed", key=key, error=str(e))
            return False
    
    def exists(self, key: str) -> bool:
        """Check if key exists."""
        try:
            return bool(self.client.exists(key))
        except Exception:
            return False
    
    # ==========================================================================
    # JSON Operations
    # ==========================================================================
    
    def get_json(self, key: str) -> Optional[Any]:
        """Get and deserialize JSON value."""
        try:
            value = self.client.get(key)
            if value is None:
                return None
            return json.loads(value)
        except json.JSONDecodeError:
            logger.error("Cache JSON decode failed", key=key)
            return None
        except Exception as e:
            logger.error("Cache get_json failed", key=key, error=str(e))
            return None
    
    def set_json(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
    ) -> bool:
        """Serialize and set JSON value."""
        try:
            json_str = json.dumps(value, default=str)
            self.client.set(key, json_str, ex=ttl or self.default_ttl)
            return True
        except Exception as e:
            logger.error("Cache set_json failed", key=key, error=str(e))
            return False
    
    # ==========================================================================
    # Pattern Operations
    # ==========================================================================
    
    def delete_pattern(self, pattern: str) -> int:
        """
        Delete all keys matching pattern.
        
        Args:
            pattern: Redis pattern (e.g., "user:*")
            
        Returns:
            Number of keys deleted
        """
        try:
            keys = self.client.keys(pattern)
            if keys:
                return self.client.delete(*keys)
            return 0
        except Exception as e:
            logger.error("Cache delete_pattern failed", pattern=pattern, error=str(e))
            return 0
    
    def get_keys(self, pattern: str = "*") -> list[str]:
        """Get all keys matching pattern."""
        try:
            return self.client.keys(pattern)
        except Exception:
            return []
    
    # ==========================================================================
    # Counter Operations
    # ==========================================================================
    
    def incr(self, key: str, amount: int = 1) -> int:
        """Increment a counter."""
        try:
            return self.client.incrby(key, amount)
        except Exception:
            return 0
    
    def decr(self, key: str, amount: int = 1) -> int:
        """Decrement a counter."""
        try:
            return self.client.decrby(key, amount)
        except Exception:
            return 0
    
    # ==========================================================================
    # Hash Operations (for structured data)
    # ==========================================================================
    
    def hget(self, name: str, key: str) -> Optional[str]:
        """Get a hash field."""
        try:
            return self.client.hget(name, key)
        except Exception:
            return None
    
    def hset(self, name: str, key: str, value: str) -> bool:
        """Set a hash field."""
        try:
            self.client.hset(name, key, value)
            return True
        except Exception:
            return False
    
    def hgetall(self, name: str) -> dict:
        """Get all hash fields."""
        try:
            return self.client.hgetall(name)
        except Exception:
            return {}
    
    # ==========================================================================
    # TTL Operations
    # ==========================================================================
    
    def ttl(self, key: str) -> int:
        """Get remaining TTL for a key."""
        try:
            return self.client.ttl(key)
        except Exception:
            return -1
    
    def expire(self, key: str, ttl: int) -> bool:
        """Set TTL on existing key."""
        try:
            return bool(self.client.expire(key, ttl))
        except Exception:
            return False


# Singleton instance
_cache: Optional[Cache] = None


def get_cache() -> Cache:
    """
    Get or create cache singleton.
    
    Returns:
        Cache instance
    """
    global _cache
    
    if _cache is None:
        settings = get_settings()
        _cache = Cache(
            redis_url=settings.redis_url,
            max_connections=settings.redis_max_connections,
            default_ttl=settings.cache_ttl_seconds,
        )
    
    return _cache


def reset_cache():
    """Reset cache client (useful for testing)."""
    global _cache
    _cache = None


# ==========================================================================
# Caching Decorator
# ==========================================================================

def cached(
    ttl: int = 300,
    key_prefix: str = "",
    key_builder: Optional[Callable[..., str]] = None,
):
    """
    Caching decorator for functions.
    
    Args:
        ttl: Cache TTL in seconds
        key_prefix: Prefix for cache keys
        key_builder: Optional function to build cache key from args
        
    Usage:
        @cached(ttl=300, key_prefix="user")
        def get_user(user_id: int):
            ...
    """
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache = get_cache()
            
            # Build cache key
            if key_builder:
                cache_key = key_builder(*args, **kwargs)
            else:
                # Default key: prefix:func_name:args:kwargs
                args_str = ":".join(str(a) for a in args)
                kwargs_str = ":".join(f"{k}={v}" for k, v in sorted(kwargs.items()))
                parts = [key_prefix or func.__name__, args_str, kwargs_str]
                cache_key = ":".join(p for p in parts if p)
            
            # Try to get from cache
            cached_value = cache.get_json(cache_key)
            if cached_value is not None:
                logger.debug("Cache hit", key=cache_key)
                return cached_value
            
            # Execute function
            result = func(*args, **kwargs)
            
            # Store in cache
            cache.set_json(cache_key, result, ttl=ttl)
            logger.debug("Cache miss, stored", key=cache_key)
            
            return result
        
        return wrapper
    return decorator
