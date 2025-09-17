"""
Simple Workflow Tools - Basic logging and utilities
No complex monitoring, just essential functionality
"""

import logging
from datetime import datetime
from typing import Dict, Any

logger = logging.getLogger(__name__)

class SimpleWorkflowLogger:
    """Simple logging for workflow execution"""
    
    def __init__(self):
        self.execution_count = 0
        self.start_time = datetime.now()
        logger.info("Simple workflow logger initialized")
    
    def log_execution(self, result: Dict[str, Any]):
        """Log workflow execution with basic info"""
        self.execution_count += 1
        
        success = result.get("success", False)
        execution_time = result.get("execution_time", 0)
        
        if success:
            logger.info(f"✅ Workflow #{self.execution_count} completed in {execution_time:.2f}s")
        else:
            logger.error(f"❌ Workflow #{self.execution_count} failed: {result.get('error', 'Unknown error')}")
    
    def get_simple_stats(self) -> Dict[str, Any]:
        """Get basic execution statistics"""
        uptime = (datetime.now() - self.start_time).total_seconds()
        
        return {
            "total_executions": self.execution_count,
            "uptime_seconds": uptime,
            "average_per_minute": (self.execution_count / uptime) * 60 if uptime > 0 else 0,
            "status": "operational"
        }

# Global logger instance
workflow_logger = SimpleWorkflowLogger()

def log_workflow_execution(result: Dict[str, Any]):
    """Helper function to log workflow execution"""
    workflow_logger.log_execution(result)

def get_workflow_stats() -> Dict[str, Any]:
    """Helper function to get workflow statistics"""
    return workflow_logger.get_simple_stats()