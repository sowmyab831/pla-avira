"""Search indexing module: MeiliSearch (text) + Qdrant (vectors)."""
import logging
import json
from typing import Dict, List, Optional
import httpx
import asyncio
import threading

from app.config import settings

logger = logging.getLogger(__name__)

# Keep optional ML dependencies and model downloads out of application startup.
_embedding_model = None
_embedding_lock = threading.Lock()


def _encode(text: str):
    global _embedding_model
    with _embedding_lock:
        if _embedding_model is None:
            from sentence_transformers import SentenceTransformer
            _embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
        return _embedding_model.encode(text).tolist()


class SearchIndexer:
    """Handle indexing to MeiliSearch (text) and Qdrant (vectors)."""
    
    def __init__(self):
        self.meili_url = settings.meili_url
        self.meili_key = settings.meili_master_key
        self.qdrant_url = settings.qdrant_url
        self.qdrant_key = settings.qdrant_api_key
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def index_document(
        self,
        text: str,
        metadata: Dict,
        collection_name: str = "documents",
    ) -> bool:
        """
        Index document to both MeiliSearch (text) and Qdrant (vectors).
        
        Args:
            text: Document text to index
            metadata: Metadata dict (user_id, category, timestamp, etc.)
            collection_name: Qdrant collection name
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Generate embedding
            embedding = await asyncio.to_thread(_encode, text)
            
            # Index to MeiliSearch
            meili_success = await self._index_meili(text, metadata)
            
            # Index to Qdrant
            qdrant_success = await self._index_qdrant(
                text, embedding, metadata, collection_name
            )
            
            return meili_success and qdrant_success
            
        except Exception as e:
            logger.error(f"Error indexing document: {e}")
            return False
    
    async def _index_meili(self, text: str, metadata: Dict) -> bool:
        """Index to MeiliSearch."""
        try:
            doc = {
                "id": metadata.get("id", ""),
                "text": text,
                **metadata,
            }
            
            url = f"{self.meili_url}/indexes/documents/documents"
            headers = {"Authorization": f"Bearer {self.meili_key}"}
            
            response = await self.client.post(url, json=[doc], headers=headers)
            response.raise_for_status()
            logger.info(f"Indexed to MeiliSearch: {metadata.get('id')}")
            return True
            
        except Exception as e:
            logger.error(f"MeiliSearch indexing failed: {e}")
            return False
    
    async def _index_qdrant(
        self,
        text: str,
        embedding: List[float],
        metadata: Dict,
        collection_name: str,
    ) -> bool:
        """Index to Qdrant."""
        try:
            # Ensure collection exists
            await self._ensure_collection(collection_name, len(embedding))
            
            # Upsert point
            url = f"{self.qdrant_url}/collections/{collection_name}/points"
            headers = {}
            if self.qdrant_key:
                headers["api-key"] = self.qdrant_key
            
            point = {
                "id": int(metadata.get("id", 0)),
                "vector": embedding,
                "payload": {
                    "text": text,
                    **metadata,
                },
            }
            
            response = await self.client.put(url, json=point, headers=headers)
            response.raise_for_status()
            logger.info(f"Indexed to Qdrant: {metadata.get('id')}")
            return True
            
        except Exception as e:
            logger.error(f"Qdrant indexing failed: {e}")
            return False
    
    async def _ensure_collection(self, collection_name: str, vector_size: int):
        """Ensure Qdrant collection exists."""
        try:
            url = f"{self.qdrant_url}/collections/{collection_name}"
            headers = {}
            if self.qdrant_key:
                headers["api-key"] = self.qdrant_key
            
            # Check if collection exists
            response = await self.client.get(url, headers=headers)
            if response.status_code == 200:
                return
            
            # Create collection
            create_url = f"{self.qdrant_url}/collections/{collection_name}"
            payload = {
                "vectors": {
                    "size": vector_size,
                    "distance": "Cosine",
                }
            }
            response = await self.client.put(create_url, json=payload, headers=headers)
            response.raise_for_status()
            logger.info(f"Created Qdrant collection: {collection_name}")
            
        except Exception as e:
            logger.error(f"Error ensuring collection: {e}")
    
    async def search(
        self,
        query: str,
        collection_name: str = "documents",
        limit: int = 10,
    ) -> List[Dict]:
        """
        Search documents using vector similarity.
        
        Args:
            query: Search query text
            collection_name: Qdrant collection name
            limit: Max results
        
        Returns:
            List of search results with scores
        """
        try:
            # Generate query embedding
            query_embedding = await asyncio.to_thread(_encode, query)
            
            url = f"{self.qdrant_url}/collections/{collection_name}/points/search"
            headers = {}
            if self.qdrant_key:
                headers["api-key"] = self.qdrant_key
            
            payload = {
                "vector": query_embedding,
                "limit": limit,
                "with_payload": True,
            }
            
            response = await self.client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            
            results = response.json().get("result", [])
            return results
            
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []
    
    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()


# Global indexer instance
_indexer: Optional[SearchIndexer] = None


def get_indexer() -> SearchIndexer:
    """Get or create global indexer instance."""
    global _indexer
    if _indexer is None:
        _indexer = SearchIndexer()
    return _indexer
