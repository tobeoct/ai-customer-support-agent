from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import re

from app.models.database import Customer, Message, Conversation, Interaction
from app.services.cache import cache_service


class ClassificationService:
    """Customer and conversation classification with ML-ready foundation"""
    
    def __init__(self):
        self.cache = cache_service
    
    async def classify_customer_comprehensive(self, customer_id: int, db: Session) -> Dict[str, Any]:
        """Comprehensive customer classification with caching"""
        
        # Check cache first
        cache_key = f"customer_classification:{customer_id}"
        cached_classification = await self.cache.redis.get(cache_key)
        if cached_classification:
            return cached_classification
        
        customer = db.query(Customer).filter(Customer.id == customer_id).first()
        if not customer:
            return {}
        
        # Get customer's conversation and interaction history
        conversations = db.query(Conversation).filter(
            Conversation.customer_id == customer_id
        ).all()
        
        messages = db.query(Message).join(Conversation).filter(
            Conversation.customer_id == customer_id
        ).all()
        
        interactions = db.query(Interaction).filter(
            Interaction.customer_id == customer_id
        ).all()
        
        # Perform comprehensive classification
        classification = {
            "customer_id": customer_id,
            "relationship_stage": self._classify_relationship_stage(customer, conversations, interactions),
            "communication_style": self._classify_communication_style(messages),
            "urgency_pattern": self._analyze_urgency_patterns(messages, conversations),
            "satisfaction_trend": self._analyze_satisfaction_trend(conversations, messages),
            "engagement_level": self._classify_engagement_level(interactions, messages),
            "support_complexity": self._analyze_support_complexity(conversations, messages),
            "behavioral_insights": self._extract_behavioral_insights(customer, messages, conversations),
            "risk_assessment": self._assess_customer_risk(customer, conversations, interactions),
            "classified_at": datetime.utcnow().isoformat()
        }
        
        # Cache classification for 1 hour
        await self.cache.redis.set(cache_key, classification, 3600)
        
        return classification
    
    def _classify_relationship_stage(self, customer: Customer, conversations: List[Conversation], 
                                   interactions: List[Interaction]) -> Dict[str, Any]:
        """Classify customer relationship stage"""
        days_since_signup = (datetime.utcnow() - customer.created_at).days
        total_conversations = len(conversations)
        total_interactions = len(interactions)
        
        # Calculate engagement metrics
        avg_response_time = sum(i.response_time_seconds or 0 for i in interactions) / len(interactions) if interactions else 0
        resolution_rate = sum(1 for c in conversations if c.status == "resolved") / len(conversations) if conversations else 0
        
        stage_score = {
            "new": 0,
            "returning": 0,
            "vip": 0,
            "at_risk": 0
        }
        
        # New customer indicators
        if days_since_signup <= 7:
            stage_score["new"] += 3
        if total_conversations <= 2:
            stage_score["new"] += 2
        
        # Returning customer indicators
        if 7 < days_since_signup <= 90 and total_conversations > 2:
            stage_score["returning"] += 3
        if resolution_rate > 0.8:
            stage_score["returning"] += 2
        
        # VIP customer indicators
        if total_conversations > 10:
            stage_score["vip"] += 3
        if days_since_signup > 90:
            stage_score["vip"] += 2
        if avg_response_time < 30:  # Fast response times indicate priority
            stage_score["vip"] += 2
        
        # At-risk indicators
        recent_conversations = [c for c in conversations if 
                              c.started_at and (datetime.utcnow() - c.started_at).days <= 30]
        recent_escalations = sum(1 for c in recent_conversations if c.status == "escalated")
        
        if recent_escalations > 1:
            stage_score["at_risk"] += 3
        if resolution_rate < 0.5:
            stage_score["at_risk"] += 2
        
        # Determine primary stage
        primary_stage = max(stage_score.items(), key=lambda x: x[1])[0]
        
        return {
            "primary_stage": primary_stage,
            "confidence_scores": stage_score,
            "metrics": {
                "days_since_signup": days_since_signup,
                "total_conversations": total_conversations,
                "resolution_rate": resolution_rate,
                "avg_response_time": avg_response_time
            }
        }
    
    def _classify_communication_style(self, messages: List[Message]) -> Dict[str, Any]:
        """Analyze communication style from message patterns"""
        if not messages:
            return {"primary_style": "unknown", "confidence": 0}
        
        user_messages = [msg for msg in messages if msg.message_type == "user"]
        if not user_messages:
            return {"primary_style": "unknown", "confidence": 0}
        
        # Combine all user text
        user_text = " ".join([msg.content.lower() for msg in user_messages])
        
        style_indicators = {
            "formal": {
                "patterns": [r'\b(please|thank you|regards|sincerely|appreciate|kindly)\b',
                           r'\b(sir|madam|mr\.|mrs\.|ms\.)\b'],
                "score": 0
            },
            "casual": {
                "patterns": [r'\b(hey|hi|thanks|cool|awesome|great|nice)\b',
                           r'[!]{2,}', r'[?]{2,}'],
                "score": 0
            },
            "technical": {
                "patterns": [r'\b(api|endpoint|configuration|error|code|bug|integration)\b',
                           r'\b(database|server|client|authentication|token)\b'],
                "score": 0
            },
            "emotional": {
                "patterns": [r'\b(frustrated|angry|disappointed|upset|love|hate)\b',
                           r'\b(wonderful|terrible|amazing|awful|fantastic)\b'],
                "score": 0
            }
        }
        
        # Score each style
        for style, data in style_indicators.items():
            for pattern in data["patterns"]:
                matches = re.findall(pattern, user_text)
                data["score"] += len(matches)
        
        # Normalize scores
        total_words = len(user_text.split())
        for style in style_indicators:
            if total_words > 0:
                style_indicators[style]["normalized_score"] = style_indicators[style]["score"] / total_words
        
        # Determine primary style
        primary_style = max(style_indicators.items(), 
                          key=lambda x: x[1]["normalized_score"])[0]
        
        return {
            "primary_style": primary_style,
            "style_scores": {k: v["normalized_score"] for k, v in style_indicators.items()},
            "confidence": style_indicators[primary_style]["normalized_score"],
            "message_count": len(user_messages)
        }
    
    def _analyze_urgency_patterns(self, messages: List[Message], conversations: List[Conversation]) -> Dict[str, Any]:
        """Analyze customer urgency patterns"""
        urgency_indicators = {
            "critical_keywords": ["urgent", "emergency", "critical", "asap", "immediately"],
            "high_keywords": ["soon", "quickly", "important", "priority", "needed"],
            "time_indicators": ["today", "now", "right away", "can't wait"]
        }
        
        user_messages = [msg for msg in messages if msg.message_type == "user"]
        all_text = " ".join([msg.content.lower() for msg in user_messages])
        
        urgency_score = 0
        urgency_reasons = []
        
        # Keyword analysis
        for level, keywords in urgency_indicators.items():
            for keyword in keywords:
                if keyword in all_text:
                    if level == "critical_keywords":
                        urgency_score += 3
                    elif level == "high_keywords":
                        urgency_score += 2
                    else:
                        urgency_score += 1
                    urgency_reasons.append(f"{level}: {keyword}")
        
        # Conversation frequency analysis
        recent_conversations = [c for c in conversations if 
                              c.started_at and (datetime.utcnow() - c.started_at).days <= 7]
        
        if len(recent_conversations) > 3:
            urgency_score += 2
            urgency_reasons.append("high_frequency_conversations")
        
        # Message density analysis
        if len(user_messages) > 10:
            urgency_score += 1
            urgency_reasons.append("high_message_volume")
        
        # Determine urgency level
        if urgency_score >= 8:
            urgency_level = "critical"
        elif urgency_score >= 5:
            urgency_level = "high"
        elif urgency_score >= 2:
            urgency_level = "medium"
        else:
            urgency_level = "low"
        
        return {
            "urgency_level": urgency_level,
            "urgency_score": urgency_score,
            "indicators": urgency_reasons,
            "recent_conversations": len(recent_conversations)
        }
    
    def _analyze_satisfaction_trend(self, conversations: List[Conversation], messages: List[Message]) -> Dict[str, Any]:
        """Analyze customer satisfaction trends"""
        # Get conversations with ratings
        rated_conversations = [c for c in conversations if c.satisfaction_rating is not None]
        
        if not rated_conversations:
            return {"trend": "unknown", "confidence": 0}
        
        # Sort by date
        rated_conversations.sort(key=lambda x: x.started_at or datetime.min)
        
        ratings = [c.satisfaction_rating for c in rated_conversations]
        avg_satisfaction = sum(ratings) / len(ratings)
        
        # Calculate trend
        if len(ratings) >= 3:
            recent_avg = sum(ratings[-3:]) / 3
            older_avg = sum(ratings[:-3]) / len(ratings[:-3]) if len(ratings) > 3 else avg_satisfaction
            
            if recent_avg > older_avg + 0.5:
                trend = "improving"
            elif recent_avg < older_avg - 0.5:
                trend = "declining"
            else:
                trend = "stable"
        else:
            trend = "insufficient_data"
        
        # Analyze sentiment from messages
        positive_sentiments = sum(1 for msg in messages if msg.sentiment == "positive")
        negative_sentiments = sum(1 for msg in messages if msg.sentiment == "negative")
        total_sentiments = positive_sentiments + negative_sentiments
        
        sentiment_ratio = positive_sentiments / total_sentiments if total_sentiments > 0 else 0.5
        
        return {
            "trend": trend,
            "average_rating": avg_satisfaction,
            "latest_rating": ratings[-1] if ratings else None,
            "sentiment_ratio": sentiment_ratio,
            "total_ratings": len(ratings),
            "confidence": min(len(ratings) / 5.0, 1.0)  # More ratings = higher confidence
        }
    
    def _classify_engagement_level(self, interactions: List[Interaction], messages: List[Message]) -> Dict[str, Any]:
        """Classify customer engagement level"""
        if not interactions and not messages:
            return {"level": "low", "score": 0}
        
        engagement_score = 0
        
        # Interaction frequency
        recent_interactions = [i for i in interactions if 
                             i.created_at and (datetime.utcnow() - i.created_at).days <= 30]
        
        engagement_score += min(len(recent_interactions) * 2, 10)
        
        # Message engagement
        user_messages = [msg for msg in messages if msg.message_type == "user"]
        avg_message_length = sum(len(msg.content) for msg in user_messages) / len(user_messages) if user_messages else 0
        
        if avg_message_length > 100:
            engagement_score += 3
        elif avg_message_length > 50:
            engagement_score += 2
        else:
            engagement_score += 1
        
        # Response patterns
        if len(user_messages) > 5:
            engagement_score += 2
        
        # Determine engagement level
        if engagement_score >= 12:
            level = "high"
        elif engagement_score >= 6:
            level = "medium"
        else:
            level = "low"
        
        return {
            "level": level,
            "score": engagement_score,
            "recent_interactions": len(recent_interactions),
            "avg_message_length": avg_message_length
        }
    
    def _analyze_support_complexity(self, conversations: List[Conversation], messages: List[Message]) -> Dict[str, Any]:
        """Analyze the complexity of support needs"""
        complexity_indicators = {
            "escalated_conversations": sum(1 for c in conversations if c.status == "escalated"),
            "total_conversations": len(conversations),
            "avg_messages_per_conversation": 0,
            "technical_keywords": 0,
            "multiple_topics": len(set(c.topic for c in conversations if c.topic))
        }
        
        if conversations:
            total_messages = len(messages)
            complexity_indicators["avg_messages_per_conversation"] = total_messages / len(conversations)
        
        # Count technical keywords
        technical_terms = ["api", "integration", "configuration", "error", "bug", "database", 
                          "authentication", "ssl", "server", "client", "endpoint"]
        
        all_text = " ".join([msg.content.lower() for msg in messages])
        complexity_indicators["technical_keywords"] = sum(1 for term in technical_terms if term in all_text)
        
        # Calculate complexity score
        complexity_score = 0
        
        escalation_rate = complexity_indicators["escalated_conversations"] / max(complexity_indicators["total_conversations"], 1)
        if escalation_rate > 0.3:
            complexity_score += 3
        elif escalation_rate > 0.1:
            complexity_score += 2
        
        if complexity_indicators["avg_messages_per_conversation"] > 10:
            complexity_score += 2
        elif complexity_indicators["avg_messages_per_conversation"] > 5:
            complexity_score += 1
        
        if complexity_indicators["technical_keywords"] > 5:
            complexity_score += 2
        elif complexity_indicators["technical_keywords"] > 2:
            complexity_score += 1
        
        if complexity_indicators["multiple_topics"] > 3:
            complexity_score += 1
        
        # Determine complexity level
        if complexity_score >= 6:
            complexity_level = "high"
        elif complexity_score >= 3:
            complexity_level = "medium"
        else:
            complexity_level = "low"
        
        return {
            "complexity_level": complexity_level,
            "complexity_score": complexity_score,
            "indicators": complexity_indicators
        }
    
    def _extract_behavioral_insights(self, customer: Customer, messages: List[Message], 
                                   conversations: List[Conversation]) -> Dict[str, Any]:
        """Extract behavioral insights for personalization"""
        insights = {
            "preferred_communication_times": self._analyze_communication_timing(messages),
            "common_topics": self._extract_common_topics(conversations),
            "response_expectations": self._analyze_response_patterns(messages),
            "escalation_triggers": self._identify_escalation_triggers(conversations, messages)
        }
        
        return insights
    
    def _analyze_communication_timing(self, messages: List[Message]) -> Dict[str, Any]:
        """Analyze when customer prefers to communicate"""
        if not messages:
            return {}
        
        hour_counts = {}
        day_counts = {}
        
        for msg in messages:
            if msg.created_at and msg.message_type == "user":
                hour = msg.created_at.hour
                day = msg.created_at.strftime("%A")
                
                hour_counts[hour] = hour_counts.get(hour, 0) + 1
                day_counts[day] = day_counts.get(day, 0) + 1
        
        preferred_hours = sorted(hour_counts.items(), key=lambda x: x[1], reverse=True)[:3]
        preferred_days = sorted(day_counts.items(), key=lambda x: x[1], reverse=True)[:3]
        
        return {
            "preferred_hours": [{"hour": h, "count": c} for h, c in preferred_hours],
            "preferred_days": [{"day": d, "count": c} for d, c in preferred_days]
        }
    
    def _extract_common_topics(self, conversations: List[Conversation]) -> List[Dict[str, Any]]:
        """Extract most common conversation topics"""
        topic_counts = {}
        
        for conv in conversations:
            if conv.topic:
                topic_counts[conv.topic] = topic_counts.get(conv.topic, 0) + 1
        
        return [{"topic": topic, "count": count} 
                for topic, count in sorted(topic_counts.items(), key=lambda x: x[1], reverse=True)[:5]]
    
    def _analyze_response_patterns(self, messages: List[Message]) -> Dict[str, Any]:
        """Analyze customer response patterns"""
        user_messages = [msg for msg in messages if msg.message_type == "user"]
        
        if len(user_messages) < 2:
            return {}
        
        # Calculate average response time (simplified)
        total_length = sum(len(msg.content) for msg in user_messages)
        avg_length = total_length / len(user_messages)
        
        # Analyze message patterns
        quick_responses = sum(1 for msg in user_messages if len(msg.content) < 50)
        detailed_responses = sum(1 for msg in user_messages if len(msg.content) > 200)
        
        return {
            "avg_message_length": avg_length,
            "quick_response_ratio": quick_responses / len(user_messages),
            "detailed_response_ratio": detailed_responses / len(user_messages),
            "total_messages": len(user_messages)
        }
    
    def _identify_escalation_triggers(self, conversations: List[Conversation], messages: List[Message]) -> List[str]:
        """Identify what typically triggers escalations"""
        escalated_conversations = [c for c in conversations if c.status == "escalated"]
        
        if not escalated_conversations:
            return []
        
        triggers = []
        
        # Analyze topics that lead to escalation
        escalated_topics = [c.topic for c in escalated_conversations if c.topic]
        topic_counts = {}
        for topic in escalated_topics:
            topic_counts[topic] = topic_counts.get(topic, 0) + 1
        
        common_escalation_topics = [topic for topic, count in topic_counts.items() if count > 1]
        triggers.extend([f"topic:{topic}" for topic in common_escalation_topics])
        
        # Look for keywords in escalated conversations
        escalated_conv_ids = [c.id for c in escalated_conversations]
        escalated_messages = [msg for msg in messages if msg.conversation_id in escalated_conv_ids]
        
        escalation_keywords = ["frustrated", "angry", "unacceptable", "manager", "supervisor", "cancel"]
        escalated_text = " ".join([msg.content.lower() for msg in escalated_messages])
        
        for keyword in escalation_keywords:
            if keyword in escalated_text:
                triggers.append(f"keyword:{keyword}")
        
        return triggers[:5]  # Return top 5 triggers
    
    def _assess_customer_risk(self, customer: Customer, conversations: List[Conversation], 
                            interactions: List[Interaction]) -> Dict[str, Any]:
        """Assess customer churn/satisfaction risk"""
        risk_score = 0
        risk_factors = []
        
        # Recent escalations
        recent_escalations = sum(1 for c in conversations if 
                               c.status == "escalated" and 
                               c.started_at and (datetime.utcnow() - c.started_at).days <= 30)
        
        if recent_escalations > 0:
            risk_score += recent_escalations * 3
            risk_factors.append(f"recent_escalations:{recent_escalations}")
        
        # Low satisfaction ratings
        recent_ratings = [c.satisfaction_rating for c in conversations if 
                         c.satisfaction_rating is not None and
                         c.started_at and (datetime.utcnow() - c.started_at).days <= 30]
        
        if recent_ratings:
            avg_recent_rating = sum(recent_ratings) / len(recent_ratings)
            if avg_recent_rating < 3:
                risk_score += (3 - avg_recent_rating) * 2
                risk_factors.append(f"low_satisfaction:{avg_recent_rating:.1f}")
        
        # Inactive periods
        if customer.last_interaction:
            days_inactive = (datetime.utcnow() - customer.last_interaction).days
            if days_inactive > 30:
                risk_score += 2
                risk_factors.append(f"inactive_days:{days_inactive}")
        
        # Determine risk level
        if risk_score >= 8:
            risk_level = "high"
        elif risk_score >= 4:
            risk_level = "medium"
        else:
            risk_level = "low"
        
        return {
            "risk_level": risk_level,
            "risk_score": risk_score,
            "risk_factors": risk_factors,
            "recommendations": self._get_risk_mitigation_recommendations(risk_level, risk_factors)
        }
    
    def _get_risk_mitigation_recommendations(self, risk_level: str, risk_factors: List[str]) -> List[str]:
        """Get recommendations for risk mitigation"""
        recommendations = []
        
        if risk_level == "high":
            recommendations.extend([
                "immediate_manager_escalation",
                "priority_support_assignment",
                "proactive_outreach_required"
            ])
        elif risk_level == "medium":
            recommendations.extend([
                "enhanced_monitoring",
                "satisfaction_survey",
                "account_review"
            ])
        
        # Specific recommendations based on risk factors
        for factor in risk_factors:
            if "escalations" in factor:
                recommendations.append("improve_first_contact_resolution")
            elif "satisfaction" in factor:
                recommendations.append("satisfaction_recovery_program")
            elif "inactive" in factor:
                recommendations.append("re_engagement_campaign")
        
        return list(set(recommendations))  # Remove duplicates
    
    async def invalidate_classification_cache(self, customer_id: int):
        """Invalidate classification cache when customer data changes"""
        cache_key = f"customer_classification:{customer_id}"
        await self.cache.redis.delete(cache_key)


# Global service instance
classification_service = ClassificationService()