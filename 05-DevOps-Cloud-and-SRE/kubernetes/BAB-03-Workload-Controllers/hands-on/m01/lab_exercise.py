#!/usr/bin/env python3
"""
Kubernetes Workload Controllers Simulation Lab
BAB-03: Workload Controllers (Deployment, ReplicaSet, RollingUpdate, Self-Healing)
"""

import time
import random
import sys
from dataclasses import dataclass, field
from typing import List, Dict, Optional

# ANSI Color Codes for Rich Terminal Output
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
RED = "\033[31m"
BG_BLUE = "\033[44m"
GRAY = "\033[90m"

@dataclass
class Pod:
    name: str
    image: str
    status: str = "Running"
    ip: str = ""
    restart_count: int = 0
    ready: bool = True

    def __post_init__(self):
        if not self.ip:
            self.ip = f"10.244.{random.randint(1, 5)}.{random.randint(2, 254)}"

@dataclass
class ReplicaSet:
    name: str
    revision: int
    image: str
    replicas: int
    pods: List[Pod] = field(default_factory=list)

    def active_pod_count(self) -> int:
        return len([p for p in self.pods if p.status == "Running"])

class DeploymentController:
    """
    Simulates Kubernetes Deployment and ReplicaSet Controller reconciliation loops,
    supporting Rolling Updates (maxSurge=1, maxUnavailable=0) and Self-Healing.
    """
    def __init__(self, name: str, replicas: int, image: str):
        self.name = name
        self.desired_replicas = replicas
        self.current_image = image
        self.revision = 1
        self.replica_sets: Dict[int, ReplicaSet] = {}
        
        # Inisialisasi ReplicaSet v1
        init_rs = ReplicaSet(
            name=f"{self.name}-rs-v{self.revision}",
            revision=self.revision,
            image=self.current_image,
            replicas=self.desired_replicas
        )
        self.replica_sets[self.revision] = init_rs
        self._scale_rs(init_rs, self.desired_replicas)

    def _generate_pod_name(self, rs_name: str) -> str:
        random_suffix = ''.join(random.choices('abcdef0123456789', k=5))
        return f"{rs_name}-{random_suffix}"

    def _scale_rs(self, rs: ReplicaSet, target_count: int):
        rs.replicas = target_count
        while len(rs.pods) < target_count:
            pod = Pod(name=self._generate_pod_name(rs.name), image=rs.image)
            rs.pods.append(pod)
        while len(rs.pods) > target_count:
            rs.pods.pop()

    def print_status(self, title: str = "CLUSTER RECONCILIATION STATE"):
        print(f"\n{BOLD}{CYAN}=== {title} ==={RESET}")
        print(f"{BOLD}Deployment:{RESET} {self.name} | Desired Replicas: {GREEN}{self.desired_replicas}{RESET} | Active Image: {YELLOW}{self.current_image}{RESET}")
        print("-" * 75)
        print(f"{'REPLICASET':<22} {'REVISION':<10} {'DESIRED':<10} {'CURRENT':<10} {'IMAGE'}")
        print("-" * 75)
        for rev, rs in sorted(self.replica_sets.items()):
            print(f"{rs.name:<22} {f'rev-{rev}':<10} {rs.replicas:<10} {rs.active_pod_count():<10} {rs.image}")
        print("-" * 75)
        print(f"{'POD NAME':<30} {'STATUS':<12} {'POD IP':<18} {'IMAGE'}")
        print("-" * 75)
        for rs in self.replica_sets.values():
            for p in rs.pods:
                status_color = GREEN if p.status == "Running" else RED
                print(f"{p.name:<30} {status_color}{p.status:<12}{RESET} {p.ip:<18} {p.image}")
        print("-" * 75 + "\n")

    def self_healing_trigger(self):
        """Simulasikan node crash / pod termination dan uji rekonsiliasi controller."""
        all_pods = []
        for rs in self.replica_sets.values():
            if rs.replicas > 0:
                all_pods.extend(rs.pods)

        if not all_pods:
            print(f"{RED}[!] Tidak ada Pod yang sedang aktif untuk diuji crash.{RESET}")
            return

        victim = random.choice(all_pods)
        print(f"{MAGENTA}[EVENT]{RESET} Simulasi hardware node crash! Mengeliminasi Pod: {BOLD}{victim.name}{RESET}")
        victim.status = "Terminated"
        self.print_status("POD CRASH DETECTED")
        
        print(f"{BLUE}[RECONCILE LOOP]{RESET} Kube-Controller-Manager mendeteksi drift: Desired != Actual")
        time.sleep(1.2)
        
        # Reconcile: Bersihkan terminated pod dan instantiate pod baru
        for rs in self.replica_sets.values():
            if victim in rs.pods:
                rs.pods.remove(victim)
                new_pod = Pod(name=self._generate_pod_name(rs.name), image=rs.image)
                rs.pods.append(new_pod)
                print(f"{GREEN}[HEALED]{RESET} Controller menjadwalkan Pod pengganti: {BOLD}{new_pod.name}{RESET} ({new_pod.ip})")
                break

        time.sleep(0.8)
        self.print_status("RECONCILIATION COMPLETE: DESIRED STATE RESTORED")

    def rolling_update(self, new_image: str):
        """
        Simulasi Strategi RollingUpdate:
        maxSurge = 1, maxUnavailable = 0
        """
        if new_image == self.current_image:
            print(f"{YELLOW}[!] Deployment sudah menjalankan versi {new_image}. Tidak ada perubahan spec.{RESET}")
            return

        print(f"\n{BOLD}{BG_BLUE} >> MEMULAI ROLLING UPDATE: {self.current_image} -> {new_image} << {RESET}")
        self.revision += 1
        old_rev = self.revision - 1
        old_rs = self.replica_sets[old_rev]
        
        new_rs = ReplicaSet(
            name=f"{self.name}-rs-v{self.revision}",
            revision=self.revision,
            image=new_image,
            replicas=0
        )
        self.replica_sets[self.revision] = new_rs
        self.current_image = new_image

        step = 1
        while new_rs.replicas < self.desired_replicas or old_rs.replicas > 0:
            print(f"\n{CYAN}--- Rolling Update Step {step} (maxSurge=1, maxUnavailable=0) ---{RESET}")
            
            # Step A: Scale Up New RS (Surge)
            if new_rs.replicas < self.desired_replicas:
                target_new = new_rs.replicas + 1
                self._scale_rs(new_rs, target_new)
                print(f"{GREEN}[SURGE UP]{RESET} Scaling {new_rs.name} to {new_rs.replicas} replica(s)")
                time.sleep(0.7)

            # Step B: Scale Down Old RS
            if old_rs.replicas > 0:
                target_old = old_rs.replicas - 1
                self._scale_rs(old_rs, target_old)
                print(f"{YELLOW}[DRAIN DOWN]{RESET} Scaling down {old_rs.name} to {old_rs.replicas} replica(s)")
                time.sleep(0.7)

            self.print_status(f"ROLLING UPDATE IN PROGRESS (Step {step})")
            step += 1

        print(f"{GREEN}{BOLD}✓ Rolling Update selesai! Seluruh Pod berjalan pada versi {new_image}.{RESET}\n")

    def rollback(self, target_revision: Optional[int] = None):
        """Simulasikan kubectl rollout undo."""
        previous_revisions = [r for r, rs in self.replica_sets.items() if rs.image != self.current_image]
        if not previous_revisions:
            print(f"{RED}[!] Tidak ada histori revisi sebelumnya untuk rollback.{RESET}")
            return

        target_rev = target_revision if (target_revision and target_revision in self.replica_sets) else max(previous_revisions)
        target_image = self.replica_sets[target_rev].image
        print(f"{MAGENTA}[ROLLBACK]{RESET} Mengembalikan deployment ke Revision {target_rev} ({target_image})...")
        self.rolling_update(target_image)

def interactive_cli():
    print(f"{BOLD}{BLUE}===================================================================={RESET}")
    print(f"{BOLD}{GREEN}  SIMULATOR INTERAKTIF WORKLOAD CONTROLLERS KUBERNETES (BAB-03)     {RESET}")
    print(f"{BOLD}{BLUE}===================================================================={RESET}")
    print(f"Modul Praktikum: Konsep Dasar Deployment, ReplicaSet & Reconciliation Loop")
    
    deploy = DeploymentController(name="ecommerce-api", replicas=3, image="nginx:1.24-alpine")
    deploy.print_status("INITIAL DEPLOYMENT STATE")

    menu = f"""{BOLD}Menu Kontrol Operasional:{RESET}
  {CYAN}[1]{RESET} Tampilkan Status Kluster Saat Ini
  {CYAN}[2]{RESET} Jalankan Rolling Update (Update Versi Kontainer)
  {CYAN}[3]{RESET} Simulasi Pod Crash & Self-Healing Loop
  {CYAN}[4]{RESET} Rollout Undo (Rollback ke Revisi Sebelumnya)
  {CYAN}[5]{RESET} Ubah Skala Replikasi (Scale Desired Replicas)
  {CYAN}[6]{RESET} Jalankan Demo Otomatis Lengkap
  {CYAN}[0]{RESET} Keluar
"""

    while True:
        print(menu)
        try:
            choice = input(f"{BOLD}Pilih opsi [0-6]: {RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{YELLOW}Program dihentikan.{RESET}")
            break

        if choice == "1":
            deploy.print_status("CURRENT CLUSTER STATUS")
        elif choice == "2":
            new_tag = input("Masukkan versi image baru (contoh: nginx:1.25-alpine, nginx:v2): ").strip()
            if new_tag:
                deploy.rolling_update(new_tag)
        elif choice == "3":
            deploy.self_healing_trigger()
        elif choice == "4":
            deploy.rollback()
        elif choice == "5":
            scale_input = input("Masukkan target jumlah replika: ").strip()
            if scale_input.isdigit() and int(scale_input) > 0:
                new_scale = int(scale_input)
                deploy.desired_replicas = new_scale
                active_rs = deploy.replica_sets[deploy.revision]
                deploy._scale_rs(active_rs, new_scale)
                deploy.print_status("SCALE RECONCILED")
            else:
                print(f"{RED}[!] Input skala tidak valid.{RESET}")
        elif choice == "6":
            print(f"\n{BOLD}{CYAN}>>> MEMULAI SKENARIO DEMO OTOMATIS <<<{RESET}")
            time.sleep(1)
            print(f"\n{BOLD}Skenario 1: Deployment v1 stabil dengan 3 replika.{RESET}")
            deploy.print_status()
            time.sleep(1.5)
            
            print(f"\n{BOLD}Skenario 2: Simulasi kegagalan pod dan pembuktian Self-Healing.{RESET}")
            deploy.self_healing_trigger()
            time.sleep(1.5)

            print(f"\n{BOLD}Skenario 3: Rolling Update zero-downtime ke versi v2 (nginx:1.25).{RESET}")
            deploy.rolling_update("nginx:1.25-alpine")
            time.sleep(1.5)

            print(f"\n{BOLD}Skenario 4: Rollback instan ke versi v1.{RESET}")
            deploy.rollback()
            print(f"\n{BOLD}{GREEN}>>> DEMO OTOMATIS SELESAI DENGAN SUKSES <<<{RESET}\n")
        elif choice == "0":
            print(f"{GREEN}Terima kasih telah mempelajari arsitektur Workload Controllers Kubernetes!{RESET}")
            break
        else:
            print(f"{RED}[!] Pilihan tidak valid. Silakan pilih 0-6.{RESET}")

if __name__ == "__main__":
    # Jika dijalankan dengan argument '--auto', jalankan mode demo langsung
    if "--auto" in sys.argv:
        deploy = DeploymentController(name="ecommerce-api", replicas=3, image="nginx:1.24-alpine")
        deploy.print_status("INITIAL STATE")
        deploy.self_healing_trigger()
        deploy.rolling_update("nginx:1.25-alpine")
        deploy.rollback()
    else:
        interactive_cli()
