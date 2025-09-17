from typing import Optional, Dict, Any, List
import hashlib
import json
from app.core.redis_client import redis_client


class CacheService:
    """Centralized caching service with Redis"""
    
    # Cache TTL constants (in seconds)
    CUSTOMER_SESSION_TTL = 3600  # 1 hour
    DOCUMENT_SEARCH_TTL = 1800   # 30 minutes
    GRAPH_RESULTS_TTL = 3600     # 1 hour
    LLM_RESPONSE_TTL = 600       # 10 minutes
    
    def __init__(self):
        self.redis = redis_client
    
    def _hash_query(self, query: str) -> str:
        """Create consistent hash for query caching"""
        return hashlib.md5(query.encode()).hexdigest()
    
    # Customer Session Caching
    async def cache_customer_session(self, session_id: str, customer_data: Dict[str, Any]) -> bool:
        """Cache customer session data"""
        cache_key = f"customer:session:{session_id}"
        return await self.redis.set(cache_key, customer_data, self.CUSTOMER_SESSION_TTL)
    
    async def get_cached_customer_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve cached customer session data"""
        cache_key = f"customer:session:{session_id}"
        return await self.redis.get(cache_key)
    
    async def invalidate_customer_session(self, session_id: str) -> bool:
        """Invalidate customer session cache"""
        cache_key = f"customer:session:{session_id}"
        return await self.redis.delete(cache_key)
    
    # Document Search Caching
    async def cache_document_search(self, query: str, results: List[Dict[str, Any]]) -> bool:
        """Cache document search results"""
        query_hash = self._hash_query(query)
        cache_key = f"docs:search:{query_hash}"
        return await self.redis.set(cache_key, results, self.DOCUMENT_SEARCH_TTL)
    
    async def get_cached_document_search(self, query: str) -> Optional[List[Dict[str, Any]]]:
        """Retrieve cached document search results"""
        query_hash = self._hash_query(query)
        cache_key = f"docs:search:{query_hash}"
        return await self.redis.get(cache_key)
    
    # Graph Query Results Caching
    async def cache_graph_results(self, customer_id: int, query_type: str, results: List[Dict[str, Any]]) -> bool:
        """Cache Neo4j graph query results"""
        cache_key = f"graph:{query_type}:{customer_id}"
        return await self.redis.set(cache_key, results, self.GRAPH_RESULTS_TTL)
    
    async def get_cached_graph_results(self, customer_id: int, query_type: str) -> Optional[List[Dict[str, Any]]]:
        """Retrieve cached graph query results"""
        cache_key = f"graph:{query_type}:{customer_id}"
        return await self.redis.get(cache_key)
    
    async def invalidate_customer_graph_cache(self, customer_id: int) -> bool:
        """Invalidate all graph caches for a customer"""
        pattern = f"graph:*:{customer_id}"
        return await self.redis.invalidate_pattern(pattern)
    
    # LLM Response Caching
    async def cache_llm_response(self, customer_classification: str, query: str, 
                               context_summary: str, response: str) -> bool:
        """Cache LLM response to avoid duplicate API calls"""
        # Create unique hash for the combination
        combined_input = f"{customer_classification}:{query}:{context_summary}"
        response_hash = self._hash_query(combined_input)
        cache_key = f"llm:response:{response_hash}"
        
        cached_data = {
            "response": response,
            "classification": customer_classification,
            "query": query,
            "context_summary": context_summary
        }
        
        return await self.redis.set(cache_key, cached_data, self.LLM_RESPONSE_TTL)
    
    async def get_cached_llm_response(self, customer_classification: str, query: str, 
                                    context_summary: str) -> Optional[str]:
        """Retrieve cached LLM response"""
        combined_input = f"{customer_classification}:{query}:{context_summary}"
        response_hash = self._hash_query(combined_input)
        cache_key = f"llm:response:{response_hash}"
        
        cached_data = await self.redis.get(cache_key)
        if cached_data:
            return cached_data.get("response")
        return None
    
    # General Cache Operations
    async def exists(self, key: str) -> bool:
        """Check if cache key exists"""
        return await self.redis.exists(key)
    
    async def delete(self, key: str) -> bool:
        """Delete specific cache key"""
        return await self.redis.delete(key)
    
    async def clear_all_customer_cache(self, customer_id: int) -> bool:
        """Clear all cache entries for a specific customer"""
        patterns = [
            f"customer:*:{customer_id}",
            f"graph:*:{customer_id}"
        ]
        
        success = True
        for pattern in patterns:
            result = await self.redis.invalidate_pattern(pattern)
            success = success and result
        
        return success
    
    # Cache Statistics and Health
    async def get_cache_stats(self) -> Dict[str, Any]:
        """Get basic cache statistics"""
        try:
            # Count keys by pattern
            customer_keys = len(await self.redis.client.keys("customer:*"))
            doc_keys = len(await self.redis.client.keys("docs:*"))
            graph_keys = len(await self.redis.client.keys("graph:*"))
            llm_keys = len(await self.redis.client.keys("llm:*"))
            
            return {
                "customer_cache_entries": customer_keys,
                "document_cache_entries": doc_keys,
                "graph_cache_entries": graph_keys,
                "llm_cache_entries": llm_keys,
                "total_entries": customer_keys + doc_keys + graph_keys + llm_keys
            }
        except Exception as e:
            print(f"Failed to get cache stats: {e}")
            return {"error": "Failed to retrieve cache statistics"}


# Global cache service instance
cache_service = CacheService()