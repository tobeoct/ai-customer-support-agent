from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, JSON, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class Customer(Base):
    __tablename__ = "customers"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(255), unique=True, index=True, nullable=False)
    name = Column(String(255))
    email = Column(String(255))
    phone = Column(String(50))
    
    # Classification fields
    relationship_stage = Column(String(50))  # new, returning, vip, churned
    communication_style = Column(String(50))  # formal, casual, technical, emotional
    urgency_level = Column(String(20))  # low, medium, high, critical
    satisfaction_score = Column(Float)  # 0.0 to 1.0
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_interaction = Column(DateTime(timezone=True))
    
    # Relationships
    conversations = relationship("Conversation", back_populates="customer")
    interactions = relationship("Interaction", back_populates="customer")


class Conversation(Base):
    __tablename__ = "conversations"
    
    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    session_id = Column(String(255), index=True)
    
    # Conversation metadata
    topic = Column(String(255))
    status = Column(String(50))  # active, resolved, escalated, abandoned
    priority = Column(String(20))  # low, medium, high, urgent
    
    # Summary and outcomes
    summary = Column(Text)
    resolution = Column(Text)
    satisfaction_rating = Column(Integer)  # 1-5 scale
    
    # Timestamps
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    ended_at = Column(DateTime(timezone=True))
    
    # Relationships
    customer = relationship("Customer", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation")


class Message(Base):
    __tablename__ = "messages"
    
    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False)
    
    # Message content
    content = Column(Text, nullable=False)
    message_type = Column(String(20))  # user, assistant, system
    
    # Context and metadata
    intent = Column(String(100))  # question, complaint, compliment, request
    sentiment = Column(String(20))  # positive, negative, neutral
    confidence_score = Column(Float)  # AI confidence in response
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    conversation = relationship("Conversation", back_populates="messages")


class Interaction(Base):
    __tablename__ = "interactions"
    
    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    
    # Interaction details
    interaction_type = Column(String(50))  # chat, email, phone, escalation
    channel = Column(String(50))  # web, mobile, api
    outcome = Column(String(100))  # resolved, escalated, pending, abandoned
    
    # Performance metrics
    response_time_seconds = Column(Float)
    resolution_time_seconds = Column(Float)
    agent_interventions = Column(Integer, default=0)
    
    # Context
    context_data = Column(JSON)  # Store additional context as JSON
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    customer = relationship("Customer", back_populates="interactions")


class Document(Base):
    __tablename__ = "documents"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Document metadata
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    document_type = Column(String(50))  # faq, policy, procedure, product_info
    category = Column(String(100))  # billing, support, technical, sales
    
    # Search and retrieval
    keywords = Column(Text)  # Comma-separated keywords
    embedding_vector = Column(Text)  # Serialized vector for similarity search
    
    # Status and versioning
    is_active = Column(Boolean, default=True)
    version = Column(String(20), default="1.0")
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class ConversationMemory(Base):
    __tablename__ = "conversation_memory"
    
    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    
    # Memory content
    memory_type = Column(String(50))  # preference, issue, context, note
    content = Column(Text, nullable=False)
    importance = Column(Float, default=0.5)  # 0.0 to 1.0
    
    # Context
    source_conversation_id = Column(Integer, ForeignKey("conversations.id"))
    tags = Column(String(255))  # Comma-separated tags
    
    # Lifecycle
    is_active = Column(Boolean, default=True)
    expires_at = Column(DateTime(timezone=True))  # Optional expiration
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())