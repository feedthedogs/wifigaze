import os
import subprocess
import shutil

def build_vue():
    # Navigate to the frontend directory
    frontend_dir = os.path.join(os.path.dirname(__file__), 'frontend')
    # Run the Vue build command
    subprocess.run(['npm', 'install'], cwd=frontend_dir, check=True)
    subprocess.run(['npm', 'run', 'build'], cwd=frontend_dir, check=True)
    # Move the build output to the static directory
    build_output_dir = os.path.join(frontend_dir, 'dist')
    static_dir = os.path.join(os.path.dirname(__file__), 'wifigaze', 'static')
    if not os.path.exists(static_dir):
        os.makedirs(static_dir)
    for item in os.listdir(build_output_dir):
        item_path = os.path.join(build_output_dir, item)
        if os.path.isdir(item_path):
            shutil.copytree(item_path, os.path.join(static_dir, item), dirs_exist_ok=True)
        else:
            shutil.copy2(item_path, static_dir)

# Build the Vue project before setup
build_vue()