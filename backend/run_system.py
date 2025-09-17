#!/usr/bin/env python3
"""
System Runner - Manages API Server and ETL Worker

This script runs both the FastAPI server and ETL worker as separate processes
for proper production deployment.
"""

import asyncio
import subprocess
import signal
import sys
import logging
import os
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class SystemManager:
    """Manages API server, ETL worker, and MCP server processes"""
    
    def __init__(self):
        self.api_process = None
        self.etl_process = None
        self.mcp_process = None
        self.running = False
    
    async def start(self):
        """Start both API server and ETL worker"""
        logger.info("🚀 Starting Customer Support System...")
        self.running = True
        
        try:
            # Start API server
            logger.info("📡 Starting API Server...")
            self.api_process = subprocess.Popen([
                sys.executable, "-m", "uvicorn", 
                "app.main:app", 
                "--host", "0.0.0.0", 
                "--port", "8000",
                "--reload"
            ])
            
            # Wait a moment for API to start
            await asyncio.sleep(2)
            
            # Start ETL worker
            logger.info("⚙️ Starting ETL Worker...")
            self.etl_process = subprocess.Popen([
                sys.executable, "etl_worker/main.py"
            ])
            
            # Wait a moment for ETL to start
            await asyncio.sleep(1)
            
            # Start MCP server
            logger.info("🤖 Starting MCP Server...")
            self.mcp_process = subprocess.Popen([
                sys.executable, "app/mcp_server.py"
            ])
            
            logger.info("✅ System started successfully!")
            logger.info("   📡 API Server: http://localhost:8000")
            logger.info("   ⚙️ ETL Worker: Background processing active")
            logger.info("   🤖 MCP Server: Agent tools available via FastMCP")
            logger.info("   📊 Health Check: http://localhost:8000/health")
            logger.info("   💬 Chat via MCP: Use 'chat_with_customer' tool")
            
            # Monitor processes
            await self._monitor_processes()
            
        except Exception as e:
            logger.error(f"❌ System startup failed: {e}")
            await self.stop()
    
    async def stop(self):
        """Stop both processes gracefully"""
        logger.info("🛑 Stopping Customer Support System...")
        self.running = False
        
        # Stop MCP server first
        if self.mcp_process:
            logger.info("🤖 Stopping MCP Server...")
            self.mcp_process.terminate()
            try:
                self.mcp_process.wait(timeout=10)
                logger.info("✅ MCP Server stopped")
            except subprocess.TimeoutExpired:
                logger.warning("⚠️ MCP Server force killed")
                self.mcp_process.kill()
        
        # Stop ETL worker
        if self.etl_process:
            logger.info("⚙️ Stopping ETL Worker...")
            self.etl_process.terminate()
            try:
                self.etl_process.wait(timeout=10)
                logger.info("✅ ETL Worker stopped")
            except subprocess.TimeoutExpired:
                logger.warning("⚠️ ETL Worker force killed")
                self.etl_process.kill()
        
        # Stop API server last
        if self.api_process:
            logger.info("📡 Stopping API Server...")
            self.api_process.terminate()
            try:
                self.api_process.wait(timeout=10)
                logger.info("✅ API Server stopped")
            except subprocess.TimeoutExpired:
                logger.warning("⚠️ API Server force killed")
                self.api_process.kill()
        
        logger.info("✅ System shutdown complete")
    
    async def _monitor_processes(self):
        """Monitor all processes and restart if needed"""
        while self.running:
            try:
                # Check API process
                if self.api_process.poll() is not None:
                    logger.error(f"❌ API Server crashed! Exit code: {self.api_process.returncode}")
                    self.running = False
                    break
                
                # Check ETL process
                if self.etl_process.poll() is not None:
                    logger.error(f"❌ ETL Worker crashed! Exit code: {self.etl_process.returncode}")
                    self.running = False
                    break
                
                # Check MCP process
                if self.mcp_process.poll() is not None:
                    logger.error(f"❌ MCP Server crashed! Exit code: {self.mcp_process.returncode}")
                    self.running = False
                    break
                
                await asyncio.sleep(5)  # Check every 5 seconds
                
            except Exception as e:
                logger.error(f"❌ Process monitoring error: {e}")
                break

# Global system manager
system_manager = SystemManager()

async def main():
    """Main entry point"""
    
    def signal_handler(signum, frame):
        """Handle shutdown signals"""
        logger.info(f"📋 Received signal {signum}, shutting down system...")
        asyncio.create_task(system_manager.stop())
    
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        await system_manager.start()
    except KeyboardInterrupt:
        logger.info("📋 Keyboard interrupt received")
    finally:
        await system_manager.stop()

if __name__ == "__main__":
    print("🎯 Customer Support System Manager")
    print("=" * 40)
    print("This will start:")
    print("  📡 FastAPI Server (port 8000)")
    print("  ⚙️ ETL Background Worker")
    print("  🤖 FastMCP Server (agent tools)")
    print("  📊 Health monitoring")
    print()
    print("Press Ctrl+C to stop all services")
    print("=" * 40)
    
    asyncio.run(main())