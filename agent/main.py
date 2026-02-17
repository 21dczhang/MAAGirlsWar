# -*- coding: utf-8 -*-

import os
import sys
import json
import subprocess
from pathlib import Path
import importlib

# 1. 强制 UTF-8 输出，防止乱码
sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]

# 2. 路径设置
# current_file_path: .../MAAGirlsWar/agent/main.py
current_file_path = os.path.abspath(__file__)
current_script_dir = os.path.dirname(current_file_path)  # .../MAAGirlsWar/agent
project_root_dir = os.path.dirname(current_script_dir)    # .../MAAGirlsWar

# 更改工作目录到项目根目录
if os.getcwd() != project_root_dir:
    os.chdir(project_root_dir)

# 将 agent 目录加入 sys.path，确保能 import utils 和 custom
if current_script_dir not in sys.path:
    sys.path.insert(0, current_script_dir)

# 现在可以安全导入 utils 了
from utils import logger

VENV_NAME = ".venv"
VENV_DIR = Path(project_root_dir) / VENV_NAME

# =========================================================
# region 1. 虚拟环境管理 (保留原样，非常通用且健壮)
# =========================================================

def _is_running_in_our_venv():
    """检查脚本是否在虚拟环境中运行。"""
    in_venv = sys.prefix != sys.base_prefix
    if in_venv:
        logger.debug(f"当前在虚拟环境中运行: {sys.prefix}")
    else:
        logger.debug(f"当前不在虚拟环境中，使用系统Python: {sys.prefix}")
    return in_venv

def ensure_venv_and_relaunch_if_needed():
    """确保venv存在并使用venv重启"""
    logger.info(f"检测到系统: {sys.platform}。当前Python解释器: {sys.executable}")

    if _is_running_in_our_venv():
        logger.info(f"已在目标虚拟环境 ({VENV_DIR}) 中运行。")
        return

    if not VENV_DIR.exists():
        logger.info(f"正在 {VENV_DIR} 创建虚拟环境...")
        try:
            subprocess.run(
                [sys.executable, "-m", "venv", str(VENV_DIR)],
                check=True, capture_output=True,
            )
            logger.info("创建成功")
        except Exception as e:
            logger.error(f"创建虚拟环境失败: {e}")
            sys.exit(1)

    # 确定 venv 中的 python 路径
    if sys.platform.startswith("win"):
        python_in_venv = VENV_DIR / "Scripts" / "python.exe"
    else:
        python_in_venv = VENV_DIR / "bin" / "python3"
        if not python_in_venv.exists():
            python_in_venv = VENV_DIR / "bin" / "python"

    if not python_in_venv.exists():
        logger.error(f"未找到虚拟环境 Python: {python_in_venv}")
        sys.exit(1)

    logger.info("正在使用虚拟环境Python重新启动...")
    try:
        # 使用绝对路径重启
        script_abs = current_file_path
        args = sys.argv[1:]
        cmd = [str(python_in_venv), str(script_abs)] + args
        
        result = subprocess.run(
            cmd, cwd=project_root_dir, env=os.environ.copy(), check=False
        )
        sys.exit(result.returncode)
    except Exception as e:
        logger.exception(f"重启失败: {e}")
        sys.exit(1)

# =========================================================
# region 2. 依赖管理 (保留原样，支持离线/在线安装)
# =========================================================

def read_config(config_name: str, default_config: dict) -> dict:
    config_dir = Path("./config")
    config_dir.mkdir(exist_ok=True)
    config_path = config_dir / f"{config_name}.json"
    
    if not config_path.exists():
        try:
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(default_config, f, indent=4, ensure_ascii=False)
        except Exception:
            pass
        return default_config

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default_config

def read_pip_config() -> dict:
    default_config = {
        "enable_pip_install": True,
        "mirror": "https://pypi.tuna.tsinghua.edu.cn/simple",
        "backup_mirror": "https://mirrors.ustc.edu.cn/pypi/simple",
    }
    return read_config("pip_config", default_config)

def _run_pip_command(cmd_args: list, operation_name: str) -> bool:
    try:
        logger.info(f"开始 {operation_name}")
        process = subprocess.Popen(
            cmd_args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace", bufsize=1, universal_newlines=True
        )
        for line in iter(process.stdout.readline, ""):
            if line.strip():
                # 这里可以过滤掉一些无用的pip日志
                if "Requirement already satisfied" not in line: 
                     logger.debug(line.strip())
        return_code = process.wait()
        return return_code == 0
    except Exception as e:
        logger.exception(f"{operation_name} 异常: {e}")
        return False

def install_requirements() -> bool:
    pip_config = read_pip_config()
    if not pip_config.get("enable_pip_install", True):
        return True

    req_path = Path(project_root_dir) / "requirements.txt"
    if not req_path.exists():
        logger.warning("未找到 requirements.txt，跳过依赖安装")
        return True

    # 1. 尝试本地 deps 安装
    deps_dir = Path(project_root_dir) / "deps"
    has_local_whl = deps_dir.exists() and any(deps_dir.glob("*.whl"))
    
    if has_local_whl:
        logger.info("发现本地离线依赖包，优先尝试离线安装...")
        cmd = [
            sys.executable, "-m", "pip", "install", "-U", "-r", str(req_path),
            "--no-warn-script-location", "--break-system-packages",
            "--find-links", str(deps_dir), "--no-index"
        ]
        if _run_pip_command(cmd, "本地离线安装"):
            return True
        logger.warning("本地安装失败，尝试在线安装...")

    # 2. 在线安装
    mirror = pip_config.get("mirror", "")
    cmd = [
        sys.executable, "-m", "pip", "install", "-U", "-r", str(req_path),
        "--no-warn-script-location", "--break-system-packages"
    ]
    if mirror:
        cmd.extend(["-i", mirror])
        if pip_config.get("backup_mirror"):
            cmd.extend(["--extra-index-url", pip_config.get("backup_mirror")])
            
    return _run_pip_command(cmd, "在线安装依赖")

# =========================================================
# region 3. 核心业务 (大幅修改：移除 M9A 特有逻辑)
# =========================================================

def read_interface_version() -> str:
    # 简单的版本读取，用于判断是否是 DEBUG 模式
    # 如果 assets/interface.json 存在，通常意味着是开发环境或解压后的环境
    path = Path(project_root_dir) / "assets" / "interface.json"
    if path.exists():
        return "DEBUG"
    # 如果根目录有 interface.json (打包后)
    path = Path(project_root_dir) / "interface.json"
    if path.exists():
         try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f).get("version", "unknown")
         except:
             pass
    return "unknown"

def agent(is_dev_mode=False):
    try:
        # 1. 设置日志等级
        if is_dev_mode:
            from utils.logger import change_console_level
            change_console_level("DEBUG")
            logger.info("开发模式：日志等级已设置为 DEBUG")

        # 2. [移除/注释] M9A 的热更新和版本检查逻辑
        # 你的项目刚起步，没有后端服务器支持，这段代码会报错。
        # 除非你自己实现了 utils/manifest_checker.py 等文件，否则保持注释。
        """
        version_info = check_resource_version()
        if not version_info["is_latest"]:
            logger.warning("发现新版本...")
        
        manifest_result = check_manifest_updates()
        if manifest_result["has_any_update"]:
            check_and_update_resources(...)
        """
        logger.info("跳过热更新检查 (如需启用请在 main.py 取消注释并配置后端)")

        # 3. 启动 MaaFramework Agent
        from maa.agent.agent_server import AgentServer
        from maa.toolkit import Toolkit
        
        # 这里的 import custom 非常重要
        # 它会加载 agent/custom/__init__.py，你应该在那里注册你的任务
        import custom 

        # 初始化 Toolkit (指向 assets 目录)
        # 注意：如果是在 dev 模式，我们已经在 main() 里 cd 到了 assets，这里可以直接 "./"
        # 如果不是 dev 模式，这里通常指向当前目录
        Toolkit.init_option("./")

        # 4. 获取 Socket ID 并启动
        if len(sys.argv) < 2:
            logger.error(">>> 错误: 缺少 socket_id 参数 <<<")
            logger.error("本程序设计为由 MaaFramework (MaaPiCli.exe 或 MFAAvalonia.exe) 启动。")
            logger.error("如果你想单独测试逻辑，请不要直接运行 main.py，或者手动传入一个模拟 ID。")
            return

        socket_id = sys.argv[-1]
        logger.info(f"启动 AgentServer, Socket ID: {socket_id}")
        
        AgentServer.start_up(socket_id)
        logger.info("AgentServer 运行中... (按 Ctrl+C 无法直接停止，需关闭宿主程序)")
        AgentServer.join()
        AgentServer.shut_down()
        logger.info("AgentServer 已关闭")

    except ImportError as e:
        logger.error(f"导入核心模块失败: {e}")
        logger.error("请检查：1. 是否安装了 maa 库 2. agent/custom 目录是否存在")
        sys.exit(1)
    except Exception as e:
        logger.exception("Agent 运行过程中发生未捕获异常")
        sys.exit(1)

# =========================================================
# region 4. 入口
# =========================================================

def main():
    # 1. 确定运行模式
    current_version = read_interface_version()
    # 只要版本号是 DEBUG 或者 你的 assets 下有 interface.json，就认为是开发模式
    is_dev_mode = (current_version == "DEBUG")

    # 2. 虚拟环境准备 (Linux 必选，Windows 开发模式推荐)
    if sys.platform.startswith("linux") or is_dev_mode:
        ensure_venv_and_relaunch_if_needed()

    # 3. 安装依赖
    install_requirements()

    # 4. 切换目录 (关键)
    # MaaFramework 运行时通常需要工作目录在 assets 文件夹，或者资源路径正确配置
    # M9A 的做法是 Dev 模式下切到 assets，Release 模式下保持在根目录(因为资源释放位置不同)
    if is_dev_mode:
        assets_dir = Path(project_root_dir) / "assets"
        if assets_dir.exists():
            os.chdir(assets_dir)
            logger.info(f"开发模式：工作目录已切换至 {os.getcwd()}")
            # 注意：一旦切换目录，sys.path 里的相对路径可能失效，
            # 但我们在文件开头已经把绝对路径加入了 sys.path，所以没问题。

    # 5. 启动业务
    agent(is_dev_mode=is_dev_mode)

if __name__ == "__main__":
    main()