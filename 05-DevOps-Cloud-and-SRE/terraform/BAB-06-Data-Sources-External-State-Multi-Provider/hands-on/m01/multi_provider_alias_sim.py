#!/usr/bin/env python3
"""
Multi-Provider Architecture & External Data Source Simulator
Standard: GEMINI Technical Curriculum Engine
Contract: Reads JSON from stdin (map[string]string), writes JSON to stdout (map[string]string).
Any logging or debugging MUST be written to sys.stderr.
"""

import sys
import json
import ipaddress
import os

def log_debug(message: str):
    """Write internal diagnostics directly to stderr to avoid polluting stdout."""
    sys.stderr.write(f"[EXTERNAL-IPC-SIMULATOR] {message}\n")
    sys.stderr.flush()

def validate_environment(env: str) -> str:
    allowed = ["production", "staging", "dr-simulation"]
    if env.lower() not in allowed:
        raise ValueError(f"Invalid environment '{env}'. Allowed values: {allowed}")
    return env.lower()

def resolve_network_matrix(env: str):
    """
    Simulate enterprise IPAM/CMDB resolving cross-region network topologies.
    """
    matrix = {
        "production": {
            "primary_region": "ap-southeast-1",
            "primary_cidr": "10.100.0.0/16",
            "dr_region": "ap-southeast-3",
            "dr_cidr": "10.200.0.0/16",
            "compliance_tier": "tier-1-pci-dss"
        },
        "staging": {
            "primary_region": "ap-southeast-1",
            "primary_cidr": "172.16.0.0/16",
            "dr_region": "ap-southeast-3",
            "dr_cidr": "172.17.0.0/16",
            "compliance_tier": "tier-3-internal"
        },
        "dr-simulation": {
            "primary_region": "ap-southeast-1",
            "primary_cidr": "192.168.10.0/24",
            "dr_region": "ap-southeast-3",
            "dr_cidr": "192.168.20.0/24",
            "compliance_tier": "tier-sandbox"
        }
    }
    return matrix[env]

def check_cidr_overlap(cidr_a: str, cidr_b: str):
    net_a = ipaddress.ip_network(cidr_a)
    net_b = ipaddress.ip_network(cidr_b)
    if net_a.overlaps(net_b):
        raise ValueError(f"CRITICAL: Overlapping CIDR detected: {cidr_a} overlaps with {cidr_b}")

def main():
    # 1. Verification of Non-Interactive Stdin
    try:
        raw_input_data = sys.stdin.read()
        if not raw_input_data.strip():
            log_debug("No stdin received. Running in standalone CLI self-test mode...")
            query = {"environment": "production", "requestor": "terraform-ci-runner"}
        else:
            query = json.loads(raw_input_data)
    except Exception as e:
        log_debug(f"JSON Parse Exception on stdin: {str(e)}")
        sys.exit(1)

    log_debug(f"Received Query Payload: {json.dumps(query)}")

    # 2. Extract and Validate Input Query
    target_env = query.get("environment", "staging")
    try:
        validated_env = validate_environment(target_env)
        topology = resolve_network_matrix(validated_env)
        
        # Guardrail Validation
        check_cidr_overlap(topology["primary_cidr"], topology["dr_cidr"])
    except Exception as err:
        log_debug(f"Validation Failure: {str(err)}")
        # Terraform external data source expects non-zero exit code on failure
        sys.exit(1)

    # 3. Formulate Output Contract (Flat map of string to string)
    # CONTRACT REQUIREMENT: ALL VALUES MUST BE STRINGS
    payload_response = {
        "environment": validated_env,
        "primary_region": topology["primary_region"],
        "primary_cidr": topology["primary_cidr"],
        "dr_region": topology["dr_region"],
        "dr_cidr": topology["dr_cidr"],
        "compliance_tier": topology["compliance_tier"],
        "status_code": "200",
        "ipc_signature": "sha256-verified-sim-engine"
    }

    log_debug("Successfully resolved network matrix. Emitting JSON to stdout.")
    
    # Write ONLY the JSON response to stdout
    sys.stdout.write(json.dumps(payload_response))
    sys.stdout.flush()
    sys.exit(0)

if __name__ == "__main__":
    main()