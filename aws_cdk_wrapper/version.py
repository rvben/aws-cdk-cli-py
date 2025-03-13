"""Version information for aws-cdk-wrapper package.

This file is automatically updated during the build process to match
the version of the AWS CDK CLI being bundled.
"""

__version__ = "2.1003.0-dev1"  # Placeholder that will be updated during build

# Build information
__build_date__ = None
__build_timestamp__ = None
__build_commit__ = None

# Bundled software versions
__node_version__ = "18.16.0"  # Version of Node.js bundled with this package
__cdk_version__ = __version__  # Version of AWS CDK bundled (same as package version)

# Component licenses
__license__ = "MIT"  # License for the Python wrapper package
__cdk_license__ = "Apache-2.0"  # License for AWS CDK
__node_license__ = "MIT"  # License for Node.js

def get_version_info():
    """Return version information as a dictionary."""
    return {
        "version": __version__,
        "build_date": __build_date__,
        "build_timestamp": __build_timestamp__,
        "build_commit": __build_commit__,
        "node_version": __node_version__,
        "cdk_version": __cdk_version__,
        "license": __license__,
        "cdk_license": __cdk_license__,
        "node_license": __node_license__
    } 