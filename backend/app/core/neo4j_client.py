from neo4j import GraphDatabase
from .config import settings
from typing import Optional, Dict, Any


class Neo4jClient:
    def __init__(self):
        self.driver = None
        
    def connect(self):
        """Initialize Neo4j connection"""
        try:
            self.driver = GraphDatabase.driver(
                settings.neo4j_uri,
                auth=(settings.neo4j_user, settings.neo4j_password)
            )
            return True
        except Exception as e:
            print(f"Neo4j connection failed: {e}")
            return False
    
    def close(self):
        """Close Neo4j connection"""
        if self.driver:
            self.driver.close()
    
    def test_connection(self):
        """Test Neo4j connection"""
        try:
            with self.driver.session() as session:
                result = session.run("RETURN 1 as test")
                return result.single()["test"] == 1
        except Exception as e:
            print(f"Neo4j test failed: {e}")
            return False
    
    def execute_query(self, query: str, parameters: Optional[Dict[str, Any]] = None):
        """Execute a Neo4j query"""
        try:
            with self.driver.session() as session:
                result = session.run(query, parameters or {})
                return [record.data() for record in result]
        except Exception as e:
            print(f"Query execution failed: {e}")
            return []


neo4j_client = Neo4jClient()