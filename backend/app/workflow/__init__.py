"""
Simple LangGraph Workflow Module for Memory-Enhanced Customer Support Agent

Simple 6-Node Workflow:
1. Load Customer - Get customer profile and session info
2. Classify Customer - Analyze communication style and risk level
3. Get Context - Retrieve relevant documents and customer history
4. Analyze Query - Simple sentiment and urgency analysis
5. Generate Response - AI-powered response using OpenAI (with fallback)
6. Finalize - Personalize based on customer profile

Features:
- Simple logging instead of complex monitoring
- Basic async workflow execution
- Customer intelligence integration
- Fallback responses when AI unavailable
"""

from .agent import simple_agent, SimpleCustomerSupportAgent
from .tools import workflow_logger, log_workflow_execution, get_workflow_stats

__all__ = [
    "simple_agent",
    "SimpleCustomerSupportAgent", 
    "workflow_logger",
    "log_workflow_execution",
    "get_workflow_stats"
]