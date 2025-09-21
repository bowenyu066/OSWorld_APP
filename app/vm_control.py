"""VMware virtual machine control via vmrun and vmware.exe."""

import os
import subprocess
import time
import random
from pathlib import Path
from typing import List, Optional, Callable, Any
from .config import config_manager
from .logging_setup import get_logger

logger = get_logger(__name__)


class VMOperationError(Exception):
    """Custom exception for VM operations."""
    pass


class VMTimeoutError(VMOperationError):
    """Exception for VM operation timeouts."""
    pass


class VMController:
    """Controls VMware virtual machines using vmrun and vmware.exe with enhanced robustness."""
    
    def __init__(self):
        self.config = config_manager.config
        self.vmrun_path = config_manager.get_vmrun_path()
        self.vmware_path = config_manager.get_vmware_path()
        self.vmx_path = self.config.vmx_path
        self.vmrun_path = os.path.normpath(self.vmrun_path)
        self.vmware_path = os.path.normpath(self.vmware_path)
        self.vmx_path = os.path.normpath(self.vmx_path)
        
        # Status callback for GUI updates
        self.status_callback: Optional[Callable[[str], None]] = None
    
    def set_status_callback(self, callback: Callable[[str], None]) -> None:
        """Set callback function for status updates."""
        self.status_callback = callback
    
    def _update_status(self, message: str) -> None:
        """Update status via callback if available."""
        if self.status_callback:
            self.status_callback(message)
        else:
            logger.info(message)
    
    def _retry_with_backoff(self, operation: Callable[[], Any], max_attempts: int = 3, 
                           base_delay: float = 1.0, max_delay: float = 30.0,
                           operation_name: str = "operation") -> Any:
        """
        Retry an operation with exponential backoff.
        
        Args:
            operation: Function to retry
            max_attempts: Maximum number of attempts
            base_delay: Base delay in seconds
            max_delay: Maximum delay in seconds
            operation_name: Name for logging
            
        Returns:
            Result of successful operation
            
        Raises:
            VMOperationError: If all attempts fail
        """
        last_exception = None
        
        for attempt in range(1, max_attempts + 1):
            try:
                self._update_status(f"Attempting {operation_name} (attempt {attempt}/{max_attempts})")
                result = operation()
                if attempt > 1:
                    self._update_status(f"{operation_name} succeeded on attempt {attempt}")
                return result
                
            except Exception as e:
                last_exception = e
                logger.warning(f"{operation_name} attempt {attempt} failed: {e}")
                
                if attempt < max_attempts:
                    # Calculate delay with exponential backoff and jitter
                    delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
                    jitter = random.uniform(0, 0.1 * delay)  # Add up to 10% jitter
                    total_delay = delay + jitter
                    
                    self._update_status(f"Retrying {operation_name} in {total_delay:.1f} seconds...")
                    time.sleep(total_delay)
                else:
                    self._update_status(f"{operation_name} failed after {max_attempts} attempts")
        
        raise VMOperationError(f"{operation_name} failed after {max_attempts} attempts: {last_exception}")

    def start(self, fullscreen: bool = True) -> None:
        """Start the virtual machine after revert to snapshot with retry logic."""
        def _start_operation():
            self._update_status("Starting virtual machine...")
            cmd = [self.vmware_path, "-X" if fullscreen else "start", self.vmx_path]
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            time.sleep(20)
            if self.is_running():
                self._update_status("VM started successfully")
                return True
            else:
                raise VMOperationError("VM failed to start")
        
        self._retry_with_backoff(_start_operation, max_attempts=3, operation_name="VM start")
   
    def start_from_scratch(self, fullscreen: bool = True) -> None:
        """Start the virtual machine if it's off with enhanced error handling."""
        def _start_from_scratch_operation():
            self._update_status(f"Starting VM from scratch: {self.vmx_path}")
            
            if fullscreen:
                # Use vmware.exe -X for fullscreen mode
                cmd = [self.vmware_path, "-X", self.vmx_path]
                self._update_status("Starting VM in fullscreen mode...")
                
                try:
                    # Start the process without waiting for it to complete
                    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    self._update_status("VM fullscreen process started, checking status...")
                    
                    # Wait and check if VM is running
                    time.sleep(10)
                    
                    if not self.is_running():
                        # Check if process failed immediately
                        poll_result = process.poll()
                        if poll_result is not None and poll_result != 0:
                            _, stderr = process.communicate()
                            raise VMOperationError(f"Failed to start VM: {stderr.decode()}")
                        
                        # Wait a bit more for VM to start
                        self._update_status("VM not detected yet, waiting longer...")
                        time.sleep(10)
                        
                        if not self.is_running():
                            logger.warning("VM not detected by vmrun list, but vmware process is running")
                            self._update_status("VM starting up (process running but not yet detected)")
                        else:
                            self._update_status("VM detected and running!")
                    else:
                        self._update_status("VM detected and running!")
                    
                    return True
                    
                except FileNotFoundError:
                    raise VMOperationError(f"VMware executable not found: {cmd[0]}")
            else:
                # Use vmrun start for normal mode
                cmd = [self.vmrun_path, "start", self.vmx_path]
                self._update_status("Starting VM in normal mode...")
                
                try:
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                    if result.returncode != 0:
                        raise VMOperationError(f"Failed to start VM: {result.stderr}")
                    self._update_status("VM started successfully in normal mode")
                    return True
                    
                except subprocess.TimeoutExpired:
                    raise VMTimeoutError("VM start timed out after 30 seconds")
                except FileNotFoundError:
                    raise VMOperationError(f"VMware executable not found: {cmd[0]}")
        
        self._retry_with_backoff(_start_from_scratch_operation, max_attempts=3, operation_name="VM start from scratch")
    
    def run_in_guest(self, program_path: str, args: List[str] = None, 
                 interactive: bool = True, nowait: bool = True, 
                 workdir: Optional[str] = None, max_attempts: int = 3, timeout: int = 60) -> int:
        """Run program in guest with enhanced retry and timeout logic."""
        if args is None:
            args = []

        def _run_operation():
            cmd = [
                self.vmrun_path, "-T", "ws",
                "-gu", self.config.guest_username,
                "-gp", self.config.guest_password,
                "runProgramInGuest", self.vmx_path
            ]
            if nowait:
                cmd.append("-noWait")
            if interactive:
                cmd += ["-interactive", "-activeWindow"]
            if workdir:
                cmd += ["-workingDirectory", workdir]
            cmd.append(program_path)
            cmd += args

            def _q(s: str) -> str:
                return f"\"{s}\"" if (" " in s or "\t" in s) else s

            self._update_status(f"Running in guest: {program_path} {' '.join(args)}")
            logger.debug("> " + " ".join(_q(x) for x in cmd))

            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=False,
                    timeout=timeout,
                    shell=False,
                )
            except subprocess.TimeoutExpired:
                raise VMTimeoutError(f"Guest program execution timed out after {timeout} seconds")
            except Exception as e:
                raise VMOperationError(f"Error running guest program: {e}")

            # Manually decode bytes, first try utf-8, then mbcs as fallback
            def _decode(b: bytes) -> str:
                if not b:
                    return ""
                try:
                    return b.decode("utf-8")
                except UnicodeDecodeError:
                    return b.decode("mbcs", errors="replace")

            stdout = _decode(result.stdout)
            stderr = _decode(result.stderr)

            # Check return code
            rc = result.returncode
            if rc == 0:
                if stdout:
                    logger.debug(f"Guest stdout: {stdout}")
                if stderr:
                    logger.debug(f"Guest stderr: {stderr}")
                return 0

            # If return code is non-zero, check for definite errors
            if stdout:
                logger.debug(f"Guest stdout: {stdout}")
            if stderr:
                logger.debug(f"Guest stderr: {stderr}")

            # Some versions of vmrun print "Error:" to stdout
            is_definitely_error = ("Error:" in stdout) or ("错误" in stdout) or ("失败" in stdout)
            
            if is_definitely_error:
                raise VMOperationError(f"Guest program failed with error: stdout={stdout if stdout else 'None'}, stderr={stderr if stderr else 'None'}")
            
            logger.warning(f"Guest program returned non-zero exit code: {rc}")
            return rc

        try:
            return self._retry_with_backoff(
                _run_operation, 
                max_attempts=max_attempts, 
                operation_name=f"run {program_path}"
            )
        except VMOperationError:
            # If all retries failed, return error code instead of raising
            logger.error(f"Guest program execution failed after {max_attempts} attempts")
            return -1

    def _run_vmrun(self, args: List[str], timeout: int = 120):
        """Run vmrun command with timeout and error handling."""
        def _vmrun_operation():
            proc = subprocess.run(
                [self.vmrun_path] + args,
                capture_output=True,
                text=False,
                timeout=timeout,
                shell=False,
            )
            
            def _decode(b: bytes) -> str:
                if not b: 
                    return ""
                try:
                    return b.decode("utf-8")
                except UnicodeDecodeError:
                    return b.decode("mbcs", errors="replace")
            
            stdout = _decode(proc.stdout)
            stderr = _decode(proc.stderr)
            
            if proc.returncode != 0:
                raise VMOperationError(f"vmrun failed: {stderr}")
            
            return proc.returncode, stdout, stderr
        
        try:
            return self._retry_with_backoff(
                _vmrun_operation, 
                max_attempts=3, 
                operation_name=f"vmrun {' '.join(args[:2])}"
            )
        except VMTimeoutError:
            raise VMTimeoutError(f"vmrun command timed out after {timeout} seconds")
    
    def copy_to_guest(self, host_path: str, guest_path: str) -> None:
        """Copy file to guest with retry logic."""
        def _copy_operation():
            args = [
                "-T", "ws",
                "-gu", self.config.guest_username,
                "-gp", self.config.guest_password,
                "CopyFileFromHostToGuest",
                self.vmx_path,
                host_path,
                guest_path,
            ]
            self._update_status(f"Copying to guest: {host_path} -> {guest_path}")
            returncode, stdout, stderr = self._run_vmrun(args, timeout=60)
            self._update_status("File copied to guest successfully")
            return True
        
        self._retry_with_backoff(_copy_operation, max_attempts=3, operation_name="copy to guest")
    
    def copy_from_guest(self, guest_path: str, host_path: str) -> None:
        """Copy file from guest VM to host with retry logic."""
        def _copy_operation():
            args = [
                "-T", "ws",
                "-gu", self.config.guest_username,
                "-gp", self.config.guest_password,
                "CopyFileFromGuestToHost",
                self.vmx_path,
                guest_path,
                host_path,
            ]
            
            self._update_status(f"Copying from guest: {guest_path} -> {host_path}")
            returncode, stdout, stderr = self._run_vmrun(args, timeout=60)
            self._update_status("File copied from guest successfully")
            return True
        
        self._retry_with_backoff(_copy_operation, max_attempts=3, operation_name="copy from guest")
    
    def can_revert_snapshot(self, name: str) -> bool:
        """Quick check if snapshot revert is possible without actually doing it."""
        try:
            self._update_status(f"Checking if snapshot '{name}' exists...")
            
            # First check if vmrun is accessible
            returncode, stdout, stderr = self._run_vmrun(["-T", "ws", "listSnapshots", self.vmx_path], timeout=10)
            
            # Check if our target snapshot exists in the output
            snapshot_exists = name in stdout
            if not snapshot_exists:
                logger.info(f"Snapshot '{name}' not found in VM. Available snapshots:")
                for line in stdout.strip().split('\n'):
                    if line.strip():
                        logger.info(f"  - {line.strip()}")
            else:
                self._update_status(f"Snapshot '{name}' found and ready for revert")
            
            return snapshot_exists
            
        except Exception as e:
            logger.warning(f"Cannot check snapshots: {e}")
            return False

    def revert_snapshot(self, name: str) -> None:
        """Revert VM to specified snapshot with enhanced error handling."""
        def _revert_operation():
            # Quick pre-check to avoid long waits
            if not self.can_revert_snapshot(name):
                raise VMOperationError(f"Snapshot '{name}' not found in VM")
            
            # Now do the actual revert
            args = ["-T", "ws", "revertToSnapshot", self.vmx_path, name]
            self._update_status(f"Reverting to snapshot: {name}")
            
            returncode, stdout, stderr = self._run_vmrun(args, timeout=120)
            self._update_status("Snapshot reverted, starting VM...")
            self.start(fullscreen=True)
            self._update_status("✓ Snapshot reverted and VM started successfully")
            return True
        
        self._retry_with_backoff(_revert_operation, max_attempts=2, operation_name="snapshot revert")
    
    def stop(self) -> None:
        """Stop the virtual machine with retry logic."""
        def _stop_operation():
            args = ["-T", "ws", "stop", self.vmx_path, "soft"]
            
            self._update_status("Stopping VM (soft stop)...")
            
            try:
                returncode, stdout, stderr = self._run_vmrun(args, timeout=60)
                self._update_status("VM stopped successfully")
                return True
            except VMOperationError:
                # Try hard stop
                self._update_status("Soft stop failed, trying hard stop...")
                args[-1] = "hard"
                returncode, stdout, stderr = self._run_vmrun(args, timeout=30)
                self._update_status("VM stopped successfully (hard stop)")
                return True
        
        try:
            self._retry_with_backoff(_stop_operation, max_attempts=2, operation_name="VM stop")
        except VMOperationError:
            logger.warning("VM stop failed, but continuing...")
    
    def is_running(self) -> bool:
        """Check if the VM is currently running with timeout."""
        try:
            args = ["list"]
            returncode, stdout, stderr = self._run_vmrun(args, timeout=30)
            vm_list = stdout.strip()
            
            # Use normalized path for comparison
            norm_vmx = os.path.normpath(self.vmx_path)
            if norm_vmx in vm_list or norm_vmx.replace('\\', '/') in vm_list:
                return True
            base = os.path.basename(norm_vmx)
            return (base in vm_list) or (norm_vmx.lower() in vm_list.lower())
            
        except Exception as e:
            logger.warning(f"Failed to check VM status: {e}")
            return False
    
    def ensure_guest_dir(self, path: str) -> None:
        """Ensure a directory exists in the guest VM with retry logic."""
        def _ensure_dir_operation():
            ps = f"New-Item -ItemType Directory -Force -Path '{path}'"
            self.run_in_guest(
                "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe",
                ["-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
                interactive=False, nowait=False
            )
            return True
        
        self._retry_with_backoff(_ensure_dir_operation, max_attempts=2, operation_name=f"create directory {path}")
    
    def _wait_for_vm_ready(self) -> None:
        """Wait for VM to be fully ready for operations with status updates."""
        self._update_status("Waiting for VM to be fully ready...")
        max_attempts = 15

        for attempt in range(1, max_attempts + 1):
            try:
                self._update_status(f"Checking VM readiness ({attempt}/{max_attempts})...")
                args = [
                    "-T","ws","-gu",self.config.guest_username,"-gp",self.config.guest_password,
                    "runProgramInGuest", self.vmx_path, "cmd.exe","/c","echo","test"
                ]
                rc, stdout, stderr = self._run_vmrun(args, timeout=5)
                self._update_status("✓ VM is ready for operations")
                return
            except Exception:
                if attempt < max_attempts:
                    time.sleep(1)
        
        self._update_status("VM readiness check completed (proceeding with operations)")
    
    def _wait_for_user_login(self, timeout: int = 60) -> bool:
        """Wait for user to login to the VM with enhanced progress reporting."""
        import time
        from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeRemainingColumn
        
        self._update_status(f"Waiting up to {timeout} seconds for user login...")
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]Waiting for user login..."),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeRemainingColumn(),
            console=logger.console if hasattr(logger, 'console') else None
        ) as progress:
            
            task = progress.add_task("Login detection", total=timeout)
            
            for elapsed in range(timeout):
                # Check if user has logged in
                if self.test_guest_access():
                    progress.update(task, completed=timeout)
                    self._update_status(f"✓ User login detected after {elapsed + 1} seconds!")
                    return True
                
                # Update progress bar and status
                progress.update(task, advance=1)
                if elapsed % 10 == 0 and elapsed > 0:
                    self._update_status(f"Still waiting for login... ({elapsed}/{timeout}s)")
            
            self._update_status(f"✗ No user login detected after {timeout} seconds")
            return False
    
    def test_guest_access(self) -> bool:
        """Test if we can access the guest VM (i.e., if it's logged in) with timeout."""
        try:
            args = [
                "-T", "ws", 
                "-gu", self.config.guest_username, 
                "-gp", self.config.guest_password,
                "listProcessesInGuest", 
                self.vmx_path
            ]
            returncode, stdout, stderr = self._run_vmrun(args, timeout=10)
            return True
        except Exception:
            return False