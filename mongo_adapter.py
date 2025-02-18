from typing import List, Dict, Any
from pymongo import MongoClient


class MongoAdapter:
    """Adapter for MongoDB operations"""
    
    def __init__(self, connection_string: str, database_name: str):
        """Initialize MongoDB connection
        
        Args:
            connection_string: MongoDB connection string
            database_name: Name of the database to connect to
        """
        self.client = MongoClient(connection_string)
        self.db = self.client[database_name]
    
    def read_from_collection(self, collection_name: str, **kwargs) -> List[Dict[str, Any]]:
        """Read items from a collection with optional filters
        
        Args:
            collection_name: Name of the collection to read from
            **kwargs: Key-value pairs to filter results
            
        Returns:
            List of documents matching the filter criteria
        """
        collection = self.db[collection_name]
        query_filter = kwargs if kwargs else {}
        return list(collection.find(query_filter))
    
    def delete_items_in_collection(self, collection_name: str, **kwargs) -> None:
        """Delete items from a collection based on filters
        
        Args:
            collection_name: Name of the collection to delete from
            **kwargs: Key-value pairs to filter which items to delete
        """
        collection = self.db[collection_name]
        if not kwargs:
            raise ValueError("Delete operation requires filter criteria")
        collection.delete_many(kwargs)
    
    def load_items_into_collection(self, collection_name: str, items: List[Dict[str, Any]]) -> None:
        """Load items into a collection
        
        Args:
            collection_name: Name of the collection to load into
            items: List of dictionaries to insert into the collection
        """
        if not items:
            return
            
        collection = self.db[collection_name]
        collection.insert_many(items)
    
    def close(self) -> None:
        """Close the MongoDB connection"""
        self.client.close()
