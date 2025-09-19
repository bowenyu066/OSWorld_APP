import subprocess
import time
import shlex

VMRUN = r"C:\Program Files (x86)\VMware\VMware Workstation\vmrun.exe"
VMX   = r"E:\Virtual Machines\Windows 11 x64\Windows 11 x64 (2).vmx"

# 来宾系统里的账户与密码（用于在来宾内执行程序）
GUEST_USER = "user"
GUEST_PASS = "password"

def run(cmd):
    # 小工具：同步执行并打印输出，便于调试
    print(">", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout.strip())
    if result.stderr:
        print(result.stderr.strip())
    result.check_returncode()
    return result

def start_vm(gui=False):
    # 启动 VM
    # - nogui：后台启动；不写则带 GUI
    args = [VMRUN, "-T", "ws", "start", VMX]
    if not gui:
        args.append("nogui")
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

def graceful_shutdown():
    run([VMRUN, "-T", "ws", "shutdown", VMX, "soft"])

if __name__ == "__main__":
    # 1) 启动虚拟机
    start_vm(gui=True)

    # 2) 等待 VMware Tools 起来（意味着系统基本引导完毕）
    wait_for_tools(timeout=300)

    # 3) （可选）拷贝脚本或配置到来宾
    # copy_host_to_guest(r"D:\setup\bootstrap.ps1", r"C:\Users\your_user\bootstrap.ps1")

    # 4) 在来宾内启动应用（示例：记事本 / Edge）
    run_in_guest(r"C:\Windows\System32\notepad.exe",
                 interactive=True, nowait=True)
    run_in_guest(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                 args=["https://www.mit.edu"], interactive=True, nowait=True)

    # …后续你还可以用 run_in_guest 跑 PowerShell、Python、你自己的 App
