#!/usr/bin/env python3
"""
Test script for AWS CDK Python wrapper.
This script tests the basic functionality of the AWS CDK Python wrapper.
"""

import os
import sys
import subprocess
import tempfile
import shutil
from pathlib import Path

def test_installation():
    """Test if the package can be installed in a virtual environment."""
    print("Testing installation...")
    with tempfile.TemporaryDirectory() as tmp_dir:
        venv_dir = os.path.join(tmp_dir, "venv")
        # Create a virtual environment
        subprocess.run([sys.executable, "-m", "venv", venv_dir], check=True)
        
        # Get the path to the Python executable in the virtual environment
        if os.name == "nt":  # Windows
            python_executable = os.path.join(venv_dir, "Scripts", "python.exe")
        else:  # Unix/Linux/MacOS
            python_executable = os.path.join(venv_dir, "bin", "python")
        
        # Install the package in development mode
        print("Installing package in development mode...")
        subprocess.run(
            [python_executable, "-m", "pip", "install", "-e", "."],
            check=True
        )
        
        # Test importing the package
        print("Testing import...")
        result = subprocess.run(
            [python_executable, "-c", "import aws_cdk; print(aws_cdk.__version__)"],
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            print(f"Failed to import aws_cdk: {result.stderr}")
            return False
        
        print(f"Successfully imported aws_cdk version: {result.stdout.strip()}")
        return True

def test_cdk_version():
    """Test if the CDK version command works."""
    print("Testing CDK version command...")
    result = subprocess.run(
        [sys.executable, "-m", "aws_cdk.cli", "--version"],
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        print(f"Failed to run CDK version command: {result.stderr}")
        return False
    
    print(f"CDK version output: {result.stdout}")
    return True

def test_cdk_init():
    """Test if the CDK init command works."""
    print("Testing CDK init command...")
    with tempfile.TemporaryDirectory() as tmp_dir:
        os.chdir(tmp_dir)
        result = subprocess.run(
            [sys.executable, "-m", "aws_cdk.cli", "init", "app", "--language=python"],
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            print(f"Failed to run CDK init command: {result.stderr}")
            print(f"Output: {result.stdout}")
            return False
        
        print("CDK init command successful")
        print(f"Project created in {tmp_dir}")
        # Check if expected files were created
        expected_files = ["app.py", "cdk.json", "requirements.txt", "setup.py"]
        for file in expected_files:
            if not os.path.exists(os.path.join(tmp_dir, file)):
                print(f"Expected file {file} not found")
                return False
        
        print("All expected files were created")
        return True

def main():
    """Run all tests."""
    tests = [
        ("Installation", test_installation),
        ("CDK Version", test_cdk_version),
        ("CDK Init", test_cdk_init)
    ]
    
    success = True
    for name, test_func in tests:
        print(f"\n=== Running Test: {name} ===")
        try:
            if not test_func():
                success = False
                print(f"❌ Test '{name}' failed")
            else:
                print(f"✅ Test '{name}' passed")
        except Exception as e:
            success = False
            print(f"❌ Test '{name}' raised an exception: {e}")
    
    if success:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print("\n❌ Some tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 