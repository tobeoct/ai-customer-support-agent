import redis.asyncio as redis
import json
from typing import Optional, Dict, Any, Union
from .config import settings


class RedisClient:
    def __init__(self):
        self.pool = None
        self.client = None
    
    async def connect(self):
        """Initialize Redis connection pool"""
        try:
            self.pool = redis.ConnectionPool.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
                max_connections=20
            )
            self.client = redis.Redis(connection_pool=self.pool)
            return True
        except Exception as e:
            print(f"Redis connection failed: {e}")
            return False
    
    async def close(self):
        """Close Redis connection"""
        if self.client:
            await self.client.close()
        if self.pool:
            await self.pool.disconnect()
    
    async def test_connection(self):
        """Test Redis connection"""
        try:
            if not self.client:
                return False
            await self.client.ping()
            return True
        except Exception as e:
            print(f"Redis test failed: {e}")
            return False
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from Redis with JSON deserialization"""
        try:
            value = await self.client.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            print(f"Redis get failed for key {key}: {e}")
            return None
    
    async def set(self, key: str, value: Any, expire: Optional[int] = None) -> bool:
        """Set value in Redis with JSON serialization"""
        try:
            json_value = json.dumps(value, default=str)
            if expire:
                await self.client.setex(key, expire, json_value)
            else:
                await self.client.set(key, json_value)
            return True
        except Exception as e:
            print(f"Redis set failed for key {key}: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete key from Redis"""
        try:
            await self.client.delete(key)
            return True
        except Exception as e:
            print(f"Redis delete failed for key {key}: {e}")
            return False
    
    async def exists(self, key: str) -> bool:
        """Check if key exists in Redis"""
        try:
            return bool(await self.client.exists(key))
        except Exception as e:
            print(f"Redis exists check failed for key {key}: {e}")
            return False
    
    async def invalidate_pattern(self, pattern: str) -> bool:
        """Delete keys matching pattern"""
        try:
            keys = await self.client.keys(pattern)
            if keys:
                await self.client.delete(*keys)
            return True
        except Exception as e:
            print(f"Redis pattern deletion failed for {pattern}: {e}")
            return False


redis_client = RedisClient()

async def get_redis_client() -> RedisClient:
    """Get Redis client instance"""
    if not redis_client.client:
        await redis_client.connect()
    return redis_client