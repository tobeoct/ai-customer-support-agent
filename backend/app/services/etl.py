from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import asyncio
import logging
from pathlib import Path

from app.core.database import SessionLocal
from app.models.database import Customer, Conversation, Message, Interaction
from app.services.graph import graph_service
from app.services.cache import cache_service
from app.services.rag import rag_service

logger = logging.getLogger(__name__)


class ETLService:
    """ETL pipeline for syncing PostgreSQL data to Neo4j with intelligent batching"""
    
    def __init__(self):
        self.graph = graph_service
        self.cache = cache_service
    
    async def full_sync_customers(self, batch_size: int = 100) -> Dict[str, Any]:
        """Full sync of all customers from PostgreSQL to Neo4j"""
        
        db = SessionLocal()
        try:
            # Get total customer count
            total_customers = db.query(Customer).count()
            
            sync_stats = {
                "total_customers": total_customers,
                "synced_customers": 0,
                "failed_customers": 0,
                "batch_size": batch_size,
                "batches_processed": 0,
                "started_at": datetime.utcnow().isoformat()
            }
            
            print(f"🔄 Starting full customer sync: {total_customers} customers")
            
            # Process in batches for memory efficiency
            offset = 0
            while offset < total_customers:
                customers = db.query(Customer).offset(offset).limit(batch_size).all()
                
                if not customers:
                    break
                
                batch_results = await self._sync_customer_batch(customers, db)
                
                sync_stats["synced_customers"] += batch_results["synced"]
                sync_stats["failed_customers"] += batch_results["failed"]
                sync_stats["batches_processed"] += 1
                
                print(f"📊 Batch {sync_stats['batches_processed']}: {batch_results['synced']} synced, {batch_results['failed']} failed")
                
                offset += batch_size
                
                # Small delay to prevent overwhelming Neo4j
                await asyncio.sleep(0.1)
            
            sync_stats["completed_at"] = datetime.utcnow().isoformat()
            sync_stats["success_rate"] = sync_stats["synced_customers"] / total_customers if total_customers > 0 else 0
            
            print(f"✅ Customer sync completed: {sync_stats['synced_customers']}/{total_customers} customers synced")
            
            return sync_stats
            
        except Exception as e:
            print(f"❌ Full customer sync failed: {e}")
            return {"error": str(e), "synced_customers": 0}
        
        finally:
            db.close()
    
    async def _sync_customer_batch(self, customers: List[Customer], db: Session) -> Dict[str, int]:
        """Sync a batch of customers to Neo4j"""
        
        synced = 0
        failed = 0
        
        for customer in customers:
            try:
                customer_data = {
                    "id": customer.id,
                    "name": customer.name,
                    "email": customer.email,
                    "communication_style": customer.communication_style,
                    "relationship_stage": customer.relationship_stage,
                    "satisfaction_score": customer.satisfaction_score,
                    "created_at": customer.created_at.isoformat() if customer.created_at else None
                }
                
                success = await self.graph.sync_customer_to_graph(customer_data)
                
                if success:
                    synced += 1
                else:
                    failed += 1
                    
            except Exception as e:
                print(f"Failed to sync customer {customer.id}: {e}")
                failed += 1
        
        return {"synced": synced, "failed": failed}
    
    async def full_sync_conversations(self, batch_size: int = 50) -> Dict[str, Any]:
        """Full sync of conversations and messages from PostgreSQL to Neo4j"""
        
        db = SessionLocal()
        try:
            # Get conversations with messages
            total_conversations = db.query(Conversation).count()
            
            sync_stats = {
                "total_conversations": total_conversations,
                "synced_conversations": 0,
                "failed_conversations": 0,
                "synced_messages": 0,
                "batch_size": batch_size,
                "started_at": datetime.utcnow().isoformat()
            }
            
            print(f"🔄 Starting conversation sync: {total_conversations} conversations")
            
            offset = 0
            while offset < total_conversations:
                conversations = db.query(Conversation).offset(offset).limit(batch_size).all()
                
                if not conversations:
                    break
                
                for conv in conversations:
                    try:
                        # Get messages for this conversation
                        messages = db.query(Message).filter(
                            Message.conversation_id == conv.id
                        ).all()
                        
                        conv_data = {
                            "id": conv.id,
                            "customer_id": conv.customer_id,
                            "topic": conv.topic,
                            "status": conv.status,
                            "satisfaction_rating": conv.satisfaction_rating,
                            "resolution": conv.resolution,
                            "started_at": conv.started_at.isoformat() if conv.started_at else None
                        }
                        
                        message_data = [
                            {
                                "id": msg.id,
                                "content": msg.content,
                                "message_type": msg.message_type,
                                "intent": msg.intent,
                                "sentiment": msg.sentiment
                            }
                            for msg in messages
                        ]
                        
                        success = await self.graph.sync_conversation_to_graph(conv_data, message_data)
                        
                        if success:
                            sync_stats["synced_conversations"] += 1
                            sync_stats["synced_messages"] += len(messages)
                        else:
                            sync_stats["failed_conversations"] += 1
                            
                    except Exception as e:
                        print(f"Failed to sync conversation {conv.id}: {e}")
                        sync_stats["failed_conversations"] += 1
                
                offset += batch_size
                await asyncio.sleep(0.1)
            
            sync_stats["completed_at"] = datetime.utcnow().isoformat()
            print(f"✅ Conversation sync completed: {sync_stats['synced_conversations']}/{total_conversations} conversations synced")
            
            return sync_stats
            
        except Exception as e:
            print(f"❌ Conversation sync failed: {e}")
            return {"error": str(e), "synced_conversations": 0}
        
        finally:
            db.close()
    
    async def incremental_sync(self, since: datetime = None) -> Dict[str, Any]:
        """Incremental sync of recent changes"""
        
        if not since:
            since = datetime.utcnow() - timedelta(hours=1)  # Default: last hour
        
        db = SessionLocal()
        try:
            sync_stats = {
                "sync_type": "incremental",
                "since": since.isoformat(),
                "customers_synced": 0,
                "conversations_synced": 0,
                "started_at": datetime.utcnow().isoformat()
            }
            
            # Sync recently updated customers
            recent_customers = db.query(Customer).filter(
                Customer.updated_at >= since
            ).all()
            
            if recent_customers:
                print(f"🔄 Syncing {len(recent_customers)} updated customers")
                batch_result = await self._sync_customer_batch(recent_customers, db)
                sync_stats["customers_synced"] = batch_result["synced"]
            
            # Sync recent conversations
            recent_conversations = db.query(Conversation).filter(
                Conversation.started_at >= since
            ).all()
            
            if recent_conversations:
                print(f"🔄 Syncing {len(recent_conversations)} new conversations")
                
                for conv in recent_conversations:
                    try:
                        messages = db.query(Message).filter(
                            Message.conversation_id == conv.id
                        ).all()
                        
                        conv_data = {
                            "id": conv.id,
                            "customer_id": conv.customer_id,
                            "topic": conv.topic,
                            "status": conv.status,
                            "satisfaction_rating": conv.satisfaction_rating,
                            "resolution": conv.resolution,
                            "started_at": conv.started_at.isoformat() if conv.started_at else None
                        }
                        
                        message_data = [
                            {
                                "id": msg.id,
                                "content": msg.content,
                                "message_type": msg.message_type,
                                "intent": msg.intent,
                                "sentiment": msg.sentiment
                            }
                            for msg in messages
                        ]
                        
                        success = await self.graph.sync_conversation_to_graph(conv_data, message_data)
                        if success:
                            sync_stats["conversations_synced"] += 1
                            
                    except Exception as e:
                        print(f"Failed to sync conversation {conv.id}: {e}")
            
            sync_stats["completed_at"] = datetime.utcnow().isoformat()
            
            print(f"✅ Incremental sync completed: {sync_stats['customers_synced']} customers, {sync_stats['conversations_synced']} conversations")
            
            return sync_stats
            
        except Exception as e:
            print(f"❌ Incremental sync failed: {e}")
            return {"error": str(e)}
        
        finally:
            db.close()
    
    async def sync_customer_realtime(self, customer_id: int) -> bool:
        """Real-time sync of a single customer"""
        
        db = SessionLocal()
        try:
            customer = db.query(Customer).filter(Customer.id == customer_id).first()
            
            if not customer:
                return False
            
            customer_data = {
                "id": customer.id,
                "name": customer.name,
                "email": customer.email,
                "communication_style": customer.communication_style,
                "relationship_stage": customer.relationship_stage,
                "satisfaction_score": customer.satisfaction_score,
                "created_at": customer.created_at.isoformat() if customer.created_at else None
            }
            
            return await self.graph.sync_customer_to_graph(customer_data)
            
        except Exception as e:
            print(f"Real-time customer sync failed: {e}")
            return False
        
        finally:
            db.close()
    
    async def sync_conversation_realtime(self, conversation_id: int) -> bool:
        """Real-time sync of a single conversation with its messages"""
        
        db = SessionLocal()
        try:
            conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
            
            if not conversation:
                return False
            
            messages = db.query(Message).filter(
                Message.conversation_id == conversation_id
            ).all()
            
            conv_data = {
                "id": conversation.id,
                "customer_id": conversation.customer_id,
                "topic": conversation.topic,
                "status": conversation.status,
                "satisfaction_rating": conversation.satisfaction_rating,
                "resolution": conversation.resolution,
                "started_at": conversation.started_at.isoformat() if conversation.started_at else None
            }
            
            message_data = [
                {
                    "id": msg.id,
                    "content": msg.content,
                    "message_type": msg.message_type,
                    "intent": msg.intent,
                    "sentiment": msg.sentiment
                }
                for msg in messages
            ]
            
            return await self.graph.sync_conversation_to_graph(conv_data, message_data)
            
        except Exception as e:
            print(f"Real-time conversation sync failed: {e}")
            return False
        
        finally:
            db.close()
    
    async def validate_sync_integrity(self) -> Dict[str, Any]:
        """Validate data integrity between PostgreSQL and Neo4j"""
        
        db = SessionLocal()
        try:
            # Count records in PostgreSQL
            pg_counts = {
                "customers": db.query(Customer).count(),
                "conversations": db.query(Conversation).count(),
                "messages": db.query(Message).count()
            }
            
            # Get Neo4j analytics
            neo4j_analytics = await self.graph.get_graph_analytics()
            
            # Extract Neo4j counts
            neo4j_counts = {"customers": 0, "conversations": 0, "messages": 0}
            
            if "node_counts" in neo4j_analytics:
                for record in neo4j_analytics["node_counts"]:
                    label = record["label"][0] if record["label"] else ""
                    count = record["count"]
                    
                    if label == "Customer":
                        neo4j_counts["customers"] = count
                    elif label == "Conversation":
                        neo4j_counts["conversations"] = count
                    elif label == "Message":
                        neo4j_counts["messages"] = count
            
            # Calculate sync percentages
            integrity_report = {
                "postgresql_counts": pg_counts,
                "neo4j_counts": neo4j_counts,
                "sync_percentages": {},
                "recommendations": []
            }
            
            for entity in ["customers", "conversations", "messages"]:
                pg_count = pg_counts[entity]
                neo4j_count = neo4j_counts[entity]
                
                if pg_count > 0:
                    sync_percentage = (neo4j_count / pg_count) * 100
                    integrity_report["sync_percentages"][entity] = round(sync_percentage, 2)
                    
                    if sync_percentage < 95:
                        integrity_report["recommendations"].append(
                            f"Consider full sync for {entity} - only {sync_percentage:.1f}% synced"
                        )
                else:
                    integrity_report["sync_percentages"][entity] = 100.0
            
            return integrity_report
            
        except Exception as e:
            print(f"Sync validation failed: {e}")
            return {"error": str(e)}
        
        finally:
            db.close()
    
    async def get_sync_status(self) -> Dict[str, Any]:
        """Get overall sync status and health"""
        
        try:
            # Test connections
            db_connected = True
            neo4j_connected = self.graph.neo4j.test_connection() if self.graph.neo4j.driver else False
            
            # Get last sync timestamp from cache
            last_full_sync = await self.cache.redis.get("last_full_sync")
            last_incremental_sync = await self.cache.redis.get("last_incremental_sync")
            
            # Get integrity report
            integrity = await self.validate_sync_integrity()
            
            status = {
                "connections": {
                    "postgresql": db_connected,
                    "neo4j": neo4j_connected
                },
                "last_syncs": {
                    "full_sync": last_full_sync,
                    "incremental_sync": last_incremental_sync
                },
                "data_integrity": integrity,
                "recommendations": []
            }
            
            # Generate recommendations
            if not neo4j_connected:
                status["recommendations"].append("Neo4j connection failed - check service status")
            
            if not last_full_sync:
                status["recommendations"].append("No full sync recorded - consider running initial sync")
            elif integrity.get("sync_percentages", {}).get("customers", 0) < 90:
                status["recommendations"].append("Customer sync integrity below 90% - run full sync")
            
            return status
            
        except Exception as e:
            print(f"Sync status check failed: {e}")
            return {"error": str(e)}
    
    async def schedule_automatic_sync(self, interval_minutes: int = 60):
        """Schedule automatic incremental syncs"""
        
        print(f"📅 Scheduling automatic sync every {interval_minutes} minutes")
        
        while True:
            try:
                await asyncio.sleep(interval_minutes * 60)
                
                print("🔄 Running scheduled incremental sync")
                result = await self.incremental_sync()
                
                # Store sync timestamp
                await self.cache.redis.set("last_incremental_sync", datetime.utcnow().isoformat(), 86400)
                
                if "error" not in result:
                    print(f"✅ Scheduled sync completed: {result.get('customers_synced', 0)} customers, {result.get('conversations_synced', 0)} conversations")
                else:
                    print(f"❌ Scheduled sync failed: {result['error']}")
                    
            except Exception as e:
                print(f"❌ Scheduled sync error: {e}")
    
    async def sync_knowledge_base(self, documents_path: str = "data/documents") -> Dict[str, Any]:
        """Sync knowledge base documents to RAG system"""
        
        try:
            documents_dir = Path(documents_path)
            
            if not documents_dir.exists():
                logger.warning(f"Documents directory not found: {documents_path}")
                return {"error": "Documents directory not found", "synced_documents": 0}
            
            # Get all markdown files
            doc_files = list(documents_dir.glob("*.md"))
            
            if not doc_files:
                logger.warning(f"No documents found in: {documents_path}")
                return {"error": "No documents found", "synced_documents": 0}
            
            sync_stats = {
                "total_documents": len(doc_files),
                "synced_documents": 0,
                "failed_documents": 0,
                "total_chunks": 0,
                "started_at": datetime.utcnow().isoformat()
            }
            
            logger.info(f"📚 Starting knowledge base sync: {len(doc_files)} documents")
            
            for doc_file in doc_files:
                try:
                    logger.info(f"📖 Processing: {doc_file.name}")
                    
                    # Read document content
                    with open(doc_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # Determine category from filename
                    category = doc_file.stem.replace('_', ' ').title()
                    
                    # Process document through RAG service
                    chunks_processed = await self._process_document_for_rag(
                        content, category, doc_file.name
                    )
                    
                    sync_stats["synced_documents"] += 1
                    sync_stats["total_chunks"] += chunks_processed
                    
                    logger.info(f"✅ Processed {chunks_processed} chunks from {doc_file.name}")
                    
                except Exception as e:
                    logger.error(f"Failed to process document {doc_file.name}: {e}")
                    sync_stats["failed_documents"] += 1
            
            sync_stats["completed_at"] = datetime.utcnow().isoformat()
            
            # Store sync timestamp
            await self.cache.redis.set("last_knowledge_sync", datetime.utcnow().isoformat(), 86400)
            
            logger.info(f"✅ Knowledge base sync completed: {sync_stats['synced_documents']}/{sync_stats['total_documents']} documents, {sync_stats['total_chunks']} chunks")
            
            return sync_stats
            
        except Exception as e:
            logger.error(f"Knowledge base sync failed: {e}")
            return {"error": str(e), "synced_documents": 0}
    
    async def _process_document_for_rag(self, content: str, category: str, filename: str) -> int:
        """Process a document into chunks for RAG system"""
        
        try:
            # Split content into sections (chunk by headers)
            sections = []
            
            # Split by ## headers first
            major_sections = content.split('\n## ')
            if len(major_sections) == 1:
                # Fall back to # headers
                major_sections = content.split('\n# ')
            
            for i, section in enumerate(major_sections):
                section_content = section.strip()
                
                if len(section_content) < 50:  # Skip very short sections
                    continue
                
                # Further split long sections by ### headers
                subsections = section_content.split('\n### ')
                
                for j, subsection in enumerate(subsections):
                    subsection_content = subsection.strip()
                    
                    if len(subsection_content) < 30:
                        continue
                    
                    # Create chunk metadata
                    chunk_data = {
                        "content": subsection_content,
                        "category": category,
                        "source": filename,
                        "section_index": i,
                        "subsection_index": j,
                        "word_count": len(subsection_content.split()),
                        "char_count": len(subsection_content),
                        "created_at": datetime.utcnow().isoformat()
                    }
                    
                    sections.append(chunk_data)
            
            # Process chunks through RAG service
            # In production, this would:
            # 1. Generate embeddings for each chunk
            # 2. Store in vector database (Pinecone, Weaviate, etc.)
            # 3. Create searchable index
            # 4. Update document metadata
            
            logger.info(f"Created {len(sections)} chunks for {filename}")
            
            # Store document metadata
            doc_metadata = {
                "filename": filename,
                "category": category,
                "total_chunks": len(sections),
                "processed_at": datetime.utcnow().isoformat(),
                "status": "processed"
            }
            
            # Cache document info
            cache_key = f"knowledge_doc:{filename}"
            await self.cache.redis.set(cache_key, doc_metadata, 86400 * 7)  # 7 days
            
            return len(sections)
            
        except Exception as e:
            logger.error(f"Error processing document {filename}: {e}")
            return 0
    
    async def get_knowledge_base_status(self) -> Dict[str, Any]:
        """Get knowledge base sync status"""
        
        try:
            # Get last sync info
            last_knowledge_sync = await self.cache.redis.get("last_knowledge_sync")
            
            # Count processed documents from cache
            document_keys = await self.cache.redis.keys("knowledge_doc:*")
            total_docs = len(document_keys) if document_keys else 0
            
            total_chunks = 0
            document_info = []
            
            for key in document_keys or []:
                doc_data = await self.cache.redis.get(key)
                if doc_data and isinstance(doc_data, dict):
                    total_chunks += doc_data.get("total_chunks", 0)
                    document_info.append({
                        "filename": doc_data.get("filename"),
                        "category": doc_data.get("category"),
                        "chunks": doc_data.get("total_chunks", 0),
                        "processed_at": doc_data.get("processed_at")
                    })
            
            # Check if documents directory exists and count files
            documents_dir = Path("data/documents")
            available_docs = len(list(documents_dir.glob("*.md"))) if documents_dir.exists() else 0
            
            status = {
                "last_sync": last_knowledge_sync,
                "documents_available": available_docs,
                "documents_processed": total_docs,
                "total_chunks": total_chunks,
                "sync_percentage": (total_docs / max(1, available_docs)) * 100,
                "document_details": document_info,
                "recommendations": []
            }
            
            # Generate recommendations
            if not last_knowledge_sync:
                status["recommendations"].append("No knowledge base sync recorded - run initial sync")
            elif status["sync_percentage"] < 100:
                status["recommendations"].append(f"Only {status['sync_percentage']:.1f}% of documents synced - run knowledge base sync")
            elif available_docs == 0:
                status["recommendations"].append("No documents found in data/documents directory")
            
            return status
            
        except Exception as e:
            logger.error(f"Knowledge base status check failed: {e}")
            return {"error": str(e)}
    
    async def full_system_sync(self) -> Dict[str, Any]:
        """Complete system sync: customers, conversations, and knowledge base"""
        
        logger.info("🚀 Starting full system sync...")
        
        sync_results = {
            "started_at": datetime.utcnow().isoformat(),
            "customers": {},
            "conversations": {},
            "knowledge_base": {},
            "overall_success": True
        }
        
        try:
            # 1. Sync customers
            logger.info("📊 Syncing customers...")
            sync_results["customers"] = await self.full_sync_customers()
            
            # 2. Sync conversations
            logger.info("💬 Syncing conversations...")
            sync_results["conversations"] = await self.full_sync_conversations()
            
            # 3. Sync knowledge base
            logger.info("📚 Syncing knowledge base...")
            sync_results["knowledge_base"] = await self.sync_knowledge_base()
            
            # Check for any failures
            for component in ["customers", "conversations", "knowledge_base"]:
                if "error" in sync_results[component]:
                    sync_results["overall_success"] = False
                    logger.error(f"❌ {component} sync failed: {sync_results[component]['error']}")
            
            sync_results["completed_at"] = datetime.utcnow().isoformat()
            
            # Store full sync timestamp
            await self.cache.redis.set("last_full_sync", datetime.utcnow().isoformat(), 86400)
            
            if sync_results["overall_success"]:
                logger.info("✅ Full system sync completed successfully")
            else:
                logger.warning("⚠️ Full system sync completed with some failures")
            
            return sync_results
            
        except Exception as e:
            logger.error(f"❌ Full system sync failed: {e}")
            sync_results["error"] = str(e)
            sync_results["overall_success"] = False
            return sync_results


# Global service instance
etl_service = ETLService()