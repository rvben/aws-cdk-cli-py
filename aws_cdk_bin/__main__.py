"""
Entry point for running aws_cdk_bin module directly.
"""
from aws_cdk_bin.cli import main
import sys

if __name__ == "__main__":
    sys.exit(main()) 