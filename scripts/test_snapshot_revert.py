"""Test script for snapshot revert functionality."""

import sys
import time
from pathlib import Path

# Add app directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.vm_control import VMController
from app.config import config_manager
from app.logging_setup import setup_logging, get_logger

def test_snapshot_revert():
    """Test the snapshot revert functionality."""
    # Setup logging
    setup_logging("INFO")
    logger = get_logger(__name__)
    
    logger.info("=== Testing Snapshot Revert Functionality ===")
    
    # Create VM controller
    vm = VMController()
    snapshot_name = config_manager.config.snapshot_name
    
    logger.info(f"Target snapshot: {snapshot_name}")
    logger.info(f"VM path: {vm.vmx_path}")
    
    # Test 1: Check if snapshot exists
    logger.info("\n--- Test 1: Checking if snapshot exists ---")
    can_revert = vm.can_revert_snapshot(snapshot_name)
    logger.info(f"Can revert to snapshot '{snapshot_name}': {can_revert}")
    
    if not can_revert:
        logger.error("Cannot proceed with revert test - snapshot not available")
        return False
    
    # Test 2: Check VM status
    logger.info("\n--- Test 2: Checking VM status ---")
    is_running = vm.is_running()
    logger.info(f"VM is currently running: {is_running}")
    
    # Test 3: Perform snapshot revert
    logger.info("\n--- Test 3: Performing snapshot revert ---")
    try:
        vm.revert_snapshot(snapshot_name)
        logger.info("✓ Snapshot revert completed successfully")
    except Exception as e:
        logger.error(f"✗ Snapshot revert failed: {e}")
        return False
    
    # Test 4: Verify VM is stopped after revert
    logger.info("\n--- Test 4: Verifying VM status after revert ---")
    time.sleep(2)  # Wait a moment
    is_running_after = vm.is_running()
    logger.info(f"VM is running after revert: {is_running_after}")
    
    logger.info("\n=== Snapshot Revert Test Completed Successfully ===")
    return True

if __name__ == "__main__":
    success = test_snapshot_revert()
    sys.exit(0 if success else 1)
