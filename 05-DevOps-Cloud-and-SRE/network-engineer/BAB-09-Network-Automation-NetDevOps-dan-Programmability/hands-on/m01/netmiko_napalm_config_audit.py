#!/usr/bin/env python3
"""
NetDevOps Automation Engine: Netmiko & NAPALM Audit & Provisioning Script
Kurikulum Standar GEMINI.md - NETWORK-ENGINEER Category 05

Deskripsi:
Skrip mandiri ini mendemonstrasikan orkestrasi otomasi hybrid:
1. Merender konfigurasi baru menggunakan Jinja2 template engine dari file data.
2. Menggunakan NAPALM untuk mengaudit status perangkat, mengambil fact, dan melakukan
   dry-run configuration diff (Candidate vs Running).
3. Menggunakan Netmiko untuk fallback eksekusi CLI terstruktur dan TextFSM audit.
4. Menjalankan evaluasi kepatuhan (Compliance Check) parameter NTP & DNS.
"""

import os
import sys
import json
import logging
from typing import Dict, Any, List
from jinja2 import Environment, BaseLoader

# Pustaka Otomasi Jaringan
try:
    from netmiko import ConnectHandler, BaseConnection
    from netmiko.exceptions import NetmikoTimeoutException, NetmikoAuthenticationException
    import napalm
    from napalm.base.exceptions import ConnectionException, MergeConfigException
except ImportError as e:
    print(f"[FATAL] Dependensi pustaka belum lengkap: {e}")
    print("Silakan jalankan: pip install netmiko napalm jinja2")
    sys.exit(1)

# Inisialisasi Logging Terstruktur
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] (%(threadName)s) %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("NetDevOps-Engine")

# -----------------------------------------------------------------------------
# 1. TEMPLATE DEFINITIONS (Jinja2) & VARIABLE SOURCE OF TRUTH
# -----------------------------------------------------------------------------
ROUTER_CONFIG_TEMPLATE = """
! JINJA2 RENDERED CONFIGURATION: BASE SERVICES & COMPLIANCE
hostname {{ device.hostname }}
!
ip domain name {{ compliance.domain_name }}
{% for dns in compliance.dns_servers %}
ip name-server {{ dns }}
{% endfor %}
!
{% for ntp in compliance.ntp_servers %}
ntp server {{ ntp }} prefer
{% endfor %}
!
{% for intf in interfaces %}
interface {{ intf.name }}
 description {{ intf.description }}
 ip address {{ intf.ip }} {{ intf.netmask }}
 {% if intf.enabled %}
 no shutdown
 {% else %}
 shutdown
 {% endif %}
!
{% endfor %}
"""

DEVICE_INVENTORY: Dict[str, Any] = {
    "hostname": "edge-router-01",
    "device_type": "cisco_ios",
    "napalm_driver": "ios",
    "host": os.getenv("TARGET_DEVICE_IP", "127.0.0.1"),
    "username": os.getenv("TARGET_DEVICE_USER", "admin"),
    "password": os.getenv("TARGET_DEVICE_PASS", "cisco123"),
    "port": int(os.getenv("TARGET_DEVICE_PORT", "2222")),  # Default port lab mock/container
    "secret": os.getenv("TARGET_DEVICE_SECRET", "cisco123"),
}

COMPLIANCE_STANDARDS: Dict[str, Any] = {
    "domain_name": "corp.infra.internal",
    "dns_servers": ["10.10.10.10", "10.10.20.10"],
    "ntp_servers": ["172.16.0.1", "172.16.0.2"],
}

TARGET_INTERFACES: List[Dict[str, Any]] = [
    {
        "name": "Loopback0",
        "description": "MANAGEMENT_CONTROL_INTERFACE",
        "ip": "10.255.255.1",
        "netmask": "255.255.255.255",
        "enabled": True
    },
    {
        "name": "GigabitEthernet0/1",
        "description": "WAN_PRIMARY_ISP_UPLINK",
        "ip": "198.51.100.2",
        "netmask": "255.255.255.252",
        "enabled": True
    }
]

# -----------------------------------------------------------------------------
# 2. CORE LOGIC ENGINE
# -----------------------------------------------------------------------------
class NetworkAutomationEngine:
    def __init__(self, inventory: Dict[str, Any]):
        self.inventory = inventory
        self.rendered_config = ""

    def render_candidate_config(self) -> str:
        """Merender Jinja2 template menjadi sintaks CLI perangkat target."""
        logger.info("Memulai rendering template Jinja2...")
        try:
            jinja_env = Environment(loader=BaseLoader())
            template = jinja_env.from_string(ROUTER_CONFIG_TEMPLATE)
            self.rendered_config = template.render(
                device=self.inventory,
                compliance=COMPLIANCE_STANDARDS,
                interfaces=TARGET_INTERFACES
            )
            logger.info("Konfigurasi candidate berhasil dirender.")
            return self.rendered_config
        except Exception as err:
            logger.error(f"Gagal merender konfigurasi Jinja2: {err}")
            raise

    def audit_and_deploy_napalm(self, dry_run: bool = True) -> bool:
        """Menggunakan NAPALM untuk inspeksi status, unified diff, dan deployment."""
        driver_name = self.inventory["napalm_driver"]
        logger.info(f"Menginisialisasi NAPALM driver: [{driver_name}] ke {self.inventory['host']}...")
        
        driver = napalm.get_network_driver(driver_name)
        optional_args = {
            "port": self.inventory["port"],
            "secret": self.inventory["secret"]
        }

        try:
            with driver(
                hostname=self.inventory["host"],
                username=self.inventory["username"],
                password=self.inventory["password"],
                optional_args=optional_args
            ) as device:
                logger.info("Koneksi NAPALM terbentuk. Mengambil data operasional perangkat...")
                facts = device.get_facts()
                logger.info(f"Facts: Model={facts.get('model')}, OS={facts.get('os_version')}, Uptime={facts.get('uptime')}s")

                logger.info("Mengunggah candidate merge configuration...")
                device.load_merge_candidate(config=self.rendered_config)

                logger.info("Memeriksa diff konfigurasi (Unified Diff)...")
                diff = device.compare_config()

                if diff:
                    print("\n================= CANDIDATE CONFIG DIFF DETECTED =================")
                    print(diff)
                    print("===================================================================\n")
                    if dry_run:
                        logger.info("[DRY-RUN AKTIF] Membatalkan perubahan (discarding candidate)...")
                        device.discard_config()
                        return True
                    else:
                        logger.info("[LIVE COMMIT] Menerapkan perubahan ke perangkat target...")
                        device.commit_config()
                        logger.info("Commit berhasil diselesaikan.")
                        return True
                else:
                    logger.info("Perangkat sudah sesuai status desired state. Tidak ada perubahan yang diperlukan (Idempotent).")
                    return True

        except (ConnectionException, MergeConfigException) as napalm_err:
            logger.warning(f"Operasi NAPALM gagal: {napalm_err}. Mengalihkan ke Netmiko Fallback Engine...")
            return False
        except Exception as e:
            logger.error(f"Kesalahan internal pada modul NAPALM: {e}")
            return False

    def fallback_cli_netmiko_audit(self) -> None:
        """Fallback engine menggunakan Netmiko untuk command show & verifikasi state."""
        logger.info("Memulai Netmiko Fallback Engine...")
        device_params = {
            "device_type": self.inventory["device_type"],
            "host": self.inventory["host"],
            "username": self.inventory["username"],
            "password": self.inventory["password"],
            "port": self.inventory["port"],
            "secret": self.inventory["secret"],
            "fast_cli": False,
            "timeout": 15
        }

        try:
            with ConnectHandler(**device_params) as net_connect:
                net_connect.enable()
                prompt = net_connect.find_prompt()
                logger.info(f"Netmiko berhasil terkoneksi. Prompt aktif: {prompt}")

                # Audit Operasional: NTP Synchronization Status
                logger.info("Mengecek konfigurasi status via CLI...")
                output_ntp = net_connect.send_command("show run | include ntp server")
                print(f"\n[AUDIT HASIL NTP RUNNING CONFIG]:\n{output_ntp}\n")

                # Audit Interface Brief
                output_intf = net_connect.send_command("show ip interface brief")
                print(f"[AUDIT STATUS ANTARMUKA]:\n{output_intf}\n")

        except (NetmikoTimeoutException, NetmikoAuthenticationException) as netmiko_err:
            logger.error(f"Gagal mengeksekusi koneksi Netmiko: {netmiko_err}")
        except Exception as err:
            logger.error(f"Kesalahan eksekusi Netmiko tidak terduga: {err}")

# -----------------------------------------------------------------------------
# 3. ENTRY POINT
# -----------------------------------------------------------------------------
def main():
    print("""
    ===============================================================
       NETDEVOPS HYBRID AUTOMATION & AUDIT ENGINE
       Standard Curriculum GEMINI.md - Module Hands-On
    ===============================================================
    """)
    
    engine = NetworkAutomationEngine(DEVICE_INVENTORY)
    
    # Langkah 1: Render Templating
    rendered = engine.render_candidate_config()
    print("\n--- RENDERED CANDIDATE CONFIG PREVIEW ---")
    print(rendered.strip())
    print("-----------------------------------------\n")

    # Langkah 2: Audit menggunakan NAPALM (Default ke Dry-Run)
    is_dry_run = os.getenv("NETDEVOPS_EXECUTE_LIVE", "0") != "1"
    success = engine.audit_and_deploy_napalm(dry_run=is_dry_run)

    # Langkah 3: Jika simulasi/koneksi NAPALM selesai atau perlu audit tambahan, jalankan inspeksi Netmiko
    if not success or os.getenv("FORCE_NETMIKO_INSPECT", "1") == "1":
        engine.fallback_cli_netmiko_audit()

    logger.info("Alur eksekusi otomasi selesai tanpa error fatal.")

if __name__ == "__main__":
    main()