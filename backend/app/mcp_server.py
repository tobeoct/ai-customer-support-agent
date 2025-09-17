"""
FastMCP Server for AI Customer Support Agent

This server exposes admin operations and chat functionality as MCP tools 
for agent-based management using the FastMCP framework.
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path
import sys

# Add parent directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

from fastmcp import FastMCP
from app.mcp_tools.admin_tools import (
    CustomerManagementTools, AnalyticsTools, SystemTools, 
    DocumentTools, RLTools
)
from app.workflow.agent import SimpleWorkflowAgent

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("customer-support-mcp")

# Initialize FastMCP server
mcp = FastMCP("Customer Support AI")

# Initialize workflow agent for chat functionality
workflow_agent = SimpleWorkflowAgent()

# Customer Management Tools
@mcp.tool()
async def create_customer(name: str, session_id: str, email: str = None) -> Dict[str, Any]:
    """
    Create a new customer in the system
    
    Args:
        name: Customer's full name
        session_id: Unique session identifier
        email: Customer's email address (optional)
    
    Returns:
        Customer creation result with ID and session info
    """
    return await CustomerManagementTools.create_customer(name, session_id, email)

@mcp.tool()
async def get_customer_profile(session_id: str) -> Dict[str, Any]:
    """
    Get comprehensive customer profile with intelligence insights
    
    Args:
        session_id: Customer session ID
    
    Returns:
        Complete customer profile with analytics and history
    """
    return await CustomerManagementTools.get_customer_profile(session_id)

@mcp.tool()
async def find_similar_customers(customer_id: int, limit: int = 5) -> Dict[str, Any]:
    """
    Find customers similar to the given customer using graph intelligence
    
    Args:
        customer_id: ID of the reference customer
        limit: Maximum number of similar customers to return
    
    Returns:
        List of similar customers with similarity scores
    """
    return await CustomerManagementTools.find_similar_customers(customer_id, limit)

# Analytics Tools
@mcp.tool()
async def get_escalation_patterns(days: int = 7) -> Dict[str, Any]:
    """
    Analyze escalation patterns over specified period
    
    Args:
        days: Number of days to analyze (default: 7)
    
    Returns:
        Escalation pattern analysis and trends
    """
    return await AnalyticsTools.get_escalation_patterns(days)

@mcp.tool()
async def get_customer_insights(customer_id: int) -> Dict[str, Any]:
    """
    Get detailed insights for a specific customer
    
    Args:
        customer_id: Customer ID to analyze
    
    Returns:
        Detailed customer insights and recommendations
    """
    return await AnalyticsTools.get_customer_insights(customer_id)

# System Management Tools
@mcp.tool()
async def get_etl_status() -> Dict[str, Any]:
    """
    Get ETL pipeline status and statistics
    
    Returns:
        ETL system status, last sync times, and health metrics
    """
    return await SystemTools.get_etl_status()

@mcp.tool()
async def sync_knowledge_base() -> Dict[str, Any]:
    """
    Manually trigger knowledge base synchronization
    
    Returns:
        Knowledge base sync results and statistics
    """
    return await SystemTools.sync_knowledge_base()

@mcp.tool()
async def get_knowledge_base_status() -> Dict[str, Any]:
    """
    Get knowledge base sync status and statistics
    
    Returns:
        Knowledge base status, document counts, and recommendations
    """
    return await SystemTools.get_knowledge_base_status()

@mcp.tool()
async def run_full_system_sync() -> Dict[str, Any]:
    """
    Run complete system sync (customers, conversations, knowledge base)
    
    Returns:
        Full system sync results for all components
    """
    return await SystemTools.run_full_system_sync()

@mcp.tool()
async def get_cache_statistics() -> Dict[str, Any]:
    """
    Get Redis cache performance statistics
    
    Returns:
        Cache performance metrics and usage statistics
    """
    return await SystemTools.get_cache_statistics()

@mcp.tool()
async def get_workflow_health() -> Dict[str, Any]:
    """
    Get workflow system health and performance metrics
    
    Returns:
        Workflow health status and performance data
    """
    return await SystemTools.get_workflow_health()

# Document Management Tools
@mcp.tool()
async def search_documents(
    query: str, 
    limit: int = 10, 
    category: Optional[str] = None
) -> Dict[str, Any]:
    """
    Search knowledge base documents using RAG
    
    Args:
        query: Search query text
        limit: Maximum number of results (default: 10)
        category: Optional category filter
    
    Returns:
        Relevant documents with similarity scores
    """
    return await DocumentTools.search_documents(query, limit, category)

# Reinforcement Learning Tools
@mcp.tool()
async def get_rl_metrics() -> Dict[str, Any]:
    """
    Get Reinforcement Learning system performance metrics
    
    Returns:
        RL system metrics, learning progress, and performance data
    """
    return await RLTools.get_rl_metrics()

@mcp.tool()
async def provide_rl_feedback(
    session_id: str,
    satisfaction_score: float,
    reward_type: str = "satisfaction"
) -> Dict[str, Any]:
    """
    Provide feedback to the RL system for learning
    
    Args:
        session_id: Session identifier
        satisfaction_score: Score from 0.0 to 1.0
        reward_type: Type of reward (satisfaction, response_time, etc.)
    
    Returns:
        Feedback processing result
    """
    return await RLTools.provide_rl_feedback(session_id, satisfaction_score, reward_type)

# Chat Functionality - Main Customer Interface
@mcp.tool()
async def chat_with_customer(
    message: str,
    session_id: str,
    customer_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    Send a message to the AI customer support agent
    
    Args:
        message: Customer's message or query
        session_id: Unique session identifier
        customer_name: Customer's name (optional, for new sessions)
    
    Returns:
        AI agent response with conversation context
    """
    try:
        # Process message through the 6-node workflow
        response = await workflow_agent.process_message(
            user_query=message,
            session_id=session_id,
            customer_name=customer_name
        )
        
        return {
            "success": True,
            "response": response.get("response", "I'm here to help!"),
            "session_id": session_id,
            "conversation_id": response.get("conversation_id"),
            "customer_id": response.get("customer_id"),
            "timestamp": response.get("timestamp"),
            "metadata": {
                "message_type": response.get("message_type"),
                "urgency": response.get("urgency"),
                "sentiment": response.get("sentiment"),
                "rl_action": response.get("rl_action"),
                "context_used": response.get("context_used", False)
            }
        }
        
    except Exception as e:
        logger.error(f"Chat processing error: {e}")
        return {
            "success": False,
            "error": str(e),
            "response": "I apologize, but I'm experiencing technical difficulties. Please try again.",
            "session_id": session_id
        }

@mcp.tool()
async def get_conversation_history(session_id: str, limit: int = 10) -> Dict[str, Any]:
    """
    Get conversation history for a session
    
    Args:
        session_id: Session identifier
        limit: Maximum number of messages to return
    
    Returns:
        Conversation history with messages and metadata
    """
    try:
        # This would typically fetch from database
        # For now, return a placeholder structure
        return {
            "success": True,
            "session_id": session_id,
            "messages": [],
            "total_messages": 0,
            "session_started": None,
            "last_activity": None
        }
        
    except Exception as e:
        logger.error(f"Conversation history error: {e}")
        return {
            "success": False,
            "error": str(e),
            "session_id": session_id
        }

# System Health and Status
@mcp.tool()
async def get_system_health() -> Dict[str, Any]:
    """
    Get comprehensive system health status
    
    Returns:
        Complete system health including all components
    """
    try:
        # Gather health from all components
        etl_status = await SystemTools.get_etl_status()
        cache_stats = await SystemTools.get_cache_statistics()
        workflow_health = await SystemTools.get_workflow_health()
        kb_status = await SystemTools.get_knowledge_base_status()
        rl_metrics = await RLTools.get_rl_metrics()
        
        return {
            "success": True,
            "overall_status": "healthy",
            "components": {
                "etl_pipeline": etl_status.get("etl_status", {}),
                "cache_system": cache_stats.get("cache_statistics", {}),
                "workflow_engine": workflow_health.get("workflow_health", {}),
                "knowledge_base": kb_status.get("knowledge_base_status", {}),
                "rl_system": rl_metrics.get("rl_metrics", {})
            },
            "checked_at": etl_status.get("checked_at")
        }
        
    except Exception as e:
        logger.error(f"System health check error: {e}")
        return {
            "success": False,
            "error": str(e),
            "overall_status": "unhealthy"
        }

if __name__ == "__main__":
    logger.info("🚀 Starting FastMCP Customer Support Server...")
    logger.info("Available tools:")
    
    # List available tools
    tools = [
        "create_customer", "get_customer_profile", "find_similar_customers",
        "get_escalation_patterns", "get_customer_insights",
        "get_etl_status", "sync_knowledge_base", "get_knowledge_base_status", 
        "run_full_system_sync", "get_cache_statistics", "get_workflow_health",
        "search_documents", "get_rl_metrics", "provide_rl_feedback",
        "chat_with_customer", "get_conversation_history", "get_system_health"
    ]
    
    for tool in tools:
        logger.info(f"  📋 {tool}")
    
    logger.info("✅ MCP Server ready for agent connections")
    
    # Run the MCP server
    mcp.run()