"""Task adapter for executing OSWorld task configurations."""

import time
from typing import Dict, Any, Callable
from .models import Task, Action
from .vm_control import VMController
from .logging_setup import get_logger

logger = get_logger(__name__)


class TaskRunner:
    """Executes OSWorld task configurations."""
    
    def __init__(self):
        self.action_handlers: Dict[str, Callable[[Action, VMController, Task], None]] = {
            "launch": self._handle_launch,
            "sleep": self._handle_sleep,
            "chrome_open_tabs": self._handle_chrome_open_tabs,
        }
    
    def run_config(self, task: Task, vm: VMController) -> None:
        """Execute all actions in the task configuration.
        
        Args:
            task: The task to execute
            vm: VM controller instance
        """
        logger.info(f"Starting task configuration for: {task.id}")
        
        for i, action in enumerate(task.config):
            logger.info(f"Executing action {i+1}/{len(task.config)}: {action.type}")
            
            handler = self.action_handlers.get(action.type)
            if handler:
                try:
                    handler(action, vm, task)
                    logger.info(f"Action {action.type} completed successfully")
                except Exception as e:
                    logger.error(f"Action {action.type} failed: {e}")
                    raise
            else:
                logger.warning(f"Unknown action type: {action.type}, skipping")
        
        logger.info("Task configuration completed")
    
    def _handle_launch(self, action: Action, vm: VMController, task: Task) -> None:
        """Handle launch action - start a program in the guest VM."""
        command = action.parameters.get("command", [])
        if not command:
            raise ValueError("Launch action requires 'command' parameter")
        
        if isinstance(command, str):
            # Single command string
            program = command
            args = []
        elif isinstance(command, list):
            # Command with arguments
            program = command[0]
            args = command[1:] if len(command) > 1 else []
        else:
            raise ValueError("Command must be string or list")
        
        # Map common program names to Windows paths
        program_mappings = {
            "google-chrome": "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
            "chrome": "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
            "notepad": "C:\\Windows\\System32\\notepad.exe",
            "powershell": "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe",
        }
        
        # Use mapping if available, otherwise use as-is
        if program in program_mappings:
            program = program_mappings[program]
        
        logger.info(f"Launching program: {program} with args: {args}")
        
        # Run the program in guest
        return_code = vm.run_in_guest(program, args)
        if return_code != 0:
            logger.warning(f"Program exited with non-zero code: {return_code}")
    
    def _handle_sleep(self, action: Action, vm: VMController, task: Task) -> None:
        """Handle sleep action - pause execution for specified seconds."""
        seconds = action.parameters.get("seconds", 1)
        logger.info(f"Sleeping for {seconds} seconds")
        time.sleep(seconds)
    
    def _handle_chrome_open_tabs(self, action: Action, vm: VMController, task: Task) -> None:
        """Handle chrome_open_tabs action - open URLs in Chrome tabs."""
        urls = action.parameters.get("urls_to_open", [])
        if not urls:
            logger.warning("chrome_open_tabs action has no URLs to open")
            return
        
        chrome_path = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
        
        for url in urls:
            logger.info(f"Opening URL in Chrome: {url}")
            # Use PowerShell to start Chrome with the URL
            powershell_cmd = f"Start-Process -FilePath '{chrome_path}' -ArgumentList '{url}'"
            vm.run_in_guest("powershell.exe", ["-Command", powershell_cmd])
            
            # Small delay between opening tabs
            time.sleep(1)
