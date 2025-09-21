"""VMware virtual machine control via vmrun and vmware.exe."""

import os
import subprocess
import time
from pathlib import Path
from typing import List, Optional
from .config import config_manager
from .logging_setup import get_logger

logger = get_logger(__name__)


class VMController:
    """Controls VMware virtual machines using vmrun and vmware.exe."""
    
    def __init__(self):
        self.config = config_manager.config
        self.vmrun_path = config_manager.get_vmrun_path()
        self.vmware_path = config_manager.get_vmware_path()
        self.vmx_path = self.config.vmx_path
        self.vmrun_path = os.path.normpath(self.vmrun_path)
        self.vmware_path = os.path.normpath(self.vmware_path)
        self.vmx_path = os.path.normpath(self.vmx_path)
    
    def start(self, fullscreen: bool = True) -> None:
        """Start the virtual machine.
        
        Args:
            fullscreen: If True, start in fullscreen mode using vmware.exe -X
                       If False, start normally using vmrun start
        """
        logger.info(f"Starting VM: {self.vmx_path}")
        
        if fullscreen:
            # Use vmware.exe -X for fullscreen mode - this doesn't return immediately
            cmd = [self.vmware_path, "-X", self.vmx_path]
            logger.info("Starting VM in fullscreen mode")
            
            try:
                # Start the process without waiting for it to complete
                process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                logger.info("VM fullscreen process started")
                
                # Wait a bit and check if VM is running
                logger.info("Checking if VM started successfully...")
                time.sleep(10)
                
                if not self.is_running():
                    # Check if process failed immediately
                    poll_result = process.poll()
                    if poll_result is not None and poll_result != 0:
                        _, stderr = process.communicate()
                        raise RuntimeError(f"Failed to start VM: {stderr.decode()}")
                    
                    # Wait a bit more for VM to start
                    logger.info("VM not detected yet, waiting longer...")
                    time.sleep(10)
                    
                    if not self.is_running():
                        logger.warning("VM not detected by vmrun list, but vmware process is running")
                        logger.info("This might be normal - VM could still be starting up")
                        logger.info("Proceeding with assumption that VM is starting...")
                    else:
                        logger.info("VM detected on second check!")
                else:
                    logger.info("VM detected on first check!")
                
                logger.info("VM started successfully in fullscreen mode")

                time.sleep(60) # Wait until user logs in; TODO: make a progress bar
                
                # Wait for user to login with progress bar
                if self._wait_for_user_login(timeout=10):
                    logger.info("User login detected! Proceeding with task...")
                    # Ensure fullscreen mode after login
                    time.sleep(2)
                    # self.ensure_fullscreen()
                else:
                    logger.warning("User login not detected within 10 detection attempts")
                    logger.info("Proceeding anyway - you may need to login manually")
                
            except FileNotFoundError:
                raise RuntimeError(f"VMware executable not found: {cmd[0]}")
        else:
            # Use vmrun start for normal mode - this returns when VM is started
            cmd = [self.vmrun_path, "start", self.vmx_path]
            logger.info("Starting VM in normal mode")
            
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                if result.returncode != 0:
                    raise RuntimeError(f"Failed to start VM: {result.stderr}")
                logger.info("VM started successfully in normal mode")
                
                # Wait for user to login with progress bar
                if self._wait_for_user_login(timeout=10):
                    logger.info("User login detected! Proceeding with task...")
                else:
                    logger.warning("User login not detected within 10 detection attempts")
                    logger.info("Proceeding anyway - you may need to login manually")
                    
            except subprocess.TimeoutExpired:
                raise RuntimeError("VM start timed out after 10 detection attempts")
            except FileNotFoundError:
                raise RuntimeError(f"VMware executable not found: {cmd[0]}")
    
    def run_in_guest(self, program_path: str, args: List[str] = None, 
                 interactive: bool = True, nowait: bool = True, 
                 workdir: Optional[str] = None, max_attempts: int = 10) -> int:
        if args is None:
            args = []

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

        logger.info(f"Running in guest: {program_path} {' '.join(args)}")
        logger.debug("> " + " ".join(_q(x) for x in cmd))

        # Instead of text=True, we capture bytes and decode manually
        for attempt in range(1, max_attempts + 1):
            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=False,                # capture bytes
                    timeout=60,
                    shell=False,
                )
            except subprocess.TimeoutExpired:
                logger.error("Guest program execution timed out")
                return -1
            except Exception as e:
                logger.error(f"Error running guest program: {e}")
                return -1

            # Manually decode bytes, first try utf-8, then mbcs as fallback
            def _decode(b: bytes) -> str:
                if not b:
                    return ""
                try:
                    return b.decode("utf-8")
                except UnicodeDecodeError:
                    # Windows local code page (Chinese usually cp936)
                    return b.decode("mbcs", errors="replace")

            stdout = _decode(result.stdout)
            stderr = _decode(result.stderr)

            # First check return code
            rc = result.returncode
            # vmrun fails sometimes with -1 (unsigned shows 4294967295)
            if rc == 0:
                if stdout:
                    logger.debug(f"Guest stdout: {stdout}")
                if stderr:
                    logger.debug(f"Guest stderr: {stderr}")
                logger.info(f"Attempt {attempt}: success (rc=0)")
                return 0

            # If return code is non-zero, log details and check stdout for error keywords
            if stdout:
                logger.debug(f"Guest stdout: {stdout}")
            if stderr:
                logger.debug(f"Guest stderr: {stderr}")

            # Some versions of vmrun print "Error:" to stdout
            is_definitely_error = ("Error:" in stdout) or ("错误" in stdout) or ("失败" in stdout)

            logger.warning(f"Attempt {attempt}: non-zero return code {rc}"
                        + (" (error text in stdout)" if is_definitely_error else ""))

            if attempt < max_attempts:
                time.sleep(5)
                logger.info("Retrying guest program in 5 seconds...")
            else:
                logger.debug(f"Guest program execution failed after {max_attempts} attempts")
                return rc if rc != 0 else -1

    def _run_vmrun(self, args: List[str], timeout: int = 120):
        proc = subprocess.run(
            [self.vmrun_path] + args,
            capture_output=True,
            text=False,            # bytes!
            timeout=timeout,
            shell=False,
        )
        def _decode(b: bytes) -> str:
            if not b: return ""
            try:
                return b.decode("utf-8")
            except UnicodeDecodeError:
                return b.decode("mbcs", errors="replace")
        stdout = _decode(proc.stdout)
        stderr = _decode(proc.stderr)
        return proc.returncode, stdout, stderr
    
    def copy_to_guest(self, host_path: str, guest_path: str) -> None:
        args = [
            "-T", "ws",
            "-gu", self.config.guest_username,
            "-gp", self.config.guest_password,
            "CopyFileFromHostToGuest",
            self.vmx_path,
            host_path,
            guest_path,
        ]
        logger.info(f"Copying to guest: {host_path} -> {guest_path}")
        returncode, stdout, stderr = self._run_vmrun(args, timeout=60)
        if returncode != 0:
            raise RuntimeError(f"Failed to copy to guest: stdout={stdout}, stderr={stderr}")
        logger.info("File copied to guest successfully")

    
    def copy_from_guest(self, guest_path: str, host_path: str) -> None:
        """Copy file from guest VM to host."""
        args = [
            "-T", "ws",
            "-gu", self.config.guest_username,
            "-gp", self.config.guest_password,
            "CopyFileFromGuestToHost",
            self.vmx_path,
            guest_path,
            host_path,
        ]
        
        logger.info(f"Copying from guest: {guest_path} -> {host_path}")
        
        try:
            returncode, stdout, stderr = self._run_vmrun(args, timeout=60)
            if returncode != 0:
                raise RuntimeError(f"Failed to copy from guest: stdout={stdout}, stderr={stderr}")
            logger.info("File copied from guest successfully")
        except subprocess.TimeoutExpired:
            raise RuntimeError("Copy from guest timed out")
    
    def can_revert_snapshot(self, name: str) -> bool:
        """Quick check if snapshot revert is possible without actually doing it."""
        # First check if vmrun is accessible
        try:
            returncode, stdout, stderr = self._run_vmrun(["-T", "ws", "listSnapshots", self.vmx_path], timeout=3)
            if returncode != 0:
                return False
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False
        
        # Quick test to see if we can list snapshots (this will fail fast if encrypted)
        try:
            returncode, stdout, stderr = self._run_vmrun(["-T", "ws", "listSnapshots", self.vmx_path], timeout=5)
            
            if returncode != 0:
                error_msg = (stderr or "").lower()
                if "encrypted" in error_msg or "password" in error_msg:
                    logger.info("VM is encrypted, snapshot operations not available")
                    return False
                elif "not found" in error_msg:
                    logger.info("VM file not found")
                    return False
                return name in stdout
        except subprocess.TimeoutExpired:
            logger.info("Snapshot list timed out")
            return False
        except Exception as e:
            logger.info(f"Cannot check snapshots: {e}")
            return False

    def revert_snapshot(self, name: str) -> None:
        """Revert VM to specified snapshot."""
        logger.info(f"Checking if snapshot revert is possible...")
        
        # Quick pre-check to avoid long waits
        if not self.can_revert_snapshot(name):
            logger.info("Snapshot revert not possible or not needed, skipping")
            return
        
        # If VM is running, stop it first
        if self.is_running():
            logger.info("VM is running, stopping before snapshot revert")
            self.stop()
            time.sleep(2)
        
        # Now do the actual revert (we know it should work)
        args = ["-T", "ws", "revertToSnapshot", self.vmx_path, name]
        logger.info(f"Reverting to snapshot: {name}")
        
        try:
            returncode, stdout, stderr = self._run_vmrun(args, timeout=15)
            if returncode == 0:
                logger.info("Snapshot reverted successfully")
            else:
                logger.warning(f"Snapshot revert failed: {stderr}")
        except subprocess.TimeoutExpired:
            logger.warning("Snapshot revert timed out")
        except Exception as e:
            logger.warning(f"Snapshot revert failed: {e}")
    
    def stop(self) -> None:
        """Stop the virtual machine."""
        args = ["-T", "ws", "stop", self.vmx_path, "soft"]
        
        logger.info("Stopping VM")
        
        try:
            returncode, stdout, stderr = self._run_vmrun(args, timeout=60)
            if returncode != 0:
                logger.warning(f"Soft stop failed: {stderr}, trying hard stop")
                # Try hard stop
                args[-1] = "hard"
                returncode, stdout, stderr = self._run_vmrun(args, timeout=30)
            logger.info("VM stopped successfully")
        except subprocess.TimeoutExpired:
            logger.warning("VM stop timed out")
        except Exception as e:
            logger.warning(f"VM stop failed: {e}")
    
    def is_running(self) -> bool:
        """Check if the VM is currently running."""
        args = ["list"]
        returncode, stdout, stderr = self._run_vmrun(args, timeout=30)
        if returncode != 0:
            logger.warning(f"Failed to list VMs: {stderr}")
            return False
        vm_list = stdout.strip()
        # Use normalized path for comparison
        norm_vmx = os.path.normpath(self.vmx_path)
        if norm_vmx in vm_list or norm_vmx.replace('\\', '/') in vm_list:
            return True
        base = os.path.basename(norm_vmx)
        return (base in vm_list) or (norm_vmx.lower() in vm_list.lower())

    
    def ensure_guest_dir(self, path: str) -> None:
        """Ensure a directory exists in the guest VM."""
        ps = f"New-Item -ItemType Directory -Force -Path '{path}'"
        self.run_in_guest(
            "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe",
            ["-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
            interactive=False, nowait=False
        )
    
    def _wait_for_vm_ready(self) -> None:
        """Wait for VM to be fully ready for operations."""
        logger.info("Waiting for VM to be fully ready...")
        max_attempts = 15  # Reduced to 15 seconds

        for _ in range(max_attempts):
            try:
                args = [
                    "-T","ws","-gu",self.config.guest_username,"-gp",self.config.guest_password,
                    "runProgramInGuest", self.vmx_path, "cmd.exe","/c","echo","test"
                ]
                rc, stdout, stderr = self._run_vmrun(args, timeout=5)
                if rc == 0:
                    logger.info("VM is ready for operations")
                    return
            except subprocess.TimeoutExpired:
                pass
            time.sleep(1)
        
        logger.info("VM readiness check timed out, but VM is running. Proceeding anyway...")
        logger.info("Note: You may need to manually login to the VM for full functionality")
    
    def _wait_for_user_login(self, timeout: int = 60) -> bool:
        """Wait for user to login to the VM with a progress bar.
        
        Args:
            timeout: Maximum time to wait in seconds
            
        Returns:
            True if user login detected, False if timeout
        """
        import time
        from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeRemainingColumn
        
        logger.info(f"Waiting up to {timeout} seconds for user to login to VM...")
        # logger.info("Please login to the VM manually when you see the login screen")
        
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
                    logger.info(f"✓ User login detected after {elapsed + 1} detection attempts!")
                    return True
                
                # Update progress bar
                progress.update(task, advance=1)
                # time.sleep(1)
            
            logger.warning(f"✗ No user login detected after {timeout} detection attempts")
            return False
    
    # Auto-login functionality removed - VM configured with auto-login software instead
    
    def test_guest_access(self) -> bool:
        """Test if we can access the guest VM (i.e., if it's logged in)."""
        try:
            args = [
                "-T", "ws", 
                "-gu", self.config.guest_username, 
                "-gp", self.config.guest_password,
                "listProcessesInGuest", 
                self.vmx_path
            ]
            returncode, stdout, stderr = self._run_vmrun(args)
            return returncode == 0
        except:
            return False
    
    def ensure_fullscreen(self) -> None:
        """Ensure VM is in fullscreen mode by sending fullscreen hotkey."""
        try:
            # Send Ctrl+Alt+Enter to toggle fullscreen using vmrun sendKeystrokes
            logger.info("Sending fullscreen toggle hotkey (Ctrl+Alt+Enter)")
            self._send_keys_to_vm("ctrl+alt+Return")
            
        except Exception as e:
            logger.warning(f"Failed to ensure fullscreen mode: {e}")
