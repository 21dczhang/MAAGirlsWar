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

working_dir = Path(__file__).parent.parent.parent
install_path = working_dir / Path("install")
version = len(sys.argv) > 1 and sys.argv[1] or "v0.0.1"
platform_tag = len(sys.argv) > 2 and sys.argv[2] or ""


def install_maa_runtimes(platform_tag: str):
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

def check_python_environment():
    """【修改】确认 Python 环境存在于 install/python"""
    print(">> Checking Python environment...")
    
    # 根据日志，Python 已经被 setup_embed_python.py 放到了 install/python
    target_python = install_path / "python" / "python.exe"
    
    if target_python.exists():
        print(f"   Python found at: {target_python}")
    else:
        # 如果万一不在，尝试从根目录找（兜底）
        src_python = working_dir / "python"
        if src_python.exists():
             print(f"   Copying Python from {src_python}...")
             shutil.copytree(src_python, install_path / "python", dirs_exist_ok=True)
        else:
             raise FileNotFoundError(f"Critical: Python executable not found at {target_python}")

def install_python_wheels():
    """复制 deps (whl包)"""
    print(">> Installing Python wheels (deps)...")
    
    # 这里的 deps 是由 download_deps.py 生成的 whl 目录
    # 我们在 install.yml 里指定了它下载到根目录的 'deps'
    src = working_dir / "deps"
    dst = install_path / "deps"
    
    if src.exists():
        shutil.copytree(src, dst, dirs_exist_ok=True)
        print("   Deps folder copied successfully.")
    else:
        print(f"Warning: 'deps' folder not found at {src}. Install might be incomplete.")

def install_resource_and_agent():
    print(">> Installing resources and agent...")
    configure_ocr_model()

    # Resource
    shutil.copytree(working_dir / "assets" / "resource", install_path / "resource", dirs_exist_ok=True)
    shutil.copy2(working_dir / "assets" / "interface.json", install_path)
    
    target_json = install_path / "interface.json"
    interface = load_json_with_comments(target_json)
    interface["version"] = version
    interface["title"] = f"MAAGirlsWar {version}"
    
    with open(target_json, "w", encoding="utf-8") as f:
        json.dump(interface, f, ensure_ascii=False, indent=4)

    # Agent
    shutil.copytree(working_dir / "agent", install_path / "agent", dirs_exist_ok=True)
    
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
        install_path.mkdir(parents=True, exist_ok=True)

        install_maa_runtimes(platform_tag)
        check_python_environment() # 只要检查，不用强制复制了
        install_python_wheels()
        install_resource_and_agent()
        install_chores()
        install_manifest_cache()

        print(f"✅ Install to {install_path} successfully.")
        
    except Exception as e:
        print(f"❌ Error during installation: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)