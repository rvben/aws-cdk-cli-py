# GitHub Workflows for AWS CDK Wrapper

## check-cdk-version.yml

This workflow checks for new releases of the AWS CDK package in the npm registry and creates a new tag in the repository when a new version is detected.

### Features:

- Runs every 6 hours
- Resource-efficient design to minimize GitHub Actions minutes usage
- Early exit if no new version is detected
- Automated tag creation when a new AWS CDK version is available
- Can be manually triggered via the GitHub Actions interface

### How it works:

1. The workflow runs a Python script that:
   - Determines the current version from `aws_cdk_cli/version.py`
   - Checks the npm registry API for the latest version of AWS CDK
   - Compares the versions to detect updates

2. If a new version is detected:
   - Updates the version in the repository
   - Creates a new git tag matching the AWS CDK version
   - Pushes the tag to the repository

### Configuration:

No additional configuration is needed as the workflow uses your existing repository structure and version file.

### Manual Triggering:

You can manually trigger this workflow from the Actions tab in the GitHub repository interface by selecting "Check for AWS CDK Updates" and clicking "Run workflow". 