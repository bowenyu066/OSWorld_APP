#!/usr/bin/env python3
"""
Guest-side evaluator script for OSWorld tasks.
This script runs inside the VM to evaluate task completion.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, Any
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


def exact_match_evaluator(task: Dict[str, Any]) -> Dict[str, Any]:
    """
    Stub implementation for exact_match evaluator.
    Day 2: Simple stub that returns True if expected.rules.expected == "true"
    Day 3: Will be replaced with full OSWorld evaluator integration
    """
    try:
        evaluator = task.get('evaluator', {})
        expected = evaluator.get('expected', {})
        rules = expected.get('rules', {})
        expected_value = rules.get('expected', '')
        
        # Simple stub logic for Day 2
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
    Stub implementation for Chrome-related evaluators.
    Day 2: Simple placeholder
    Day 3: Will implement Chrome DevTools integration
    """
    try:
        # For Day 2, just return success for chrome functions
        return {
            "passed": True,
            "details": {
                "evaluator_type": f"chrome.{func_name}",
                "message": f"Chrome evaluator '{func_name}' - Day 2 stub implementation"
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
    Stub implementation for file-related evaluators.
    Day 2: Simple placeholder
    Day 3: Will implement file system checks
    """
    try:
        return {
            "passed": True,
            "details": {
                "evaluator_type": f"file.{func_name}",
                "message": f"File evaluator '{func_name}' - Day 2 stub implementation"
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


def generic_evaluator(task: Dict[str, Any], func_name: str) -> Dict[str, Any]:
    """
    Generic fallback evaluator for unknown function types.
    Day 2: Simple placeholder that always passes
    Day 3: Will implement more sophisticated logic
    """
    try:
        return {
            "passed": True,
            "details": {
                "evaluator_type": f"generic.{func_name}",
                "message": f"Generic evaluator '{func_name}' - Day 2 stub implementation"
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
    Main task evaluation dispatcher.
    Routes to appropriate evaluator based on task.evaluator.func
    """
    try:
        evaluator = task.get('evaluator', {})
        func = evaluator.get('func', 'unknown')
        
        logger.info(f"Evaluating task with function: {func}")
        
        # Route to appropriate evaluator
        if func == 'exact_match':
            return exact_match_evaluator(task)
        elif func.startswith('chrome.') or func in ['enable_do_not_track', 'compare_pdfs']:
            return chrome_evaluator(task, func)
        elif func.startswith('file.') or func in ['exists', 'contains']:
            return file_evaluator(task, func)
        else:
            logger.warning(f"Unknown evaluator function: {func}, using generic evaluator")
            return generic_evaluator(task, func)
            
    except Exception as e:
        logger.error(f"Error in evaluate_task: {e}")
        return {
            "passed": False,
            "details": {
                "error": str(e),
                "evaluator_type": "dispatcher"
            }
        }


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
        result['timestamp'] = str(Path().cwd())  # Simple timestamp placeholder
        
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
            "timestamp": "error"
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
