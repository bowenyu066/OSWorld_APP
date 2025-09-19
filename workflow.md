# OS-World Project

Project主页：https://github.com/xlang-ai/OSWorld

这个Project本身是为AI Agent设计的benchmark（Benchmarking Multimodal Agents for Open-Ended Tasks in Real Computer Environments），其操作者是运行在计算机的AI Agent。一个典型的命令格式如下：（https://github.com/xlang-ai/OSWorld/blob/main/evaluation_examples/examples/chrome/030eeff7-b492-4218-b312-701ec99ee0cc.json）

```json
{
  "id": "030eeff7-b492-4218-b312-701ec99ee0cc",
  "snapshot": "chrome",
  "instruction": "Can you enable the 'Do Not Track' feature in Chrome to enhance my online privacy?",
  "source": "https://www.surreycc.gov.uk/website/cookies/do-not-track",
  "config": [
    {
      "type": "launch",
      "parameters": {
        "command": [
          "google-chrome",
          "--remote-debugging-port=1337"
        ]
      }
    },
    {
      "type": "launch",
      "parameters": {
        "command": [
          "socat",
          "tcp-listen:9222,fork",
          "tcp:localhost:1337"
        ]
      }
    }
  ],
  "trajectory": "trajectories/",
  "related_apps": [
    "chrome"
  ],
  "evaluator": {
    "postconfig": [
      {
        "type": "launch",
        "parameters": {
          "command": [
            "pkill",
            "chrome"
          ]
        }
      },
      {
        "type": "launch",
        "parameters": {
          "command": [
            "google-chrome",
            "--remote-debugging-port=1337"
          ]
        }
      },
      {
        "type": "sleep",
        "parameters": {
          "seconds": 3
        }
      }
    ],
    "func": "exact_match",
    "result": {
      "type": "enable_do_not_track"
    },
    "expected": {
      "type": "rule",
      "rules": {
        "expected": "true"
      }
    }
  },
  "proxy": false,
  "fixed_ip": false,
  "possibility_of_env_change": "low"
}
```

正如先前所说，这个是给agent设计的benchmark，所以输入格式都是这样的json。我们现在想要做的，是找一群人类annotator来做这些任务，收集人类的操作数据（目标是训练agent）。为了给人类annotator一个方便上手的环境，我们肯定不能假定人类annotator都懂编程或者命令行，因此我们要设计一个GUI界面，给人类annotator在后台起虚拟机、准备好环境、打开浏览器或下载文件，并弹出方便人类annotator阅读的指令，这就是我们大概要做的。

具体来说，环境系统应当这样设计：

1. 整个系统分为宿主机和虚拟机（均为Windows系统）。
2. 人类annotator工作在宿主机上，点击我们的软件，就可以自动加载虚拟机（及各种需要的环境配置），起vmware虚拟机全屏，人在全屏虚拟机上进行操作；
3. annotator不一定会代码/装环境，所以需要简洁的图形界面，点开后自动启动vmware和弹出小框告知instruction；同时，vmware所需要的context在后台配置（比如，打开chrome，或者打开文档）
4. 一个录制软件工作在宿主机上（录制软件的部分不需要我们关心），宿主机上的键盘鼠标操作会被录制，这些操作直接作用于虚拟机；
5. 图形界面需要有一个按钮叫做validate/verify，在人类操作完成后，点击该按钮，运行evaluation function，看人做的对不对；如果做对了，录制片段就可以被使用，反之则不可以

整个项目时间紧迫，只有 3 天时间，因此必须有秩序地进行。我大概整理了这 3 天计划依次实现的功能：

---

## 仓库骨架（一次性建立）

**AI PROMPT — init repo**

* 目标：初始化 Python 项目骨架（Windows 主机侧 GUI + vmware 控制 + 任务执行 + 评估触发）
* 要求：

  * 使用 Python 3.10+，依赖 `PySide6`, `pyyaml`, `pydantic`, `requests`（如 evaluator 需要）, `rich`.
  * 目录结构：

    ```
    annotator-kit/
      app/
        __init__.py
        gui.py
        config.py
        vm_control.py
        task_adapter.py
        evaluator_runner.py
        snapshot.py
        logging_setup.py
        models.py
      scripts/
        run_config_guest.ps1
        eval_guest.ps1
      tasks/
        samples/   # 放 OSWorld 示例 json
      runs/
      assets/
        icon.ico
      pyproject.toml
      README.md
    ```
  * `pyproject.toml` 配置 `pyinstaller` 打包（后面 Day3 用）。
  * 在 `README.md` 放“本地开发启动说明（python -m app.gui）”。

**验收标准**

* 能 `python -m app.gui` 启动空窗口
* 目录结构与依赖文件完整可运行

---

## Day 1 — 能跑：一键全屏启动 VM、展示任务指令、按 JSON 执行最小 config（launch/sleep/chrome\_open\_tabs）

### 1. 配置加载与模型

**AI PROMPT — config & models**

* 目标：实现配置与任务 JSON 的数据模型
* 任务：

  1. 在 `app/config.py`：

     * 读取 `config.yaml`（如果不存在则生成模板）：

       ```yaml
       vmx_path: "D:/VMs/Win11/Win11.vmx"
       guest_username: "user"
       guest_password: "password"
       tasks_dir: "./tasks/samples"
       output_dir: "./runs"
       vmware_bin: "C:/Program Files (x86)/VMware/VMware Workstation"
       start_fullscreen: true
       snapshot_name: "clean"
       ```
  2. 在 `app/models.py`（用 `pydantic`）定义：

     * `Task`: 字段 `id: str, instruction: str, source: Optional[str], snapshot: Optional[str], config: List[Action], evaluator: Optional[Evaluator], ...`
     * `Action`: `type: Literal["launch","sleep","chrome_open_tabs", ...]`, `parameters: Dict[str, Any]`
     * `Evaluator`: `postconfig: List[Action]`, `func: str`, `result: Dict[str,Any]`, `expected: Dict[str,Any]`
* 验收标准：

  * 能用 `Task.parse_file(path)` 成功加载 OSWorld 示例 JSON
  * 缺字段时给出明确报错（pydantic 校验）

### 2. 控制 VMware（主机侧）

**AI PROMPT — vm\_control**

* 目标：封装 `vmrun`/`vmware.exe` 控制 VM
* 在 `app/vm_control.py` 实现：

  * `class VMController:`

    * `start(fullscreen: bool) -> None`

      * 若 `fullscreen=True` 使用 `vmware.exe -X <vmx>`，否则 `vmrun start <vmx>`
    * `run_in_guest(program_path: str, args: list[str] = None, interactive: bool=False, workdir: Optional[str]=None) -> int`

      * 调用：`vmrun -T ws -gu <user> -gp <pass> runProgramInGuest "<vmx>" "<program_path>" [args]`
    * `copy_to_guest(host_path: str, guest_path: str) -> None`
    * `copy_from_guest(guest_path: str, host_path: str) -> None`
    * `revert_snapshot(name: str) -> None`
    * `is_running() -> bool`（可用 `vmrun list` 判断）
* 验收标准：

  * 本地能执行 `start(fullscreen=True)` 打开目标 VM
  * 成功在客机中启动 `notepad.exe`（返回码 0）

### 3. GUI 雏形（展示任务 + Start/Validate）

**AI PROMPT — gui skeleton**

* 目标：PySide6 窗口，左侧任务列表，右侧显示 instruction + source + 按钮
* 在 `app/gui.py`：

  * 加载 `tasks_dir` 下所有 `.json`，列表显示 `task.id`
  * 右侧显示大字 `instruction`，下面 `source`（可点击）
  * 按钮：

    * `Start Task` → 触发：快照还原（Day2 再接）、启动 VM、执行 `config`（Day1 仅支持 `launch`/`sleep`/`chrome_open_tabs`）
    * `Validate`（Day1 先禁用，置灰）
* 验收标准：

  * 选择任一任务后，点击 `Start Task` 能全屏进入 VM，并在客机里启动 Chrome（用于 `--remote-debugging-port=1337`）

### 4. 最小任务适配器（执行 config）

**AI PROMPT — task\_adapter (Day1 scope)**

* 目标：把 `Task.config` 里的 action 翻译为主机侧调用
* 在 `app/task_adapter.py`：

  * `class TaskRunner:`

    * `run_config(task: Task, vm: VMController) -> None`
    * 支持 Action：

      * `"launch"`：将 `parameters.command` 映射到客机 `run_in_guest(program, args)`

        * 程序与参数路径**必须是客机路径**，如：`C:\Program Files\Google\Chrome\Application\chrome.exe`
      * `"sleep"`：主机 `time.sleep(seconds)`
      * `"chrome_open_tabs"`：如果存在，按 `urls_to_open` 逐个 `run_in_guest("powershell.exe", ["-Command", "Start-Process", "chrome", "<url>"])`
* 验收标准：

  * 能执行你给的 DNT 示例：起 Chrome + 打开所需网页

---

## Day 2 — 能评估：在客机内跑 evaluator，Validate 按钮完成判定并落盘

### 1. 在客机内跑脚本（主机触发）

**AI PROMPT — guest scripts**

* 目标：通过 `vmrun` 把脚本复制进客机并执行
* 产物：

  * `scripts/run_config_guest.ps1`：支持在客机内按顺序执行 `chrome.exe`、打开额外 tab、sleep 等（备用）
  * `scripts/eval_guest.ps1`：执行 `python C:\evaluators\eval.py --task C:\Tasks\<id>.json --out C:\Tasks\<id>_result.json`
* 修改 `vm_control.py` 增加：

  * `ensure_guest_dir(path: str) -> None`（在客机创建目录：`powershell -Command "New-Item -ItemType Directory -Force ..."`)
* 验收标准：

  * 能把 `tasks/<id>.json` 复制到 `C:\Tasks\`，并能在客机执行 `eval_guest.ps1`（暂时 eval.py 是个占位脚本）

### 2. evaluator\_runner（调用 OSWorld evaluator）

**AI PROMPT — evaluator\_runner**

* 目标：在客机里调用 Python evaluator，并把结果拉回主机
* 在 `app/evaluator_runner.py`：

  * `class EvaluatorRunner:`

    * `prepare_guest_env(vm: VMController) -> None`

      * 假设客机已预装 Python（Day0 你会准备好的镜像），并在 `C:\evaluators\` 放置我们自带 `eval.py` 与 `requirements.txt`（如需）。
    * `run(task: Task, vm: VMController, guest_task_dir="C:\\Tasks") -> dict`

      * 流程：

        1. `copy_to_guest(task_json_path, f"{guest_task_dir}\\{task.id}.json")`
        2. `run_in_guest("powershell.exe", ["-Command", "python", "C:\\evaluators\\eval.py", "--task", f"{guest_task_dir}\\{task.id}.json", "--out", f"{guest_task_dir}\\{task.id}_result.json"])`
        3. `copy_from_guest(f"{guest_task_dir}\\{task.id}_result.json", host_runs_dir)`
        4. 读取并返回 dict
* 在 `C:\evaluators\eval.py`（请生成示例实现）：

  * 读取 `task.json`，按 `evaluator.func` 分发到 OSWorld 对应函数（先写一个 stub：当 `func="exact_match"` 且 `expected.rules.expected=="true"` 时，返回 `{"passed": true}`），Day2 先跑通链路，Day3 再对接完备 evaluator。
* 验收标准：

  * 点击 GUI 的 **Validate**，能在主机 `runs/<run_id>/eval_result.json` 得到结构 `{ "passed": true/false, "details": ... }` 并在 GUI 上绿/红提示

### 3. 快照策略接入 GUI

**AI PROMPT — snapshot integration**

* 目标：**每次任务开始前**强制快照还原
* 在 `app/snapshot.py`：

  * `prepare_for_task(vm: VMController, snapshot_name: str) -> None`：`revert_snapshot` → `start(fullscreen=cfg.start_fullscreen)`
* 在 `app/gui.py` 的 `Start Task` 流程里调用：

  * `snapshot.prepare_for_task(vm, cfg.snapshot_name)`
  * 然后 `TaskRunner.run_config(...)`
* 验收标准：

  * 连续运行两个任务时，第二个任务开始前能看到 VM 被还原（比如浏览器历史被清空等）

### 4. 运行记录落盘

**AI PROMPT — run logging**

* 目标：把每次任务的元数据写到 `runs/<timestamp>_<taskid>/`
* 在 `app/gui.py`：

  * 生成 `run_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + task.id`
  * 写入：

    ```
    runs/<run_id>/
      task.json
      eval_result.json (Validate 后)
      notes.txt (预留给标注员)
    ```
* 验收标准：

  * 执行一条任务 + Validate 后，文件完整落地

---

## Day 3 — 覆盖“全部任务类型” & 健壮性 & 打包交付

> 由于 OSWorld 的 JSON 有较多 `type`，Day3 的策略是：**插件式 action 适配器 + 覆盖表 + 合理降级**。当遇到未知 `type` 时，统一交由「在客机内执行 PowerShell/批处理脚本」兜底，确保“全部任务类型**都可执行**”（即使内部实现是通用命令执行），以满足“必须全部实现”的硬性要求。

### 1. 动作类型覆盖表（Action Registry）

**AI PROMPT — action registry**

* 目标：支持 OSWorld 常见/全部 `config` 与 `evaluator.postconfig` 的 Action 类型
* 在 `app/task_adapter.py`：

  * 引入注册表：

    ```python
    ACTION_HANDLERS: dict[str, Callable[[Action, VMController, Task], None]] = {}
    def register(action_type): ...
    @register("launch") ...
    @register("sleep") ...
    @register("chrome_open_tabs") ...
    # Day3 新增：
    @register("open_file") ...
    @register("download") ...
    @register("set_env") ...
    @register("kill_process") ...
    @register("powershell") ...
    @register("shell") ...
    @register("copy_to_guest") ...
    @register("copy_from_guest") ...
    @register("unzip") ...
    @register("write_file") ...
    # 以及任何 JSON 里出现过的 type，若未知 → fallback
    ```
  * 兜底处理器 `@register("*")`：

    * 若 `action.type` 未知：将 `action.parameters` 序列化为 `C:\Tasks\actions\<task.id>_<idx>.json`，在客机执行一个通用脚本 `C:\evaluators\generic_action_runner.py` 去解释执行（PowerShell/Shell/Registry 操作等）
    * 这样做到“全部任务类型均可执行”，哪怕内部是“解释器式”实现
* 验收标准：

  * 对于未声明过的新 `type`，程序**不崩溃**，而是走通用 runner；GUI 需提示“使用通用动作执行器”

> 注：你们可以先把 OSWorld 仓库中 `examples/**` 扫一遍，统计出现的 `type`，把最常见的 10–20 个写成专用 handler，剩下走通用。

### 2. evaluator 对接 OSWorld（覆盖全部函数）

**AI PROMPT — eval.py full mapping**

* 目标：在 `C:\evaluators\eval.py` 中**完整映射** `evaluator.func` 到 OSWorld 的 evaluator 实现（或等价逻辑）
* 任务：

  * 读取 `task.evaluator.func`，用 `if/elif` 或 `entry_points` 映射到对应函数（如 `general.exact_match`, `chrome.enable_do_not_track`, `chrome.compare_pdfs`, `file.exists`, `text.contains`, `ui.window_exists` 等——根据任务集补齐）
  * `expected/result` 的语义：实现规则比对（exact / regex / subset / file-hash / DOM-query 等）
  * 如 evaluator 依赖 Chrome DevTools：在**客机**内用 `requests` 走 `http://localhost:1337/json` 接口取页面/target，再发命令；或直接通过 Windows API/PowerShell 查询设置、文件等
  * 统一输出：

    ```json
    {
      "passed": true/false,
      "details": { "metrics": {...}, "diff": "...", "logs": [...] }
    }
    ```
* 验收标准：

  * 针对任务集批量跑 Validate，不报错，能给出布尔结果；随机抽查 5–10 条人工核验

> 说明：如果你们希望**直接 import OSWorld 的 Python 包**，可将其 evaluator 代码打包到镜像里；若许可/依赖有障碍，就在 `eval.py` 里实现等价逻辑（Chrome DevTools、文件对比、注册表/设置读取、截图 OCR 等）。MVP 以能判定为准。

### 3. 健壮性与并发

**AI PROMPT — robustness**

* 目标：提升使用稳定性
* 任务：

  * `vm_control` 的所有外部调用增加超时与重试（指数退避 3 次）
  * `TaskRunner.run_config` 执行中断时，GUI 提供 `Retry`/`Skip` 按钮
  * `Evaluate` 时，若失败/超时（如 60s），提示“可重试/记录失败原因”
  * GUI 状态条显示当前动作（e.g., “Reverting snapshot…”, “Starting Chrome…”）
* 验收标准：

  * 人为制造一个失败（比如改错路径），程序不崩溃，有清晰提示并可跳过

### 4. 批量任务 & 标注流

**AI PROMPT — queue & notes**

* 目标：形成“上一条/下一条”工作流
* 任务：

  * GUI 增加：`Prev Task` / `Next Task` 按钮（顺序/随机）
  * `notes` 输入框：标注员可写备注，保存在 `runs/<run_id>/notes.txt`
  * 任务过滤：按 app（如 `chrome`）、难度、是否已通过等条件筛选
* 验收标准：

  * 可顺畅完成“开始 → 操作 → Validate → 记备注 → 下一条”

### 5. 打包交付

**AI PROMPT — packaging**

* 目标：一键打包 Windows 可执行
* 任务：

  * 新建 `scripts/build.ps1`：

    * 清理构建 → `pyinstaller --noconsole --onefile --icon=assets/icon.ico app/gui.py -n AnnotatorKit.exe`
  * 生成 `docs/QuickStart.pdf`（可用 Markdown 转 PDF）：三步上手 + 常见问题（见下）
* 验收标准：

  * 产出 `dist/AnnotatorKit.exe`，在干净 Windows 主机（装有 VMware）上可运行

---

### 快速验证清单（给线下测试用）

* [ ] 打开 `AnnotatorKit.exe`，选择一条 Chrome 任务
* [ ] 点击 `Start Task` → 看到 VM 全屏、Chrome 打开、目标网页加载
* [ ] 在 VM 内完成操作（例如打开设置并开启“Do Not Track”）
* [ ] 回到主机点击 `Validate` → 出现“✔ Passed”或“✖ Failed”
* [ ] 检查 `runs/<run_id>/eval_result.json`、`task.json`、`notes.txt` 是否齐全
* [ ] 再次点击下一条任务，确认**每次开始前都自动快照还原**

---

## 常见问题（FAQ 摘要，写进 QuickStart）

* **要不要 WSL？** 不需要。用 Windows PowerShell/命令提示符即可。
* **VMware 的路径/权限**：`vmrun` 和 `vmware.exe` 的路径请在 `config.yaml` 配好；必须有 Workstation Pro 或 Player + vmrun。
* **客机内 Python/evaluator**：镜像准备时预装 Python 3.10+，把 `C:\evaluators\` 放好（`eval.py`、依赖）
* **录屏**：由宿主机软件完成，输出与 `runs/<run_id>/` 关联（文件名或软链接）。
* **Chrome 远程调试**：若 evaluator 需要，用 `--remote-debugging-port=1337` 启动；如果端口占用，评测脚本应支持自动回退端口。
* **全屏**：`vmware.exe -X <vmx>`；若失效，用热键在 VMware 中切换全屏。
* **网络/代理**：MVP 默认直连；遇到需要代理/固定 IP 的任务，先走通用 action runner（记录需求），后续补齐。

---

## 风险与兜底

* **“必须全部实现任务类型”**：
  Day3 的**通用动作解释器**是关键兜底：即使遇到新类型，也能把参数 JSON 传入客机内一个万能脚本，由它调用 PowerShell/注册表/Chrome DevTools/API 实现。这样满足“全类型可执行”的硬性要求；之后再逐步把高频类型写成专用 handler 提升体验与稳健性。
* **评估耦合**：
  若不能直接引 OSWorld evaluator 代码，就按任务语义实现等价检查（Chrome DevTools、文件比较、UI窗口存在、文本包含等）。评估始终**在客机运行**，避免端口转发复杂度。
* **时间约束（3 天）**：
  Day1 跑通启动与最小 config；Day2 跑通 Validate 全链路；Day3 用“注册表 + 通用解释器”覆盖所有动作类型 + 打包交付。

---

## 已澄清/记录的不确定点（当前版本的处理）

1. **评估脚本位置**：**客机内运行**（更稳）。
2. **快照策略**：**每次任务前还原**，已写入 `snapshot.prepare_for_task` 并在 GUI 流程调用。
3. **任务子集**：**全部实现**——通过“专用 handler + 通用解释器”策略覆盖。
4. **数据合规**：暂不做强校验，但在 QuickStart 里提醒：**不要在任务中使用真实个人账号/敏感信息**；如确需登录，使用**标注专用测试账号**并告知隐私注意事项。
