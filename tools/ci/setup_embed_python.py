import os
import shutil
import urllib.request
import zipfile
import subprocess

# 配置
PYTHON_VERSION = "3.11.5"
PYTHON_URL = f"https://www.python.org/ftp/python/{PYTHON_VERSION}/python-{PYTHON_VERSION}-embed-amd64.zip"
INSTALL_DIR = "install/python"

def setup():
    if not os.path.exists(INSTALL_DIR):
        os.makedirs(INSTALL_DIR)

    # 1. 下载并解压
    zip_path = "python_embed.zip"
    print(f"Downloading Python {PYTHON_VERSION}...")
    urllib.request.urlretrieve(PYTHON_URL, zip_path)
    
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(INSTALL_DIR)
    os.remove(zip_path)

    # 2. 修复 ._pth 文件 (让嵌入式 Python 能够识别 site-packages)
    for file in os.listdir(INSTALL_DIR):
        if file.endswith("._pth"):
            pth_path = os.path.join(INSTALL_DIR, file)
            with open(pth_path, 'w') as f:
                f.write(".\npython311.zip\nimport site\n") # 注意版本号要对应
            print(f"Fixed {file}")

    # 3. 安装 pip
    print("Installing pip...")
    get_pip_path = os.path.join(INSTALL_DIR, "get-pip.py")
    urllib.request.urlretrieve("https://bootstrap.pypa.io/get-pip.py", get_pip_path)
    
    python_exe = os.path.join(INSTALL_DIR, "python.exe")
    subprocess.check_call([python_exe, get_pip_path, "--no-warn-script-location"])
    os.remove(get_pip_path)
    print("Pip setup complete.")

if __name__ == "__main__":
    setup()