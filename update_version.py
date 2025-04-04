import os
import datetime
import sys

version = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("CDK_VERSION")
if not version:
    print("Error: No version specified")
    sys.exit(1)

os.makedirs("aws_cdk_cli", exist_ok=True)
with open("aws_cdk_cli/version.py", "w") as f:
    f.write(f'''"""Version information for aws-cdk-cli package.

This file is auto-generated during the build process.
It contains the AWS CDK version information.
"""

__version__ = "{version}"  # Current AWS CDK version

# Build information
__build_date__ = "{datetime.datetime.now().strftime("%Y-%m-%d")}"
__build_timestamp__ = "{datetime.datetime.now().timestamp()}"
__build_commit__ = None

# Bundled software versions
__node_version__ = "22.14.0"  # Version of Node.js downloaded during installation
__cdk_version__ = __version__  # Version of AWS CDK bundled (same as package version)

# Component licenses
__license__ = "MIT"  # License for the Python wrapper package
__cdk_license__ = "Apache-2.0"  # License for AWS CDK
__node_license__ = "MIT"  # License for Node.js

def get_version_info():
    """Return version information as a dictionary."""
    return {{
        "version": __version__,
        "build_date": __build_date__,
        "build_timestamp": __build_timestamp__,
        "build_commit": __build_commit__,
        "node_version": __node_version__,
        "cdk_version": __cdk_version__,
        "license": __license__,
        "cdk_license": __cdk_license__,
        "node_license": __node_license__
    }}
''')
print(f"Updated version.py with version {version}")
