from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc, func
from datetime import datetime, timedelta

from app.models.database import Conversation, Message, ConversationMemory, Customer
from app.models.schemas import (
    ConversationCreate, MessageCreate, MemoryCreate,
    Conversation as ConversationSchema, Message as MessageSchema
)
from app.services.cache import cache_service


class MemoryService:
    """Conversation and episodic memory management with caching"""
    
    def __init__(self):
        self.cache = cache_service
    
    async def create_conversation(self, conversation_data: ConversationCreate, db: Session) -> Conversation:
        """Create new conversation"""
        conversation = Conversation(**conversation_data.dict())
        conversation.started_at = datetime.utcnow()
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
        
        # Update customer's last interaction
        customer = db.query(Customer).filter(Customer.id == conversation.customer_id).first()
        if customer:
            customer.last_interaction = datetime.utcnow()
            db.commit()
            # Invalidate customer cache
            await self.cache.invalidate_customer_session(customer.session_id)
        
        return conversation
    
    async def add_message(self, message_data: MessageCreate, db: Session) -> Message:
        """Add message to conversation"""
        message = Message(**message_data.dict())
        message.created_at = datetime.utcnow()
        db.add(message)
        db.commit()
        db.refresh(message)
        
        # Update conversation's last activity
        conversation = db.query(Conversation).filter(
            Conversation.id == message.conversation_id
        ).first()
        if conversation:
            # Update customer's last interaction
            customer = db.query(Customer).filter(Customer.id == conversation.customer_id).first()
            if customer:
                customer.last_interaction = datetime.utcnow()
                db.commit()
                # Invalidate customer cache
                await self.cache.invalidate_customer_session(customer.session_id)
        
        return message
    
    async def get_conversation_history(self, customer_id: int, limit: int = 50, db: Session = None) -> List[Dict[str, Any]]:
        """Get conversation history with intelligent caching"""
        # Create cache key based on customer and limit
        cache_key = f"conversation_history:{customer_id}:{limit}"
        
        # Try cache first (20-60x faster than DB query)
        cached_history = await self.cache.redis.get(cache_key)
        if cached_history:
            return cached_history
        
        # Cache miss - get from database
        conversations = db.query(Conversation).filter(
            Conversation.customer_id == customer_id
        ).order_by(desc(Conversation.started_at)).limit(limit).all()
        
        history = []
        for conv in conversations:
            messages = db.query(Message).filter(
                Message.conversation_id == conv.id
            ).order_by(Message.created_at).all()
            
            conv_data = {
                "conversation_id": conv.id,
                "topic": conv.topic,
                "status": conv.status,
                "started_at": conv.started_at.isoformat() if conv.started_at else None,
                "ended_at": conv.ended_at.isoformat() if conv.ended_at else None,
                "summary": conv.summary,
                "messages": [
                    {
                        "id": msg.id,
                        "content": msg.content,
                        "message_type": msg.message_type,
                        "intent": msg.intent,
                        "sentiment": msg.sentiment,
                        "created_at": msg.created_at.isoformat() if msg.created_at else None
                    }
                    for msg in messages
                ]
            }
            history.append(conv_data)
        
        # Cache for 30 minutes (conversations don't change frequently)
        await self.cache.redis.set(cache_key, history, 1800)
        
        return history
    
    async def get_recent_context(self, customer_id: int, max_messages: int = 10, db: Session = None) -> List[Message]:
        """Get recent conversation context for AI"""
        # Get most recent messages across all conversations
        messages = db.query(Message).join(Conversation).filter(
            Conversation.customer_id == customer_id
        ).order_by(desc(Message.created_at)).limit(max_messages).all()
        
        return list(reversed(messages))  # Return in chronological order
    
    async def create_memory(self, memory_data: MemoryCreate, db: Session) -> ConversationMemory:
        """Create episodic memory entry"""
        memory = ConversationMemory(**memory_data.dict())
        memory.created_at = datetime.utcnow()
        db.add(memory)
        db.commit()
        db.refresh(memory)
        
        # Invalidate customer cache since memory affects context
        customer = db.query(Customer).filter(Customer.id == memory.customer_id).first()
        if customer:
            await self.cache.invalidate_customer_session(customer.session_id)
        
        return memory
    
    async def get_customer_memories(self, customer_id: int, memory_type: Optional[str] = None, db: Session = None) -> List[ConversationMemory]:
        """Get customer's episodic memories"""
        query = db.query(ConversationMemory).filter(
            ConversationMemory.customer_id == customer_id,
            ConversationMemory.is_active == True
        )
        
        if memory_type:
            query = query.filter(ConversationMemory.memory_type == memory_type)
        
        # Order by importance and recency
        memories = query.order_by(
            desc(ConversationMemory.importance),
            desc(ConversationMemory.created_at)
        ).all()
        
        return memories
    
    async def summarize_conversation(self, conversation_id: int, db: Session) -> Optional[str]:
        """Generate conversation summary for memory"""
        conversation = db.query(Conversation).filter(
            Conversation.id == conversation_id
        ).first()
        
        if not conversation:
            return None
        
        messages = db.query(Message).filter(
            Message.conversation_id == conversation_id
        ).order_by(Message.created_at).all()
        
        if not messages:
            return "Empty conversation"
        
        # Simple extractive summary (can be enhanced with LLM)
        user_messages = [msg.content for msg in messages if msg.message_type == "user"]
        assistant_messages = [msg.content for msg in messages if msg.message_type == "assistant"]
        
        summary_parts = []
        
        if user_messages:
            summary_parts.append(f"Customer inquiry: {user_messages[0][:100]}...")
        
        if assistant_messages:
            summary_parts.append(f"Resolution approach: {assistant_messages[-1][:100]}...")
        
        summary_parts.append(f"Status: {conversation.status}")
        summary_parts.append(f"Messages exchanged: {len(messages)}")
        
        return " | ".join(summary_parts)
    
    async def end_conversation(self, conversation_id: int, resolution: str, rating: Optional[int], db: Session) -> Optional[Conversation]:
        """End conversation and create memory"""
        conversation = db.query(Conversation).filter(
            Conversation.id == conversation_id
        ).first()
        
        if not conversation:
            return None
        
        # Update conversation
        conversation.status = "resolved"
        conversation.ended_at = datetime.utcnow()
        conversation.resolution = resolution
        conversation.satisfaction_rating = rating
        
        # Generate summary
        conversation.summary = await self.summarize_conversation(conversation_id, db)
        
        db.commit()
        db.refresh(conversation)
        
        # Create memory entry for important conversations
        if rating and rating >= 4:  # High satisfaction
            memory_data = MemoryCreate(
                customer_id=conversation.customer_id,
                memory_type="positive_outcome",
                content=f"Successful resolution: {resolution[:200]}",
                importance=0.8,
                source_conversation_id=conversation_id,
                tags="success,resolution"
            )
            await self.create_memory(memory_data, db)
        elif rating and rating <= 2:  # Low satisfaction
            memory_data = MemoryCreate(
                customer_id=conversation.customer_id,
                memory_type="issue",
                content=f"Dissatisfaction with: {resolution[:200]}",
                importance=0.9,
                source_conversation_id=conversation_id,
                tags="dissatisfaction,issue"
            )
            await self.create_memory(memory_data, db)
        
        # Invalidate relevant caches
        customer = db.query(Customer).filter(Customer.id == conversation.customer_id).first()
        if customer:
            await self.cache.invalidate_customer_session(customer.session_id)
            # Clear conversation history cache
            cache_pattern = f"conversation_history:{conversation.customer_id}:*"
            await self.cache.redis.invalidate_pattern(cache_pattern)
        
        return conversation
    
    async def get_memory_insights(self, customer_id: int, db: Session) -> Dict[str, Any]:
        """Get memory-based insights for personalization"""
        memories = await self.get_customer_memories(customer_id, db=db)
        
        # Analyze memory patterns
        memory_types = {}
        common_tags = {}
        total_importance = 0
        
        for memory in memories:
            # Count memory types
            memory_types[memory.memory_type] = memory_types.get(memory.memory_type, 0) + 1
            
            # Extract tags
            if memory.tags:
                tags = memory.tags.split(',')
                for tag in tags:
                    tag = tag.strip()
                    common_tags[tag] = common_tags.get(tag, 0) + 1
            
            total_importance += memory.importance
        
        insights = {
            "total_memories": len(memories),
            "memory_types": memory_types,
            "common_themes": sorted(common_tags.items(), key=lambda x: x[1], reverse=True)[:5],
            "average_importance": total_importance / len(memories) if memories else 0,
            "key_memories": [
                {
                    "type": memory.memory_type,
                    "content": memory.content[:100] + "..." if len(memory.content) > 100 else memory.content,
                    "importance": memory.importance,
                    "created_at": memory.created_at.isoformat() if memory.created_at else None
                }
                for memory in sorted(memories, key=lambda m: m.importance, reverse=True)[:3]
            ]
        }
        
        return insights


# Global service instance
memory_service = MemoryService()