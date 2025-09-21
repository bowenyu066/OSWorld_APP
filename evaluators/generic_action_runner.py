#!/usr/bin/env python3
"""
Generic action runner for unknown OSWorld action types.
This script provides a fallback mechanism for executing any action type
by interpreting the action parameters and executing appropriate commands.
"""

import argparse
import json
import sys
import subprocess
import logging
from pathlib import Path
from typing import Dict, Any

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('C:\\evaluators\\generic_runner.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def execute_powershell_command(command: str) -> int:
    """Execute a PowerShell command and return exit code."""
    try:
        result = subprocess.run(
            ["powershell.exe", "-Command", command],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.stdout:
            logger.info(f"PowerShell output: {result.stdout}")
        if result.stderr:
            logger.warning(f"PowerShell error: {result.stderr}")
            
        return result.returncode
    except subprocess.TimeoutExpired:
        logger.error("PowerShell command timed out")
        return 1
    except Exception as e:
        logger.error(f"Error executing PowerShell command: {e}")
        return 1


def handle_generic_action(action_data: Dict[str, Any]) -> int:
    """Handle generic action by interpreting parameters and executing commands."""
    action_type = action_data.get("type", "unknown")
    parameters = action_data.get("parameters", {})
    
    logger.info(f"Handling generic action: {action_type}")
    logger.info(f"Parameters: {parameters}")
    
    # Try to interpret common parameter patterns
    if "command" in parameters:
        # Action has a command to execute
        command = parameters["command"]
        
        if isinstance(command, str):
            # Execute as shell command
            logger.info(f"Executing shell command: {command}")
            return execute_powershell_command(f"cmd.exe /c '{command}'")
        elif isinstance(command, list):
            # Execute as program with arguments
            program = command[0]
            args = " ".join(f'"{arg}"' for arg in command[1:])
            cmd = f"& '{program}' {args}" if args else f"& '{program}'"
            logger.info(f"Executing program: {cmd}")
            return execute_powershell_command(cmd)
    
    elif "script" in parameters:
        # Action has a script to execute
        script = parameters["script"]
        logger.info(f"Executing script: {script}")
        return execute_powershell_command(f"& '{script}'")
    
    elif "path" in parameters:
        # Action involves a file path
        path = parameters["path"]
        
        # Convert Linux paths to Windows paths
        windows_path = path.replace("/home/user/", "C:\\Users\\user\\")
        windows_path = windows_path.replace("/", "\\")
        
        if action_type.startswith("open") or action_type == "launch_file":
            # Try to open the file
            logger.info(f"Opening file: {windows_path}")
            return execute_powershell_command(f"Start-Process '{windows_path}'")
        elif action_type.startswith("delete") or action_type == "remove":
            # Try to delete the file
            logger.info(f"Deleting file: {windows_path}")
            return execute_powershell_command(f"Remove-Item '{windows_path}' -Force -ErrorAction SilentlyContinue")
        elif action_type.startswith("create") or action_type == "mkdir":
            # Try to create directory
            logger.info(f"Creating directory: {windows_path}")
            return execute_powershell_command(f"New-Item -ItemType Directory -Force -Path '{windows_path}'")
    
    elif "url" in parameters:
        # Action involves a URL
        url = parameters["url"]
        logger.info(f"Opening URL: {url}")
        return execute_powershell_command(f"Start-Process '{url}'")
    
    elif "process" in parameters or "name" in parameters:
        # Action involves process management
        process_name = parameters.get("process") or parameters.get("name")
        
        if action_type.startswith("kill") or action_type.startswith("stop"):
            logger.info(f"Stopping process: {process_name}")
            return execute_powershell_command(f"Stop-Process -Name '{process_name}' -Force -ErrorAction SilentlyContinue")
        elif action_type.startswith("start") or action_type.startswith("launch"):
            logger.info(f"Starting process: {process_name}")
            return execute_powershell_command(f"Start-Process '{process_name}'")
    
    elif "registry" in parameters or "reg" in parameters:
        # Action involves registry operations
        reg_data = parameters.get("registry") or parameters.get("reg")
        if isinstance(reg_data, dict):
            key = reg_data.get("key", "")
            value = reg_data.get("value", "")
            data = reg_data.get("data", "")
            
            if key and value:
                logger.info(f"Setting registry value: {key}\\{value} = {data}")
                cmd = f"Set-ItemProperty -Path 'Registry::{key}' -Name '{value}' -Value '{data}' -ErrorAction SilentlyContinue"
                return execute_powershell_command(cmd)
    
    # If we can't interpret the action, try to execute it as a generic command
    # Convert the entire action to a JSON string and log it
    action_json = json.dumps(action_data, indent=2)
    logger.warning(f"Could not interpret action type '{action_type}', logging parameters:")
    logger.warning(action_json)
    
    # Try to find any executable content in the parameters
    for key, value in parameters.items():
        if isinstance(value, str) and (
            value.endswith(".exe") or 
            value.endswith(".bat") or 
            value.endswith(".ps1") or
            value.startswith("cmd") or
            value.startswith("powershell")
        ):
            logger.info(f"Found executable in parameter '{key}': {value}")
            return execute_powershell_command(value)
    
    # Last resort: create a simple log entry and return success
    logger.info(f"Generic action '{action_type}' processed (no specific handler available)")
    return 0


def main():
    """Main entry point for the generic action runner."""
    parser = argparse.ArgumentParser(description='Generic OSWorld Action Runner')
    parser.add_argument('--action', required=True, help='Path to action JSON file')
    
    args = parser.parse_args()
    
    try:
        logger.info(f"Starting generic action runner for: {args.action}")
        
        # Read action file
        action_path = Path(args.action)
        if not action_path.exists():
            raise FileNotFoundError(f"Action file not found: {args.action}")
        
        with open(action_path, 'r', encoding='utf-8') as f:
            action_data = json.load(f)
        
        logger.info(f"Loaded action: {action_data.get('type', 'unknown')}")
        
        # Execute the action
        exit_code = handle_generic_action(action_data)
        
        logger.info(f"Generic action completed with exit code: {exit_code}")
        sys.exit(exit_code)
        
    except Exception as e:
        logger.error(f"Fatal error in generic action runner: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
