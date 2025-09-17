from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import json

from app.core.neo4j_client import neo4j_client
from app.services.cache import cache_service
from app.models.database import Customer, Conversation, Message


class GraphService:
    """Neo4j graph operations with aggressive Redis caching for 20-60x performance boost"""
    
    def __init__(self):
        self.neo4j = neo4j_client
        self.cache = cache_service
    
    # === CUSTOMER SIMILARITY QUERIES ===
    
    async def find_similar_customers(self, customer_id: int, limit: int = 5) -> List[Dict[str, Any]]:
        """Find similar customers with Redis caching (20-60x faster)"""
        
        # Try cache first (1-5ms vs 100-300ms for graph query)
        cache_key = f"similar_customers:{customer_id}:{limit}"
        cached_similar = await self.cache.get_cached_graph_results(customer_id, "similar_customers")
        if cached_similar:
            return cached_similar[:limit]
        
        # Cache miss - execute expensive graph query
        query = """
        MATCH (c1:Customer {customer_id: $customer_id})
        MATCH (c2:Customer)
        WHERE c1 <> c2
        
        // Calculate similarity based on multiple factors
        WITH c1, c2,
        // Communication style similarity
        CASE WHEN c1.communication_style = c2.communication_style THEN 2 ELSE 0 END as style_score,
        // Relationship stage similarity  
        CASE WHEN c1.relationship_stage = c2.relationship_stage THEN 1 ELSE 0 END as stage_score,
        // Satisfaction score proximity
        CASE WHEN abs(c1.satisfaction_score - c2.satisfaction_score) < 0.2 THEN 1 ELSE 0 END as satisfaction_score,
        // Topic overlap (calculated from relationships)
        size((c1)-[:DISCUSSED]->(:Topic)<-[:DISCUSSED]-(c2)) as topic_overlap
        
        WITH c1, c2, (style_score + stage_score + satisfaction_score + topic_overlap) as similarity_score
        WHERE similarity_score > 0
        
        RETURN c2.customer_id as customer_id,
               c2.name as name,
               c2.communication_style as communication_style,
               c2.relationship_stage as relationship_stage,
               c2.satisfaction_score as satisfaction_score,
               similarity_score
        ORDER BY similarity_score DESC
        LIMIT $limit
        """
        
        try:
            results = self.neo4j.execute_query(query, {
                "customer_id": customer_id,
                "limit": limit
            })
            
            similar_customers = [
                {
                    "customer_id": record["customer_id"],
                    "name": record["name"],
                    "communication_style": record["communication_style"],
                    "relationship_stage": record["relationship_stage"],
                    "satisfaction_score": record["satisfaction_score"],
                    "similarity_score": record["similarity_score"]
                }
                for record in results
            ]
            
            # Cache results for 1 hour
            await self.cache.cache_graph_results(customer_id, "similar_customers", similar_customers)
            
            return similar_customers
            
        except Exception as e:
            print(f"Similar customers query failed: {e}")
            return []
    
    async def find_customer_success_patterns(self, customer_id: int) -> Dict[str, Any]:
        """Find successful resolution patterns from similar customers"""
        
        cache_key = f"success_patterns:{customer_id}"
        cached_patterns = await self.cache.redis.get(cache_key)
        if cached_patterns:
            return cached_patterns
        
        # Get similar customers first
        similar_customers = await self.find_similar_customers(customer_id, limit=10)
        if not similar_customers:
            return {"patterns": [], "confidence": 0}
        
        similar_ids = [c["customer_id"] for c in similar_customers]
        
        query = """
        MATCH (c:Customer)-[:HAD_CONVERSATION]->(conv:Conversation)-[:RESOLVED_WITH]->(resolution:Resolution)
        WHERE c.customer_id IN $customer_ids AND conv.satisfaction_rating >= 4
        
        WITH resolution.strategy as strategy, 
             resolution.outcome as outcome,
             conv.satisfaction_rating as rating,
             count(*) as frequency
        
        RETURN strategy, outcome, avg(rating) as avg_satisfaction, frequency
        ORDER BY frequency DESC, avg_satisfaction DESC
        LIMIT 5
        """
        
        try:
            results = self.neo4j.execute_query(query, {"customer_ids": similar_ids})
            
            patterns = [
                {
                    "strategy": record["strategy"],
                    "outcome": record["outcome"],
                    "avg_satisfaction": record["avg_satisfaction"],
                    "frequency": record["frequency"],
                    "confidence": min(record["frequency"] / len(similar_customers), 1.0)
                }
                for record in results
            ]
            
            success_data = {
                "patterns": patterns,
                "similar_customers_analyzed": len(similar_customers),
                "confidence": sum(p["confidence"] for p in patterns) / len(patterns) if patterns else 0
            }
            
            # Cache for 1 hour
            await self.cache.redis.set(cache_key, success_data, 3600)
            
            return success_data
            
        except Exception as e:
            print(f"Success patterns query failed: {e}")
            return {"patterns": [], "confidence": 0}
    
    # === CONVERSATION FLOW ANALYSIS ===
    
    async def analyze_conversation_flows(self, customer_type: str = None) -> Dict[str, Any]:
        """Analyze successful conversation flows and patterns"""
        
        cache_key = f"conversation_flows:{customer_type or 'all'}"
        cached_flows = await self.cache.redis.get(cache_key)
        if cached_flows:
            return cached_flows
        
        where_clause = "WHERE c.relationship_stage = $customer_type" if customer_type else ""
        
        query = f"""
        MATCH (c:Customer)-[:HAD_CONVERSATION]->(conv:Conversation)
        {where_clause}
        
        MATCH (conv)-[:CONTAINS_MESSAGE]->(msg:Message)
        WITH conv, collect(msg.intent) as message_intents, conv.satisfaction_rating as rating
        WHERE rating IS NOT NULL
        
        WITH message_intents, rating, 
             CASE WHEN rating >= 4 THEN 'successful' ELSE 'unsuccessful' END as outcome
        
        WITH outcome, message_intents, count(*) as frequency
        WHERE frequency > 1
        
        RETURN outcome, message_intents, frequency
        ORDER BY frequency DESC
        LIMIT 10
        """
        
        try:
            results = self.neo4j.execute_query(query, {"customer_type": customer_type})
            
            flows = {
                "successful_patterns": [],
                "unsuccessful_patterns": [],
                "insights": {}
            }
            
            for record in results:
                pattern = {
                    "flow": record["message_intents"],
                    "frequency": record["frequency"]
                }
                
                if record["outcome"] == "successful":
                    flows["successful_patterns"].append(pattern)
                else:
                    flows["unsuccessful_patterns"].append(pattern)
            
            # Generate insights
            if flows["successful_patterns"]:
                most_common_success = flows["successful_patterns"][0]["flow"]
                flows["insights"]["recommended_flow"] = most_common_success
                flows["insights"]["success_rate"] = len(flows["successful_patterns"]) / (len(flows["successful_patterns"]) + len(flows["unsuccessful_patterns"]))
            
            # Cache for 2 hours (flows change slowly)
            await self.cache.redis.set(cache_key, flows, 7200)
            
            return flows
            
        except Exception as e:
            print(f"Conversation flows query failed: {e}")
            return {"successful_patterns": [], "unsuccessful_patterns": [], "insights": {}}
    
    # === ETL SYNC FROM POSTGRESQL TO NEO4J ===
    
    async def sync_customer_to_graph(self, customer_data: Dict[str, Any]) -> bool:
        """Sync customer data from PostgreSQL to Neo4j"""
        
        query = """
        MERGE (c:Customer {customer_id: $customer_id})
        SET c.name = $name,
            c.email = $email,
            c.communication_style = $communication_style,
            c.relationship_stage = $relationship_stage,
            c.satisfaction_score = $satisfaction_score,
            c.created_at = $created_at,
            c.updated_at = datetime()
        RETURN c.customer_id as customer_id
        """
        
        try:
            result = self.neo4j.execute_query(query, {
                "customer_id": customer_data["id"],
                "name": customer_data.get("name", ""),
                "email": customer_data.get("email", ""),
                "communication_style": customer_data.get("communication_style", ""),
                "relationship_stage": customer_data.get("relationship_stage", ""),
                "satisfaction_score": customer_data.get("satisfaction_score", 0.5),
                "created_at": customer_data.get("created_at", datetime.utcnow().isoformat())
            })
            
            # Invalidate similarity caches since customer data changed
            await self.cache.invalidate_customer_graph_cache(customer_data["id"])
            
            return len(result) > 0
            
        except Exception as e:
            print(f"Customer sync failed: {e}")
            return False
    
    async def sync_conversation_to_graph(self, conversation_data: Dict[str, Any], messages: List[Dict[str, Any]]) -> bool:
        """Sync conversation and messages to Neo4j with relationships"""
        
        # Create conversation node
        conv_query = """
        MATCH (c:Customer {customer_id: $customer_id})
        MERGE (c)-[:HAD_CONVERSATION]->(conv:Conversation {conversation_id: $conversation_id})
        SET conv.topic = $topic,
            conv.status = $status,
            conv.satisfaction_rating = $satisfaction_rating,
            conv.started_at = $started_at
        """
        
        try:
            self.neo4j.execute_query(conv_query, {
                "customer_id": conversation_data["customer_id"],
                "conversation_id": conversation_data["id"],
                "topic": conversation_data.get("topic", ""),
                "status": conversation_data.get("status", "active"),
                "satisfaction_rating": conversation_data.get("satisfaction_rating"),
                "started_at": conversation_data.get("started_at", datetime.utcnow().isoformat())
            })
            
            # Create message nodes and topic relationships
            for msg in messages:
                if msg.get("intent"):
                    msg_query = """
                    MATCH (conv:Conversation {conversation_id: $conversation_id})
                    MERGE (conv)-[:CONTAINS_MESSAGE]->(msg:Message {message_id: $message_id})
                    SET msg.content = $content,
                        msg.message_type = $message_type,
                        msg.intent = $intent,
                        msg.sentiment = $sentiment
                    
                    // Create topic relationships
                    MERGE (topic:Topic {name: $intent})
                    MERGE (conv)-[:DISCUSSED]->(topic)
                    """
                    
                    self.neo4j.execute_query(msg_query, {
                        "conversation_id": conversation_data["id"],
                        "message_id": msg["id"],
                        "content": msg.get("content", "")[:200],  # Limit content length
                        "message_type": msg.get("message_type", "user"),
                        "intent": msg.get("intent", "unknown"),
                        "sentiment": msg.get("sentiment", "neutral")
                    })
            
            # Create resolution relationship if conversation is resolved
            if conversation_data.get("status") == "resolved" and conversation_data.get("resolution"):
                resolution_query = """
                MATCH (conv:Conversation {conversation_id: $conversation_id})
                MERGE (conv)-[:RESOLVED_WITH]->(r:Resolution {
                    strategy: $resolution,
                    outcome: $status,
                    satisfaction: $satisfaction_rating
                })
                """
                
                self.neo4j.execute_query(resolution_query, {
                    "conversation_id": conversation_data["id"],
                    "resolution": conversation_data.get("resolution", "")[:100],
                    "status": "resolved",
                    "satisfaction_rating": conversation_data.get("satisfaction_rating", 3)
                })
            
            return True
            
        except Exception as e:
            print(f"Conversation sync failed: {e}")
            return False
    
    # === PATTERN DISCOVERY ===
    
    async def discover_escalation_patterns(self) -> Dict[str, Any]:
        """Discover patterns that lead to escalations"""
        
        cache_key = "escalation_patterns"
        cached_patterns = await self.cache.redis.get(cache_key)
        if cached_patterns:
            return cached_patterns
        
        query = """
        MATCH (c:Customer)-[:HAD_CONVERSATION]->(conv:Conversation)
        WHERE conv.status = 'escalated'
        
        MATCH (conv)-[:DISCUSSED]->(topic:Topic)
        WITH topic.name as escalation_topic, 
             c.communication_style as style,
             c.relationship_stage as stage,
             count(*) as frequency
        
        RETURN escalation_topic, style, stage, frequency
        ORDER BY frequency DESC
        LIMIT 10
        """
        
        try:
            results = self.neo4j.execute_query(query)
            
            patterns = {
                "common_escalation_topics": [],
                "high_risk_profiles": [],
                "recommendations": []
            }
            
            # Analyze topic patterns
            topic_counts = {}
            profile_counts = {}
            
            for record in results:
                topic = record["escalation_topic"]
                profile = f"{record['style']}_{record['stage']}"
                frequency = record["frequency"]
                
                topic_counts[topic] = topic_counts.get(topic, 0) + frequency
                profile_counts[profile] = profile_counts.get(profile, 0) + frequency
                
                patterns["common_escalation_topics"].append({
                    "topic": topic,
                    "frequency": frequency,
                    "customer_profile": profile
                })
            
            # Identify high-risk profiles
            for profile, count in sorted(profile_counts.items(), key=lambda x: x[1], reverse=True)[:5]:
                style, stage = profile.split("_")
                patterns["high_risk_profiles"].append({
                    "communication_style": style,
                    "relationship_stage": stage,
                    "escalation_frequency": count
                })
            
            # Generate recommendations
            if patterns["common_escalation_topics"]:
                top_topic = max(topic_counts.items(), key=lambda x: x[1])
                patterns["recommendations"].append(f"Focus training on '{top_topic[0]}' issues - {top_topic[1]} escalations")
            
            if patterns["high_risk_profiles"]:
                risk_profile = patterns["high_risk_profiles"][0]
                patterns["recommendations"].append(f"Monitor {risk_profile['communication_style']} {risk_profile['relationship_stage']} customers closely")
            
            # Cache for 4 hours (patterns change slowly)
            await self.cache.redis.set(cache_key, patterns, 14400)
            
            return patterns
            
        except Exception as e:
            print(f"Escalation patterns query failed: {e}")
            return {"common_escalation_topics": [], "high_risk_profiles": [], "recommendations": []}
    
    async def discover_success_strategies(self) -> Dict[str, Any]:
        """Discover strategies that lead to successful resolutions"""
        
        cache_key = "success_strategies"
        cached_strategies = await self.cache.redis.get(cache_key)
        if cached_strategies:
            return cached_strategies
        
        query = """
        MATCH (c:Customer)-[:HAD_CONVERSATION]->(conv:Conversation)-[:RESOLVED_WITH]->(r:Resolution)
        WHERE conv.satisfaction_rating >= 4
        
        WITH r.strategy as strategy, 
             c.communication_style as style,
             c.relationship_stage as stage,
             avg(conv.satisfaction_rating) as avg_satisfaction,
             count(*) as success_count
        
        RETURN strategy, style, stage, avg_satisfaction, success_count
        ORDER BY success_count DESC, avg_satisfaction DESC
        LIMIT 15
        """
        
        try:
            results = self.neo4j.execute_query(query)
            
            strategies = {
                "top_strategies": [],
                "style_specific_strategies": {},
                "stage_specific_strategies": {},
                "insights": {}
            }
            
            for record in results:
                strategy_data = {
                    "strategy": record["strategy"],
                    "communication_style": record["style"],
                    "relationship_stage": record["stage"],
                    "avg_satisfaction": record["avg_satisfaction"],
                    "success_count": record["success_count"]
                }
                
                strategies["top_strategies"].append(strategy_data)
                
                # Group by communication style
                style = record["style"]
                if style not in strategies["style_specific_strategies"]:
                    strategies["style_specific_strategies"][style] = []
                strategies["style_specific_strategies"][style].append(strategy_data)
                
                # Group by relationship stage
                stage = record["stage"]
                if stage not in strategies["stage_specific_strategies"]:
                    strategies["stage_specific_strategies"][stage] = []
                strategies["stage_specific_strategies"][stage].append(strategy_data)
            
            # Generate insights
            if strategies["top_strategies"]:
                best_strategy = strategies["top_strategies"][0]
                strategies["insights"]["most_effective_strategy"] = best_strategy["strategy"]
                strategies["insights"]["best_satisfaction_score"] = best_strategy["avg_satisfaction"]
            
            # Cache for 4 hours
            await self.cache.redis.set(cache_key, strategies, 14400)
            
            return strategies
            
        except Exception as e:
            print(f"Success strategies query failed: {e}")
            return {"top_strategies": [], "style_specific_strategies": {}, "stage_specific_strategies": {}, "insights": {}}
    
    # === GRAPH SCHEMA INITIALIZATION ===
    
    def initialize_graph_schema(self) -> bool:
        """Initialize Neo4j schema and constraints"""
        
        schema_queries = [
            # Customer constraints and indexes
            "CREATE CONSTRAINT customer_id_unique IF NOT EXISTS FOR (c:Customer) REQUIRE c.customer_id IS UNIQUE",
            "CREATE INDEX customer_style_index IF NOT EXISTS FOR (c:Customer) ON (c.communication_style)",
            "CREATE INDEX customer_stage_index IF NOT EXISTS FOR (c:Customer) ON (c.relationship_stage)",
            
            # Conversation constraints
            "CREATE CONSTRAINT conversation_id_unique IF NOT EXISTS FOR (conv:Conversation) REQUIRE conv.conversation_id IS UNIQUE",
            "CREATE INDEX conversation_status_index IF NOT EXISTS FOR (conv:Conversation) ON (conv.status)",
            "CREATE INDEX conversation_satisfaction_index IF NOT EXISTS FOR (conv:Conversation) ON (conv.satisfaction_rating)",
            
            # Topic and Resolution indexes
            "CREATE INDEX topic_name_index IF NOT EXISTS FOR (t:Topic) ON (t.name)",
            "CREATE INDEX resolution_strategy_index IF NOT EXISTS FOR (r:Resolution) ON (r.strategy)",
            
            # Message indexes
            "CREATE INDEX message_intent_index IF NOT EXISTS FOR (m:Message) ON (m.intent)",
            "CREATE INDEX message_sentiment_index IF NOT EXISTS FOR (m:Message) ON (m.sentiment)"
        ]
        
        try:
            for query in schema_queries:
                self.neo4j.execute_query(query)
            
            print("✅ Neo4j schema initialized successfully")
            return True
            
        except Exception as e:
            print(f"❌ Schema initialization failed: {e}")
            return False
    
    # === ANALYTICS AND INSIGHTS ===
    
    async def get_graph_analytics(self) -> Dict[str, Any]:
        """Get comprehensive graph analytics"""
        
        cache_key = "graph_analytics"
        cached_analytics = await self.cache.redis.get(cache_key)
        if cached_analytics:
            return cached_analytics
        
        analytics_queries = {
            "node_counts": "MATCH (n) RETURN labels(n) as label, count(n) as count",
            "relationship_counts": "MATCH ()-[r]->() RETURN type(r) as relationship, count(r) as count",
            "customer_distribution": """
                MATCH (c:Customer) 
                RETURN c.relationship_stage as stage, c.communication_style as style, count(*) as count
            """,
            "conversation_outcomes": """
                MATCH (conv:Conversation) 
                RETURN conv.status as status, avg(conv.satisfaction_rating) as avg_satisfaction, count(*) as count
            """,
            "topic_popularity": """
                MATCH (t:Topic)<-[:DISCUSSED]-() 
                RETURN t.name as topic, count(*) as discussions 
                ORDER BY discussions DESC LIMIT 10
            """
        }
        
        analytics = {}
        
        try:
            for key, query in analytics_queries.items():
                results = self.neo4j.execute_query(query)
                analytics[key] = results
            
            # Cache for 1 hour
            await self.cache.redis.set(cache_key, analytics, 3600)
            
            return analytics
            
        except Exception as e:
            print(f"Graph analytics query failed: {e}")
            return {}
    
    # === CACHE MANAGEMENT ===
    
    async def invalidate_customer_graph_cache(self, customer_id: int):
        """Invalidate all graph caches for a customer"""
        patterns = [
            f"similar_customers:{customer_id}:*",
            f"success_patterns:{customer_id}",
            "escalation_patterns",
            "success_strategies",
            "graph_analytics"
        ]
        
        for pattern in patterns:
            await self.cache.redis.invalidate_pattern(pattern)


# Global service instance
graph_service = GraphService()