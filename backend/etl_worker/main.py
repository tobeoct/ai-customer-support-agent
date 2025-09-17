#!/usr/bin/env python3
"""
ETL Worker - Background Data Processing Service

This runs as a separate process to handle:
- Data synchronization between PostgreSQL and Neo4j
- Knowledge base document processing
- Scheduled data pipeline operations
"""

import asyncio
import logging
import signal
import sys
from pathlib import Path

# Add parent directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.etl import etl_service
from app.core.config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ETLWorker:
    """Background ETL processing worker"""
    
    def __init__(self):
        self.running = False
        self.tasks = []
    
    async def start(self):
        """Start the ETL worker"""
        logger.info("🚀 Starting ETL Worker...")
        self.running = True
        
        # Schedule background tasks
        self.tasks = [
            asyncio.create_task(self._knowledge_base_sync_loop()),
            asyncio.create_task(self._incremental_sync_loop()),
        ]
        
        # Wait for all tasks
        try:
            await asyncio.gather(*self.tasks)
        except asyncio.CancelledError:
            logger.info("📋 ETL Worker tasks cancelled")
    
    async def stop(self):
        """Stop the ETL worker gracefully"""
        logger.info("🛑 Stopping ETL Worker...")
        self.running = False
        
        # Cancel all tasks
        for task in self.tasks:
            task.cancel()
        
        # Wait for tasks to complete cancellation
        await asyncio.gather(*self.tasks, return_exceptions=True)
        logger.info("✅ ETL Worker stopped")
    
    async def _knowledge_base_sync_loop(self):
        """Background loop for knowledge base synchronization"""
        logger.info("📚 Starting knowledge base sync loop...")
        
        # Initial sync
        try:
            result = await etl_service.sync_knowledge_base()
            if result.get("synced_documents", 0) > 0:
                logger.info(f"✅ Initial knowledge sync: {result['synced_documents']} documents")
        except Exception as e:
            logger.error(f"❌ Initial knowledge sync failed: {e}")
        
        # Periodic sync every 30 minutes
        while self.running:
            try:
                await asyncio.sleep(30 * 60)  # 30 minutes
                
                if not self.running:
                    break
                
                logger.info("🔄 Running scheduled knowledge base sync...")
                result = await etl_service.sync_knowledge_base()
                
                if "error" in result:
                    logger.warning(f"⚠️ Knowledge sync issue: {result['error']}")
                else:
                    logger.info(f"✅ Knowledge sync: {result.get('synced_documents', 0)} documents")
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ Knowledge sync loop error: {e}")
                await asyncio.sleep(60)  # Wait 1 minute before retry
    
    async def _incremental_sync_loop(self):
        """Background loop for incremental data synchronization"""
        logger.info("📊 Starting incremental sync loop...")
        
        # Wait a bit before starting incremental syncs
        await asyncio.sleep(60)
        
        # Incremental sync every 10 minutes
        while self.running:
            try:
                await asyncio.sleep(10 * 60)  # 10 minutes
                
                if not self.running:
                    break
                
                logger.info("🔄 Running incremental data sync...")
                result = await etl_service.incremental_sync()
                
                if "error" in result:
                    logger.warning(f"⚠️ Incremental sync issue: {result['error']}")
                else:
                    customers = result.get('customers_synced', 0)
                    conversations = result.get('conversations_synced', 0)
                    if customers > 0 or conversations > 0:
                        logger.info(f"✅ Incremental sync: {customers} customers, {conversations} conversations")
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ Incremental sync loop error: {e}")
                await asyncio.sleep(60)  # Wait 1 minute before retry

# Global worker instance
worker = ETLWorker()

async def main():
    """Main entry point for ETL worker"""
    
    def signal_handler(signum, frame):
        """Handle shutdown signals"""
        logger.info(f"📋 Received signal {signum}, initiating shutdown...")
        asyncio.create_task(worker.stop())
    
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        await worker.start()
    except KeyboardInterrupt:
        logger.info("📋 Keyboard interrupt received")
    finally:
        await worker.stop()

if __name__ == "__main__":
    logger.info("🎯 ETL Worker starting...")
    asyncio.run(main())