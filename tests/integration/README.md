# Integration Tests for AWS CDK Python Wrapper

This directory contains integration tests for the AWS CDK Python wrapper. These tests perform actual downloads and run real CDK commands, so they are skipped by default.

## Running Integration Tests

To run the integration tests, use the `--integration` flag with pytest:

```bash
pytest tests/integration/ -v --integration
```

You can also run all tests including integration tests:

```bash
pytest -v --integration
```

## What These Tests Do

The integration tests perform the following:

1. **Node.js Download Test**: Tests that Node.js is downloaded automatically when needed.
2. **CDK Download Test**: Tests that AWS CDK is downloaded automatically when needed.
3. **CDK Version Command Test**: Tests running the CDK version command with the real binary.
4. **CDK Init and Synth Test**: Tests creating a new CDK app and synthesizing it with the real binary.

## Requirements

These tests require:
- Internet connection to download Node.js and AWS CDK
- Sufficient permissions to write to the package directory
- Sufficient disk space for Node.js binaries (~30-50MB)

## CI/CD Integration

These tests are run as part of the CI/CD pipeline in a separate job after the regular tests. They are run on all supported platforms (Linux, Windows, macOS) to ensure cross-platform compatibility. 