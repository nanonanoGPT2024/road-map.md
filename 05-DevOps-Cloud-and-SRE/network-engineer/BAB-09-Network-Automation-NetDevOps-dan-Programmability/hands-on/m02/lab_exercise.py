#!/usr/bin/env python3
"""
NetDevOps Automation & Programmability Lab Simulation
=====================================================
Modul 02: Hands-on Network Automation Pipeline Simulation
Topik: Source of Truth (SoT), Data Modeling (YANG/RESTCONF),
       Configuration Generation (Jinja2-style), Pre/Post-flight Validation,
       and Automated Config Deployment with Rollback Guardrails.

Standalone Runnable Python 3 Script.
"""

import sys
import time
import json
import re
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from enum import Enum

# ANSI Terminal Color Palette
class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    BG_BLUE = "\033[44m"
    BG_DARK = "\033[40m"


class DeviceRole(Enum):
    SPINE = "spine"
    LEAF = "leaf"
    BORDER_LEAF = "border-leaf"


@dataclass
class InterfaceConfig:
    name: str
    ip_address: str
    subnet_mask: str
    description: str
    enabled: bool = True
    vlan_id: Optional[int] = None


@dataclass
class NetworkDevice:
    hostname: str
    role: DeviceRole
    mgmt_ip: str
    asn: int
    loopback_ip: str
    interfaces: Dict[str, InterfaceConfig] = field(default_factory=dict)
    bgp_neighbors: List[Dict[str, Any]] = field(default_factory=list)
    state: str = "SYNCHRONIZED"


class SourceOfTruthDB:
    """Simulates an IPAM / DCIM Source of Truth (NetBox-like catalog)."""

    def __init__(self):
        self.devices: Dict[str, NetworkDevice] = {}
        self._seed_inventory()

    def _seed_inventory(self):
        # Spine 01
        sp01 = NetworkDevice(
            hostname="dc1-spine-01",
            role=DeviceRole.SPINE,
            mgmt_ip="10.250.0.11",
            asn=65000,
            loopback_ip="10.0.0.1/32"
        )
        sp01.interfaces["Ethernet1/1"] = InterfaceConfig("Ethernet1/1", "10.0.10.1", "255.255.255.252", "Uplink to Leaf-01")
        sp01.interfaces["Ethernet1/2"] = InterfaceConfig("Ethernet1/2", "10.0.10.5", "255.255.255.252", "Uplink to Leaf-02")
        sp01.bgp_neighbors = [
            {"peer_ip": "10.0.10.2", "remote_asn": 65001, "name": "dc1-leaf-01"},
            {"peer_ip": "10.0.10.6", "remote_asn": 65002, "name": "dc1-leaf-02"}
        ]
        self.devices[sp01.hostname] = sp01

        # Leaf 01
        lf01 = NetworkDevice(
            hostname="dc1-leaf-01",
            role=DeviceRole.LEAF,
            mgmt_ip="10.250.0.21",
            asn=65001,
            loopback_ip="10.0.1.1/32"
        )
        lf01.interfaces["Ethernet1/1"] = InterfaceConfig("Ethernet1/1", "10.0.10.2", "255.255.255.252", "Uplink to Spine-01")
        lf01.interfaces["Ethernet1/48"] = InterfaceConfig("Ethernet1/48", "192.168.10.1", "255.255.255.0", "Compute Trunk", vlan_id=10)
        lf01.bgp_neighbors = [
            {"peer_ip": "10.0.10.1", "remote_asn": 65000, "name": "dc1-spine-01"}
        ]
        self.devices[lf01.hostname] = lf01

        # Leaf 02
        lf02 = NetworkDevice(
            hostname="dc1-leaf-02",
            role=DeviceRole.LEAF,
            mgmt_ip="10.250.0.22",
            asn=65002,
            loopback_ip="10.0.1.2/32"
        )
        lf02.interfaces["Ethernet1/1"] = InterfaceConfig("Ethernet1/1", "10.0.10.6", "255.255.255.252", "Uplink to Spine-01")
        lf02.interfaces["Ethernet1/48"] = InterfaceConfig("Ethernet1/48", "192.168.20.1", "255.255.255.0", "Storage Access", vlan_id=20)
        lf02.bgp_neighbors = [
            {"peer_ip": "10.0.10.5", "remote_asn": 65000, "name": "dc1-spine-01"}
        ]
        self.devices[lf02.hostname] = lf02


class TemplateEngine:
    """Simulates Jinja2 declarative rendering for multi-vendor network configs."""

    @staticmethod
    def render_cli_config(dev: NetworkDevice) -> str:
        lines = [
            f"! Architecture Template: NetDevOps Spine-Leaf CI v2.4",
            f"! Generated for: {dev.hostname} ({dev.role.value.upper()})",
            f"hostname {dev.hostname}",
            f"service password-encryption",
            f"ip routing",
            f"!",
            f"interface Loopback0",
            f" description System Router-ID",
            f" ip address {dev.loopback_ip.split('/')[0]} 255.255.255.255",
            f" no shutdown",
            f"!"
        ]
        for if_name, if_cfg in dev.interfaces.items():
            lines.extend([
                f"interface {if_name}",
                f" description {if_cfg.description}",
                f" ip address {if_cfg.ip_address} {if_cfg.subnet_mask}",
                f" {'no shutdown' if if_cfg.enabled else 'shutdown'}",
                f"!"
            ])
            if if_cfg.vlan_id:
                lines.insert(-1, f" switchport access vlan {if_cfg.vlan_id}")

        lines.extend([
            f"router bgp {dev.asn}",
            f" bgp router-id {dev.loopback_ip.split('/')[0]}",
            f" bgp log-neighbor-changes"
        ])
        for peer in dev.bgp_neighbors:
            lines.extend([
                f" neighbor {peer['peer_ip']} remote-as {peer['remote_asn']}",
                f" neighbor {peer['peer_ip']} description Peering_{peer['name']}",
                f" neighbor {peer['peer_ip']} update-source Loopback0"
            ])
        lines.append("end\n")
        return "\n".join(lines)

    @staticmethod
    def render_yang_restconf_payload(dev: NetworkDevice) -> Dict[str, Any]:
        """Simulates RFC 8040 RESTCONF YANG ietf-interfaces & ietf-bgp payload."""
        return {
            "ietf-interfaces:interfaces": {
                "interface": [
                    {
                        "name": if_name,
                        "type": "iana-if-type:ethernetCsmacd",
                        "enabled": if_cfg.enabled,
                        "description": if_cfg.description,
                        "ietf-ip:ipv4": {
                            "address": [{
                                "ip": if_cfg.ip_address,
                                "netmask": if_cfg.subnet_mask
                            }]
                        }
                    }
                    for if_name, if_cfg in dev.interfaces.items()
                ]
            },
            "openconfig-bgp:bgp": {
                "global": {
                    "config": {
                        "as": dev.asn,
                        "router-id": dev.loopback_ip.split('/')[0]
                    }
                },
                "neighbors": {
                    "neighbor": [
                        {
                            "neighbor-address": peer["peer_ip"],
                            "config": {
                                "peer-as": peer["remote_asn"],
                                "description": f"Peering_{peer['name']}"
                            }
                        }
                        for peer in dev.bgp_neighbors
                    ]
                }
            }
        }


class NetDevOpsPipeline:
    """Simulates CI/CD stages: Lint -> Test/Simulate (Batfish) -> Canary Push -> Healthcheck."""

    def __init__(self, db: SourceOfTruthDB):
        self.db = db

    def run_preflight_lint(self, dev: NetworkDevice) -> bool:
        print(f"{Color.CYAN}[Stage 1: Lint & YANG Schema Verification]{Color.RESET}")
        time.sleep(0.3)
        valid = True

        # Validation Rule 1: ASN Boundary
        if not (64512 <= dev.asn <= 65534 or 4200000000 <= dev.asn <= 4294967294):
            print(f" {Color.RED}✖ FAIL:{Color.RESET} ASN {dev.asn} is outside RFC 6996 Private ASN range")
            valid = False
        else:
            print(f" {Color.GREEN}✔ PASS:{Color.RESET} ASN {dev.asn} matches RFC 6996 private datacenter policy")

        # Validation Rule 2: Loopback validity
        ip_part = dev.loopback_ip.split("/")[0]
        if not re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", ip_part):
            print(f" {Color.RED}✖ FAIL:{Color.RESET} Malformed Router-ID: {dev.loopback_ip}")
            valid = False
        else:
            print(f" {Color.GREEN}✔ PASS:{Color.RESET} Router-ID format validated: {ip_part}")

        # Validation Rule 3: Subnet overlaps
        configured_ips = [iface.ip_address for iface in dev.interfaces.values()]
        if len(configured_ips) != len(set(configured_ips)):
            print(f" {Color.RED}✖ FAIL:{Color.RESET} Duplicate IP addresses detected on interfaces")
            valid = False
        else:
            print(f" {Color.GREEN}✔ PASS:{Color.RESET} Interface IP uniqueness verified (no local overlap)")

        return valid

    def run_batfish_simulation(self, dev: NetworkDevice) -> bool:
        print(f"\n{Color.CYAN}[Stage 2: Digital Twin & Topology Simulation (pyATS/Batfish)]{Color.RESET}")
        steps = [
            "Parsing device intent and generating network graph...",
            "Simulating BGP peering state machines...",
            "Verifying multipath routing (ECMP) reachability...",
            "Checking ACL security policies & packet-forwarding invariants..."
        ]
        for step in steps:
            time.sleep(0.25)
            print(f" {Color.YELLOW}•{Color.RESET} {step}")

        print(f" {Color.GREEN}✔ PASS:{Color.RESET} No routing loops detected. 0 blackholes identified.")
        return True

    def deploy_config_transaction(self, dev: NetworkDevice, candidate_config: str) -> bool:
        print(f"\n{Color.CYAN}[Stage 3: NETCONF / RESTCONF Atomic Transaction Deployment]{Color.RESET}")
        print(f" {Color.MAGENTA}» Connecting to {dev.hostname} via NETCONF over SSH:830...{Color.RESET}")
        time.sleep(0.3)
        print(f" {Color.MAGENTA}» Lock <candidate/> datastore...{Color.RESET}")
        time.sleep(0.2)
        print(f" {Color.MAGENTA}» Uploading diff changesets...{Color.RESET}")
        time.sleep(0.3)
        print(f" {Color.MAGENTA}» Running commit-confirmed timeout=30 (Safe guard against lockouts)...{Color.RESET}")
        time.sleep(0.4)
        print(f" {Color.GREEN}✔ Deployment Successful:{Color.RESET} Target config committed and active.")
        dev.state = "SYNCHRONIZED"
        return True

    def detect_configuration_drift(self, dev: NetworkDevice) -> None:
        print(f"\n{Color.CYAN}[Stage 4: Automated Drift Detection & Closed-Loop Telemetry]{Color.RESET}")
        print(f" Polling telemetry streams (gNMI/Streaming Telemetry) for {dev.hostname}...")
        time.sleep(0.4)
        print(f" {Color.GREEN}✔ State Integrity:{Color.RESET} Operational state matches Source of Truth 100%. No unmanaged drift.")


def print_banner():
    banner = f"""{Color.BLUE}{Color.BOLD}
========================================================================
   _  __     __  ___             ____               _             
  / |/ /__  / /_/ _ \___ _  __  / __ \___  ___ ____(_)__  ___ ____
 /    / -_)/ __/ // / -_) |/ / / /_/ / _ \/ -_) __/ / _ \/ _ `/ _ \\
/_/|_/\__/ \__/____/\__/|___/  \____/ .__/\__/_/ /_/\___/\_, /_//_/
                                    /_/                  /___/     
        Spine-Leaf Fabric Automation & RESTCONF/YANG Engine
========================================================================{Color.RESET}
{Color.DIM}Repository: BAB-09-Network-Automation-NetDevOps-dan-Programmability{Color.RESET}
"""
    print(banner)


def show_menu():
    print(f"\n{Color.BOLD}{Color.WHITE}--- INTERACTIVE WORKBENCH MENU ---{Color.RESET}")
    print(f" {Color.CYAN}[1]{Color.RESET} Tampilkan Data Model Source of Truth (NetBox-style Inventory)")
    print(f" {Color.CYAN}[2]{Color.RESET} Generate Multi-Vendor CLI Configurations (Jinja2 Simulation)")
    print(f" {Color.CYAN}[3]{Color.RESET} Inspect RESTCONF / YANG Data Payloads (RFC 8040)")
    print(f" {Color.CYAN}[4]{Color.RESET} Jalankan NetDevOps CI/CD Pipeline (Lint, Batfish, Deploy)")
    print(f" {Color.CYAN}[5]{Color.RESET} Simulasi Network Configuration Drift & Auto-Remediation")
    print(f" {Color.RED}[0]{Color.RESET} Keluar / Exit Lab")
    print(f"{Color.DIM}----------------------------------{Color.RESET}")


def interactive_loop():
    db = SourceOfTruthDB()
    pipeline = NetDevOpsPipeline(db)

    print_banner()

    while True:
        show_menu()
        try:
            choice = input(f"{Color.BOLD}Pilih opsi [0-5]: {Color.RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print(f"\n{Color.YELLOW}Exiting simulation.{Color.RESET}")
            sys.exit(0)

        if choice == "1":
            print(f"\n{Color.GREEN}=== Source of Truth (Inventory Topology) ==={Color.RESET}")
            for name, dev in db.devices.items():
                print(f"\n{Color.BOLD}Device: {dev.hostname}{Color.RESET} | Role: {dev.role.value} | Mgmt: {dev.mgmt_ip} | BGP ASN: {dev.asn}")
                print(f"  Loopback0: {dev.loopback_ip}")
                print("  Interfaces:")
                for if_name, if_cfg in dev.interfaces.items():
                    vlan_str = f" [VLAN {if_cfg.vlan_id}]" if if_cfg.vlan_id else ""
                    print(f"    • {if_name:<14} -> {if_cfg.ip_address:<15} ({if_cfg.description}){vlan_str}")
                print("  BGP Neighbors:")
                for nbr in dev.bgp_neighbors:
                    print(f"    • Peer: {nbr['peer_ip']:<15} | Remote-AS: {nbr['remote_asn']:<6} | Target: {nbr['name']}")

        elif choice == "2":
            print(f"\n{Color.GREEN}=== Declarative CLI Configuration Generation ==={Color.RESET}")
            for dev in db.devices.values():
                print(f"\n{Color.YELLOW}--- Configuration for {dev.hostname} ---{Color.RESET}")
                config_str = TemplateEngine.render_cli_config(dev)
                for line in config_str.splitlines()[:15]:
                    print(f"  {line}")
                print(f"  {Color.DIM}... [truncated remaining lines] ...{Color.RESET}")

        elif choice == "3":
            print(f"\n{Color.GREEN}=== RESTCONF / YANG RFC 8040 Data Structure ==={Color.RESET}")
            sample_dev = db.devices["dc1-leaf-01"]
            yang_data = TemplateEngine.render_yang_restconf_payload(sample_dev)
            formatted_json = json.dumps(yang_data, indent=2)
            print(f"{Color.CYAN}Target URI: https://{sample_dev.mgmt_ip}/restconf/data{Color.RESET}")
            print(formatted_json[:600] + f"\n{Color.DIM}  ... [YANG Payload Complete] ...{Color.RESET}")

        elif choice == "4":
            print(f"\n{Color.GREEN}=== Running NetDevOps End-to-End Pipeline ==={Color.RESET}")
            target_device = db.devices["dc1-leaf-01"]
            print(f"Targeting Node: {Color.BOLD}{target_device.hostname}{Color.RESET}")

            # Step 1: Lint
            if pipeline.run_preflight_lint(target_device):
                # Step 2: Batfish simulation
                if pipeline.run_batfish_simulation(target_device):
                    # Step 3: Deployment
                    cli_cfg = TemplateEngine.render_cli_config(target_device)
                    pipeline.deploy_config_transaction(target_device, cli_cfg)
                    # Step 4: Verification
                    pipeline.detect_configuration_drift(target_device)
                    print(f"\n{Color.GREEN}{Color.BOLD}>>> Pipeline Completed Successfully with Zero Errors! <<<{Color.RESET}")

        elif choice == "5":
            print(f"\n{Color.YELLOW}=== Drift Simulation & Closed-Loop Remediation ==={Color.RESET}")
            dev = db.devices["dc1-leaf-02"]
            print(f"Simulating unauthorized out-of-band change on {dev.hostname}...")
            time.sleep(0.4)
            print(f"{Color.RED}⚠️  ALERT:{Color.RESET} Rogue interface 'Ethernet1/12' added manually by operator via console!")
            dev.state = "CONFIGURATION_DRIFT_DETECTED"
            time.sleep(0.4)
            print(f"{Color.MAGENTA}⚡ Event Driven Automation (EDA):{Color.RESET} Webhook received from syslog agent.")
            print("Diff Analysis: + interface Ethernet1/12 (Not in Source of Truth)")
            time.sleep(0.3)
            print(f"{Color.CYAN}Applying Auto-Remediation:{Color.RESET} Overwriting with authoritative SoT template...")
            time.sleep(0.5)
            dev.state = "SYNCHRONIZED"
            print(f"{Color.GREEN}✔ REMEDIATED:{Color.RESET} Node state reconciled. Compliance restored.")

        elif choice == "0":
            print(f"\n{Color.CYAN}Terima kasih telah menggunakan NetDevOps Interactive Lab.{Color.RESET}")
            break
        else:
            print(f"{Color.RED}Pilihan tidak valid. Silakan pilih 0-5.{Color.RESET}")


if __name__ == "__main__":
    interactive_loop()
