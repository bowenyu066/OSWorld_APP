"""
Used to test running softwares after the system has fully booted.

Currently, the main issue is that we don't know exactly when the system would be able to
run softwares, even though the interactive login has been successfully established. This
script is used to test such timing: we start the VM, wait for the system to fully boot,
and then try to run a software for every 5 seconds repeatedly until it works.
"""

import subprocess
import time
import shlex
import os
from test_basic_start_and_running import *

VMRUN = r"C:\Program Files (x86)\VMware\VMware Workstation\vmrun.exe"
VMX   = r"E:\Virtual Machines\Windows 11 x64\Windows 11 x64 (2).vmx"

GUEST_USER = "user"
GUEST_PASS = "password"

VM_ENCRYPT_PASS = os.environ.get("VM_VMX_PASSWORD")

if __name__ == "__main__":
    # print("====== VM starting ======")
    # time_1 = time.time()
    # start_vm(gui=True)
    # time_2 = time.time()
    # print(f"====== VM started in {time_2 - time_1:.2f} seconds ======")

    # print("====== Waiting for VMware Tools ======")
    # wait_for_tools(timeout=300)
    # time_3 = time.time()
    # print(f"====== VMware Tools started in {time_3 - time_2:.2f} seconds ======")
    
    # print("====== Waiting for user login in 120 seconds ... ======")
    # time.sleep(120)
    has_interactive = check_interactive_session()
    print(f"Interactive session status: {'Available' if has_interactive else 'Not available'}")
    print(f"====== User login in 120 seconds ======")

    if has_interactive:
        print("====== Trying to run software in guest ======")
        for idx in range(1):
            start_time = time.time()
            try:
                run_in_guest(r"C:\Windows\System32\notepad.exe", interactive=True, nowait=True)
                end_time = time.time()
                print(f"====== Software run in guest in {end_time - start_time:.2f} seconds ======")
            except subprocess.CalledProcessError as e:
                print(f"====== Software run in guest failed at attempt {idx + 1} ======")
                print(f"Error: {e}")
            finally:
                end_time = time.time()
                if end_time - start_time < 10:
                    time.sleep(10 - (end_time - start_time))
        print("====== Software run in guest ======")

    else:
        print("====== No interactive session available ======")

    