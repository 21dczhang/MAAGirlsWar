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
    print(">> Checking Python environment...")
    target_python = install_path / "python" / "python.exe"
    
    if target_python.exists():
        print(f"   Python found at: {target_python}")
    else:
        src_python = working_dir / "python"
        if src_python.exists():
             print(f"   Copying Python from {src_python}...")
             shutil.copytree(src_python, install_path / "python", dirs_exist_ok=True)
        else:
             raise FileNotFoundError(f"Critical: Python executable not found at {target_python}")

def install_python_wheels():
    print(">> Installing Python wheels (deps)...")
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
    # 强制设置输出编码为 utf-8 (防止未来其他 print 报错)
    sys.stdout.reconfigure(encoding='utf-8')
    
    try:
        install_path.mkdir(parents=True, exist_ok=True)

        install_maa_runtimes(platform_tag)
        check_python_environment()
        install_python_wheels()
        install_resource_and_agent()
        install_chores()
        install_manifest_cache()

        # 修改点：去掉了 Emoji
        print(f"[SUCCESS] Install to {install_path} successfully.")
        
    except Exception as e:
        print(f"[ERROR] Error during installation: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)