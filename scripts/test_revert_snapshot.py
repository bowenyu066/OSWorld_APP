import subprocess
import time
import shlex
import os

VMRUN = r"C:\Program Files (x86)\VMware\VMware Workstation\vmrun.exe"
VMX   = r"E:\Virtual Machines\Windows 11 x64\Windows 11 x64 (2).vmx"

# 来宾系统里的账户与密码（用于在来宾内执行程序）
GUEST_USER = "user"
GUEST_PASS = "password"

VM_ENCRYPT_PASS = os.environ.get("VM_VMX_PASSWORD")