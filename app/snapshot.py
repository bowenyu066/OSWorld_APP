"""VM snapshot management for task preparation."""

import time
from .vm_control import VMController
from .config import config_manager
from .logging_setup import get_logger

logger = get_logger(__name__)


def prepare_for_task(vm: VMController) -> None:
    """Prepare VM for task execution by reverting to clean snapshot and starting.
    
    Args:
        vm: VM controller instance
    """
    logger.info("Preparing VM for task - reverting to clean snapshot")
    
    try:
        # Revert to clean snapshot if enabled
        if not vm.is_running():
            logger.info("VM is not running, starting from scratch")
            start_time = time.time()
            fullscreen = config_manager.config.start_fullscreen
            vm.start_from_scratch(fullscreen=fullscreen)
            end_time = time.time()
            logger.info(f"VM started successfully in {end_time - start_time:.2f} seconds")
            
        if config_manager.config.use_snapshots:
            logger.info("Configuring VM to the clean working environment")
            vm.revert_snapshot("clean")
            logger.info("VM configured successfully for task execution")
        else:
            logger.info("Snapshot revert disabled in configuration")
            logger.info("VM prepared successfully for task execution")
        
    except Exception as e:
        logger.error(f"Failed to prepare VM for task: {e}")
        raise
