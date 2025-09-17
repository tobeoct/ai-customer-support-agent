from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_
from datetime import datetime, timedelta

from app.models.database import Customer, Conversation, Message
from app.models.schemas import CustomerCreate, CustomerUpdate, Customer as CustomerSchema
from app.services.cache import cache_service
from app.core.database import get_db


class CustomerService:
    """Customer management with Redis caching for performance"""
    
    def __init__(self):
        self.cache = cache_service
    
    async def get_customer_by_session(self, session_id: str, db: Session) -> Optional[Customer]:
        """Get customer by session with cache-aside pattern"""
        # Try cache first (10-50x faster than DB)
        cached_customer = await self.cache.get_cached_customer_session(session_id)
        if cached_customer:
            # Convert cached dict back to Customer object
            customer = Customer(**cached_customer)
            return customer
        
        # Cache miss - get from database
        customer = db.query(Customer).filter(Customer.session_id == session_id).first()
        if customer:
            # Cache for future requests
            customer_dict = {
                "id": customer.id,
                "session_id": customer.session_id,
                "name": customer.name,
                "email": customer.email,
                "phone": customer.phone,
                "relationship_stage": customer.relationship_stage,
                "communication_style": customer.communication_style,
                "urgency_level": customer.urgency_level,
                "satisfaction_score": customer.satisfaction_score,
                "created_at": customer.created_at.isoformat() if customer.created_at else None,
                "updated_at": customer.updated_at.isoformat() if customer.updated_at else None,
                "last_interaction": customer.last_interaction.isoformat() if customer.last_interaction else None
            }
            await self.cache.cache_customer_session(session_id, customer_dict)
        
        return customer
    
    async def create_customer(self, customer_data: CustomerCreate, db: Session) -> Customer:
        """Create new customer and cache immediately"""
        # Create in database
        customer = Customer(**customer_data.dict())
        customer.created_at = datetime.utcnow()
        db.add(customer)
        db.commit()
        db.refresh(customer)
        
        # Cache immediately for future requests
        customer_dict = {
            "id": customer.id,
            "session_id": customer.session_id,
            "name": customer.name,
            "email": customer.email,
            "phone": customer.phone,
            "relationship_stage": customer.relationship_stage,
            "communication_style": customer.communication_style,
            "urgency_level": customer.urgency_level,
            "satisfaction_score": customer.satisfaction_score,
            "created_at": customer.created_at.isoformat(),
            "updated_at": None,
            "last_interaction": None
        }
        await self.cache.cache_customer_session(customer.session_id, customer_dict)
        
        return customer
    
    async def update_customer(self, customer_id: int, updates: CustomerUpdate, db: Session) -> Optional[Customer]:
        """Update customer and invalidate cache"""
        customer = db.query(Customer).filter(Customer.id == customer_id).first()
        if not customer:
            return None
        
        # Update fields
        for field, value in updates.dict(exclude_unset=True).items():
            setattr(customer, field, value)
        
        customer.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(customer)
        
        # Invalidate cache to force refresh on next request
        await self.cache.invalidate_customer_session(customer.session_id)
        
        return customer
    
    async def classify_customer(self, customer_id: int, conversation_history: List[Message], db: Session) -> Dict[str, Any]:
        """Classify customer based on behavior patterns"""
        customer = db.query(Customer).filter(Customer.id == customer_id).first()
        if not customer:
            return {}
        
        # Simple classification logic (can be enhanced with ML)
        classification = {
            "relationship_stage": self._determine_relationship_stage(customer, db),
            "communication_style": self._analyze_communication_style(conversation_history),
            "urgency_level": self._assess_urgency(conversation_history),
            "satisfaction_score": self._calculate_satisfaction(conversation_history)
        }
        
        # Update customer with new classification
        for field, value in classification.items():
            setattr(customer, field, value)
        
        customer.updated_at = datetime.utcnow()
        db.commit()
        
        # Invalidate cache since customer data changed
        await self.cache.invalidate_customer_session(customer.session_id)
        
        return classification
    
    def _determine_relationship_stage(self, customer: Customer, db: Session) -> str:
        """Determine customer relationship stage"""
        conversation_count = db.query(Conversation).filter(
            Conversation.customer_id == customer.id
        ).count()
        
        days_since_created = (datetime.utcnow() - customer.created_at).days
        
        if conversation_count == 1 and days_since_created < 7:
            return "new"
        elif conversation_count > 10 or days_since_created > 90:
            return "vip"
        elif days_since_created > 30:
            return "returning"
        else:
            return "new"
    
    def _analyze_communication_style(self, messages: List[Message]) -> str:
        """Analyze communication style from messages"""
        if not messages:
            return "neutral"
        
        # Simple keyword-based analysis
        formal_keywords = ["please", "thank you", "regards", "sincerely"]
        technical_keywords = ["api", "integration", "configuration", "error"]
        casual_keywords = ["hey", "thanks", "cool", "awesome"]
        
        text = " ".join([msg.content.lower() for msg in messages if msg.message_type == "user"])
        
        formal_score = sum(1 for keyword in formal_keywords if keyword in text)
        technical_score = sum(1 for keyword in technical_keywords if keyword in text)
        casual_score = sum(1 for keyword in casual_keywords if keyword in text)
        
        if technical_score > formal_score and technical_score > casual_score:
            return "technical"
        elif formal_score > casual_score:
            return "formal"
        elif casual_score > 0:
            return "casual"
        else:
            return "neutral"
    
    def _assess_urgency(self, messages: List[Message]) -> str:
        """Assess urgency level from conversation"""
        if not messages:
            return "low"
        
        urgent_keywords = ["urgent", "asap", "immediately", "critical", "emergency"]
        high_keywords = ["soon", "quickly", "important", "priority"]
        
        text = " ".join([msg.content.lower() for msg in messages])
        
        if any(keyword in text for keyword in urgent_keywords):
            return "critical"
        elif any(keyword in text for keyword in high_keywords):
            return "high"
        elif len(messages) > 5:  # Many messages might indicate urgency
            return "medium"
        else:
            return "low"
    
    def _calculate_satisfaction(self, messages: List[Message]) -> float:
        """Calculate satisfaction score from sentiment"""
        if not messages:
            return 0.5
        
        positive_count = sum(1 for msg in messages if msg.sentiment == "positive")
        negative_count = sum(1 for msg in messages if msg.sentiment == "negative")
        total_count = len(messages)
        
        if total_count == 0:
            return 0.5
        
        # Simple satisfaction calculation
        satisfaction = (positive_count - negative_count + total_count) / (2 * total_count)
        return max(0.0, min(1.0, satisfaction))
    
    async def get_customer_analytics(self, customer_id: int, db: Session) -> Dict[str, Any]:
        """Get customer analytics and insights"""
        customer = db.query(Customer).filter(Customer.id == customer_id).first()
        if not customer:
            return {}
        
        # Get conversation statistics
        conversations = db.query(Conversation).filter(
            Conversation.customer_id == customer_id
        ).all()
        
        messages = db.query(Message).join(Conversation).filter(
            Conversation.customer_id == customer_id
        ).all()
        
        analytics = {
            "customer_info": {
                "id": customer.id,
                "session_id": customer.session_id,
                "relationship_stage": customer.relationship_stage,
                "communication_style": customer.communication_style,
                "satisfaction_score": customer.satisfaction_score
            },
            "engagement_stats": {
                "total_conversations": len(conversations),
                "total_messages": len(messages),
                "avg_messages_per_conversation": len(messages) / len(conversations) if conversations else 0,
                "last_interaction": customer.last_interaction
            },
            "conversation_outcomes": {
                "resolved": sum(1 for c in conversations if c.status == "resolved"),
                "active": sum(1 for c in conversations if c.status == "active"),
                "escalated": sum(1 for c in conversations if c.status == "escalated")
            }
        }
        
        return analytics


# Global service instance
customer_service = CustomerService()