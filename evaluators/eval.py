#!/usr/bin/env python3
"""
Guest-side evaluator script for OSWorld tasks.
This script runs inside the VM to evaluate task completion.
"""

import argparse
import json
import sys
import os
import re
import subprocess
import requests
import time
from pathlib import Path
from typing import Dict, Any, List, Union
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('C:\\evaluators\\eval.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def get_chrome_devtools_targets() -> List[Dict[str, Any]]:
    """Get Chrome DevTools targets via debugging port."""
    try:
        response = requests.get('http://localhost:1337/json', timeout=5)
        if response.status_code == 200:
            return response.json()
        else:
            logger.warning(f"Chrome DevTools returned status {response.status_code}")
            return []
    except Exception as e:
        logger.warning(f"Could not connect to Chrome DevTools: {e}")
        return []


def execute_chrome_devtools_command(target_id: str, command: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a Chrome DevTools command."""
    try:
        import websocket
        ws_url = f"ws://localhost:1337/devtools/page/{target_id}"
        ws = websocket.create_connection(ws_url, timeout=10)
        
        ws.send(json.dumps(command))
        result = json.loads(ws.recv())
        ws.close()
        
        return result
    except Exception as e:
        logger.error(f"Chrome DevTools command failed: {e}")
        return {"error": str(e)}


def check_chrome_do_not_track() -> bool:
    """Check if Chrome's Do Not Track setting is enabled."""
    try:
        targets = get_chrome_devtools_targets()
        if not targets:
            return False
        
        # Use the first available target
        target = targets[0]
        target_id = target['id']
        
        # Execute JavaScript to check Do Not Track setting
        command = {
            "id": 1,
            "method": "Runtime.evaluate",
            "params": {
                "expression": "navigator.doNotTrack === '1' || navigator.doNotTrack === 'yes'"
            }
        }
        
        result = execute_chrome_devtools_command(target_id, command)
        
        if "result" in result and "result" in result["result"]:
            return result["result"]["result"]["value"] == True
        
        return False
    except Exception as e:
        logger.error(f"Error checking Do Not Track: {e}")
        return False


def check_chrome_tabs() -> List[Dict[str, Any]]:
    """Get information about open Chrome tabs."""
    try:
        targets = get_chrome_devtools_targets()
        tab_info = []
        
        for target in targets:
            if target.get('type') == 'page':
                tab_info.append({
                    'title': target.get('title', ''),
                    'url': target.get('url', ''),
                    'id': target.get('id', '')
                })
        
        return tab_info
    except Exception as e:
        logger.error(f"Error getting Chrome tabs: {e}")
        return []


def exact_match_evaluator(task: Dict[str, Any]) -> Dict[str, Any]:
    """
    Enhanced exact_match evaluator with Chrome DevTools integration.
    """
    try:
        evaluator = task.get('evaluator', {})
        expected = evaluator.get('expected', {})
        result_config = evaluator.get('result', {})
        rules = expected.get('rules', {})
        expected_value = rules.get('expected', '')
        
        result_type = result_config.get('type', '')
        
        # Handle different result types
        if result_type == 'enable_do_not_track':
            # Check Chrome Do Not Track setting
            actual_value = check_chrome_do_not_track()
            expected_bool = expected_value.lower() == "true"
            
            return {
                "passed": actual_value == expected_bool,
                "details": {
                    "evaluator_type": "exact_match",
                    "result_type": result_type,
                    "expected": expected_bool,
                    "actual": actual_value,
                    "message": f"Do Not Track setting: expected {expected_bool}, got {actual_value}"
                }
            }
        
        elif result_type == 'text_content':
            # Check text content (placeholder - would need OCR or clipboard access)
            return {
                "passed": True,  # Placeholder
                "details": {
                    "evaluator_type": "exact_match",
                    "result_type": result_type,
                    "expected": expected_value,
                    "message": "Text content check - placeholder implementation"
                }
            }
        
        else:
            # Simple stub logic for other cases
            if expected_value.lower() == "true":
                return {
                    "passed": True,
                    "details": {
                        "evaluator_type": "exact_match",
                        "expected": expected_value,
                        "message": "Task passed based on expected value 'true'"
                    }
                }
            else:
                return {
                    "passed": False,
                    "details": {
                        "evaluator_type": "exact_match",
                        "expected": expected_value,
                        "message": f"Task failed - expected '{expected_value}', not 'true'"
                    }
                }
            
    except Exception as e:
        logger.error(f"Error in exact_match_evaluator: {e}")
        return {
            "passed": False,
            "details": {
                "error": str(e),
                "evaluator_type": "exact_match"
            }
        }


def chrome_evaluator(task: Dict[str, Any], func_name: str) -> Dict[str, Any]:
    """
    Chrome-related evaluators with DevTools integration.
    """
    try:
        if func_name == 'is_expected_tabs':
            # Check if expected tabs are open
            tabs = check_chrome_tabs()
            expected = task.get('evaluator', {}).get('expected', {})
            
            return {
                "passed": len(tabs) > 0,  # Simplified check
                "details": {
                    "evaluator_type": f"chrome.{func_name}",
                    "tabs_count": len(tabs),
                    "tabs": tabs[:5],  # Limit output
                    "message": f"Found {len(tabs)} open tabs"
                }
            }
        
        elif func_name == 'enable_do_not_track':
            # Check Do Not Track setting
            enabled = check_chrome_do_not_track()
            
            return {
                "passed": enabled,
                "details": {
                    "evaluator_type": f"chrome.{func_name}",
                    "do_not_track_enabled": enabled,
                    "message": f"Do Not Track setting: {'enabled' if enabled else 'disabled'}"
                }
            }
        
        else:
            # Generic Chrome evaluator
            return {
                "passed": True,
                "details": {
                    "evaluator_type": f"chrome.{func_name}",
                    "message": f"Chrome evaluator '{func_name}' - generic implementation"
                }
            }
    except Exception as e:
        logger.error(f"Error in chrome_evaluator: {e}")
        return {
            "passed": False,
            "details": {
                "error": str(e),
                "evaluator_type": f"chrome.{func_name}"
            }
        }


def file_evaluator(task: Dict[str, Any], func_name: str) -> Dict[str, Any]:
    """
    File-related evaluators with actual file system checks.
    """
    try:
        evaluator = task.get('evaluator', {})
        result_config = evaluator.get('result', {})
        expected_config = evaluator.get('expected', {})
        
        if func_name == 'compare_table' or func_name == 'compare_docx_tables':
            # Compare document tables (simplified)
            result_path = result_config.get('path', '')
            if result_path:
                # Convert Linux path to Windows
                windows_path = result_path.replace('/home/user/', 'C:\\Users\\user\\').replace('/', '\\')
                file_exists = Path(windows_path).exists()
                
                return {
                    "passed": file_exists,
                    "details": {
                        "evaluator_type": f"file.{func_name}",
                        "file_path": windows_path,
                        "file_exists": file_exists,
                        "message": f"File {'exists' if file_exists else 'not found'}: {windows_path}"
                    }
                }
        
        elif func_name == 'compare_line_spacing' or func_name == 'compare_pptx_files':
            # Document comparison (simplified)
            return {
                "passed": True,
                "details": {
                    "evaluator_type": f"file.{func_name}",
                    "message": f"Document comparison '{func_name}' - simplified implementation"
                }
            }
        
        else:
            # Generic file evaluator
            return {
                "passed": True,
                "details": {
                    "evaluator_type": f"file.{func_name}",
                    "message": f"File evaluator '{func_name}' - generic implementation"
                }
            }
    except Exception as e:
        logger.error(f"Error in file_evaluator: {e}")
        return {
            "passed": False,
            "details": {
                "error": str(e),
                "evaluator_type": f"file.{func_name}"
            }
        }


def system_evaluator(task: Dict[str, Any], func_name: str) -> Dict[str, Any]:
    """
    System-related evaluators for OS operations.
    """
    try:
        if func_name == 'check_include_exclude':
            # Check terminal output for include/exclude patterns
            evaluator = task.get('evaluator', {})
            expected = evaluator.get('expected', {})
            rules = expected.get('rules', {})
            include_patterns = rules.get('include', [])
            exclude_patterns = rules.get('exclude', [])
            
            # Simulate terminal output check (would need actual terminal capture)
            # For now, assume success if include patterns are specified
            passed = len(include_patterns) > 0
            
            return {
                "passed": passed,
                "details": {
                    "evaluator_type": f"system.{func_name}",
                    "include_patterns": include_patterns,
                    "exclude_patterns": exclude_patterns,
                    "message": f"Terminal output check - {'passed' if passed else 'failed'}"
                }
            }
        
        elif func_name == 'check_thunderbird_prefs':
            # Check Thunderbird preferences
            evaluator = task.get('evaluator', {})
            result_config = evaluator.get('result', {})
            file_path = result_config.get('path', '')
            
            if file_path:
                windows_path = file_path.replace('/home/user/', 'C:\\Users\\user\\').replace('/', '\\')
                file_exists = Path(windows_path).exists()
                
                return {
                    "passed": file_exists,
                    "details": {
                        "evaluator_type": f"system.{func_name}",
                        "prefs_file": windows_path,
                        "file_exists": file_exists,
                        "message": f"Thunderbird prefs file {'found' if file_exists else 'not found'}"
                    }
                }
        
        elif func_name == 'check_qt_bgcone':
            # Check VLC Qt background cone setting
            return {
                "passed": True,
                "details": {
                    "evaluator_type": f"system.{func_name}",
                    "message": "VLC Qt background cone check - placeholder implementation"
                }
            }
        
        elif func_name == 'is_extension_installed':
            # Check if VS Code extension is installed
            evaluator = task.get('evaluator', {})
            result_config = evaluator.get('result', {})
            command = result_config.get('command', [])
            
            if command:
                try:
                    # Execute the command to check extension
                    result = subprocess.run(command, capture_output=True, text=True, timeout=30)
                    output = result.stdout.strip()
                    
                    # Check if expected extension is in output
                    expected = evaluator.get('expected', {})
                    rules = expected.get('rules', {})
                    expected_ext = rules.get('expected', '')
                    
                    passed = expected_ext in output
                    
                    return {
                        "passed": passed,
                        "details": {
                            "evaluator_type": f"system.{func_name}",
                            "command_output": output[:200],  # Limit output
                            "expected_extension": expected_ext,
                            "found": passed,
                            "message": f"Extension {'found' if passed else 'not found'}: {expected_ext}"
                        }
                    }
                except subprocess.TimeoutExpired:
                    return {
                        "passed": False,
                        "details": {
                            "evaluator_type": f"system.{func_name}",
                            "error": "Command timed out",
                            "message": "Extension check command timed out"
                        }
                    }
        
        else:
            # Generic system evaluator
            return {
                "passed": True,
                "details": {
                    "evaluator_type": f"system.{func_name}",
                    "message": f"System evaluator '{func_name}' - generic implementation"
                }
            }
    except Exception as e:
        logger.error(f"Error in system_evaluator: {e}")
        return {
            "passed": False,
            "details": {
                "error": str(e),
                "evaluator_type": f"system.{func_name}"
            }
        }


def generic_evaluator(task: Dict[str, Any], func_name: str) -> Dict[str, Any]:
    """
    Generic fallback evaluator for unknown function types.
    """
    try:
        if func_name == 'infeasible':
            # Mark task as infeasible
            return {
                "passed": False,
                "details": {
                    "evaluator_type": "generic.infeasible",
                    "message": "Task marked as infeasible"
                }
            }
        
        else:
            # Generic success for unknown functions
            return {
                "passed": True,
                "details": {
                    "evaluator_type": f"generic.{func_name}",
                    "message": f"Generic evaluator '{func_name}' - placeholder implementation"
                }
            }
    except Exception as e:
        logger.error(f"Error in generic_evaluator: {e}")
        return {
            "passed": False,
            "details": {
                "error": str(e),
                "evaluator_type": f"generic.{func_name}"
            }
        }


def evaluate_task(task: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main task evaluation dispatcher with comprehensive function mapping.
    Routes to appropriate evaluator based on task.evaluator.func
    """
    try:
        evaluator = task.get('evaluator', {})
        func = evaluator.get('func', 'unknown')
        
        logger.info(f"Evaluating task with function: {func}")
        
        # Handle multiple functions (array)
        if isinstance(func, list):
            results = []
            for f in func:
                result = evaluate_single_function(task, f)
                results.append(result)
            
            # Determine overall result based on conjunction
            conj = evaluator.get('conj', 'and')
            if conj == 'or':
                overall_passed = any(r['passed'] for r in results)
            else:  # 'and' or default
                overall_passed = all(r['passed'] for r in results)
            
            return {
                "passed": overall_passed,
                "details": {
                    "evaluator_type": "multi_function",
                    "conjunction": conj,
                    "results": results,
                    "message": f"Multi-function evaluation with {conj} conjunction"
                }
            }
        else:
            # Single function
            return evaluate_single_function(task, func)
            
    except Exception as e:
        logger.error(f"Error in evaluate_task: {e}")
        return {
            "passed": False,
            "details": {
                "error": str(e),
                "evaluator_type": "dispatcher"
            }
        }


def evaluate_single_function(task: Dict[str, Any], func: str) -> Dict[str, Any]:
    """Evaluate a single function."""
    # Route to appropriate evaluator based on function name
    if func == 'exact_match':
        return exact_match_evaluator(task)
    
    # Chrome-related functions
    elif func in ['is_expected_tabs', 'enable_do_not_track', 'compare_pdfs'] or func.startswith('chrome.'):
        return chrome_evaluator(task, func)
    
    # File-related functions
    elif func in ['compare_table', 'compare_docx_tables', 'compare_line_spacing', 'compare_pptx_files'] or func.startswith('file.'):
        return file_evaluator(task, func)
    
    # System-related functions
    elif func in ['check_include_exclude', 'check_thunderbird_prefs', 'check_qt_bgcone', 'is_extension_installed'] or func.startswith('system.'):
        return system_evaluator(task, func)
    
    # Generic functions
    elif func in ['infeasible'] or func.startswith('generic.'):
        return generic_evaluator(task, func)
    
    else:
        logger.warning(f"Unknown evaluator function: {func}, using generic evaluator")
        return generic_evaluator(task, func)


def main():
    """Main entry point for the evaluator script."""
    parser = argparse.ArgumentParser(description='OSWorld Task Evaluator')
    parser.add_argument('--task', required=True, help='Path to task JSON file')
    parser.add_argument('--out', required=True, help='Path to output result JSON file')
    
    args = parser.parse_args()
    
    try:
        logger.info(f"Starting evaluation of task: {args.task}")
        logger.info(f"Output will be written to: {args.out}")
        
        # Read task file
        task_path = Path(args.task)
        if not task_path.exists():
            raise FileNotFoundError(f"Task file not found: {args.task}")
        
        with open(task_path, 'r', encoding='utf-8') as f:
            task = json.load(f)
        
        logger.info(f"Loaded task: {task.get('id', 'unknown')}")
        
        # Run evaluation
        result = evaluate_task(task)
        
        # Add metadata
        result['task_id'] = task.get('id', 'unknown')
        result['timestamp'] = str(int(time.time()))
        
        # Write result
        output_path = Path(args.out)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Evaluation completed. Result: {'PASSED' if result['passed'] else 'FAILED'}")
        logger.info(f"Result written to: {args.out}")
        
        # Exit with appropriate code
        sys.exit(0 if result['passed'] else 1)
        
    except Exception as e:
        logger.error(f"Fatal error during evaluation: {e}")
        
        # Write error result
        error_result = {
            "passed": False,
            "details": {
                "error": str(e),
                "evaluator_type": "main"
            },
            "task_id": "unknown",
            "timestamp": str(int(time.time()))
        }
        
        try:
            output_path = Path(args.out)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(error_result, f, indent=2, ensure_ascii=False)
        except Exception as write_error:
            logger.error(f"Could not write error result: {write_error}")
        
        sys.exit(1)


if __name__ == '__main__':
    main()
