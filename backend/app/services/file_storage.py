"""File storage service for persistent document management."""
import os
import shutil
import logging
from pathlib import Path
from typing import Optional, List
from datetime import datetime
import json

logger = logging.getLogger(__name__)

class FileStorageService:
    """Manages persistent file storage for uploaded documents."""
    
    def __init__(self, base_path: str = None):
        """Initialize file storage service."""
        base = base_path or os.environ.get("AVIRA_DATA_DIR", "/data/documents")
        self.base_path = Path(base)
        self.base_path.mkdir(parents=True, exist_ok=True)
        
        # Create category directories
        self.categories = {
            "finance": self.base_path / "finance",
            "health": self.base_path / "health",
            "school": self.base_path / "school",
            "other": self.base_path / "other",
        }
        
        for category_path in self.categories.values():
            category_path.mkdir(parents=True, exist_ok=True)
        
        # Metadata file for tracking uploads
        self.metadata_file = self.base_path / "metadata.json"
        self.metadata = self._load_metadata()
        
        logger.info(f"FileStorageService initialized at {self.base_path}")
    
    def _load_metadata(self) -> dict:
        """Load metadata from disk."""
        if self.metadata_file.exists():
            try:
                with open(self.metadata_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading metadata: {e}")
                return {"files": {}}
        return {"files": {}}
    
    def _save_metadata(self):
        """Save metadata to disk."""
        try:
            with open(self.metadata_file, 'w') as f:
                json.dump(self.metadata, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving metadata: {e}")
    
    def save_file(
        self, 
        file_content: bytes, 
        filename: str, 
        category: str,
        user_id: str = "default",
        metadata: Optional[dict] = None
    ) -> str:
        """
        Save file to persistent storage.
        
        Args:
            file_content: File bytes
            filename: Original filename
            category: Category (finance, health, school, other)
            user_id: User identifier
            metadata: Additional metadata
            
        Returns:
            File ID for retrieval
        """
        if category not in self.categories:
            category = "other"
        
        # Generate unique file ID
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_id = f"{category}_{user_id}_{timestamp}_{filename}"
        
        # Save file
        category_path = self.categories[category]
        file_path = category_path / file_id
        
        try:
            with open(file_path, 'wb') as f:
                f.write(file_content)
            
            # Update metadata
            self.metadata["files"][file_id] = {
                "filename": filename,
                "category": category,
                "user_id": user_id,
                "upload_time": timestamp,
                "file_path": str(file_path),
                "size_bytes": len(file_content),
                "metadata": metadata or {}
            }
            self._save_metadata()
            
            logger.info(f"Saved file {filename} as {file_id}")
            return file_id
            
        except Exception as e:
            logger.error(f"Error saving file {filename}: {e}")
            raise
    
    def get_file(self, file_id: str) -> Optional[bytes]:
        """Retrieve file content by ID."""
        if file_id not in self.metadata["files"]:
            return None
        
        file_path = Path(self.metadata["files"][file_id]["file_path"])
        if not file_path.exists():
            logger.warning(f"File {file_id} not found at {file_path}")
            return None
        
        try:
            with open(file_path, 'rb') as f:
                return f.read()
        except Exception as e:
            logger.error(f"Error reading file {file_id}: {e}")
            return None
    
    def get_file_path(self, file_id: str) -> Optional[Path]:
        """Get file path by ID."""
        if file_id not in self.metadata["files"]:
            return None
        return Path(self.metadata["files"][file_id]["file_path"])
    
    def list_files(
        self, 
        category: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> List[dict]:
        """List files with optional filtering."""
        files = []
        for file_id, info in self.metadata["files"].items():
            if category and info["category"] != category:
                continue
            if user_id and info["user_id"] != user_id:
                continue
            files.append({
                "file_id": file_id,
                **info
            })
        return sorted(files, key=lambda x: x["upload_time"], reverse=True)
    
    def delete_file(self, file_id: str) -> bool:
        """Delete file by ID."""
        if file_id not in self.metadata["files"]:
            return False
        
        file_path = Path(self.metadata["files"][file_id]["file_path"])
        try:
            if file_path.exists():
                file_path.unlink()
            del self.metadata["files"][file_id]
            self._save_metadata()
            logger.info(f"Deleted file {file_id}")
            return True
        except Exception as e:
            logger.error(f"Error deleting file {file_id}: {e}")
            return False
    
    def get_category_summary(self, category: str) -> dict:
        """Get summary of files in a category."""
        files = self.list_files(category=category)
        total_size = sum(f["size_bytes"] for f in files)
        return {
            "category": category,
            "file_count": len(files),
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "files": files
        }


# Singleton instance
_file_storage_service: Optional[FileStorageService] = None

def get_file_storage() -> FileStorageService:
    """Get or create file storage service instance."""
    global _file_storage_service
    if _file_storage_service is None:
        _file_storage_service = FileStorageService()
    return _file_storage_service
