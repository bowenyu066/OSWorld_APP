"""Evaluator runner for task validation (Day 2 implementation)."""

import json
import os
from pathlib import Path
from typing import Dict, Any
from .models import Task
from .vm_control import VMController
from .logging_setup import get_logger

logger = get_logger(__name__)


class EvaluatorRunner:
    """Runs task evaluators in the guest VM."""
    
    def __init__(self):
        self.guest_evaluator_dir = "C:\\evaluators"
        self.guest_task_dir = "C:\\Tasks"
    
    def prepare_guest_env(self, vm: VMController) -> None:
        """Prepare guest environment for evaluation."""

        try:
            # Ensure guest directories exist
            vm.ensure_guest_dir(self.guest_evaluator_dir)
            vm.ensure_guest_dir(self.guest_task_dir)
            
            # Copy evaluator script to guest
            host_eval_script = Path(__file__).parent.parent / "evaluators" / "eval.py"
            if host_eval_script.exists():
                guest_eval_path = f"{self.guest_evaluator_dir}\\eval.py"
                vm.copy_to_guest(str(host_eval_script), guest_eval_path)
                logger.info(f"Copied evaluator script to guest: {guest_eval_path}")
            else:
                logger.warning(f"Evaluator script not found: {host_eval_script}")
            
            # Copy requirements.txt if it exists
            host_requirements = Path(__file__).parent.parent / "evaluators" / "requirements.txt"
            if host_requirements.exists():
                guest_req_path = f"{self.guest_evaluator_dir}\\requirements.txt"
                vm.copy_to_guest(str(host_requirements), guest_req_path)
                logger.info(f"Copied requirements to guest: {guest_req_path}")
                vm.run_in_guest(
                    "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe",
                    ["-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", f"pip install -r {guest_req_path}"],
                    interactive=True, nowait=True
                )
                
            
            logger.info("Guest environment preparation completed")
            
        except Exception as e:
            logger.error(f"Failed to prepare guest environment: {e}")
            raise
    
    def run(self, task: Task, vm: VMController, guest_task_dir: str = None, host_runs_dir: str = None) -> Dict[str, Any]:
        """Run task evaluation in guest VM.
        
        Args:
            task: Task to evaluate
            vm: VM controller instance
            guest_task_dir: Directory in guest for task files (optional)
            host_runs_dir: Directory on host for results (optional)
            
        Returns:
            Evaluation result dictionary
        """
        if guest_task_dir is None:
            guest_task_dir = self.guest_task_dir
        
        logger.info(f"Running evaluation for task: {task.id}")
        
        try:
            # Step 1: Create task JSON file on host and copy to guest
            task_json_content = task.dict() if hasattr(task, 'dict') else task.__dict__
            
            # Create temporary task file on host
            host_temp_dir = Path("temp")
            host_temp_dir.mkdir(exist_ok=True)
            host_task_file = host_temp_dir / f"{task.id}.json"
            
            with open(host_task_file, 'w', encoding='utf-8') as f:
                json.dump(task_json_content, f, indent=2, ensure_ascii=False, default=str)
            
            # Copy task file to guest
            guest_task_file = f"{guest_task_dir}\\{task.id}.json"
            vm.copy_to_guest(str(host_task_file), guest_task_file)
            logger.info(f"Copied task file to guest: {guest_task_file}")
            
            # Step 2: Run evaluator in guest
            guest_result_file = f"{guest_task_dir}\\{task.id}_result.json"
            
            # Use PowerShell to run Python evaluator
            # python_cmd = [
            #     "-Command", 
            #     "python", 
            #     f"{self.guest_evaluator_dir}\\eval.py",
            #     "--task", guest_task_file,
            #     "--out", guest_result_file
            # ]

            guest_log_file = f"{guest_task_dir}\\{task.id}_eval.log"
            guest_err_file = f"{guest_task_dir}\\{task.id}_eval.err"
            guest_result_file = f"{guest_task_dir}\\{task.id}_result.json"

            eval_ps = (
                f"$ErrorActionPreference='Stop'; "
                f"$cmd = @("
                f"'python', "
                f"'{self.guest_evaluator_dir}\\eval.py', "
                f"'--task','{guest_task_file}', "
                f"'--out','{guest_result_file}'"
                f"); "
                f"$p = Start-Process -FilePath $cmd[0] -ArgumentList $cmd[1..($cmd.Length-1)] "
                f"-NoNewWindow -PassThru -WorkingDirectory '{self.guest_evaluator_dir}'; "
                f"$p.WaitForExit(); "
                f"$code=$p.ExitCode; "
            )

            eval_cmdline = (
                f"python \"{self.guest_evaluator_dir}\\eval.py\" "
                f"--task \"{guest_task_file}\" "
                f"--out \"{guest_result_file}\" "
                f"> \"{guest_log_file}\" 2> \"{guest_err_file}\"; "
                f"exit $LASTEXITCODE"
            )

            powershell_args = [
                "-NoProfile",
                "-ExecutionPolicy", "Bypass",
                "-Command",
                eval_cmdline
            ]
            
            logger.info("Executing evaluator in guest VM...")
            return_code = vm.run_in_guest(
                "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe", 
                powershell_args, 
                interactive=False, 
                nowait=False,
                max_attempts=2
            )
            
            if return_code != 0:
                logger.warning(f"Evaluator returned non-zero exit code: {return_code}")
            
            # Step 3: Copy result back to host
            if host_runs_dir:
                host_result_file = Path(host_runs_dir) / f"{task.id}_result.json"
            else:
                host_result_file = host_temp_dir / f"{task.id}_result.json"
            
            vm.copy_from_guest(guest_result_file, str(host_result_file))
            logger.info(f"Copied result from guest: {host_result_file}")
            
            # Step 4: Read and return result
            if host_result_file.exists():
                with open(host_result_file, 'r', encoding='utf-8') as f:
                    result = json.load(f)
                logger.info(f"Evaluation completed. Result: {'PASSED' if result.get('passed', False) else 'FAILED'}")
                return result
            else:
                logger.error("Result file not found after copying from guest")
                return {
                    "passed": False,
                    "details": {
                        "error": "Result file not found after copying from guest",
                        "evaluator_type": "runner"
                    }
                }
            
        except Exception as e:
            logger.error(f"Error during evaluation: {e}")
            return {
                "passed": False,
                "details": {
                    "error": str(e),
                    "evaluator_type": "runner"
                }
            }
        finally:
            # Clean up temporary files
            try:
                if 'host_task_file' in locals() and host_task_file.exists():
                    host_task_file.unlink()
            except Exception as e:
                logger.debug(f"Could not clean up temp file: {e}")
