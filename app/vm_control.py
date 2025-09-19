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
                time.sleep(3)
                
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
                
                # Wait for user to login with progress bar
                if self._wait_for_user_login(timeout=60):
                    logger.info("User login detected! Proceeding with task...")
                    # Ensure fullscreen mode after login
                    time.sleep(2)
                    self.ensure_fullscreen()
                else:
                    logger.warning("User login not detected within 60 seconds")
                    logger.info("Proceeding anyway - you may need to login manually")
                
            except FileNotFoundError:
                raise RuntimeError(f"VMware executable not found: {cmd[0]}")
        else:
            # Use vmrun start for normal mode - this returns when VM is started
            cmd = [self.vmrun_path, "start", self.vmx_path]
            logger.info("Starting VM in normal mode")
            
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
                if result.returncode != 0:
                    raise RuntimeError(f"Failed to start VM: {result.stderr}")
                logger.info("VM started successfully in normal mode")
                
                # Wait for user to login with progress bar
                if self._wait_for_user_login(timeout=60):
                    logger.info("User login detected! Proceeding with task...")
                else:
                    logger.warning("User login not detected within 60 seconds")
                    logger.info("Proceeding anyway - you may need to login manually")
                    
            except subprocess.TimeoutExpired:
                raise RuntimeError("VM start timed out after 60 seconds")
            except FileNotFoundError:
                raise RuntimeError(f"VMware executable not found: {cmd[0]}")
    
    def run_in_guest(self, program_path: str, args: List[str] = None, 
                     interactive: bool = False, workdir: Optional[str] = None) -> int:
        """Run a program in the guest VM.
        
        Args:
            program_path: Path to the program in the guest OS
            args: Command line arguments
            interactive: Whether to run interactively
            workdir: Working directory in guest OS
            
        Returns:
            Return code of the executed program
        """
        if args is None:
            args = []
        
        cmd = [
            self.vmrun_path, "-T", "ws", 
            "-gu", self.config.guest_username, 
            "-gp", self.config.guest_password,
            "runProgramInGuest", self.vmx_path, program_path
        ] + args
        
        if interactive:
            cmd.insert(-len(args)-2, "-interactive")
        
        if workdir:
            cmd.extend(["-activeWindow", "-workingDirectory", workdir])
        
        logger.info(f"Running in guest: {program_path} {' '.join(args)}")
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            logger.info(f"Guest program finished with return code: {result.returncode}")
            if result.stdout:
                logger.debug(f"Guest stdout: {result.stdout}")
            if result.stderr:
                logger.debug(f"Guest stderr: {result.stderr}")
            return result.returncode
        except subprocess.TimeoutExpired:
            logger.error("Guest program execution timed out")
            return -1
        except Exception as e:
            logger.error(f"Error running guest program: {e}")
            return -1
    
    def copy_to_guest(self, host_path: str, guest_path: str) -> None:
        """Copy file from host to guest VM."""
        cmd = [
            self.vmrun_path, "-T", "ws",
            "-gu", self.config.guest_username,
            "-gp", self.config.guest_password,
            "copyFileFromHostToGuest", self.vmx_path, host_path, guest_path
        ]
        
        logger.info(f"Copying to guest: {host_path} -> {guest_path}")
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if result.returncode != 0:
                raise RuntimeError(f"Failed to copy to guest: {result.stderr}")
            logger.info("File copied to guest successfully")
        except subprocess.TimeoutExpired:
            raise RuntimeError("Copy to guest timed out")
    
    def copy_from_guest(self, guest_path: str, host_path: str) -> None:
        """Copy file from guest VM to host."""
        cmd = [
            self.vmrun_path, "-T", "ws",
            "-gu", self.config.guest_username,
            "-gp", self.config.guest_password,
            "copyFileFromGuestToHost", self.vmx_path, guest_path, host_path
        ]
        
        logger.info(f"Copying from guest: {guest_path} -> {host_path}")
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if result.returncode != 0:
                raise RuntimeError(f"Failed to copy from guest: {result.stderr}")
            logger.info("File copied from guest successfully")
        except subprocess.TimeoutExpired:
            raise RuntimeError("Copy from guest timed out")
    
    def can_revert_snapshot(self, name: str) -> bool:
        """Quick check if snapshot revert is possible without actually doing it."""
        # First check if vmrun is accessible
        try:
            test_result = subprocess.run([self.vmrun_path, "-T", "ws", "list"], 
                                       capture_output=True, text=True, timeout=3)
            if test_result.returncode != 0:
                return False
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False
        
        # Quick test to see if we can list snapshots (this will fail fast if encrypted)
        try:
            list_cmd = [self.vmrun_path, "-T", "ws", "listSnapshots", self.vmx_path]
            result = subprocess.run(list_cmd, capture_output=True, text=True, timeout=5)
            
            if result.returncode != 0:
                error_msg = result.stderr.lower()
                if "encrypted" in error_msg or "password" in error_msg:
                    logger.info("VM is encrypted, snapshot operations not available")
                    return False
                elif "not found" in error_msg:
                    logger.info("VM file not found")
                    return False
                return False
            
            # Check if the specific snapshot exists
            if name in result.stdout:
                return True
            else:
                logger.info(f"Snapshot '{name}' not found in available snapshots")
                return False
                
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
        cmd = [self.vmrun_path, "-T", "ws", "revertToSnapshot", self.vmx_path, name]
        logger.info(f"Reverting to snapshot: {name}")
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            if result.returncode == 0:
                logger.info("Snapshot reverted successfully")
            else:
                logger.warning(f"Snapshot revert failed: {result.stderr}")
        except subprocess.TimeoutExpired:
            logger.warning("Snapshot revert timed out")
    
    def stop(self) -> None:
        """Stop the virtual machine."""
        cmd = [
            self.vmrun_path, "-T", "ws",
            "stop", self.vmx_path, "soft"
        ]
        
        logger.info("Stopping VM")
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if result.returncode != 0:
                logger.warning(f"Soft stop failed: {result.stderr}, trying hard stop")
                # Try hard stop
                cmd[-1] = "hard"
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            logger.info("VM stopped successfully")
        except subprocess.TimeoutExpired:
            logger.warning("VM stop timed out")
    
    def is_running(self) -> bool:
        """Check if the VM is currently running."""
        cmd = [self.vmrun_path, "list"]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode != 0:
                logger.warning(f"Failed to list VMs: {result.stderr}")
                return False
            
            # Debug: show what vmrun list returns
            logger.debug(f"vmrun list output: {result.stdout}")
            logger.debug(f"Looking for VM path: {self.vmx_path}")
            
            # Check if our VM is in the list - try multiple comparison methods
            vm_list = result.stdout.strip()
            
            # Method 1: Direct path match
            if self.vmx_path in vm_list:
                logger.debug("VM found via direct path match")
                return True
            
            # Method 2: Normalize paths and compare
            import os
            normalized_path = os.path.normpath(self.vmx_path).replace('\\', '/')
            if normalized_path in vm_list:
                logger.debug("VM found via normalized path match")
                return True
            
            # Method 3: Check if any line contains the VM name
            vm_name = os.path.basename(self.vmx_path)
            if vm_name in vm_list:
                logger.debug("VM found via filename match")
                return True
            
            # Method 4: Case-insensitive check
            if self.vmx_path.lower() in vm_list.lower():
                logger.debug("VM found via case-insensitive match")
                return True
            
            logger.debug("VM not found in running list")
            return False
            
        except subprocess.TimeoutExpired:
            logger.warning("VM list command timed out")
            return False
        except Exception as e:
            logger.warning(f"Error checking VM status: {e}")
            return False
    
    def ensure_guest_dir(self, path: str) -> None:
        """Ensure a directory exists in the guest VM."""
        powershell_cmd = f"New-Item -ItemType Directory -Force -Path '{path}'"
        self.run_in_guest("powershell.exe", ["-Command", powershell_cmd])
    
    def _wait_for_vm_ready(self) -> None:
        """Wait for VM to be fully ready for operations."""
        logger.info("Waiting for VM to be fully ready...")
        max_attempts = 15  # Reduced to 15 seconds
        
        for attempt in range(max_attempts):
            try:
                logger.debug(f"Attempt {attempt + 1}/{max_attempts} to check VM readiness")
                
                # Try to run a simple command to check if VM is responsive
                result = subprocess.run([
                    self.vmrun_path, "-T", "ws",
                    "-gu", self.config.guest_username,
                    "-gp", self.config.guest_password,
                    "runProgramInGuest", self.vmx_path,
                    "cmd.exe", "/c", "echo", "test"
                ], capture_output=True, text=True, timeout=5)  # Reduced timeout
                
                if result.returncode == 0:
                    logger.info("VM is ready for operations")
                    return
                else:
                    logger.debug(f"VM not ready yet, error: {result.stderr}")
                    
            except subprocess.TimeoutExpired:
                logger.debug("VM readiness check timed out")
            except Exception as e:
                logger.debug(f"VM readiness check failed: {e}")
            
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
        logger.info("Please login to the VM manually when you see the login screen")
        
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
                    logger.info(f"✓ User login detected after {elapsed + 1} seconds!")
                    return True
                
                # Update progress bar
                progress.update(task, advance=1)
                time.sleep(1)
            
            logger.warning(f"✗ No user login detected after {timeout} seconds")
            return False
    
    def _attempt_auto_login(self) -> None:
        """Attempt to automatically login to the guest VM."""
        logger.info("Attempting automatic login to guest VM")
        
        try:
            # Wait for login screen to appear
            logger.info("Waiting for login screen to appear...")
            time.sleep(5)
            
            # Try different login methods for Windows 11
            login_successful = False
            
            # Method 1: Try clicking on screen and entering password (Windows 11 style)
            logger.info("Method 1: Trying Windows 11 click-and-password login...")
            self._send_keys_to_vm("space")  # Wake up screen
            time.sleep(1)
            self._send_keys_to_vm("Return")  # Click on user
            time.sleep(2)
            self._send_keys_to_vm(self.config.guest_password)
            self._send_keys_to_vm("Return")
            time.sleep(3)
            
            if self.test_guest_access():
                logger.info("Method 1 successful!")
                login_successful = True
            else:
                # Method 2: Try traditional username/password
                logger.info("Method 1 failed, trying Method 2: Traditional login...")
                self._send_keys_to_vm("ctrl+alt+Delete")  # Secure login
                time.sleep(2)
                self._send_keys_to_vm(self.config.guest_username)
                self._send_keys_to_vm("Tab")
                self._send_keys_to_vm(self.config.guest_password)
                self._send_keys_to_vm("Return")
                time.sleep(5)
                
                if self.test_guest_access():
                    logger.info("Method 2 successful!")
                    login_successful = True
            
            if not login_successful:
                logger.warning("Auto-login failed with both methods")
                logger.info("Recommendation: Configure VM for auto-login or login manually")
                logger.info("VM is running and ready for manual interaction")
                
        except Exception as e:
            logger.warning(f"Auto-login attempt failed: {e}")
            logger.info("You may need to manually login to the VM")
    
    def _send_keys_to_vm(self, keys: str) -> None:
        """Send keystrokes directly to the VM using vmrun."""
        try:
            # Use vmrun's sendKeystrokes command
            cmd = [
                self.vmrun_path, "-T", "ws",
                "sendKeystrokes", self.vmx_path, keys
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if result.returncode != 0:
                logger.debug(f"Failed to send keys '{keys}': {result.stderr}")
            else:
                logger.debug(f"Successfully sent keys: {keys}")
                
            # Small delay between keystrokes
            time.sleep(0.5)
            
        except Exception as e:
            logger.debug(f"Error sending keys '{keys}': {e}")
    
    def test_guest_access(self) -> bool:
        """Test if we can access the guest VM (i.e., if it's logged in)."""
        try:
            result = subprocess.run([
                self.vmrun_path, "-T", "ws",
                "-gu", self.config.guest_username,
                "-gp", self.config.guest_password,
                "runProgramInGuest", self.vmx_path,
                "cmd.exe", "/c", "echo", "access_test"
            ], capture_output=True, text=True, timeout=10)
            
            return result.returncode == 0
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
