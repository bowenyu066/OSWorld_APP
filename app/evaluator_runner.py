"""Evaluator runner for task validation (Day 2 implementation)."""

from typing import Dict, Any
from .models import Task
from .vm_control import VMController
from .logging_setup import get_logger

logger = get_logger(__name__)


class EvaluatorRunner:
    """Runs task evaluators in the guest VM."""
    
    def __init__(self):
        pass
    
    def prepare_guest_env(self, vm: VMController) -> None:
        """Prepare guest environment for evaluation (Day 2 implementation)."""
        logger.info("Preparing guest environment for evaluation")
        # TODO: Day 2 - Copy evaluator scripts to guest
        pass
    
    def run(self, task: Task, vm: VMController, guest_task_dir: str = "C:\\Tasks") -> Dict[str, Any]:
        """Run task evaluation in guest VM (Day 2 implementation).
        
        Args:
            task: Task to evaluate
            vm: VM controller instance
            guest_task_dir: Directory in guest for task files
            
        Returns:
            Evaluation result dictionary
        """
        logger.info(f"Running evaluation for task: {task.id}")
        
        # TODO: Day 2 implementation
        # For now, return a placeholder result
        return {
            "passed": True,
            "details": {
                "message": "Day 1 placeholder - evaluation not implemented yet"
            }
        }
