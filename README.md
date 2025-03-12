# AWS CDK Python Wrapper

A Python package that provides a wrapper around the AWS CDK CLI tool, allowing Python developers to install and use AWS CDK via pip/uv instead of npm. This package includes a bundled Node.js runtime, eliminating the need for a separate npm/Node.js installation.

## Why Use This Package?

If you're a Python developer working with AWS CDK, you typically need to install Node.js and npm first, then install the CDK CLI globally using npm. This wrapper eliminates that requirement by bundling a minimal Node.js runtime and the CDK CLI code directly into a Python package.

Benefits:
- No need to install or configure Node.js/npm
- Works in environments where npm installation is restricted
- Keeps AWS CDK installations isolated in Python virtual environments
- Consistent CDK versioning tied to your Python dependencies

## Installation

```bash
# Using pip
pip install aws-cdk

# Using uv
uv pip install aws-cdk

# Install a specific version
pip install aws-cdk==2.108.0
```

## Features

- **Zero npm dependency**: No need to install Node.js or npm on your system
- **Platform support**: Includes Node.js binaries for Windows, macOS, and Linux
- **Automatic updates**: Stays in sync with official AWS CDK releases
- **Seamless integration**: Use the same CDK commands you're familiar with
- **Offline caching**: Downloaded binaries are cached for offline usage
- **License compliance**: Includes all necessary license texts

## Usage

After installation, you can use the `cdk` command just as you would with the npm version:

```bash
# Initialize a new CDK project
cdk init app --language python

# Deploy a CDK stack
cdk deploy

# List all CDK stacks
cdk list

# Show version information
cdk --version

# Additional wrapper-specific commands
cdk --verbose     # Show detailed installation information
cdk --license     # Show license information
cdk --update      # Update to the latest AWS CDK version
cdk --offline     # Run in offline mode using cached packages
```

## How It Works

This package:
1. Bundles a lightweight Node.js runtime specific to your platform
2. Includes the AWS CDK JavaScript code directly in the package
3. Creates Python wrappers that forward commands to the bundled Node.js runtime
4. Handles path resolution and execution of the underlying CDK commands

## Supported Platforms

- Windows (x86_64)
- macOS (Intel and Apple Silicon)
- Linux (x86_64 and ARM64)

If you're using an unsupported platform, please open an issue on our GitHub repository.

## Directory Structure

The package has the following structure:

```
aws_cdk/
├── __init__.py           # Package initialization
├── cli.py                # Command-line interface implementation
├── installer.py          # Node.js and CDK installation logic
├── post_install.py       # Post-installation script
├── version.py            # Version information
├── node_binaries/        # Platform-specific Node.js binaries
│   ├── darwin/           # macOS binaries
│   │   ├── arm64/        # Apple Silicon
│   │   └── x86_64/       # Intel
│   ├── linux/            # Linux binaries
│   │   ├── aarch64/      # ARM64
│   │   └── x86_64/       # x86_64
│   └── windows/          # Windows binaries
│       └── x86_64/       # x86_64
└── node_modules/         # CDK JavaScript code
    └── aws-cdk/          # AWS CDK npm package
```

## Testing the Implementation

The package includes a comprehensive test suite to ensure functionality across different platforms. You can run tests using the included Makefile:

```bash
# Install development dependencies
pip install -e ".[dev]"

# Run basic tests (fast tests only)
make test

# Run all tests including slow tests that create real CDK apps
make test-slow

# Test local installation in a new virtual environment
make test-local
```

### Manual Testing

You can also manually test the package:

```bash
# Install in development mode
pip install -e .

# Try importing the package
python -c "import aws_cdk; print(aws_cdk.__version__)"

# Test the CDK CLI
cdk --version

# Create and test a CDK app
mkdir test-app && cd test-app
cdk init app --language=python
cdk synth
```

## Troubleshooting

### Permission Issues

If you encounter permission issues when running cdk commands, try:
- Using a virtual environment
- Using the `--user` flag with pip install
- Running with elevated privileges if appropriate for your environment

### Extracting Binaries

If you encounter issues with binary extraction during installation:
- Ensure you have sufficient disk space
- Check write permissions in your Python packages directory
- Try reinstalling the package

### Network Connectivity

If you encounter network-related issues:
- Try running in offline mode (`cdk --offline`) if you've previously installed
- Check your network connectivity and proxy settings
- If behind a corporate proxy, set the appropriate HTTP_PROXY environment variables

## Environment Variables

The package respects the following environment variables:

- `AWS_CDK_OFFLINE`: Set to "1" to use cached packages without network access
- `AWS_CDK_DEBUG`: Set to "1" for verbose debug output
- `HTTP_PROXY` / `HTTPS_PROXY`: Used for network connections if set
- All standard AWS CDK environment variables

## License Information

This package contains:
- AWS CDK (Apache License 2.0)
- Node.js (MIT License)

All copyright notices and license texts are included in the distribution. You can view the licenses using:

```bash
cdk --license
```

## Version Synchronization

The version of this Python package matches the version of the AWS CDK npm package it wraps. Updates are automatically published when new versions of AWS CDK are released.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

### Development Setup

1. Clone the repository
   ```bash
   git clone https://github.com/your-org/aws-cdk.git
   cd aws-cdk
   ```

2. Create a virtual environment
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. Install in development mode
   ```bash
   pip install -e ".[dev]"
   ```

4. Run tests
   ```bash
   make test
   ```

### Building from Source

```bash
python -m build
```

## Acknowledgements

- [AWS CDK](https://github.com/aws/aws-cdk) - The original AWS CDK project
- [Node.js](https://nodejs.org/) - JavaScript runtime bundled with this package 