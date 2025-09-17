from typing import Dict, Any, List, Optional
from datetime import datetime
import asyncio

from app.services.graph import graph_service
from app.services.customer import customer_service
from app.services.classification import classification_service
from app.services.rag import rag_service
from app.services.cache import cache_service


class CustomerIntelligenceService:
    """Unified customer intelligence combining graph insights with service data"""
    
    def __init__(self):
        self.graph = graph_service
        self.customer = customer_service
        self.classification = classification_service
        self.rag = rag_service
        self.cache = cache_service
    
    async def get_comprehensive_customer_profile(self, customer_id: int, db_session) -> Dict[str, Any]:
        """Get complete customer profile combining all intelligence sources"""
        
        # Try cache first for complete profile
        cache_key = f"comprehensive_profile:{customer_id}"
        cached_profile = await self.cache.redis.get(cache_key)
        if cached_profile:
            return cached_profile
        
        # Gather data from all sources in parallel for speed
        tasks = [
            self.customer.get_customer_analytics(customer_id, db_session),
            self.classification.classify_customer_comprehensive(customer_id, db_session),
            self.graph.find_similar_customers(customer_id, limit=5),
            self.graph.find_customer_success_patterns(customer_id)
        ]
        
        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            customer_analytics = results[0] if not isinstance(results[0], Exception) else {}
            classification = results[1] if not isinstance(results[1], Exception) else {}
            similar_customers = results[2] if not isinstance(results[2], Exception) else []
            success_patterns = results[3] if not isinstance(results[3], Exception) else {}
            
            # Combine all intelligence
            comprehensive_profile = {
                "customer_id": customer_id,
                "profile_generated_at": datetime.utcnow().isoformat(),
                
                # Core customer data
                "customer_analytics": customer_analytics,
                
                # ML Classification insights
                "classification": classification,
                
                # Graph-based insights
                "graph_insights": {
                    "similar_customers": similar_customers,
                    "success_patterns": success_patterns,
                    "similarity_confidence": len(similar_customers) / 5.0  # Confidence based on results
                },
                
                # Unified recommendations
                "recommendations": self._generate_unified_recommendations(
                    customer_analytics, classification, similar_customers, success_patterns
                ),
                
                # Risk and opportunity assessment
                "intelligence_summary": self._generate_intelligence_summary(
                    customer_analytics, classification, success_patterns
                )
            }
            
            # Cache comprehensive profile for 30 minutes
            await self.cache.redis.set(cache_key, comprehensive_profile, 1800)
            
            return comprehensive_profile
            
        except Exception as e:
            print(f"Comprehensive profile generation failed: {e}")
            return {"error": str(e), "customer_id": customer_id}
    
    def _generate_unified_recommendations(self, analytics: Dict, classification: Dict, 
                                        similar_customers: List, success_patterns: Dict) -> List[Dict[str, Any]]:
        """Generate actionable recommendations from all intelligence sources"""
        
        recommendations = []
        
        # Classification-based recommendations
        if classification.get("risk_assessment", {}).get("risk_level") == "high":
            recommendations.append({
                "type": "risk_mitigation",
                "priority": "high",
                "action": "Immediate manager escalation recommended",
                "reason": f"High churn risk detected: {classification['risk_assessment'].get('risk_score', 0)}/10",
                "source": "classification_ai"
            })
        
        # Communication style recommendations
        comm_style = classification.get("communication_style", {}).get("primary_style")
        if comm_style == "technical":
            recommendations.append({
                "type": "communication",
                "priority": "medium",
                "action": "Provide technical documentation and API references",
                "reason": "Customer prefers technical communication style",
                "source": "classification_ai"
            })
        elif comm_style == "emotional":
            recommendations.append({
                "type": "communication", 
                "priority": "medium",
                "action": "Use empathetic language and acknowledge frustrations",
                "reason": "Customer tends toward emotional communication",
                "source": "classification_ai"
            })
        
        # Graph-based recommendations from similar customers
        if success_patterns.get("patterns"):
            best_pattern = success_patterns["patterns"][0]  # Highest success rate
            recommendations.append({
                "type": "strategy",
                "priority": "high",
                "action": f"Apply '{best_pattern['strategy']}' resolution approach",
                "reason": f"Success rate: {best_pattern.get('confidence', 0):.1%} with similar customers",
                "source": "graph_intelligence"
            })
        
        # Engagement recommendations
        if analytics.get("engagement_stats", {}).get("total_conversations", 0) > 5:
            recommendations.append({
                "type": "relationship",
                "priority": "low", 
                "action": "Consider VIP program enrollment",
                "reason": "High engagement customer with multiple conversations",
                "source": "customer_analytics"
            })
        
        # Urgency-based recommendations
        urgency = classification.get("urgency_pattern", {}).get("urgency_level")
        if urgency in ["critical", "high"]:
            recommendations.append({
                "type": "response_time",
                "priority": "critical",
                "action": "Respond within 15 minutes",
                "reason": f"Customer shows {urgency} urgency patterns",
                "source": "classification_ai"
            })
        
        return sorted(recommendations, key=lambda x: {"critical": 4, "high": 3, "medium": 2, "low": 1}[x["priority"]], reverse=True)
    
    def _generate_intelligence_summary(self, analytics: Dict, classification: Dict, success_patterns: Dict) -> Dict[str, Any]:
        """Generate executive summary of customer intelligence"""
        
        summary = {
            "overall_score": 0,
            "key_insights": [],
            "success_likelihood": 0,
            "attention_level": "normal"
        }
        
        # Calculate overall customer score
        score_components = []
        
        # Satisfaction component
        satisfaction = analytics.get("customer_info", {}).get("satisfaction_score", 0.5)
        score_components.append(satisfaction * 100)
        summary["key_insights"].append(f"Satisfaction: {satisfaction:.1%}")
        
        # Engagement component  
        engagement_level = classification.get("engagement_level", {}).get("level", "medium")
        engagement_score = {"high": 90, "medium": 60, "low": 30}.get(engagement_level, 60)
        score_components.append(engagement_score)
        summary["key_insights"].append(f"Engagement: {engagement_level}")
        
        # Risk component (inverted - lower risk = higher score)
        risk_level = classification.get("risk_assessment", {}).get("risk_level", "medium")
        risk_score = {"low": 90, "medium": 60, "high": 20}.get(risk_level, 60)
        score_components.append(risk_score)
        summary["key_insights"].append(f"Churn risk: {risk_level}")
        
        # Calculate overall score
        if score_components:
            summary["overall_score"] = sum(score_components) / len(score_components)
        
        # Success likelihood from patterns
        if success_patterns.get("confidence", 0) > 0:
            summary["success_likelihood"] = success_patterns["confidence"]
            summary["key_insights"].append(f"Success likelihood: {success_patterns['confidence']:.1%}")
        
        # Determine attention level
        if summary["overall_score"] < 40 or risk_level == "high":
            summary["attention_level"] = "high"
        elif summary["overall_score"] > 80 and engagement_level == "high":
            summary["attention_level"] = "vip"
        elif summary["overall_score"] < 60:
            summary["attention_level"] = "moderate"
        
        return summary
    
    async def get_contextual_support_guidance(self, customer_id: int, current_query: str, db_session) -> Dict[str, Any]:
        """Get contextual support guidance combining customer intelligence with relevant docs"""
        
        cache_key = f"support_guidance:{customer_id}:{hash(current_query)}"
        cached_guidance = await self.cache.redis.get(cache_key)
        if cached_guidance:
            return cached_guidance
        
        try:
            # Get customer profile and relevant documents in parallel
            profile_task = self.get_comprehensive_customer_profile(customer_id, db_session)
            
            # Get customer context for document search
            customer = await self.customer.get_customer_by_session(f"customer_{customer_id}", db_session)
            customer_context = {}
            if customer:
                customer_context = {
                    "relationship_stage": customer.relationship_stage,
                    "communication_style": customer.communication_style,
                    "urgency_level": customer.urgency_level
                }
            
            docs_task = self.rag.get_contextual_documents(customer_context, current_query, db_session)
            
            profile, relevant_docs = await asyncio.gather(profile_task, docs_task)
            
            guidance = {
                "customer_profile": profile,
                "relevant_documents": relevant_docs,
                "contextual_recommendations": self._generate_contextual_recommendations(
                    profile, relevant_docs, current_query
                ),
                "response_template": self._generate_response_template(profile, current_query),
                "generated_at": datetime.utcnow().isoformat()
            }
            
            # Cache for 10 minutes
            await self.cache.redis.set(cache_key, guidance, 600)
            
            return guidance
            
        except Exception as e:
            print(f"Contextual guidance generation failed: {e}")
            return {"error": str(e)}
    
    def _generate_contextual_recommendations(self, profile: Dict, docs: List, query: str) -> List[Dict[str, Any]]:
        """Generate specific recommendations for the current context"""
        
        recommendations = []
        
        # Communication style adaptation
        comm_style = profile.get("classification", {}).get("communication_style", {}).get("primary_style")
        
        if comm_style == "technical":
            recommendations.append({
                "type": "communication_approach",
                "recommendation": "Use technical language and provide detailed explanations",
                "example": "Include API endpoints, configuration details, and technical specifications"
            })
        elif comm_style == "casual":
            recommendations.append({
                "type": "communication_approach", 
                "recommendation": "Use friendly, conversational tone",
                "example": "Hey there! Let me help you sort this out..."
            })
        elif comm_style == "formal":
            recommendations.append({
                "type": "communication_approach",
                "recommendation": "Maintain professional, structured responses",
                "example": "Thank you for contacting support. I'll be happy to assist you with..."
            })
        
        # Document utilization
        if docs:
            most_relevant = docs[0]
            recommendations.append({
                "type": "knowledge_utilization",
                "recommendation": f"Reference '{most_relevant['title']}' for authoritative information",
                "relevance_score": most_relevant.get("relevance_score", 0)
            })
        
        # Success pattern application
        patterns = profile.get("graph_insights", {}).get("success_patterns", {}).get("patterns", [])
        if patterns:
            best_pattern = patterns[0]
            recommendations.append({
                "type": "resolution_strategy",
                "recommendation": f"Apply {best_pattern.get('strategy', 'proven')} approach based on similar customer successes",
                "success_rate": best_pattern.get("confidence", 0)
            })
        
        # Risk mitigation
        risk_level = profile.get("classification", {}).get("risk_assessment", {}).get("risk_level")
        if risk_level == "high":
            recommendations.append({
                "type": "escalation",
                "recommendation": "Consider proactive escalation to prevent churn",
                "urgency": "high"
            })
        
        return recommendations
    
    def _generate_response_template(self, profile: Dict, query: str) -> Dict[str, str]:
        """Generate response template based on customer profile"""
        
        # Get customer characteristics
        comm_style = profile.get("classification", {}).get("communication_style", {}).get("primary_style", "neutral")
        relationship_stage = profile.get("customer_analytics", {}).get("customer_info", {}).get("relationship_stage", "returning")
        
        templates = {
            "greeting": self._get_greeting_template(comm_style, relationship_stage),
            "acknowledgment": self._get_acknowledgment_template(comm_style),
            "closing": self._get_closing_template(comm_style, relationship_stage)
        }
        
        return templates
    
    def _get_greeting_template(self, comm_style: str, relationship_stage: str) -> str:
        """Generate appropriate greeting"""
        
        if relationship_stage == "new":
            base = "Welcome! I'm here to help with your question."
        elif relationship_stage == "vip":
            base = "Thank you for being a valued customer. I'm here to assist you."
        else:
            base = "Thanks for reaching out. I'm here to help."
        
        if comm_style == "formal":
            return f"Good day. {base}"
        elif comm_style == "casual":
            return f"Hi there! {base}"
        elif comm_style == "technical":
            return f"Hello. {base} I can provide technical details as needed."
        else:
            return base
    
    def _get_acknowledgment_template(self, comm_style: str) -> str:
        """Generate appropriate acknowledgment"""
        
        if comm_style == "emotional":
            return "I understand this can be frustrating. Let me help resolve this for you."
        elif comm_style == "technical":
            return "I'll provide you with the technical details you need to resolve this."
        elif comm_style == "formal":
            return "I acknowledge your inquiry and will provide a comprehensive solution."
        else:
            return "I understand your concern and I'm here to help."
    
    def _get_closing_template(self, comm_style: str, relationship_stage: str) -> str:
        """Generate appropriate closing"""
        
        if relationship_stage == "vip":
            base = "Is there anything else I can help you with today? Your satisfaction is our priority."
        else:
            base = "Is there anything else I can help you with?"
        
        if comm_style == "formal":
            return f"{base} Please don't hesitate to contact us if you need further assistance."
        elif comm_style == "casual":
            return f"{base} Feel free to reach out anytime!"
        else:
            return base
    
    async def get_real_time_insights(self, customer_id: int, db_session) -> Dict[str, Any]:
        """Get real-time customer insights for live chat support"""
        
        try:
            # Get the most critical insights quickly
            tasks = [
                self.classification.classify_customer_comprehensive(customer_id, db_session),
                self.graph.find_similar_customers(customer_id, limit=3)
            ]
            
            classification, similar_customers = await asyncio.gather(*tasks, return_exceptions=True)
            
            if isinstance(classification, Exception):
                classification = {}
            if isinstance(similar_customers, Exception):
                similar_customers = []
            
            # Extract key real-time insights
            insights = {
                "alerts": [],
                "quick_facts": [],
                "suggested_actions": []
            }
            
            # Risk alerts
            risk_level = classification.get("risk_assessment", {}).get("risk_level")
            if risk_level == "high":
                insights["alerts"].append({
                    "type": "churn_risk",
                    "message": "⚠️ High churn risk customer",
                    "priority": "critical"
                })
            
            # Communication style
            comm_style = classification.get("communication_style", {}).get("primary_style")
            if comm_style:
                insights["quick_facts"].append(f"Communication: {comm_style}")
            
            # Similar customers
            if similar_customers:
                insights["quick_facts"].append(f"Similar to {len(similar_customers)} other customers")
            
            # Urgency level
            urgency = classification.get("urgency_pattern", {}).get("urgency_level")
            if urgency in ["high", "critical"]:
                insights["alerts"].append({
                    "type": "urgency",
                    "message": f"🔥 {urgency.title()} urgency detected",
                    "priority": "high"
                })
            
            # Suggested actions
            if comm_style == "technical":
                insights["suggested_actions"].append("Provide technical details and documentation")
            
            if risk_level == "high":
                insights["suggested_actions"].append("Consider manager escalation")
            
            return insights
            
        except Exception as e:
            print(f"Real-time insights failed: {e}")
            return {"alerts": [], "quick_facts": [], "suggested_actions": []}


# Global service instance
intelligence_service = CustomerIntelligenceService()