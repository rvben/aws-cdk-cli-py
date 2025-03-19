#!/usr/bin/env python3

from aws_cdk_cli.installer import (
    find_system_nodejs, 
    get_nodejs_version, 
    get_cdk_node_requirements, 
    is_nodejs_compatible,
    setup_nodejs,
    download_node
)
import sys
import os

# Set environment variables to test functionality
os.environ['AWS_CDK_BIN_USE_SYSTEM_NODE'] = '1'
os.environ['VERBOSE'] = '1'

def main():
    print("Testing Node.js detection functionality")
    
    # Test find_system_nodejs
    node_path = find_system_nodejs()
    print(f'Node.js found: {node_path}')
    
    # Test version detection
    if node_path:
        version = get_nodejs_version(node_path)
        print(f'Version: {version}')
    
    # Test CDK requirements detection
    req = get_cdk_node_requirements() or '>= 14.15.0'
    print(f'CDK requires: {req}')
    
    # Test compatibility check
    if node_path:
        is_compatible = is_nodejs_compatible(get_nodejs_version(node_path), req)
        print(f'Compatible: {is_compatible}')
    
    # Test the default behavior
    print("\nTesting default setup_nodejs behavior:")
    if 'AWS_CDK_BIN_USE_SYSTEM_NODE' in os.environ:
        del os.environ['AWS_CDK_BIN_USE_SYSTEM_NODE']
    if 'AWS_CDK_BIN_FORCE_DOWNLOAD_NODE' in os.environ:
        del os.environ['AWS_CDK_BIN_FORCE_DOWNLOAD_NODE']
    os.environ['VERBOSE'] = '1'
    nodejs_path = setup_nodejs()
    print(f'Default Node.js path: {nodejs_path}')
    
    # Test with AWS_CDK_BIN_USE_SYSTEM_NODE=1
    print("\nTesting with AWS_CDK_BIN_USE_SYSTEM_NODE=1:")
    os.environ['AWS_CDK_BIN_USE_SYSTEM_NODE'] = '1'
    if 'AWS_CDK_BIN_FORCE_DOWNLOAD_NODE' in os.environ:
        del os.environ['AWS_CDK_BIN_FORCE_DOWNLOAD_NODE']
    nodejs_path = setup_nodejs()
    print(f'System Node.js path: {nodejs_path}')
    
    # Test with AWS_CDK_BIN_FORCE_DOWNLOAD_NODE=1
    print("\nTesting with AWS_CDK_BIN_FORCE_DOWNLOAD_NODE=1:")
    if 'AWS_CDK_BIN_USE_SYSTEM_NODE' in os.environ:
        del os.environ['AWS_CDK_BIN_USE_SYSTEM_NODE']
    os.environ['AWS_CDK_BIN_FORCE_DOWNLOAD_NODE'] = '1'
    nodejs_path = setup_nodejs()
    print(f'Forced download Node.js path: {nodejs_path}')
    
    # Test with both flags set (system should take precedence)
    print("\nTesting with both AWS_CDK_BIN_USE_SYSTEM_NODE=1 and AWS_CDK_BIN_FORCE_DOWNLOAD_NODE=1:")
    os.environ['AWS_CDK_BIN_USE_SYSTEM_NODE'] = '1'
    os.environ['AWS_CDK_BIN_FORCE_DOWNLOAD_NODE'] = '1'
    nodejs_path = setup_nodejs()
    print(f'Precedence test Node.js path: {nodejs_path}')
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 