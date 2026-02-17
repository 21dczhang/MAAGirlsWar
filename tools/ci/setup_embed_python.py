import os
import shutil
import urllib.request
import zipfile
import subprocess
import sys

# Configuration
PYTHON_VERSION = "3.11.5"
PYTHON_URL = f"https://www.python.org/ftp/python/{PYTHON_VERSION}/python-{PYTHON_VERSION}-embed-amd64.zip"
INSTALL_DIR = os.path.join("install", "python")

def setup():
    print("[*] Starting Python environment setup...")
    
    current_dir = os.getcwd()
    print(f"[*] Working directory: {current_dir}")

    if not os.path.exists(INSTALL_DIR):
        print(f"[*] Creating directory: {INSTALL_DIR}")
        os.makedirs(INSTALL_DIR, exist_ok=True)

    # 1. Download
    zip_path = "python_embed.zip"
    if not os.path.exists(zip_path):
        print(f"[*] Downloading Python from {PYTHON_URL}...")
        try:
            urllib.request.urlretrieve(PYTHON_URL, zip_path)
            print("[+] Download complete.")
        except Exception as e:
            print(f"[!] Download failed: {e}")
            sys.exit(1)

    # 2. Extract
    print("[*] Extracting...")
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(INSTALL_DIR)
        print(f"[+] Extracted to {INSTALL_DIR}")
    except Exception as e:
        print(f"[!] Extraction failed: {e}")
        sys.exit(1)
    finally:
        if os.path.exists(zip_path):
            os.remove(zip_path)

    # 3. Fix ._pth file
    print("[*] Fixing ._pth file to enable site-packages...")
    found_pth = False
    for file in os.listdir(INSTALL_DIR):
        if file.endswith("._pth"):
            pth_path = os.path.join(INSTALL_DIR, file)
            try:
                with open(pth_path, 'w') as f:
                    # Pure ASCII content
                    f.write(".\npython311.zip\nimport site\n")
                print(f"[+] Fixed: {file}")
                found_pth = True
            except Exception as e:
                print(f"[!] Failed to write .pth file: {e}")
                sys.exit(1)
    
    if not found_pth:
        print("[!] Warning: No ._pth file found.")

    # 4. Install pip
    print("[*] Installing pip...")
    get_pip_path = os.path.join(INSTALL_DIR, "get-pip.py")
    try:
        print("[*] Downloading get-pip.py...")
        urllib.request.urlretrieve("https://bootstrap.pypa.io/get-pip.py", get_pip_path)
        
        python_exe = os.path.abspath(os.path.join(INSTALL_DIR, "python.exe"))
        print(f"[*] Running: {python_exe} {get_pip_path}")
        
        # Capture output to avoid encoding issues in parent process, but check return code
        result = subprocess.run(
            [python_exe, get_pip_path, "--no-warn-script-location"], 
            check=False,
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            print("[+] Pip installation successful.")
        else:
            print(f"[!] Pip installation failed with code {result.returncode}.")
            # Print stderr but encode safely just in case
            print(f"[!] Error: {str(result.stderr)}")
            sys.exit(1)
            
    except Exception as e:
        print(f"[!] Error during pip installation: {e}")
        sys.exit(1)
    finally:
        if os.path.exists(get_pip_path):
            os.remove(get_pip_path)

    print("[+] Setup completed successfully.")

if __name__ == "__main__":
    setup()