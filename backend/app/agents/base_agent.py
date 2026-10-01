"""
Base Agent class for multi-agent orchestration
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """
    Abstract base class for all agents in the Omni-PLA system
    """
    
    def __init__(self, name: str, model: str, temperature: float = 0.7):
        self.name = name
        self.model = model
        self.temperature = temperature
        self.created_at = datetime.now()
        self.execution_count = 0
        
    @abstractmethod
    async def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the agent's primary task
        
        Args:
            task: Dictionary containing task details
            
        Returns:
            Dictionary containing execution results
        """
        pass
    
    @abstractmethod
    async def validate_input(self, task: Dict[str, Any]) -> bool:
        """
        Validate input before execution
        
        Args:
            task: Dictionary containing task details
            
        Returns:
            Boolean indicating if input is valid
        """
        pass
    
    async def pre_execute(self, task: Dict[str, Any]) -> None:
        """
        Hook for pre-execution logic
        """
        self.execution_count += 1
        logger.info(f"{self.name} executing task #{self.execution_count}")
    
    async def post_execute(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Hook for post-execution logic
        """
        result["agent"] = self.name
        result["model"] = self.model
        result["executed_at"] = datetime.now().isoformat()
        return result
    
    async def run(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main execution pipeline
        """
        # Validate input
        if not await self.validate_input(task):
            return {
                "success": False,
                "error": "Invalid input",
                "agent": self.name
            }
        
        # Pre-execution
        await self.pre_execute(task)
        
        try:
            # Execute
            result = await self.execute(task)
            
            # Post-execution
            return await self.post_execute(result)
            
        except Exception as e:
            logger.error(f"{self.name} execution failed: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "agent": self.name
            }
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get agent statistics
        """
        return {
            "name": self.name,
            "model": self.model,
            "execution_count": self.execution_count,
            "created_at": self.created_at.isoformat()
        }
