import os
import shutil
import sys

def install(version, tag):
    target_dir = "install"
    project_name = "MaaGirlsWar"

    # 1. 移动必要的文件夹
    # 假设 MaaFramework 的运行时已经在 temp 目录下 (由 Workflow 下载)
    if os.path.exists("temp"):
        for item in os.listdir("temp"):
            shutil.copy2(os.path.join("temp", item), target_dir)
        # 重命名主程序
        if os.path.exists(os.path.join(target_dir, "MaaFramework.exe")):
            os.rename(os.path.join(target_dir, "MaaFramework.exe"), 
                      os.path.join(target_dir, f"{project_name}.exe"))

    # 2. 拷贝业务代码
    folders_to_copy = ["agent", "assets"]
    for folder in folders_to_copy:
        dest = os.path.join(target_dir, folder)
        if os.path.exists(dest):
            shutil.rmtree(dest)
        shutil.copytree(folder, dest)

    print(f"Build {project_name} {version} for {tag} successful.")

if __name__ == "__main__":
    # 简单接收参数: python install.py 1.0.0 win-x64
    install(sys.argv[1], sys.argv[2])