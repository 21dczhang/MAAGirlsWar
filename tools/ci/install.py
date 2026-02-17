import os
import shutil
import sys

def install(version, tag):
    target_dir = "install"
    project_name = "MaaGirlsWar"
    temp_dir = "temp"

    # Ensure target directory exists
    if not os.path.exists(target_dir):
        os.makedirs(target_dir)

    print(f"[*] Assembling project: {project_name} {version} ({tag})")

    # 1. Copy MaaFramework runtime files
    if os.path.exists(temp_dir):
        print(f"[*] Copying runtime files from {temp_dir}...")
        try:
            for item in os.listdir(temp_dir):
                src_path = os.path.join(temp_dir, item)
                dst_path = os.path.join(target_dir, item)
                
                if os.path.isdir(src_path):
                    # Use copytree for directories
                    shutil.copytree(src_path, dst_path, dirs_exist_ok=True)
                else:
                    # Use copy2 for files
                    shutil.copy2(src_path, dst_path)
        except Exception as e:
            print(f"[!] Error copying runtime files: {e}")
            sys.exit(1)
        
        # Rename executable
        old_exe = os.path.join(target_dir, "MaaFramework.exe")
        new_exe = os.path.join(target_dir, f"{project_name}.exe")
        
        # Handle case sensitivity check roughly
        if os.path.exists(old_exe):
            if os.path.exists(new_exe):
                os.remove(new_exe)
            try:
                os.rename(old_exe, new_exe)
                print(f"[+] Renamed executable to: {project_name}.exe")
            except Exception as e:
                 print(f"[!] Failed to rename executable: {e}")
        else:
            print("[!] Warning: MaaFramework.exe not found in temp. Check download step.")

    # 2. Copy business logic folders (agent, assets)
    folders_to_copy = ["agent", "assets"]
    for folder in folders_to_copy:
        if os.path.exists(folder):
            dest = os.path.join(target_dir, folder)
            print(f"[*] Copying {folder} to {dest}...")
            if os.path.exists(dest):
                shutil.rmtree(dest)
            try:
                shutil.copytree(folder, dest)
            except Exception as e:
                print(f"[!] Error copying {folder}: {e}")
                sys.exit(1)
        else:
            print(f"[!] Warning: Folder not found: {folder}")

    print(f"[+] Build complete. Artifacts located in {target_dir}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python install.py <version> <tag>")
        sys.exit(1)
    else:
        install(sys.argv[1], sys.argv[2])