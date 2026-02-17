from pathlib import Path

import shutil
import subprocess
import sys
import urllib.request
import zipfile

try:
    import jsonc
except ModuleNotFoundError as e:
    raise ImportError(
        "Missing dependency 'json-with-comments' (imported as 'jsonc').\n"
        f"Install it with:\n  {sys.executable} -m pip install json-with-comments\n"
        "Or add it to your project's requirements."
    ) from e

from configure import configure_ocr_model


working_dir = Path(__file__).parent.parent.resolve()
install_path = working_dir / Path("install")
version = len(sys.argv) > 1 and sys.argv[1] or "v0.0.1"

if sys.argv.__len__() < 4:
    print("Usage: python install.py <version> <os> <arch>")
    print("Example: python install.py v1.0.0 win x86_64")
    sys.exit(1)

os_name = sys.argv[2]
arch = sys.argv[3]

# Python Embeddable Package 版本，只打包 Windows 产物时下载
PYTHON_EMBED_VERSION = "3.13.1"


def get_dotnet_platform_tag():
    if os_name == "win" and arch == "x86_64":
        return "win-x64"
    elif os_name == "win" and arch == "aarch64":
        return "win-arm64"
    elif os_name == "macos" and arch == "x86_64":
        return "osx-x64"
    elif os_name == "macos" and arch == "aarch64":
        return "osx-arm64"
    elif os_name == "linux" and arch == "x86_64":
        return "linux-x64"
    elif os_name == "linux" and arch == "aarch64":
        return "linux-arm64"
    else:
        print("Unsupported OS or architecture.")
        sys.exit(1)


def install_deps():
    if not (working_dir / "deps" / "bin").exists():
        print('Please download the MaaFramework to "deps" first.')
        sys.exit(1)

    if os_name == "android":
        shutil.copytree(
            working_dir / "deps" / "bin",
            install_path,
            dirs_exist_ok=True,
        )
        shutil.copytree(
            working_dir / "deps" / "share" / "MaaAgentBinary",
            install_path / "MaaAgentBinary",
            dirs_exist_ok=True,
        )
    else:
        shutil.copytree(
            working_dir / "deps" / "bin",
            install_path / "runtimes" / get_dotnet_platform_tag() / "native",
            ignore=shutil.ignore_patterns(
                "*MaaDbgControlUnit*",
                "*MaaThriftControlUnit*",
                "*MaaRpc*",
                "*MaaHttp*",
                "plugins",
                "*.node",
                "*MaaPiCli*",
            ),
            dirs_exist_ok=True,
        )
        shutil.copytree(
            working_dir / "deps" / "share" / "MaaAgentBinary",
            install_path / "libs" / "MaaAgentBinary",
            dirs_exist_ok=True,
        )
        shutil.copytree(
            working_dir / "deps" / "bin" / "plugins",
            install_path / "plugins" / get_dotnet_platform_tag(),
            dirs_exist_ok=True,
        )


def install_resource():
    configure_ocr_model()

    shutil.copytree(
        working_dir / "assets" / "resource",
        install_path / "resource",
        dirs_exist_ok=True,
    )
    shutil.copy2(
        working_dir / "assets" / "interface.json",
        install_path,
    )

    with open(install_path / "interface.json", "r", encoding="utf-8") as f:
        interface = jsonc.load(f)

    interface["version"] = version

    # 开发模式下 agent 路径是 "./../agent/main.py"
    # 打包后 interface.json 和 agent/ 同级，改为 "./agent/main.py"
    if "agent" in interface and "child_args" in interface["agent"]:
        interface["agent"]["child_args"] = [
            arg.replace("./../agent/", "./agent/")
            for arg in interface["agent"]["child_args"]
        ]

    with open(install_path / "interface.json", "w", encoding="utf-8") as f:
        jsonc.dump(interface, f, ensure_ascii=False, indent=4)


def install_chores():
    shutil.copy2(working_dir / "README.md", install_path)
    shutil.copy2(working_dir / "LICENSE", install_path)


def install_agent():
    shutil.copytree(
        working_dir / "agent",
        install_path / "agent",
        dirs_exist_ok=True,
    )


def install_requirements():
    """把 requirements.txt 复制到产物根目录（供运行时按需安装参考）。"""
    req_file = working_dir / "requirements.txt"
    if req_file.exists():
        shutil.copy2(req_file, install_path / "requirements.txt")
        print("requirements.txt copied.")
    else:
        print("requirements.txt not found, skipping.")


def install_python_env():
    """
    为 Windows 产物打包内置 Python 环境：
    - 下载 Python Embeddable Package（免安装、免注册表）
    - 解压到 install/python/
    - 启用 pip（修改 ._pth 文件）
    - 安装 requirements.txt 的依赖到 python/Lib/site-packages/
    - 修改 interface.json 的 child_exec 指向内置 python

    非 Windows 平台跳过（macOS/Linux 用户系统 Python 即可）。
    """
    if os_name != "win":
        # 非 Windows 平台：创建 .venv 并装好依赖（CI Runner 是 Linux）
        req_file = working_dir / "requirements.txt"
        if not req_file.exists():
            print("requirements.txt not found, skipping python env setup.")
            return

        venv_dir = install_path / ".venv"
        print(f"Creating venv at {venv_dir} ...")
        subprocess.check_call([sys.executable, "-m", "venv", str(venv_dir)])

        # CI Runner 是 Linux，始终用 bin/python3
        venv_python = venv_dir / "bin" / "python3"
        if not venv_python.exists():
            venv_python = venv_dir / "bin" / "python"

        print("Installing dependencies into venv ...")
        subprocess.check_call([
            str(venv_python), "-m", "pip", "install",
            "-r", str(req_file),
            "--no-warn-script-location", "-q",
        ])
        print("Python venv ready.")
        return

    # ── Windows：下载并配置 Python Embeddable Package ────────────
    embed_arch = "amd64" if arch == "x86_64" else "arm64"
    embed_zip_name = f"python-{PYTHON_EMBED_VERSION}-embed-{embed_arch}.zip"
    embed_url = (
        f"https://www.python.org/ftp/python/{PYTHON_EMBED_VERSION}/{embed_zip_name}"
    )
    embed_zip_path = install_path / embed_zip_name
    python_dir = install_path / "python"

    print(f"Downloading Python Embeddable Package: {embed_url}")
    urllib.request.urlretrieve(embed_url, embed_zip_path)

    print(f"Extracting to {python_dir} ...")
    python_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(embed_zip_path, "r") as zf:
        zf.extractall(python_dir)
    embed_zip_path.unlink()  # 删除压缩包，减小体积

    # ── 启用 pip：修改 ._pth 文件，添加 import site ──────────────
    ver_nodot = "".join(PYTHON_EMBED_VERSION.split(".")[:2])  # "313"
    pth_file = python_dir / f"python{ver_nodot}._pth"
    if pth_file.exists():
        content = pth_file.read_text(encoding="utf-8")
        # 把 "#import site" 改为 "import site"
        content = content.replace("#import site", "import site")
        pth_file.write_text(content, encoding="utf-8")
        print(f"Patched {pth_file.name} to enable site packages.")
    else:
        print(f"WARNING: {pth_file.name} not found, pip may not work.")

    # ── 安装依赖：CI 跑在 Linux 上无法执行 .exe ──────────────────
    # 用 Linux pip download 下载适配 Windows 的 whl，直接解压到 site-packages
    req_file = working_dir / "requirements.txt"
    site_packages = python_dir / "Lib" / "site-packages"
    site_packages.mkdir(parents=True, exist_ok=True)

    if req_file.exists():
        print("Downloading wheels for embedded Python (via Linux pip) ...")
        wheel_dir = install_path / "_wheels_tmp"
        wheel_dir.mkdir(exist_ok=True)

        # pip download 下载适合 Windows amd64/arm64 cp313 的 whl
        pip_platform = "win_amd64" if embed_arch == "amd64" else "win_arm64"
        subprocess.check_call([
            sys.executable, "-m", "pip", "download",
            "-r", str(req_file),
            "-d", str(wheel_dir),
            "--platform", pip_platform,
            "--python-version", "313",
            "--implementation", "cp",
            "--abi", "cp313",
            "--only-binary", ":all:",
            "-q",
        ])

        # whl 本质是 zip，直接解压到 site-packages
        print("Extracting wheels into embedded site-packages ...")
        for whl in wheel_dir.glob("*.whl"):
            with zipfile.ZipFile(whl, "r") as zf:
                zf.extractall(site_packages)
        shutil.rmtree(wheel_dir)
        print("Dependencies installed into embedded Python.")
    else:
        print("requirements.txt not found, skipping dependency install.")

    # ── 修改 interface.json：child_exec 指向内置 python ──────────
    interface_path = install_path / "interface.json"
    with open(interface_path, "r", encoding="utf-8") as f:
        interface = jsonc.load(f)

    if "agent" in interface:
        interface["agent"]["child_exec"] = "./python/python.exe"

    with open(interface_path, "w", encoding="utf-8") as f:
        jsonc.dump(interface, f, ensure_ascii=False, indent=4)

    print(f"Python Embeddable Package ready at {python_dir}")


if __name__ == "__main__":
    install_deps()
    install_resource()
    install_chores()
    install_agent()
    install_requirements()
    install_python_env()

    print(f"Install to {install_path} successfully.")