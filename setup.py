from setuptools import setup, find_packages

setup(
    name="plant-timelapse",
    version="1.0.0",
    description="Plant timelapse system using ADB to trigger Android phones and manage captures",
    author="Your Name",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "flask>=2.0.0",
    ],
    entry_points={
        "console_scripts": [
            "plant-timelapse=scripts.main:run_app",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.7",
)
