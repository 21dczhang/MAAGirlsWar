from pathlib import Path
import shutil
import sys
import json
import os
import re

def load_json_with_comments(path):
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    content = re.sub(r'(?<!:)//.*', '', content) 
    return json.loads(content)

script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(script_dir)

from configure import configure_ocr_model
from generate_manifest_cache import generate_manifest_cache

# 定义路径：working_dir 是项目根目录
working_dir = Path(__file__).parent.parent.parent
install_path = working_dir / Path("install")
version = len(sys.argv) > 1 and sys.argv[1] or "v0.0.1"
platform_tag = len(sys.argv) > 2 and sys.argv[2] or ""


def install_maa_runtimes(platform_tag: str):
    """安装 MaaFramework 的 DLL 和组件"""
    if not platform_tag:
        raise ValueError("platform_tag is required")
    
    print(f">> Installing MaaFramework binaries for {platform_tag}...")
    
    # 1. Native Runtimes
    shutil.copytree(
        working_dir / "deps" / "bin",
        install_path / "runtimes" / platform_tag / "native",
        ignore=shutil.ignore_patterns(
            "*MaaDbgControlUnit*", "*MaaThriftControlUnit*", "*MaaWin32ControlUnit*",
            "*MaaRpc*", "*MaaHttp*", "plugins", "*.node", "*MaaPiCli*",
        ),
        dirs_exist_ok=True,
    )
    # 2. MaaAgentBinary
    shutil.copytree(
        working_dir / "deps" / "share" / "MaaAgentBinary",
        install_path / "libs" / "MaaAgentBinary",
        dirs_exist_ok=True,
    )
    # 3. Plugins
    shutil.copytree(
        working_dir / "deps" / "bin" / "plugins",
        install_path / "plugins" / platform_tag,
        dirs_exist_ok=True,
    )

def install_python_environment():
    """【关键】复制 Python 环境"""
    print(">> Installing Python environment...")
    
    # 假设 CI 脚本把 python 放在了根目录的 'python' 文件夹
    src = working_dir / "python"
    dst = install_path / "python"
    
    if src.exists():
        shutil.copytree(src, dst, dirs_exist_ok=True)
        print("   Python copied successfully.")
    else:
        # 如果根目录没有，尝试看看是不是已经在 install/python 了
        if dst.exists():
            print("   Python already exists in install/python.")
        else:
            raise FileNotFoundError(f"Critical: Python environment not found at {src}")

def install_python_wheels():
    """【关键】复制 deps (whl包)"""
    print(">> Installing Python wheels (deps)...")
    
    # 假设 CI 脚本把 whl 下载到了根目录的 'deps' 文件夹
    # 注意：这里的 deps 文件夹里应该只有 .whl 文件（由 download_deps.py 生成）
    # 但由于 MaaFramework 也下载到了 deps，我们需要过滤一下，或者干脆整个考过去
    # 为了保险，我们只拷贝 whl 文件所在的目录
    
    # 在 install.yml 里，我们会强制把 whl 下载到 'whl_deps' 目录以免混淆
    # 或者我们直接把整个 deps 考过去，agent 会自己找 whl
    
    src = working_dir / "deps"
    dst = install_path / "deps"
    
    if src.exists():
        # 我们使用 dirs_exist_ok=True 进行合并
        shutil.copytree(src, dst, dirs_exist_ok=True)
        print("   Deps folder copied successfully.")
    else:
        raise FileNotFoundError(f"Critical: 'deps' folder not found at {src}")

def install_resource_and_agent():
    print(">> Installing resources and agent...")
    configure_ocr_model()

    # Resource
    shutil.copytree(working_dir / "assets" / "resource", install_path / "resource", dirs_exist_ok=True)
    shutil.copy2(working_dir / "assets" / "interface.json", install_path)
    
    # Interface.json 处理
    target_json = install_path / "interface.json"
    interface = load_json_with_comments(target_json)
    interface["version"] = version
    interface["title"] = f"MAAGirlsWar {version}"
    with open(target_json, "w", encoding="utf-8") as f:
        json.dump(interface, f, ensure_ascii=False, indent=4)

    # Agent
    shutil.copytree(working_dir / "agent", install_path / "agent", dirs_exist_ok=True)
    
    # 再次读取写入 agent 配置
    interface = load_json_with_comments(target_json)
    if sys.platform.startswith("win"):
        interface["agent"]["child_exec"] = r"./python/python.exe"
    elif sys.platform.startswith("darwin"):
        interface["agent"]["child_exec"] = r"./python/bin/python3"
    elif sys.platform.startswith("linux"):
        interface["agent"]["child_exec"] = r"python3"
    interface["agent"]["child_args"] = ["-u", r"./agent/main.py"]
    
    with open(target_json, "w", encoding="utf-8") as f:
        json.dump(interface, f, ensure_ascii=False, indent=4)

def install_chores():
    print(">> Installing chores...")
    for file in ["README.md", "LICENSE", "CONTACT", "requirements.txt"]:
        if (working_dir / file).exists():
            shutil.copy2(working_dir / file, install_path)

def install_manifest_cache():
    print(">> Generating manifest cache...")
    config_dir = install_path / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    generate_manifest_cache(config_dir)

if __name__ == "__main__":
    try:
        # 清理旧的 install 目录 (可选，CI 环境通常是干净的)
        # if install_path.exists(): shutil.rmtree(install_path)
        
        install_path.mkdir(parents=True, exist_ok=True)

        # 1. 安装 MaaFramework 运行库
        install_maa_runtimes(platform_tag)
        
        # 2. 安装 Python 环境 (修复 No module named pip)
        install_python_environment()
        
        # 3. 安装 Python 依赖包 (修复 deps 丢失)
        install_python_wheels()
        
        # 4. 安装业务逻辑
        install_resource_and_agent()
        install_chores()
        install_manifest_cache()

        print(f"✅ Install to {install_path} successfully.")
        
    except Exception as e:
        print(f"❌ Error during installation: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)