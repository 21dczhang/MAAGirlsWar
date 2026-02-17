"""
Agent 主入口

启动流程：
1. 读取 interface.json 判断是否为开发模式（version == "DEBUG"）
2. Linux 或开发模式下自动切换到 .venv 虚拟环境
3. 检查并安装依赖
4. 导入所有自定义模块（触发 @AgentServer 注册）
5. 启动 AgentServer，连接 MaaFramework 主进程
"""

import os
import sys
from pathlib import Path

# ── 把 agent/ 目录加入 sys.path，确保能 import utils / custom ────
_AGENT_DIR = Path(__file__).parent
if str(_AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(_AGENT_DIR))


def main() -> None:
    from utils import (
        ensure_venv_and_relaunch_if_needed,
        install_requirements,
        logger,
        read_interface_version,
    )

    # 1. 判断是否为开发模式
    version = read_interface_version()
    is_dev  = (version == "DEBUG")
    logger.info(f"版本: {version}  开发模式: {is_dev}")

    # 2. Linux 或开发模式下切换 venv（切换后会重启进程，不会继续往下走）
    if sys.platform.startswith("linux") or is_dev:
        ensure_venv_and_relaunch_if_needed()

    # 3. 安装依赖
    install_requirements()

    # 4. 导入自定义模块（import 即触发装饰器注册到 AgentServer）
    import custom  # noqa: F401

    # 5. 启动 AgentServer
    _run_agent()


def _run_agent() -> None:
    from utils import logger
    from maa.agent.agent_server import AgentServer

    # MaaFramework GUI 启动时会把 socket_id 作为最后一个参数传入
    sock_id = sys.argv[-1]
    logger.info(f"连接 AgentServer，socket_id: {sock_id}")

    AgentServer.start_up(sock_id)
    AgentServer.join()
    AgentServer.shut_down()
    logger.info("AgentServer 已退出")


if __name__ == "__main__":
    main()
