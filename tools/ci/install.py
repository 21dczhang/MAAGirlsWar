from pathlib import Path
import shutil
import sys
import json
import os
import re

# ---------------------------------------------------------
# 辅助函数：读取带注释的 JSON
# ---------------------------------------------------------
def load_json_with_comments(path):
    """
    读取带 // 注释的 JSON 文件
    path: Path 对象或字符串路径
    """
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    # 使用正则去除 // 开头的单行注释
    content = re.sub(r'(?<!:)//.*', '', content) 
    return json.loads(content)

# 设置 Python 搜索路径以便导入同目录下的模块
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(script_dir)

# 导入本地模块
from configure import configure_ocr_model
from generate_manifest_cache import generate_manifest_cache

# 定义全局路径
working_dir = Path(__file__).parent.parent.parent
install_path = working_dir / Path("install")
version = len(sys.argv) > 1 and sys.argv[1] or "v0.0.1"
platform_tag = len(sys.argv) > 2 and sys.argv[2] or ""


# ---------------------------------------------------------
# 步骤 1: 安装 MaaFramework 运行时文件
# ---------------------------------------------------------
def install_deps(platform_tag: str):
    """安装 MaaFramework 二进制文件到对应架构路径"""
    if not platform_tag:
        raise ValueError("platform_tag is required")

    print(f"Installing MaaFramework binaries for {platform_tag}...")

    # 1. 复制 Native Runtimes (dlls)
    shutil.copytree(
        working_dir / "deps" / "bin",
        install_path / "runtimes" / platform_tag / "native",
        ignore=shutil.ignore_patterns(
            "*MaaDbgControlUnit*",
            "*MaaThriftControlUnit*",
            "*MaaWin32ControlUnit*",
            "*MaaRpc*",
            "*MaaHttp*",
            "plugins",
            "*.node",
            "*MaaPiCli*",
        ),
        dirs_exist_ok=True,
    )
    
    # 2. 复制 MaaAgentBinary (触控/截图库)
    shutil.copytree(
        working_dir / "deps" / "share" / "MaaAgentBinary",
        install_path / "libs" / "MaaAgentBinary",
        dirs_exist_ok=True,
    )
    
    # 3. 复制 Plugins
    shutil.copytree(
        working_dir / "deps" / "bin" / "plugins",
        install_path / "plugins" / platform_tag,
        dirs_exist_ok=True,
    )

# ---------------------------------------------------------
# 步骤 2: 安装 Python 环境 (修复 Python 丢失的关键)
# ---------------------------------------------------------
def install_python_env():
    """复制嵌入式 Python 环境到 install/python"""
    # 假设 setup_embed_python.py 在根目录生成了 'python' 文件夹
    src_python = working_dir / "python"
    dst_python = install_path / "python"

    # 如果根目录有 python 文件夹，且目标目录没有，则复制
    if src_python.exists():
        print(f"Copying Embedded Python from {src_python} to {dst_python}...")
        shutil.copytree(src_python, dst_python, dirs_exist_ok=True)
    elif dst_python.exists():
        print("Python environment already exists in install/python (skipped copy).")
    else:
        print("Warning: No 'python' directory found in working_dir. Setup might be incomplete.")

# ---------------------------------------------------------
# 步骤 3: 安装资源文件
# ---------------------------------------------------------
def install_resource():
    print("Installing resources...")
    configure_ocr_model()

    shutil.copytree(
        working_dir / "assets" / "resource",
        install_path / "resource",
        dirs_exist_ok=True,
    )
    
    # 复制 interface.json
    src_json = working_dir / "assets" / "interface.json"
    dst_json = install_path / "interface.json"
    shutil.copy2(src_json, install_path)

    # 修改 interface.json
    interface = load_json_with_comments(dst_json)
    interface["version"] = version
    interface["title"] = f"MAAGirlsWar {version}"

    with open(dst_json, "w", encoding="utf-8") as f:
        json.dump(interface, f, ensure_ascii=False, indent=4)

# ---------------------------------------------------------
# 步骤 4: 安装杂项文件
# ---------------------------------------------------------
def install_chores():
    print("Installing chores...")
    for file in ["README.md", "LICENSE", "CONTACT", "requirements.txt"]:
        src = working_dir / file
        if src.exists():
            shutil.copy2(src, install_path)

# ---------------------------------------------------------
# 步骤 5: 安装 Agent 代码
# ---------------------------------------------------------
def install_agent():
    print("Installing agent code...")
    shutil.copytree(
        working_dir / "agent",
        install_path / "agent",
        dirs_exist_ok=True,
    )

    # 配置 interface.json 中的启动命令
    target_json_path = install_path / "interface.json"
    interface = load_json_with_comments(target_json_path)

    if sys.platform.startswith("win"):
        interface["agent"]["child_exec"] = r"./python/python.exe"
    elif sys.platform.startswith("darwin"):
        interface["agent"]["child_exec"] = r"./python/bin/python3"
    elif sys.platform.startswith("linux"):
        interface["agent"]["child_exec"] = r"python3"

    interface["agent"]["child_args"] = ["-u", r"./agent/main.py"]

    with open(target_json_path, "w", encoding="utf-8") as f:
        json.dump(interface, f, ensure_ascii=False, indent=4)

# ---------------------------------------------------------
# 步骤 6: 生成缓存
# ---------------------------------------------------------
def install_manifest_cache():
    """生成初始 manifest 缓存"""
    config_dir = install_path / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    
    success = generate_manifest_cache(config_dir)
    if success:
        print("Manifest cache generated successfully.")
    else:
        print("Warning: Manifest cache generation failed.")


if __name__ == "__main__":
    try:
        # 确保 install 目录存在
        install_path.mkdir(parents=True, exist_ok=True)

        install_deps(platform_tag)
        install_python_env()  # <--- 新增：确保 Python 被复制
        install_resource()
        install_chores()
        install_agent()
        install_manifest_cache()

        print(f"Install to {install_path} successfully.")
    except Exception as e:
        print(f"Error during installation: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)