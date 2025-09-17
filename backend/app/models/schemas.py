from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class MessageType(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class InteractionType(str, Enum):
    CHAT = "chat"
    EMAIL = "email"
    PHONE = "phone"
    ESCALATION = "escalation"


class RelationshipStage(str, Enum):
    NEW = "new"
    RETURNING = "returning"
    VIP = "vip"
    CHURNED = "churned"


class CommunicationStyle(str, Enum):
    FORMAL = "formal"
    CASUAL = "casual"
    TECHNICAL = "technical"
    EMOTIONAL = "emotional"
    NEUTRAL = "neutral"


class UrgencyLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ConversationStatus(str, Enum):
    ACTIVE = "active"
    RESOLVED = "resolved"
    ESCALATED = "escalated"
    CLOSED = "closed"


class Priority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class DocumentType(str, Enum):
    FAQ = "faq"
    POLICY = "policy"
    TUTORIAL = "tutorial"
    TROUBLESHOOTING = "troubleshooting"
    PRODUCT_INFO = "product_info"


class DocumentCategory(str, Enum):
    BILLING = "billing"
    TECHNICAL = "technical"
    GENERAL = "general"
    ONBOARDING = "onboarding"
    SUPPORT = "support"


class MemoryType(str, Enum):
    PREFERENCE = "preference"
    INTERACTION = "interaction"
    ISSUE = "issue"
    CONTEXT = "context"
    FEEDBACK = "feedback"


class SentimentType(str, Enum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    FRUSTRATED = "frustrated"
    SATISFIED = "satisfied"


class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


# Base schemas
class CustomerBase(BaseModel):
    session_id: str
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    relationship_stage: Optional[RelationshipStage] = RelationshipStage.NEW
    communication_style: Optional[CommunicationStyle] = CommunicationStyle.NEUTRAL
    urgency_level: Optional[UrgencyLevel] = UrgencyLevel.MEDIUM
    satisfaction_score: Optional[float] = Field(None, ge=0.0, le=5.0)


class CustomerCreate(CustomerBase):
    pass


class CustomerUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    relationship_stage: Optional[RelationshipStage] = None
    communication_style: Optional[CommunicationStyle] = None
    urgency_level: Optional[UrgencyLevel] = None
    satisfaction_score: Optional[float] = Field(None, ge=0.0, le=5.0)


class Customer(CustomerBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    last_interaction: Optional[datetime] = None
    
    class Config:
        from_attributes = True


# Message schemas
class MessageBase(BaseModel):
    content: str
    message_type: MessageType = MessageType.USER
    intent: Optional[str] = None
    sentiment: Optional[SentimentType] = None
    confidence_score: Optional[float] = Field(None, ge=0.0, le=1.0)


class MessageCreate(MessageBase):
    conversation_id: int


class Message(MessageBase):
    id: int
    conversation_id: int
    created_at: datetime
    
    class Config:
        from_attributes = True


# Conversation schemas
class ConversationBase(BaseModel):
    topic: Optional[str] = None
    status: ConversationStatus = ConversationStatus.ACTIVE
    priority: Priority = Priority.MEDIUM


class ConversationCreate(ConversationBase):
    customer_id: int
    session_id: str


class Conversation(ConversationBase):
    id: int
    customer_id: int
    session_id: str
    summary: Optional[str] = None
    resolution: Optional[str] = None
    satisfaction_rating: Optional[int] = None
    started_at: datetime
    ended_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


# Chat request/response schemas
class ChatRequest(BaseModel):
    session_id: str
    message: str
    customer_context: Optional[Dict[str, Any]] = None


class ChatResponse(BaseModel):
    response: str
    customer_id: Optional[int] = None
    conversation_id: Optional[int] = None
    confidence_score: Optional[float] = None
    suggested_actions: Optional[List[str]] = None
    escalation_needed: Optional[bool] = False


# Document schemas
class DocumentBase(BaseModel):
    title: str
    content: str
    document_type: DocumentType
    category: DocumentCategory
    keywords: Optional[str] = None


class DocumentCreate(DocumentBase):
    pass


class Document(DocumentBase):
    id: int
    is_active: bool = True
    version: str = "1.0"
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


# Memory schemas
class MemoryBase(BaseModel):
    memory_type: MemoryType
    content: str
    importance: float = Field(ge=0.0, le=1.0, default=0.5)
    tags: Optional[str] = None


class MemoryCreate(MemoryBase):
    customer_id: int
    source_conversation_id: Optional[int] = None


class Memory(MemoryBase):
    id: int
    customer_id: int
    source_conversation_id: Optional[int] = None
    is_active: bool = True
    expires_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


# Health check schema
class HealthCheck(BaseModel):
    status: HealthStatus
    message: str
    database: HealthStatus
    neo4j: HealthStatus
    redis: HealthStatus
    openai: HealthStatus