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

def run(cmd):
    # 小工具：同步执行并打印输出，便于调试
    print(">", " ".join(f'"{arg}"' if " " in arg else arg for arg in cmd))
    print("Debug - Raw command list:", cmd)
    
    # 尝试多种编码方式来正确显示中文错误信息
    encodings_to_try = ["utf-8", "gbk", "gb2312", "mbcs"]
    result = None
    
    # for encoding in encodings_to_try:
    #     try:
    #         result = subprocess.run(cmd, capture_output=True, text=True, encoding=encoding, errors="replace")
    #         # 检查输出是否包含可读的中文字符
    #         if result.stdout and not any(ord(c) > 65535 for c in result.stdout):
    #             break
    #         if result.stderr and not any(ord(c) > 65535 for c in result.stderr):
    #             break
    #     except:
    #         continue
    
    # if result is None:
    #     # 如果所有编码都失败，使用默认的mbcs
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="mbcs", errors="replace")
    
    if result.stdout:
        print("STDOUT:", result.stdout.strip())
    if result.stderr:
        print("STDERR:", result.stderr.strip())
    print("Return code:", result.returncode)
    result.check_returncode()
    return result

def start_vm(gui=False):
    # 启动 VM
    # - nogui：后台启动；不写则带 GUI
    args = [VMRUN, "-T", "ws", "start", VMX]
    if not gui:
        args.append("nogui")
    if VM_ENCRYPT_PASS:
        args += ["-vp", VM_ENCRYPT_PASS]
    run(args)

def wait_for_tools(timeout=300):
    # 等待 VMware Tools 运行就绪（来宾系统基本可用）
    # 简单轮询：checkToolsState -> 'running' 表示就绪
    t0 = time.time()
    while True:
        out = subprocess.run([VMRUN, "-T", "ws", "checkToolsState", VMX],
                             capture_output=True, text=True)
        state = (out.stdout or out.stderr or "").strip().lower()
        if "running" in state:
            print("VMware Tools is running.")
            return True
        if time.time() - t0 > timeout:
            raise TimeoutError("Waited too long for VMware Tools.")
        time.sleep(3)

def run_in_guest(program, args=None, interactive=False, nowait=True):
    # 在来宾内启动程序（需要 VMware Tools + 来宾凭证）
    # -interactive 需要来宾已有活动用户会话（自动登录很重要）
    cmd = [VMRUN, "-T", "ws",
           "-gu", GUEST_USER, "-gp", GUEST_PASS,
           "runProgramInGuest", VMX]
    if nowait:
        cmd.append("-noWait")
    if interactive:
        # 这两个参数能把窗口激活/互动（需要有人已登录）
        cmd += ["-interactive", "-activeWindow"]
    cmd += [program]
    if args:
        cmd += args
    run(cmd)

def copy_host_to_guest(host_path, guest_path):
    run([VMRUN, "-T", "ws",
         "-gu", GUEST_USER, "-gp", GUEST_PASS,
         "copyFileFromHostToGuest", VMX, host_path, guest_path])

def check_interactive_session():
    """检查是否有用户交互式登录"""
    print("Checking for interactive user session...")
    try:
        # 尝试列出来宾中的进程，这需要交互式会话
        result = subprocess.run([VMRUN, "-T", "ws", 
                               "-gu", GUEST_USER, "-gp", GUEST_PASS,
                               "listProcessesInGuest", VMX], 
                              capture_output=True, text=True, encoding="mbcs", errors="replace")
        if result.returncode == 0:
            print("Interactive session detected!")
            return True
        else:
            print("No interactive session found")
            return False
    except Exception as e:
        print(f"Error checking interactive session: {e}")
        return False

def force_interactive_login():
    """强制进行交互式登录"""
    print("Attempting to force interactive login...")
    try:
        # 方法1: 使用loginInGuest命令
        result = subprocess.run([VMRUN, "-T", "ws",
                               "loginInGuest", VMX, GUEST_USER, GUEST_PASS], 
                              capture_output=True, text=True, encoding="mbcs", errors="replace")
        if result.returncode == 0:
            print("Interactive login successful!")
            return True
        else:
            print(f"Interactive login failed: {result.stderr}")
            
        # 方法2: 尝试运行一个简单的命令来激活会话
        print("Trying to activate session with a simple command...")
        result = subprocess.run([VMRUN, "-T", "ws",
                               "-gu", GUEST_USER, "-gp", GUEST_PASS,
                               "runProgramInGuest", VMX, 
                               "cmd.exe", "/c", "echo", "session_test"], 
                              capture_output=True, text=True, encoding="mbcs", errors="replace")
        return result.returncode == 0
        
    except Exception as e:
        print(f"Error during interactive login: {e}")
        return False

def test_vmrun_basic():
    # 测试基本的vmrun命令是否工作
    print("Testing basic vmrun command...")
    try:
        result = subprocess.run([VMRUN, "-T", "ws", "list"], 
                              capture_output=True, text=True, encoding="mbcs", errors="replace")
        print("vmrun list output:", result.stdout.strip())
        print("vmrun list errors:", result.stderr.strip())
        return result.returncode == 0
    except Exception as e:
        print(f"Error testing vmrun: {e}")
        return False

def graceful_shutdown():
    run([VMRUN, "-T", "ws", "shutdown", VMX, "soft"])

if __name__ == "__main__":
    print("=== VMware Control Script Debug Mode ===")
    print(f"VMRUN path: {VMRUN}")
    print(f"VMX path: {VMX}")
    print(f"Guest user: {GUEST_USER}")
    print(f"Current working directory: {os.getcwd()}")
    
    # 0) 测试vmrun基本功能
    if not test_vmrun_basic():
        print("ERROR: vmrun basic test failed!")
        exit(1)
    
    # 1) 启动虚拟机
    print("\n=== Starting VM ===")
    try:
        start_vm(gui=True)
    except subprocess.CalledProcessError as e:
        print(f"VM start failed with return code {e.returncode}")
        if e.returncode == 4294967295:  # -1 in unsigned 32-bit
            print("This usually means the VM is already running, continuing...")
        else:
            raise

    # 2) 等待 VMware Tools 起来（意味着系统基本引导完毕）
    print("\n=== Waiting for VMware Tools ===")
    wait_for_tools(timeout=300)

    print("\n=== Waiting for user login ===")
    # 首先等待一段时间让系统完全启动
    print("Waiting 120 seconds for system to fully boot...")
    time.sleep(120)
    
    # 检查是否已有交互式会话
    if not check_interactive_session():
        print("No interactive session found, attempting to create one...")
        if force_interactive_login():
            print("Interactive login successful!")
            time.sleep(5)  # 等待会话建立
        else:
            print("Failed to establish interactive session, will try non-interactive mode")
    
    # 再次检查交互式会话状态
    has_interactive = check_interactive_session()
    print(f"Interactive session status: {'Available' if has_interactive else 'Not available'}")

    # 3) （可选）拷贝脚本或配置到来宾
    # copy_host_to_guest(r"D:\setup\bootstrap.ps1", r"C:\Users\your_user\bootstrap.ps1")

    # 4) 在来宾内启动应用（示例：记事本 / Edge）
    print("\n=== Running programs in guest ===")
    
    if has_interactive:
        print("Trying interactive mode first...")
        try:
            run_in_guest(r"C:\Windows\System32\notepad.exe",
                         interactive=True, nowait=True)
            print("Success with interactive mode!")
        except subprocess.CalledProcessError as e:
            print(f"Interactive mode failed: {e}")
            print("Falling back to non-interactive mode...")
            try:
                run_in_guest(r"C:\Windows\System32\notepad.exe",
                             interactive=False, nowait=True)
                print("Success with non-interactive mode!")
            except subprocess.CalledProcessError as e2:
                print(f"Both modes failed: {e2}")
    else:
        print("No interactive session available, using non-interactive mode...")
        try:
            run_in_guest(r"C:\Windows\System32\notepad.exe",
                         interactive=False, nowait=True)
            print("Success with non-interactive mode!")
        except subprocess.CalledProcessError as e:
            print(f"Non-interactive mode failed: {e}")
    
    # run_in_guest(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    #              args=["https://www.mit.edu"], interactive=True, nowait=True)

    print("\n=== Script completed ===")
    # …后续你还可以用 run_in_guest 跑 PowerShell、Python、你自己的 App
