"""
Entry point for running aws_cdk_cli module directly.
"""

from aws_cdk_cli.cli import main
import sys

if __name__ == "__main__":
    sys.exit(main())
