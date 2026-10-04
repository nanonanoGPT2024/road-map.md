#!/usr/bin/env python3
"""
HCL2 Dynamic Matrix Generator & Test Engine
Bab 02: HCL2 Deep Dive & Ekspresi Dinamis

Skrip ini bertindak sebagai test harness dan automation generator yang mensimulasikan
pembacaan konfigurasi JSON multi-tier enterprise network, memvalidasi integritas data
menggunakan paradigma yang setara dengan Type System HCL2, dan mengompilasi manifest
Terraform (.tf & .tfvars.json) yang memanfaatkan dynamic expressions, flattening, dan for_each.
"""

import json
import ipaddress
import os
import sys
from typing import Dict, Any, List


SAMPLE_NETWORK_SCHEMA: Dict[str, Any] = {
    "tenants": {
        "finance": {
            "environment": "production",
            "vpc_cidr": "10.10.0.0/16",
            "tiers": [
                {
                    "name": "web",
                    "subnet_offset": 1,
                    "firewall_rules": [
                        {"protocol": "tcp", "port": 443, "source": "0.0.0.0/0", "action": "allow"},
                        {"protocol": "tcp", "port": 80, "source": "0.0.0.0/0", "action": "allow"}
                    ]
                },
                {
                    "name": "core-banking",
                    "subnet_offset": 2,
                    "firewall_rules": [
                        {"protocol": "tcp", "port": 8443, "source": "10.10.1.0/24", "action": "allow"},
                        {"protocol": "tcp", "port": 5432, "source": "10.10.1.0/24", "action": "deny"}
                    ]
                }
            ]
        },
        "logistics": {
            "environment": "staging",
            "vpc_cidr": "10.20.0.0/16",
            "tiers": [
                {
                    "name": "tracking-api",
                    "subnet_offset": 1,
                    "firewall_rules": [
                        {"protocol": "tcp", "port": 443, "source": "0.0.0.0/0", "action": "allow"},
                        {"protocol": "udp", "port": 5000, "source": "10.0.0.0/8", "action": "allow"}
                    ]
                }
            ]
        }
    }
}


def validate_tenant_schema(data: Dict[str, Any]) -> None:
    """Memvalidasi integritas tipe data dan batasan semantik jaringan."""
    print("[*] Memulai validasi skema data HCL2 equivalent...")
    if "tenants" not in data or not isinstance(data["tenants"], dict):
        raise ValueError("Invalid schema: root wajib memiliki key dictionary 'tenants'.")

    for tenant_name, tenant_cfg in data["tenants"].items():
        if not tenant_name.islower() or not tenant_name.isalpha():
            raise ValueError(f"Constraint Violation: Nama tenant '{tenant_name}' harus lowercase alphabetic.")

        env = tenant_cfg.get("environment")
        if env not in ["development", "staging", "production"]:
            raise ValueError(f"Validation Error: Environment '{env}' pada tenant '{tenant_name}' tidak valid.")

        # Validasi format CIDR
        try:
            net = ipaddress.ip_network(tenant_cfg["vpc_cidr"], strict=True)
            if net.prefixlen < 16 or net.prefixlen > 24:
                raise ValueError(f"CIDR prefix /{net.prefixlen} pada '{tenant_name}' di luar rentang aman (/16 - /24).")
        except Exception as e:
            raise ValueError(f"CIDR format invalid pada tenant '{tenant_name}': {e}")

        tiers = tenant_cfg.get("tiers", [])
        if not isinstance(tiers, list) or len(tiers) == 0:
            raise ValueError(f"Tenant '{tenant_name}' harus memiliki minimal 1 tier.")

        for tier in tiers:
            for rule in tier.get("firewall_rules", []):
                port = rule.get("port")
                if not isinstance(port, int) or port < 1 or port > 65535:
                    raise ValueError(f"Port {port} pada tier '{tier.get('name')}' tidak valid (1-65535).")

    print("[+] Validasi integritas skema berhasil: Seluruh batasan terpenuhi.")


def generate_terraform_files(target_dir: str) -> None:
    """Menuliskan manifest Terraform HCL2 murni ke folder target."""
    os.makedirs(target_dir, exist_ok=True)

    tfvars_path = os.path.join(target_dir, "terraform.tfvars.json")
    with open(tfvars_path, "w", encoding="utf-8") as f:
        json.dump(SAMPLE_NETWORK_SCHEMA, f, indent=2)
    print(f"[+] File variable definitions berhasil dibuat: {tfvars_path}")

    # Menulis main.tf yang mengimplementasikan modul HCL2 lengkap
    main_tf_path = os.path.join(target_dir, "main.tf")
    main_tf_content = """# ==============================================================================
# Pipeline Arsitektur Terraform HCL2 (Tingkat Lanjut)
# Menggunakan built-in terraform_data engine untuk testing tanpa eksternal provider
# ==============================================================================

terraform {
  required_version = ">= 1.5.0"
}

variable "tenants" {
  type = map(object({
    environment = string
    vpc_cidr    = string
    tiers = list(object({
      name          = string
      subnet_offset = number
      firewall_rules = list(object({
        protocol = string
        port     = number
        source   = string
        action   = string
      }))
    }))
  }))
  description = "Matriks konfigurasi tenant multi-tier."

  validation {
    condition = alltrue([
      for t_name, t_val in var.tenants : (
        contains(["development", "staging", "production"], t_val.environment) &&
        can(cidrnetmask(t_val.vpc_cidr))
      )
    ])
    error_message = "Environment harus development/staging/production dan format CIDR harus valid."
  }
}

locals {
  # 1. Transformasi Nested Hierarchies ke 1D Flat List menggunakan Ekspresi flatten & for
  flattened_subnets = flatten([
    for tenant_key, tenant_data in var.tenants : [
      for tier in tenant_data.tiers : {
        composite_key = "${tenant_key}#${tier.name}"
        tenant        = tenant_key
        environment   = tenant_data.environment
        tier_name     = tier.name
        cidr_block    = cidrsubnet(tenant_data.vpc_cidr, 8, tier.subnet_offset)
        rules         = tier.firewall_rules
      }
    ]
  ])

  # 2. Transformasi Flat List ke Map deterministik untuk konsumsi for_each
  subnets_map = {
    for s in local.flattened_subnets : s.composite_key => s
  }
}

# 3. Provisioning deterministik dengan for_each
resource "terraform_data" "simulated_subnets" {
  for_each = local.subnets_map

  input = {
    tenant_name   = each.value.tenant
    tier          = each.value.tier_name
    cidr          = each.value.cidr_block
    environment   = each.value.environment
    rule_checksum = length(each.value.rules)
  }
}

# 4. Proyeksi Dynamic Rules ke Audit State
resource "terraform_data" "firewall_matrix" {
  for_each = local.subnets_map

  input = {
    subnet_ref = terraform_data.simulated_subnets[each.key].id
    tenant     = each.value.tenant
    
    # Transformasi rule list menjadi manifest JSON string menggunakan for expression
    compiled_rules = [
      for r in each.value.rules : {
        signature = "${upper(r.protocol)}:${r.port}->${r.action}"
        source    = r.source
      }
    ]
  }
}

# 5. Output Reporting dengan Generalized Splat Operator [*] & Indented Heredoc
output "audit_manifest" {
  value = <<-EOF
    =======================================================
    NETWORK TOPOLOGY PROVISIONING REPORT
    =======================================================
    Total Active Subnets Created : ${length(local.subnets_map)}
    Subnet Keys                  : ${join(", ", keys(local.subnets_map))}
    Environment Distinct Tags    : ${join(", ", distinct([for s in local.flattened_subnets : s.environment]))}
    =======================================================
  EOF
}

output "subnets_summary" {
  value       = values(terraform_data.simulated_subnets)[*].output
  description = "Ekstraksi ringkasan subnet menggunakan generalized splat operator."
}
"""
    with open(main_tf_path, "w", encoding="utf-8") as f:
        f.write(main_tf_content)
    print(f"[+] File konfigurasi Terraform HCL2 berhasil digenerate: {main_tf_path}")


def main():
    print("==================================================================")
    print("   HCL2 Dynamic Expression Matrix & Automation Lab Generator      ")
    print("==================================================================")
    
    try:
        validate_tenant_schema(SAMPLE_NETWORK_SCHEMA)
    except ValueError as err:
        print(f"[!] Validation Failure: {err}")
        sys.exit(1)

    workdir = os.path.dirname(os.path.abspath(__file__))
    generate_terraform_files(workdir)

    print("\n[OK] Lab environment siap dieksekusi.")
    print("Silakan ikuti instruksi pada hands-on/m01/README.md.")


if __name__ == "__main__":
    main()