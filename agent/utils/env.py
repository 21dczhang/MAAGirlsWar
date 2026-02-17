"""
环境管理工具：
- 虚拟环境自动创建与切换（开发模式 / Linux 下生效）
- 依赖安装（本地 whl 优先，失败后回退到镜像源）
- 读取 interface.json 版本号判断是否为开发模式
"""

import json
import subprocess
import sys
from pathlib import Path

from .logger import logger

# ── 路径常量 ──────────────────────────────────────────────────────
_UTILS_DIR = Path(__file__).parent          # agent/utils/
_AGENT_DIR = _UTILS_DIR.parent             # agent/


def _find_project_dir() -> Path:
    """
    从 agent/ 向上查找包含 requirements.txt 的目录作为项目根。
    支持 agent/ 在项目根下，或在 assets/ 旁边等各种布局。
    最多向上找 3 层，找不到就用 agent/ 的父目录。
    """
    candidate = _AGENT_DIR
    for _ in range(4):
        if (candidate / "requirements.txt").exists():
            return candidate
        candidate = candidate.parent
    return _AGENT_DIR.parent


def _find_interface(project_dir: Path) -> Path:
    """
    按优先级查找 interface.json：
    1. project_dir/assets/interface.json
    2. project_dir/interface.json
    3. agent/ 旁边的 assets/interface.json
    """
    candidates = [
        project_dir / "assets" / "interface.json",
        project_dir / "interface.json",
        _AGENT_DIR.parent / "assets" / "interface.json",
    ]
    for p in candidates:
        if p.exists():
            return p
    return candidates[0]  # 默认，即使不存在


_PROJECT_DIR = _find_project_dir()
_VENV_DIR    = _PROJECT_DIR / ".venv"    # .venv 建在项目根，不污染系统 Python
_DEPS_DIR    = _AGENT_DIR / "deps"       # 打包后本地 whl 目录
_REQ_FILE    = _PROJECT_DIR / "requirements.txt"
_INTERFACE   = _find_interface(_PROJECT_DIR)


# ── 版本读取 ──────────────────────────────────────────────────────

def _parse_jsonc(text: str) -> dict:
    """
    解析 JSONC（JSON with Comments）格式，支持：
    - // 单行注释（包括行尾注释，如 "key": value // 注释）
    - /* */ 块注释
    - 尾逗号（trailing comma，如 [..., ] 或 {..., }）
    标准 json 模块不支持以上特性，需预处理。
    """
    import re

    # ① 用状态机逐字符扫描，正确跳过字符串内容，去除注释
    result = []
    i = 0
    n = len(text)
    while i < n:
        c = text[i]

        # 进入字符串
        if c == '"':
            result.append(c)
            i += 1
            while i < n:
                sc = text[i]
                result.append(sc)
                if sc == "\\" :
                    # 转义字符，连同下一个字符一起保留
                    i += 1
                    if i < n:
                        result.append(text[i])
                elif sc == '"':
                    # 字符串结束
                    break
                i += 1
            i += 1
            continue

        # 块注释 /* ... */
        if text[i:i+2] == "/*":
            i += 2
            while i < n and text[i:i+2] != "*/":
                i += 1
            i += 2
            continue

        # 单行注释 //（包括行尾注释）
        if text[i:i+2] == "//":
            while i < n and text[i] != "\n":
                i += 1
            continue

        result.append(c)
        i += 1

    cleaned = "".join(result)

    # ② 去除尾逗号：, 后面只跟空白和 ] 或 }
    cleaned = re.sub(r",\s*([}\]])", r"\1", cleaned)

    return json.loads(cleaned)


def read_interface_version() -> str:
    """读取 interface.json（支持 JSONC 注释和尾逗号）中的 version 字段。"""
    try:
        with open(_INTERFACE, encoding="utf-8") as f:
            raw = f.read()
        data = _parse_jsonc(raw)
        return data.get("version", "")
    except Exception as e:
        logger.warning(f"读取 interface.json 失败: {e}")
        return ""


# ── 虚拟环境管理 ──────────────────────────────────────────────────

def ensure_venv_and_relaunch_if_needed() -> None:
    """
    确保在 .venv 虚拟环境中运行。
    优先使用打包产物中预装好的 .venv（install_python_env 生成）；
    找不到时才在项目根创建新的 .venv 并安装依赖。

    .venv 建在项目根目录，不污染系统 Python。
    触发条件：Linux 系统 或 interface.json version == "DEBUG"
    """
    # 已经在虚拟环境中，直接返回
    if sys.prefix != sys.base_prefix:
        logger.debug(f"已在虚拟环境中: {sys.prefix}")
        return

    # 创建 .venv（若不存在）——打包产物中已预装依赖，直接复用；开发模式下新建
    if not _VENV_DIR.exists():
        logger.info(f"创建虚拟环境: {_VENV_DIR}")
        subprocess.check_call([sys.executable, "-m", "venv", str(_VENV_DIR)])

    # 找到 venv 内的 python
    if sys.platform.startswith("win"):
        venv_python = _VENV_DIR / "Scripts" / "python.exe"
    else:
        venv_python = _VENV_DIR / "bin" / "python3"
        if not venv_python.exists():
            venv_python = _VENV_DIR / "bin" / "python"

    if not venv_python.exists():
        logger.error(f"找不到虚拟环境 Python: {venv_python}")
        sys.exit(1)

    # 用 venv 的 python 重新启动，传递所有原始参数（包括 socket_id）
    logger.info("切换到虚拟环境重新启动...")
    result = subprocess.run([str(venv_python)] + sys.argv)
    sys.exit(result.returncode)


# ── 依赖安装 ──────────────────────────────────────────────────────

def install_requirements() -> bool:
    """
    按优先级安装依赖：
    1. agent/deps/ 目录中的本地 whl（离线优先，打包发布时使用）
    2. 清华镜像源（在线安装）
    3. pip 全局配置（用户自定义源兜底）

    依赖安装到当前 Python 环境（开发模式下即 .venv，不污染系统）。
    """
    if not _REQ_FILE.exists():
        # 打包产物中依赖已预装到 .venv，无需 requirements.txt，静默跳过
        logger.debug(f"requirements.txt 不存在，跳过安装: {_REQ_FILE}")
        return True

    python = sys.executable
    req    = str(_REQ_FILE)

    # 策略 1：本地 whl（打包发布场景）
    if _DEPS_DIR.exists() and any(_DEPS_DIR.glob("*.whl")):
        logger.info("使用本地 whl 安装依赖...")
        ret = subprocess.run([
            python, "-m", "pip", "install",
            "-r", req,
            "--find-links", str(_DEPS_DIR),
            "--no-index",
            "--no-warn-script-location",
        ])
        if ret.returncode == 0:
            logger.info("本地依赖安装成功")
            return True
        logger.warning("本地 whl 安装失败，回退到镜像源")

    # 策略 2：清华 + 中科大镜像源
    logger.info("使用清华镜像源安装依赖...")
    cmd = [
        python, "-m", "pip", "install",
        "-r", req,
        "-i", "https://pypi.tuna.tsinghua.edu.cn/simple",
        "--extra-index-url", "https://mirrors.ustc.edu.cn/pypi/simple",
        "--no-warn-script-location",
    ]
    if sys.platform.startswith("linux"):
        cmd.append("--break-system-packages")

    if subprocess.run(cmd).returncode == 0:
        logger.info("镜像源依赖安装成功")
        return True

    # 策略 3：pip 全局配置兜底
    logger.warning("镜像源失败，使用 pip 全局配置兜底...")
    cmd2 = [python, "-m", "pip", "install", "-r", req, "--no-warn-script-location"]
    if sys.platform.startswith("linux"):
        cmd2.append("--break-system-packages")

    if subprocess.run(cmd2).returncode == 0:
        logger.info("依赖安装成功")
        return True

    logger.error("依赖安装全部失败，请手动执行: pip install -r requirements.txt")
    return False
