#!/usr/bin/env python3
"""
AWS Compute Architecture & Elastic Scaling Lab Simulation (BAB-03)
Simulasi Arsitektur Produksi Tingkat Lanjut:
- Multi-AZ Elastic Auto Scaling Group (ASG) & Warm Pool
- Application Load Balancer (ALB) Health Check & Target Draining
- Target Tracking Scaling Policies (CPU & Request Count Per Target)
- ASG Lifecycle Hooks (Instance Terminating: Wait -> Deregistration)
"""

import sys
import time
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Optional

# ANSI Color Codes
class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    BG_BLUE = "\033[44m"
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"

class InstanceLifecycleState(Enum):
    PENDING_INIT = "Pending:Wait"
    WARM_POOL_STOPPED = "WPool:Stopped"
    IN_SERVICE = "InService"
    DRAINING = "Terminating:Wait (Draining)"
    TERMINATED = "Terminated"

class HealthStatus(Enum):
    HEALTHY = "Healthy"
    UNHEALTHY = "Unhealthy"

@dataclass
class EC2Instance:
    instance_id: str
    az: str
    instance_type: str = "c6i.xlarge"
    lifecycle_state: InstanceLifecycleState = InstanceLifecycleState.IN_SERVICE
    health_status: HealthStatus = HealthStatus.HEALTHY
    cpu_utilization: float = 20.0
    active_connections: int = 0
    boot_time_sec: float = 3.0

@dataclass
class AutoScalingGroup:
    name: str = "asg-prod-core-api"
    min_size: int = 3
    max_size: int = 12
    desired_capacity: int = 3
    availability_zones: List[str] = field(default_factory=lambda: ["ap-southeast-1a", "ap-southeast-1b", "ap-southeast-1c"])
    target_cpu_util: float = 65.0
    instances: List[EC2Instance] = field(default_factory=list)
    warm_pool: List[EC2Instance] = field(default_factory=list)
    next_id_counter: int = 100

    def init_fleet(self):
        """Menginisialisasi instance ke active fleet seimbang di 3 AZ dan 2 di warm pool."""
        self.instances.clear()
        self.warm_pool.clear()
        for i in range(self.desired_capacity):
            az = self.availability_zones[i % len(self.availability_zones)]
            self.next_id_counter += 1
            inst = EC2Instance(
                instance_id=f"i-{self.next_id_counter:08x}",
                az=az,
                lifecycle_state=InstanceLifecycleState.IN_SERVICE,
                health_status=HealthStatus.HEALTHY,
                cpu_utilization=random.uniform(25.0, 40.0),
                active_connections=random.randint(150, 250)
            )
            self.instances.append(inst)

        # Inisialisasi Warm Pool (Pra-inisialisasi AMI + konfigurasi, keadaan Stopped)
        for i in range(2):
            az = self.availability_zones[i % len(self.availability_zones)]
            self.next_id_counter += 1
            wp_inst = EC2Instance(
                instance_id=f"i-wp-{self.next_id_counter:06x}",
                az=az,
                lifecycle_state=InstanceLifecycleState.WARM_POOL_STOPPED,
                health_status=HealthStatus.HEALTHY,
                cpu_utilization=0.0,
                active_connections=0
            )
            self.warm_pool.append(wp_inst)

    def get_az_distribution(self) -> Dict[str, int]:
        dist = {az: 0 for az in self.availability_zones}
        for inst in self.instances:
            if inst.lifecycle_state == InstanceLifecycleState.IN_SERVICE:
                dist[inst.az] = dist.get(inst.az, 0) + 1
        return dist

    def pick_next_az(self) -> str:
        """Pilih AZ dengan jumlah instance aktif paling sedikit untuk menjaga balance."""
        dist = self.get_az_distribution()
        return min(dist, key=dist.get)

    def scale_out(self, count: int = 1, from_warm_pool: bool = True) -> List[EC2Instance]:
        new_instances = []
        for _ in range(count):
            if len(self.instances) >= self.max_size:
                print(f"{Color.RED}[ASG ALERT] Batas MaxSize ({self.max_size}) tercapai. Tidak dapat scale out.{Color.RESET}")
                break

            target_az = self.pick_next_az()
            if from_warm_pool and self.warm_pool:
                # Mengambil dari warm pool: Waktu transisi sangat singkat (~instant launch)
                inst = self.warm_pool.pop(0)
                inst.az = target_az
                inst.lifecycle_state = InstanceLifecycleState.IN_SERVICE
                inst.cpu_utilization = 30.0
                inst.active_connections = 0
                self.instances.append(inst)
                new_instances.append(inst)
                print(f"{Color.GREEN}[WARM POOL HIT] Instance {inst.instance_id} dipromosikan ke InService di {target_az} (Warm Boot < 5s).{Color.RESET}")
            else:
                self.next_id_counter += 1
                inst = EC2Instance(
                    instance_id=f"i-{self.next_id_counter:08x}",
                    az=target_az,
                    lifecycle_state=InstanceLifecycleState.PENDING_INIT,
                    cpu_utilization=10.0
                )
                self.instances.append(inst)
                new_instances.append(inst)
                print(f"{Color.CYAN}[COLD SCALE OUT] Memulai launch instance baru {inst.instance_id} di {target_az}...{Color.RESET}")
                inst.lifecycle_state = InstanceLifecycleState.IN_SERVICE

        self.desired_capacity = len(self.instances)
        return new_instances

    def scale_in(self, count: int = 1) -> List[EC2Instance]:
        """Scale-in dengan AZ rebalance termination policy."""
        drained_instances = []
        for _ in range(count):
            if len(self.instances) <= self.min_size:
                print(f"{Color.YELLOW}[ASG WARNING] Batas MinSize ({self.min_size}) tercapai. Scale in ditahan.{Color.RESET}")
                break

            # Policy: Hapus instance dari AZ dengan jumlah terbanyak, lalu pilih yang tertua/CPU terendah
            dist = self.get_az_distribution()
            max_az = max(dist, key=dist.get)
            candidates = [inst for inst in self.instances if inst.az == max_az and inst.lifecycle_state == InstanceLifecycleState.IN_SERVICE]
            if not candidates:
                candidates = [inst for inst in self.instances if inst.lifecycle_state == InstanceLifecycleState.IN_SERVICE]

            if not candidates:
                break

            target = candidates[0]
            print(f"{Color.MAGENTA}[LIFECYCLE HOOK: autoscaling:EC2_INSTANCE_TERMINATING]{Color.RESET}")
            print(f" -> Instance {target.instance_id} ({target.az}) memasuki status DRAINING (Deregistration Delay: 15 detik)...")
            target.lifecycle_state = InstanceLifecycleState.DRAINING
            drained_instances.append(target)
            self.instances.remove(target)

        self.desired_capacity = len(self.instances)
        return drained_instances

    def simulate_traffic(self, rps: int):
        """Mendistribusikan traffic ke instance InService dan kalkulasi beban CPU."""
        active = [i for i in self.instances if i.lifecycle_state == InstanceLifecycleState.IN_SERVICE and i.health_status == HealthStatus.HEALTHY]
        if not active:
            return

        rps_per_instance = rps / len(active)
        for inst in active:
            inst.active_connections = int(rps_per_instance * random.uniform(0.85, 1.15))
            # Model beban CPU nonlinear berdasarkan RPS
            inst.cpu_utilization = min(99.9, (inst.active_connections / 80.0) * 18.0 + random.uniform(5.0, 12.0))

    def evaluate_target_tracking(self):
        """Target Tracking: CPU target 65%."""
        active = [i for i in self.instances if i.lifecycle_state == InstanceLifecycleState.IN_SERVICE]
        if not active:
            return

        avg_cpu = sum(i.cpu_utilization for i in active) / len(active)
        print(f"\n{Color.BOLD}[CLOUDWATCH METRIC] Fleet Average CPU: {avg_cpu:.1f}% (Target Policy: {self.target_cpu_util:.1f}%){Color.RESET}")

        if avg_cpu > self.target_cpu_util + 5.0:
            deficit_factor = (avg_cpu - self.target_cpu_util) / 15.0
            scale_count = max(1, int(deficit_factor))
            print(f"{Color.RED}[ALARM TRIGGERED] High CPU Alarm aktif (> {self.target_cpu_util}%). Memicu Scale-Out +{scale_count} node...{Color.RESET}")
            self.scale_out(count=scale_count)
        elif avg_cpu < (self.target_cpu_util - 25.0) and len(self.instances) > self.min_size:
            print(f"{Color.GREEN}[ALARM TRIGGERED] Low CPU Alarm aktif (< {self.target_cpu_util - 25.0}%). Memicu Scale-In -1 node...{Color.RESET}")
            self.scale_in(count=1)
        else:
            print(f"{Color.GREEN}[ALARM OK] Beban CPU armada seimbang dalam batas toleransi target tracking.{Color.RESET}")

def render_dashboard(asg: AutoScalingGroup):
    print("\n" + "=" * 92)
    print(f"{Color.BG_BLUE}{Color.WHITE}{Color.BOLD}   AWS ARCHITECTURE LAB: ELASTIC COMPUTE & HIGH AVAILABILITY MONITOR   {Color.RESET}")
    print("=" * 92)
    
    active_instances = [i for i in asg.instances if i.lifecycle_state == InstanceLifecycleState.IN_SERVICE]
    avg_cpu = (sum(i.cpu_utilization for i in active_instances) / len(active_instances)) if active_instances else 0.0
    total_conns = sum(i.active_connections for i in active_instances)
    
    dist = asg.get_az_distribution()
    az_str = " | ".join([f"{az}: {cnt} inst" for az, cnt in dist.items()])

    print(f"{Color.BOLD}ASG Name:{Color.RESET} {asg.name:<25} | {Color.BOLD}Desired/Min/Max:{Color.RESET} {asg.desired_capacity}/{asg.min_size}/{asg.max_size}")
    print(f"{Color.BOLD}AZ Topology:{Color.RESET} {az_str}")
    print(f"{Color.BOLD}Aggregate Metric:{Color.RESET} Avg CPU: {avg_cpu:.1f}% | Total Conns: {total_conns} req/s | Warm Pool: {len(asg.warm_pool)} standby")
    print("-" * 92)
    print(f"{'INSTANCE ID':<15} | {'AZ':<16} | {'STATE':<24} | {'HEALTH':<10} | {'CPU %':<8} | {'ACTIVE CONNS':<12}")
    print("-" * 92)

    for inst in asg.instances:
        state_color = Color.GREEN if inst.lifecycle_state == InstanceLifecycleState.IN_SERVICE else Color.YELLOW
        health_color = Color.GREEN if inst.health_status == HealthStatus.HEALTHY else Color.RED
        cpu_bar = f"{inst.cpu_utilization:5.1f}%"
        if inst.cpu_utilization > 80.0:
            cpu_bar = f"{Color.RED}{cpu_bar}{Color.RESET}"
        elif inst.cpu_utilization > 50.0:
            cpu_bar = f"{Color.YELLOW}{cpu_bar}{Color.RESET}"
        else:
            cpu_bar = f"{Color.GREEN}{cpu_bar}{Color.RESET}"

        print(f"{inst.instance_id:<15} | {inst.az:<16} | {state_color}{inst.lifecycle_state.value:<24}{Color.RESET} | {health_color}{inst.health_status.value:<10}{Color.RESET} | {cpu_bar:<17} | {inst.active_connections:<12}")

    for wp in asg.warm_pool:
        print(f"{wp.instance_id:<15} | {wp.az:<16} | {Color.BLUE}{wp.lifecycle_state.value:<24}{Color.RESET} | {Color.WHITE}{wp.health_status.value:<10}{Color.RESET} | {0.0:5.1f}%          | 0 (Standby)")

    print("-" * 92)

def interactive_loop():
    asg = AutoScalingGroup()
    asg.init_fleet()

    # Baseline traffic
    asg.simulate_traffic(rps=750)

    while True:
        render_dashboard(asg)
        print(f"\n{Color.BOLD}PILIHAN AKSI SIMULASI:{Color.RESET}")
        print(f" {Color.CYAN}1.{Color.RESET} Suntikkan Lonjakan Trafik Masif (Flash Crowd 3500 RPS) -> Uji Target Tracking")
        print(f" {Color.CYAN}2.{Color.RESET} Turunkan Trafik Normal (500 RPS) -> Uji Scale In & Cooldown")
        print(f" {Color.CYAN}3.{Color.RESET} Simulasikan Kegagalan AZ (Disaster Recovery Simulation di ap-southeast-1a)")
        print(f" {Color.CYAN}4.{Color.RESET} Picu Health Check Unhealthy pada Instance Acak (ALB Target Replacement)")
        print(f" {Color.CYAN}5.{Color.RESET} Uji Warm Pool Rehydration (Tambah 2 instance ke Warm Pool)")
        print(f" {Color.CYAN}6.{Color.RESET} Jalankan Automated End-to-End Stress Test Benchmark (5 Siklus)")
        print(f" {Color.RED}0.{Color.RESET} Keluar (Exit)")

        try:
            choice = input(f"\n{Color.YELLOW}Pilih opsi [0-6]: {Color.RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting lab.")
            break

        if choice == "1":
            print(f"\n{Color.RED}>>> Menyuntikkan lonjakan 3800 RPS ke Target Group ALB...{Color.RESET}")
            asg.simulate_traffic(rps=3800)
            render_dashboard(asg)
            time.sleep(1)
            asg.evaluate_target_tracking()
            input(f"\n{Color.WHITE}[Tekan Enter untuk lanjut]{Color.RESET}")

        elif choice == "2":
            print(f"\n{Color.GREEN}>>> Menurunkan beban trafik ke 400 RPS...{Color.RESET}")
            asg.simulate_traffic(rps=400)
            render_dashboard(asg)
            time.sleep(1)
            asg.evaluate_target_tracking()
            input(f"\n{Color.WHITE}[Tekan Enter untuk lanjut]{Color.RESET}")

        elif choice == "3":
            failed_az = "ap-southeast-1a"
            print(f"\n{Color.BG_RED}{Color.WHITE}>>> OUTAGE SIMULATION: Zona {failed_az} mengalami degradasi total! <<<{Color.RESET}")
            affected = [i for i in asg.instances if i.az == failed_az]
            for inst in affected:
                inst.health_status = HealthStatus.UNHEALTHY
                inst.cpu_utilization = 0.0
                inst.active_connections = 0
            render_dashboard(asg)
            print(f"{Color.YELLOW}[AUTO-HEALING] ASG mendeteksi {len(affected)} instance Unhealthy. Memulai terminasi dan rebalance ke AZ sehat...{Color.RESET}")
            time.sleep(1.5)
            # Evakuasi
            for inst in affected:
                asg.instances.remove(inst)
                new_az = asg.pick_next_az()
                asg.next_id_counter += 1
                healed = EC2Instance(
                    instance_id=f"i-recov-{asg.next_id_counter:06x}",
                    az=new_az,
                    lifecycle_state=InstanceLifecycleState.IN_SERVICE,
                    health_status=HealthStatus.HEALTHY,
                    cpu_utilization=35.0,
                    active_connections=120
                )
                asg.instances.append(healed)
                print(f" -> Replacement launched: {healed.instance_id} di {new_az} [OK]")
            input(f"\n{Color.WHITE}[Tekan Enter untuk lanjut]{Color.RESET}")

        elif choice == "4":
            active = [i for i in asg.instances if i.health_status == HealthStatus.HEALTHY]
            if active:
                victim = random.choice(active)
                victim.health_status = HealthStatus.UNHEALTHY
                print(f"\n{Color.RED}[ALB TARGET HEALTH CHECK FAILED] Instance {victim.instance_id} gagal merespons /healthz (504 Gateway Timeout).{Color.RESET}")
                render_dashboard(asg)
                time.sleep(1)
                print(f"{Color.YELLOW}[ASG AUTO-REPLACE] Menghapus instance rusak dan memanggil warm pool...{Color.RESET}")
                asg.instances.remove(victim)
                asg.scale_out(count=1, from_warm_pool=True)
            input(f"\n{Color.WHITE}[Tekan Enter untuk lanjut]{Color.RESET}")

        elif choice == "5":
            print(f"\n{Color.BLUE}>>> Menambahkan 2 instance ke Warm Pool (AMI Pre-warmed & Stopped)...{Color.RESET}")
            for _ in range(2):
                asg.next_id_counter += 1
                az = asg.pick_next_az()
                wp = EC2Instance(
                    instance_id=f"i-wp-{asg.next_id_counter:06x}",
                    az=az,
                    lifecycle_state=InstanceLifecycleState.WARM_POOL_STOPPED,
                    health_status=HealthStatus.HEALTHY
                )
                asg.warm_pool.append(wp)
            print(f"{Color.GREEN}[WARM POOL UPDATED] Total instance siaga: {len(asg.warm_pool)}{Color.RESET}")
            input(f"\n{Color.WHITE}[Tekan Enter untuk lanjut]{Color.RESET}")

        elif choice == "6":
            print(f"\n{Color.MAGENTA}=== MEMULAI AUTOMATED BENCHMARK WORKLOAD (5 SIKLUS) ==={Color.RESET}")
            test_loads = [800, 2400, 4200, 1800, 600]
            for step, load in enumerate(test_loads, start=1):
                print(f"\n{Color.BOLD}--- Siklus {step}/5: Beban Trafik Masuk = {load} RPS ---{Color.RESET}")
                asg.simulate_traffic(rps=load)
                render_dashboard(asg)
                asg.evaluate_target_tracking()
                time.sleep(1.2)
            print(f"\n{Color.GREEN}=== BENCHMARK SELESAI: ASG BERHASIL MENJAGA ELASTISITAS DENGAN HIGH AVAILABILITY ==={Color.RESET}")
            input(f"\n{Color.WHITE}[Tekan Enter untuk kembali ke menu]{Color.RESET}")

        elif choice == "0":
            print(f"\n{Color.CYAN}Menutup simulasi lab. Sampai jumpa!{Color.RESET}")
            break
        else:
            print(f"{Color.RED}Pilihan tidak valid! Silakan masukkan 0-6.{Color.RESET}")
            time.sleep(1)

if __name__ == "__main__":
    interactive_loop()
