"""VM snapshot management for task preparation."""

from .vm_control import VMController
from .config import config_manager
from .logging_setup import get_logger

logger = get_logger(__name__)


def prepare_for_task(vm: VMController, snapshot_name: str) -> None:
    """Prepare VM for task execution by reverting to snapshot and starting.
    
    Args:
        vm: VM controller instance
        snapshot_name: Name of the snapshot to revert to
    """
    logger.info(f"Preparing VM for task - reverting to snapshot: {snapshot_name}")
    
    try:
        # Revert to clean snapshot if enabled (now with better error handling)
        if config_manager.config.use_snapshots:
            vm.revert_snapshot(snapshot_name)
        else:
            logger.info("Snapshot revert disabled in configuration")
        
        # Start VM in fullscreen mode
        fullscreen = config_manager.config.start_fullscreen
        vm.start(fullscreen=fullscreen)
        
        logger.info("VM prepared successfully for task execution")
        
    except Exception as e:
        logger.error(f"Failed to prepare VM for task: {e}")
        raise
