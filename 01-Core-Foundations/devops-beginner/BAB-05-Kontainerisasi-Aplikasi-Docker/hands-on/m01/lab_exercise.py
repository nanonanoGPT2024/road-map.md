#!/usr/bin/env python3
"""
Lab Exercise: Simulasi Fondasi Kontainerisasi & Docker Runtime
Topik: BAB-05 Kontainerisasi Aplikasi Docker (DevOps Beginner)
Modul: M01 - Arsitektur Kontainer, Namespace, Cgroups, & Layered Filesystem
"""

import os
import sys
import time
import json
import random
from typing import Dict, List, Any

# ANSI Color Codes untuk Visualisasi Terminal
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_RED = "\033[31m"
CLR_GREEN = "\033[32m"
CLR_YELLOW = "\033[33m"
CLR_BLUE = "\033[34m"
CLR_MAGENTA = "\033[35m"
CLR_CYAN = "\033[36m"
CLR_BG_DARK = "\033[40m"


class ContainerSimulator:
    def __init__(self):
        self.images: Dict[str, List[Dict[str, str]]] = {
            "alpine:3.19": [
                {"layer_id": "sha256:7b5d1a", "desc": "Alpine Base OS Rootfs (5.8MB)", "readonly": True}
            ],
            "python:3.11-slim": [
                {"layer_id": "sha256:4a123f", "desc": "Debian Bookworm Base Layer (52MB)", "readonly": True},
                {"layer_id": "sha256:9c84e1", "desc": "Python Runtime & Shared Libs (98MB)", "readonly": True}
            ],
            "webapp:v1": [
                {"layer_id": "sha256:4a123f", "desc": "Debian Bookworm Base Layer (52MB)", "readonly": True},
                {"layer_id": "sha256:9c84e1", "desc": "Python Runtime & Shared Libs (98MB)", "readonly": True},
                {"layer_id": "sha256:e3b0c4", "desc": "COPY requirements.txt & pip install (34MB)", "readonly": True},
                {"layer_id": "sha256:2f1a90", "desc": "COPY app/ /app (1.2MB)", "readonly": True}
            ]
        }
        self.containers: Dict[str, Dict[str, Any]] = {}

    def print_banner(self):
        print(f"{CLR_CYAN}{CLR_BOLD}=" * 72)
        print("  DOCKER & CONTAINER ENGINE ARCHITECTURE SIMULATOR (CLI LAB)")
        print("  Belajar Namespace (Isolasi), Cgroups (Resource Limit), & OverlayFS")
        print(f"=" * 72 + f"{CLR_RESET}\n")

    def print_section(self, title: str):
        print(f"\n{CLR_MAGENTA}{CLR_BOLD}[+] {title}{CLR_RESET}")
        print(f"{CLR_BLUE}{'-' * 60}{CLR_RESET}")

    def inspect_image_layers(self, image_name: str):
        self.print_section(f"Mekanisme Layered Filesystem (UnionFS / OverlayFS): {image_name}")
        if image_name not in self.images:
            print(f"{CLR_RED}[!] Image '{image_name}' tidak ditemukan di local store.{CLR_RESET}")
            return

        layers = self.images[image_name]
        print(f"Rincian Layer Read-Only (Image Manifest):")
        for idx, layer in enumerate(layers, 1):
            ro_badge = f"{CLR_YELLOW}[RO Layer {idx}]{CLR_RESET}"
            print(f"  {ro_badge} ID: {layer['layer_id']} | {layer['desc']}")
        
        print(f"\n{CLR_GREEN}>> Konsep DevOps:{CLR_RESET} Ketika kontainer dijalankan dari image ini,")
        print("   Docker menambahkan 1 layer tipis di bagian paling atas:")
        print(f"  {CLR_CYAN}[R/W Container Layer]{CLR_RESET} Ephemeral Layer (Copy-on-Write / CoW)")

    def create_container(self, name: str, image: str, port_map: str, mem_limit: str, cpu_quota: str) -> str:
        if image not in self.images:
            print(f"{CLR_RED}[!] Gagal membuat kontainer: image '{image}' tidak valid.{CLR_RESET}")
            return ""

        container_id = f"c7{random.randint(100000, 999999):x}"
        self.containers[container_id] = {
            "name": name,
            "id": container_id,
            "image": image,
            "status": "Created",
            "port_map": port_map,
            "cgroups": {
                "memory_max": mem_limit,
                "cpu_max": cpu_quota
            },
            "namespaces": {
                "pid_namespace": f"ns_pid_{random.randint(100, 999)}",
                "net_namespace": f"ns_net_{random.randint(100, 999)}",
                "uts_hostname": name,
                "virtual_ip": f"172.17.0.{len(self.containers) + 2}"
            },
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        return container_id

    def start_container(self, container_id: str):
        if container_id not in self.containers:
            print(f"{CLR_RED}[!] Container ID tidak ditemukan.{CLR_RESET}")
            return
        
        c = self.containers[container_id]
        print(f"\n{CLR_YELLOW}[*] Menginisialisasi Kernel Primitives untuk '{c['name']}'...{CLR_RESET}")
        time.sleep(0.3)
        print(f"  -> Mengisolasi UTS Namespace: Hostname ditetapkan ke '{c['namespaces']['uts_hostname']}'")
        print(f"  -> Mengisolasi PID Namespace: Proses utama dialokasikan PID 1 di dalam kontainer")
        print(f"  -> Mengisolasi NET Namespace: Veth pair disambungkan ke docker0 bridge ({c['namespaces']['virtual_ip']})")
        print(f"  -> Menyiapkan Cgroups v2: memory.max={c['cgroups']['memory_max']}, cpu.max={c['cgroups']['cpu_max']}")
        print(f"  -> Memasang OverlayFS: LowerDir (Layers) + UpperDir (Container RW)")
        c["status"] = "Running"
        print(f"{CLR_GREEN}[✓] Kontainer {c['name']} ({c['id'][:8]}) berhasil berstatus RUNNING!{CLR_RESET}")

    def list_containers(self):
        self.print_section("Daftar Kontainer Aktif & Terdaftar (docker ps -a)")
        if not self.containers:
            print(f"{CLR_YELLOW}Belum ada kontainer yang dibuat.{CLR_RESET}")
            return

        fmt = "{:<10} {:<15} {:<18} {:<12} {:<18} {:<15}"
        print(f"{CLR_BOLD}" + fmt.format("ID", "NAME", "IMAGE", "STATUS", "PORTS", "IP (VIRTUAL)") + f"{CLR_RESET}")
        print("-" * 90)
        for cid, c in self.containers.items():
            status_color = CLR_GREEN if c["status"] == "Running" else CLR_YELLOW
            print(fmt.format(
                c["id"][:8],
                c["name"][:14],
                c["image"][:17],
                f"{status_color}{c['status']}{CLR_RESET}",
                c["port_map"],
                c["namespaces"]["virtual_ip"]
            ))

    def inspect_container_security(self, container_id: str):
        if container_id not in self.containers:
            print(f"{CLR_RED}[!] Container ID tidak valid.{CLR_RESET}")
            return

        c = self.containers[container_id]
        self.print_section(f"Deep-Dive Isolasi Kernel: {c['name']} ({container_id})")
        
        print(f"{CLR_CYAN}1. Linux Namespaces (Isolasi View):{CLR_RESET}")
        print(f"   - UTS Namespace : hostname = {c['namespaces']['uts_hostname']} (terisolasi dari host)")
        print(f"   - PID Namespace : Proses lokal kontainer melihat dirinya sebagai PID 1")
        print(f"   - NET Namespace : IP Virtual = {c['namespaces']['virtual_ip']}, Mapped Port = {c['port_map']}")
        
        print(f"\n{CLR_CYAN}2. Linux Control Groups (Cgroups Resource Guard):{CLR_RESET}")
        print(f"   - Memory Limit  : {c['cgroups']['memory_max']} (Mencegah OOM Killer menembak host)")
        print(f"   - CPU Quota     : {c['cgroups']['cpu_max']} (Mencegah CPU starvation)")

        print(f"\n{CLR_CYAN}3. Port Forwarding (iptables NAT Simulation):{CLR_RESET}")
        host_port, c_port = c["port_map"].split(":") if ":" in c["port_map"] else ("None", "None")
        print(f"   - Aturan NAT    : Host 0.0.0.0:{host_port} ---> {c['namespaces']['virtual_ip']}:{c_port}")

    def simulate_oom_event(self, container_id: str):
        if container_id not in self.containers:
            print(f"{CLR_RED}[!] Container ID tidak valid.{CLR_RESET}")
            return
        
        c = self.containers[container_id]
        self.print_section(f"Simulasi Cgroups Memory Throttling & OOM: {c['name']}")
        print(f"Kontainer memiliki batas memori: {c['cgroups']['memory_max']}.")
        print("Menjalankan beban kerja sintetis alokasi memory leak...")
        
        for usage in [32, 64, 128, 256]:
            print(f"  [Allocating] Beban kerja memakai {usage}MB RAM...")
            time.sleep(0.2)
        
        print(f"{CLR_RED}{CLR_BOLD}[OOM-KILLER TRIGGERED]{CLR_RESET}")
        print(f"{CLR_RED}Kernel cgroups mendeteksi penggunaan melebihi threshold cgroups ({c['cgroups']['memory_max']}).")
        print(f"Proses PID 1 di dalam kontainer dihentikan paksa (SIGKILL / Exit Code 137).{CLR_RESET}")
        c["status"] = "Exited (137)"
        print(f"Status kontainer kini: {CLR_RED}{c['status']}{CLR_RESET}")


def interactive_menu():
    sim = ContainerSimulator()
    sim.print_banner()

    # Pre-populate sample container
    cid1 = sim.create_container("web-prod-01", "webapp:v1", "8080:80", "128M", "0.5 CPU")
    sim.start_container(cid1)

    while True:
        print(f"\n{CLR_BOLD}PILIH MENU SIMULASI LABORATORIUM:{CLR_RESET}")
        print(" 1) Inspeksi Layer Image (OverlayFS / Storage Driver)")
        print(" 2) Jalankan Kontainer Baru (docker run)")
        print(" 3) Tampilkan Daftar Kontainer (docker ps)")
        print(" 4) Bedah Isolasi Kernel & Cgroups (docker inspect)")
        print(" 5) Simulasi Pelanggaran Resource (OOM Killer Exit 137)")
        print(" 0) Keluar (Exit)")
        
        try:
            choice = input(f"\n{CLR_GREEN}Masukkan pilihan [0-5]: {CLR_RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nSelesai.")
            break

        if choice == "1":
            print("\nPilihan Image yang Tersedia:")
            for img in sim.images.keys():
                print(f" - {img}")
            selected = input("Pilih image [webapp:v1]: ").strip() or "webapp:v1"
            sim.inspect_image_layers(selected)

        elif choice == "2":
            name = input("Nama kontainer [api-service]: ").strip() or "api-service"
            img = input("Image (alpine:3.19 / python:3.11-slim / webapp:v1) [alpine:3.19]: ").strip() or "alpine:3.19"
            ports = input("Port mapping (Host:Container) [3000:3000]: ").strip() or "3000:3000"
            mem = input("Limit RAM (misal 64M, 256M) [64M]: ").strip() or "64M"
            cpu = input("Limit CPU (misal 0.2 CPU, 1.0 CPU) [0.2 CPU]: ").strip() or "0.2 CPU"

            new_id = sim.create_container(name, img, ports, mem, cpu)
            if new_id:
                sim.start_container(new_id)

        elif choice == "3":
            sim.list_containers()

        elif choice == "4":
            sim.list_containers()
            cid = input("\nMasukkan ID Kontainer: ").strip()
            # Cari matches
            matched = [k for k in sim.containers.keys() if k.startswith(cid)]
            if matched:
                sim.inspect_container_security(matched[0])
            else:
                print(f"{CLR_RED}Kontainer ID '{cid}' tidak ditemukan.{CLR_RESET}")

        elif choice == "5":
            sim.list_containers()
            cid = input("\nPilih Kontainer untuk Uji Coba OOM: ").strip()
            matched = [k for k in sim.containers.keys() if k.startswith(cid)]
            if matched:
                sim.simulate_oom_event(matched[0])
            else:
                print(f"{CLR_RED}Kontainer ID '{cid}' tidak ditemukan.{CLR_RESET}")

        elif choice == "0":
            print(f"\n{CLR_CYAN}Terima kasih telah menyelesaikan simulasi konsep Docker!{CLR_RESET}")
            break
        else:
            print(f"{CLR_RED}Pilihan tidak valid, silakan coba lagi.{CLR_RESET}")


if __name__ == "__main__":
    interactive_menu()
