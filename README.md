# AWS CDK CLI - Python Wrapper

A Python package that provides a wrapper around the AWS CDK CLI tool, allowing Python developers to install and use AWS CDK via pip/uv instead of npm. This package bundles the AWS CDK code and either uses your system's Node.js installation or downloads a platform-specific Node.js runtime during installation.

## How It Works

This package follows a hybrid approach:
1. It bundles the AWS CDK JavaScript code with the package
2. For Node.js, it either:
   - Uses your system's Node.js installation if available (default)
   - Downloads appropriate Node.js binaries for your platform during installation
3. This approach ensures compatibility across platforms while leveraging existing Node.js installations when possible

## Why Use This Package?

If you're a Python developer working with AWS CDK, you typically need to install Node.js and npm first, then install the CDK CLI globally using npm. This wrapper simplifies this by:
- Bundling the CDK CLI code directly into a Python package
- Using your existing Node.js installation or downloading a minimal Node.js runtime

Benefits:
- No need to install npm or manage global npm packages
- Works in environments where npm installation is restricted
- Keeps AWS CDK installations isolated in Python virtual environments
- Consistent CDK versioning tied to your Python dependencies
- Optimized package size with platform-specific binary downloads only when needed

## Installation

```bash
# Using pip
pip install aws-cdk-cli

# Using uv
uv pip install aws-cdk-cli

# Install a specific version
pip install aws-cdk-cli==2.108.0
```

Note: During installation, the package will download the appropriate Node.js binaries for your platform. This requires an internet connection for the initial setup.

## Features

- **No npm dependency**: Eliminates the need for npm while still requiring Node.js (either system or downloaded)
- **Platform support**: Downloads appropriate Node.js binaries for Windows, macOS, and Linux when needed
- **Automatic updates**: Stays in sync with official AWS CDK releases
- **Seamless integration**: Use the same CDK commands you're familiar with
- **Offline caching**: Downloaded binaries are cached for offline usage
- **License compliance**: Includes all necessary license texts
- **Optimized size**: Only downloads the binaries needed for your platform
- **Flexible runtime options**: Can use system Node.js, downloaded Node.js, or Bun runtime
- **Compatible with Windows, macOS, and Linux**
- **Supports both x86_64 and ARM64 architectures**

## Additional Features

### Node.js Access in Virtual Environments

When you install AWS CDK CLI in a Python virtual environment, the package automatically creates a `node` symlink in your virtual environment's `bin` directory. This allows you to run the `node` command directly without requiring Node.js to be installed on your system.

For example:

```bash
# Activate your virtual environment
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Now you can use the node command
node --version
```

If for some reason the symlink wasn't created, you can create it manually by running:

```bash
cdk --create-node-symlink
```

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

## JavaScript Runtime Options

The wrapper supports various JavaScript runtimes in the following priority order:

### Using system Node.js (default)

By default, the wrapper first checks if you have Node.js installed on your system. It will use your system Node.js installation if it meets the minimum required version for AWS CDK (typically v14.15.0+).

> **Note:** Node.js version compatibility warnings are silenced by default. If you want to see these warnings:
> ```bash
> cdk --show-node-warnings [commands...]
> ```

If you want to force using your system Node.js regardless of version:

```bash
cdk --use-system-node [commands...]
```

### Using Bun (if explicitly enabled)

Bun is a fast JavaScript runtime with 100% Node.js compatibility. Enable it with:

```bash
cdk --use-bun [commands...]
```

Requirements for using Bun:
- Bun v1.1.0 or higher must be installed on your system
- The wrapper will verify that Bun's reported Node.js version is compatible with CDK requirements

### Using downloaded Node.js (fallback)

If no compatible system Node.js is found, the wrapper will download and use the Node.js runtime for your platform during installation. This is guaranteed to be a version that's compatible with AWS CDK.

### Using downloaded Node.js explicitly

```bash
cdk --use-downloaded-node [commands...]
```

This explicitly uses the downloaded Node.js even if a compatible system Node.js is available.

## Environment Variables

The package respects the following environment variables:

- `AWS_CDK_DEBUG`: Set to "1" for verbose debug output
- `AWS_CDK_CLI_USE_SYSTEM_NODE=1`: Use system Node.js if available
- `AWS_CDK_CLI_USE_BUN=1`: Use Bun as the JavaScript runtime
- `AWS_CDK_CLI_USE_DOWNLOADED_NODE=1`: Use downloaded Node.js instead of system Node.js

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