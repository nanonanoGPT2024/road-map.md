#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Engine Evaluasi HCL2 & Ekspresi Dinamis Terraform
Topik: BAB-02 - HCL2 Deep Dive dan Ekspresi Dinamis
Deskripsi:
    Simulasi interaktif tingkat lanjut yang memodelkan perilaku engine HCL2 Terraform:
    1. Evaluasi Dynamic Blocks (mis. Security Group rules)
    2. List & Map Comprehensions (for expressions dengan filtering & transform)
    3. Splat Expressions ([*]) & Flattening
    4. Fungsi Evaluasi Defensif (try, can, lookup, coalesce)
    5. Structural Validation Rules (precondition/postcondition assertion)
"""

import sys
import json
import time
from typing import Any, Dict, List, Optional, Union

# ANSI Colors & Formatting
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_RED = "\033[31m"
CLR_GREEN = "\033[32m"
CLR_YELLOW = "\033[33m"
CLR_BLUE = "\033[34m"
CLR_MAGENTA = "\033[35m"
CLR_CYAN = "\033[36m"
CLR_WHITE = "\033[37m"
CLR_BG_DARK = "\033[40m"


def header(title: str) -> None:
    line = "=" * 70
    print(f"\n{CLR_CYAN}{CLR_BOLD}{line}")
    print(f"  [HCL2 ENGINE SIMULATOR] :: {title.upper()}")
    print(f"{line}{CLR_RESET}\n")


def log_step(step_name: str, detail: str) -> None:
    print(f"{CLR_BLUE}[EVAL_GRAPH]{CLR_RESET} {CLR_BOLD}{step_name:<25}{CLR_RESET} -> {detail}")


def log_success(msg: str) -> None:
    print(f"{CLR_GREEN}✔ [PASS]{CLR_RESET} {msg}")


def log_warn(msg: str) -> None:
    print(f"{CLR_YELLOW}⚠ [WARN]{CLR_RESET} {msg}")


def log_error(msg: str) -> None:
    print(f"{CLR_RED}✖ [FAIL]{CLR_RESET} {msg}")


# ---------------------------------------------------------------------------
# 1. HCL2 Defensive Functions Mock: can(), try(), coalesce()
# ---------------------------------------------------------------------------

class HCL2Builtins:
    @staticmethod
    def hcl_try(func, default_value: Any) -> Any:
        """Simulasi fungsi try(expr, default) HCL2."""
        try:
            return func()
        except Exception:
            return default_value

    @staticmethod
    def hcl_can(func) -> bool:
        """Simulasi fungsi can(expr) HCL2."""
        try:
            func()
            return True
        except Exception:
            return False

    @staticmethod
    def hcl_coalesce(*args: Any) -> Any:
        """Simulasi coalesce(val1, val2, ...) -> nilai non-null/non-empty pertama."""
        for a in args:
            if a is not None and a != "":
                return a
        raise ValueError("Semua argumen bernilai null atau kosong.")


# ---------------------------------------------------------------------------
# 2. Dynamic Block Engine (Security Group Rules Generator)
# ---------------------------------------------------------------------------

class SecurityGroupRule:
    def __init__(self, port: int, proto: str, cidrs: List[str], desc: str):
        self.port = port
        self.proto = proto
        self.cidrs = cidrs
        self.desc = desc

    def to_dict(self) -> Dict[str, Any]:
        return {
            "from_port": self.port,
            "to_port": self.port,
            "protocol": self.proto,
            "cidr_blocks": self.cidrs,
            "description": self.desc,
        }


def simulate_dynamic_ingress(ports_spec: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Simulasi blok HCL:
    dynamic "ingress" {
      for_each = [for p in var.service_ports : p if p.enabled]
      content {
        from_port   = ingress.value.port
        to_port     = ingress.value.port
        protocol    = ingress.value.protocol
        cidr_blocks = ingress.value.cidrs
        description = "Allow inbound on port ${ingress.value.port}"
      }
    }
    """
    log_step("dynamic_ingress_expand", f"Mengevaluasi {len(ports_spec)} kandidat port...")
    generated_rules: List[Dict[str, Any]] = []

    # Filter iterators: [for p in ports if p.get('enabled', True)]
    active_ports = [p for p in ports_spec if p.get("enabled", True)]

    for item in active_ports:
        rule = SecurityGroupRule(
            port=item["port"],
            proto=item.get("protocol", "tcp"),
            cidrs=item.get("cidrs", ["0.0.0.0/0"]),
            desc=f"Managed by HCL2 Dynamic Engine (Port {item['port']})",
        )
        generated_rules.append(rule.to_dict())
        print(f"  {CLR_GREEN}↳ Ingress Block Generated:{CLR_RESET} Port={item['port']}/{rule.proto} "
              f"CIDRs={rule.cidrs}")

    return generated_rules


# ---------------------------------------------------------------------------
# 3. For Expressions, Splat [*], & Flattening
# ---------------------------------------------------------------------------

def simulate_hcl2_comprehensions() -> None:
    header("Demonstrasi For-Expressions, Splat & Flatten")

    vpc_subnets = {
        "ap-southeast-1a": [
            {"id": "subnet-01a-pub", "tier": "public", "cidr": "10.0.1.0/24"},
            {"id": "subnet-01a-app", "tier": "private", "cidr": "10.0.11.0/24"},
            {"id": "subnet-01a-db", "tier": "database", "cidr": "10.0.21.0/24"},
        ],
        "ap-southeast-1b": [
            {"id": "subnet-01b-pub", "tier": "public", "cidr": "10.0.2.0/24"},
            {"id": "subnet-01b-app", "tier": "private", "cidr": "10.0.12.0/24"},
            {"id": "subnet-01b-db", "tier": "database", "cidr": "10.0.22.0/24"},
        ],
    }

    log_step("raw_input_inspection", "Data multi-AZ VPC Subnet terdeteksi.")
    print(json.dumps(vpc_subnets, indent=2))

    # Simulasi: flatten([for az, subnets in var.vpc_subnets : subnets])
    log_step("hcl_flatten", "Mengeksekusi flatten([for az, subs in vpc_subnets : subs])...")
    flat_subnets: List[Dict[str, Any]] = [
        item for sublist in vpc_subnets.values() for item in sublist
    ]
    log_success(f"Total flat subnets: {len(flat_subnets)}")

    # Simulasi Map Comprehension dengan Filter:
    # { for s in local.flat_subnets : s.id => s.cidr if s.tier == "private" }
    log_step("map_comprehension", "Filter tier=='private' menjadi Map ID -> CIDR...")
    private_subnet_map = {
        s["id"]: s["cidr"] for s in flat_subnets if s.get("tier") == "private"
    }
    print(f"{CLR_MAGENTA}Hasil Map Comprehension (Private Tier):{CLR_RESET}")
    for sid, scidr in private_subnet_map.items():
        print(f"  • {sid} => {scidr}")

    # Simulasi Splat Operator: local.flat_subnets[*].id
    log_step("splat_operator", "Ekstraksi ID seluruh subnet menggunakan splat [*]...")
    all_ids = [s["id"] for s in flat_subnets]
    print(f"{CLR_YELLOW}Subnet IDs [*]: {all_ids}{CLR_RESET}")


# ---------------------------------------------------------------------------
# 4. Defensive Evaluation (can, try, coalesce)
# ---------------------------------------------------------------------------

def simulate_defensive_evaluation() -> None:
    header("Demonstrasi Fungsi Defensif (can, try, coalesce)")

    untrusted_payloads = [
        {"env": "production", "monitoring": {"tier": "prometheus", "retention_days": 30}},
        {"env": "staging", "monitoring": None},
        {"env": "dev"},  # Missing monitoring key completely
    ]

    for idx, env_config in enumerate(untrusted_payloads, start=1):
        env_name = env_config.get("env", "unknown")
        print(f"\n{CLR_BOLD}--- Menilai Lingkungan [{idx}]: {env_name.upper()} ---{CLR_RESET}")

        # Test can()
        has_monitoring = HCL2Builtins.hcl_can(lambda: env_config["monitoring"]["retention_days"])
        print(f"  can(var.env.monitoring.retention_days) : {CLR_GREEN if has_monitoring else CLR_RED}{has_monitoring}{CLR_RESET}")

        # Test try()
        retention = HCL2Builtins.hcl_try(
            lambda: env_config["monitoring"]["retention_days"],
            default_value=7  # fallback retention
        )
        print(f"  try(var.env.monitoring.retention_days, 7) : {CLR_CYAN}{retention} hari{CLR_RESET}")

        # Test coalesce()
        resolved_name = HCL2Builtins.hcl_coalesce(
            env_config.get("custom_tag"),
            f"default-{env_name}-cluster"
        )
        print(f"  coalesce(custom_tag, default_name)     : {CLR_YELLOW}{resolved_name}{CLR_RESET}")


# ---------------------------------------------------------------------------
# 5. Precondition & Postcondition Assertion Engine
# ---------------------------------------------------------------------------

def simulate_lifecycle_assertions(instance_config: Dict[str, Any]) -> bool:
    header("Validasi Kontrak Infrastruktur (Precondition / Postcondition)")

    log_step("precondition_check", "Memeriksa variable validation & precondition...")
    time.sleep(0.3)

    # Precondition 1: CPU Architecture check
    valid_archs = ["arm64", "x86_64"]
    arch = instance_config.get("architecture")
    if arch not in valid_archs:
        log_error(f"Precondition Gagal: Arsitektur '{arch}' tidak didukung! Harus {valid_archs}")
        return False
    log_success(f"Precondition Lolos: Arsitektur '{arch}' valid.")

    # Precondition 2: Root volume encryption
    is_encrypted = instance_config.get("root_volume", {}).get("encrypted", False)
    if not is_encrypted:
        log_error("Precondition Gagal: root_volume.encrypted wajib bernilai true untuk compliance ISO-27001!")
        return False
    log_success("Precondition Lolos: root_volume terenkripsi KMS.")

    # Postcondition: Cek alokasi IP publik pada private subnet
    log_step("postcondition_check", "Memeriksa invariant status resource pasca-creation...")
    time.sleep(0.3)
    is_private = instance_config.get("subnet_tier") == "private"
    has_public_ip = instance_config.get("associate_public_ip_address", False)

    if is_private and has_public_ip:
        log_error("Postcondition Gagal: Resource private tier tidak boleh memiliki public IP!")
        return False

    log_success("Postcondition Lolos: Konfigurasi networking mematuhi isolasi VPC.")
    return True


# ---------------------------------------------------------------------------
# 6. Interactive CLI Simulator Menu
# ---------------------------------------------------------------------------

def interactive_lab_menu() -> None:
    while True:
        header("Terraform HCL2 Deep Dive - Interactive Console")
        print(f"Pilih skenario simulasi HCL2:")
        print(f"  {CLR_CYAN}[1]{CLR_RESET} Simulasi Dynamic Block Ingress Rules Engine")
        print(f"  {CLR_CYAN}[2]{CLR_RESET} Evaluasi For-Expressions, Splat [*] & Subnet Flattening")
        print(f"  {CLR_CYAN}[3]{CLR_RESET} Evaluasi Defensif (can, try, coalesce)")
        print(f"  {CLR_CYAN}[4]{CLR_RESET} Lifecycle Precondition & Postcondition Checker")
        print(f"  {CLR_CYAN}[5]{CLR_RESET} Jalankan Seluruh Skenario Produksi (End-to-End Test)")
        print(f"  {CLR_RED}[0] Keluar{CLR_RESET}")

        try:
            choice = input(f"\n{CLR_BOLD}Masukkan nomor pilihan (0-5): {CLR_RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting simulator.")
            break

        if choice == "1":
            raw_ports = [
                {"port": 80, "protocol": "tcp", "cidrs": ["0.0.0.0/0"], "enabled": True},
                {"port": 443, "protocol": "tcp", "cidrs": ["0.0.0.0/0"], "enabled": True},
                {"port": 8080, "protocol": "tcp", "cidrs": ["10.0.0.0/8"], "enabled": False},  # disabled
                {"port": 9090, "protocol": "tcp", "cidrs": ["10.100.0.0/16"], "enabled": True},
            ]
            simulate_dynamic_ingress(raw_ports)
        elif choice == "2":
            simulate_hcl2_comprehensions()
        elif choice == "3":
            simulate_defensive_evaluation()
        elif choice == "4":
            print(f"\n{CLR_YELLOW}Skenario A (Config Valid):{CLR_RESET}")
            valid_cfg = {
                "architecture": "arm64",
                "root_volume": {"encrypted": True, "size_gb": 100},
                "subnet_tier": "private",
                "associate_public_ip_address": False,
            }
            simulate_lifecycle_assertions(valid_cfg)

            print(f"\n{CLR_YELLOW}Skenario B (Config Melanggar Policy):{CLR_RESET}")
            invalid_cfg = {
                "architecture": "mips",
                "root_volume": {"encrypted": False},
                "subnet_tier": "private",
                "associate_public_ip_address": True,
            }
            simulate_lifecycle_assertions(invalid_cfg)
        elif choice == "5":
            header("Mengeksekusi Pipeline Pengujian Penuh")
            simulate_dynamic_ingress([
                {"port": 80, "protocol": "tcp", "cidrs": ["0.0.0.0/0"], "enabled": True},
                {"port": 443, "protocol": "tcp", "cidrs": ["0.0.0.0/0"], "enabled": True},
            ])
            simulate_hcl2_comprehensions()
            simulate_defensive_evaluation()
            simulate_lifecycle_assertions({
                "architecture": "arm64",
                "root_volume": {"encrypted": True, "size_gb": 50},
                "subnet_tier": "private",
                "associate_public_ip_address": False,
            })
            log_success("Seluruh alur evaluasi ekspresi HCL2 sukses dieksekusi!")
        elif choice == "0":
            print(f"{CLR_GREEN}Terima kasih telah menggunakan simulator HCL2.{CLR_RESET}")
            break
        else:
            log_warn("Pilihan tidak valid, silakan ulangi.")


if __name__ == "__main__":
    # Jika dijalankan tanpa terminal interaktif (CI/headless), jalankan mode non-interaktif
    if not sys.stdin.isatty():
        print(f"{CLR_YELLOW}[INFO] Mode Non-Interaktif terdeteksi. Menjalankan Suite Penuh...{CLR_RESET}")
        simulate_dynamic_ingress([
            {"port": 80, "protocol": "tcp", "cidrs": ["0.0.0.0/0"], "enabled": True},
            {"port": 443, "protocol": "tcp", "cidrs": ["0.0.0.0/0"], "enabled": True},
        ])
        simulate_hcl2_comprehensions()
        simulate_defensive_evaluation()
        simulate_lifecycle_assertions({
            "architecture": "arm64",
            "root_volume": {"encrypted": True, "size_gb": 50},
            "subnet_tier": "private",
            "associate_public_ip_address": False,
        })
        log_success("Headless execution selesai dengan sukses.")
    else:
        interactive_lab_menu()
