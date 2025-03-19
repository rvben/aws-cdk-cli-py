#!/usr/bin/env python3

from aws_cdk_cli.installer import (
    find_system_bun,
    get_bun_version,
    get_bun_reported_nodejs_version,
    is_bun_compatible_with_cdk,
    get_cdk_node_requirements,
    setup_nodejs,
    MIN_BUN_VERSION
)
import sys
import os
import semver

def main():
    print("Testing Bun detection functionality")
    
    # Test find_system_bun
    bun_path = find_system_bun()
    print(f'Bun found: {bun_path}')
    
    if not bun_path:
        print("Bun not found on system. Please install Bun v1.1.0+ to test this functionality.")
        return 0
    
    # Test version detection
    bun_version = get_bun_version(bun_path)
    print(f'Bun version: {bun_version}')
    
    if bun_version:
        if semver.compare(bun_version, MIN_BUN_VERSION) < 0:
            print(f"Warning: Bun version {bun_version} is less than minimum required {MIN_BUN_VERSION}")
            print("The --eval flag needed for Node.js version reporting requires Bun v1.1.0+")
    
    # Test Node.js version reporting
    if bun_version and semver.compare(bun_version, MIN_BUN_VERSION) >= 0:
        reported_version = get_bun_reported_nodejs_version(bun_path)
        print(f'Bun reports as Node.js version: {reported_version}')
    
    # Test CDK requirements detection
    node_req = get_cdk_node_requirements() or '>= 14.15.0'
    print(f'CDK requires: {node_req}')
    
    # Test compatibility check
    if bun_path and bun_version and semver.compare(bun_version, MIN_BUN_VERSION) >= 0:
        is_compatible, reported_version = is_bun_compatible_with_cdk(bun_path, node_req)
        print(f'Bun compatible with CDK: {is_compatible} (reports as Node.js v{reported_version})')
    
    # Test the setup_nodejs function with Bun
    print("\nTesting setup_nodejs with Bun:")
    os.environ['AWS_CDK_BIN_USE_BUN'] = '1'
    os.environ['VERBOSE'] = '1'
    
    if 'AWS_CDK_BIN_USE_SYSTEM_NODE' in os.environ:
        del os.environ['AWS_CDK_BIN_USE_SYSTEM_NODE']
    if 'AWS_CDK_BIN_FORCE_DOWNLOAD_NODE' in os.environ:
        del os.environ['AWS_CDK_BIN_FORCE_DOWNLOAD_NODE']
        
    result = setup_nodejs()
    print(f'Result: {result}')
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 