import os
import subprocess
from setuptools import setup, find_packages
from setuptools.command.build_py import build_py

class CustomBuild(build_py):
    def run(self):
        # Build Vue.js frontend
        subprocess.check_call(["npm", "install"], cwd="frontend")
        subprocess.check_call(["npm", "run", "build"], cwd="frontend")
        # Copy build output to the static folder
        os.makedirs("wifigaze/static", exist_ok=True)
        for item in os.listdir("frontend/dist"):
            source = os.path.join("frontend/dist", item)
            dest = os.path.join("wifigaze/static", item)
            if os.path.isdir(source):
                subprocess.check_call(["cp", "-r", source, dest])
            else:
                subprocess.check_call(["cp", source, dest])
        super().run()

setup(
    name="wifigaze",
    version="0.1.0",
    packages=find_packages(),
    cmdclass={"build_py": CustomBuild},
    include_package_data=True,
    package_data={"wifigaze": ["static/*", "static/css/*", "static/js/*", "static/index.html", "static/favicon.ico"]},
    install_requires=["quart", 
                      "docopt", 
                      "loguru"],
    entry_points={
        "console_scripts": [
            "wifigaze=wifigaze.__main__:main_cli",
        ],
    },
    author="feedthedogs",
    author_email="feedthedogs@hotmail.com",
    description="Visualise the wifi devices around you communicating to each other in their own networks",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/feedthedogs/wifigaze",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],    
)
