#!/usr/bin/env python3
"""
Simulasi Mesin Status (Finite State Machine) Protokol VRRP (RFC 5798).
Modul Hands-on Bab 04: Layer 3 Routing Fundamentals & FHRP.

Script ini mensimulasikan dua node router (Master & Backup) yang berbagi satu Virtual IP.
Dilengkapi thread background untuk pengiriman Advertisement packet, deteksi Master Down Timer,
tracking interface WAN, dan CLI interaktif untuk menguji skenario kegagalan link (failover).

Kebutuhan: Python 3.8+ (Standard Library Only)
"""

import threading
import time
import sys
import logging
from dataclasses import dataclass
from typing import Optional

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] (%(threadName)s) %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("VRRP-Sim")

# Konstanta Protokol VRRP
VRRP_PRIORITY_OWNER = 255
VRRP_PRIORITY_DEFAULT = 100
VRRP_DEFAULT_ADV_INTERVAL = 1.0  # detik

@dataclass
class VRRPAdvertisement:
    vrid: int
    priority: int
    adv_interval: float
    virtual_ip: str
    source_ip: str

class VirtualRouter:
    """
    Representasi sebuah Node Router yang menjalankan instance Virtual Router (VRRP).
    Mendukung State Machine: INITIALIZE, BACKUP, MASTER.
    """
    def __init__(self, name: str, real_ip: str, vrid: int, virtual_ip: str, 
                 base_priority: int = 100, preempt: bool = True):
        self.name = name
        self.real_ip = real_ip
        self.vrid = vrid
        self.virtual_ip = virtual_ip
        self.base_priority = base_priority
        self.current_priority = base_priority
        self.preempt = preempt
        
        # State: "INITIALIZE", "BACKUP", "MASTER"
        self.state = "INITIALIZE"
        self.wan_uplink_up = True
        self.wan_track_decrement = 30
        
        # Timers
        self.adv_interval = VRRP_DEFAULT_ADV_INTERVAL
        self.master_down_interval = (3 * self.adv_interval) + ((256 - self.current_priority) / 256.0)
        self.last_heard_master_time = time.time()
        
        # Concurrency & Simulation control
        self.running = False
        self.network_bus: Optional['VirtualNetworkBus'] = None
        self._lock = threading.Lock()
        self.worker_thread: Optional[threading.Thread] = None

    def calculate_virtual_mac(self) -> str:
        """Kalkulasi Virtual MAC sesuai RFC 5798: 00-00-5E-00-01-{VRID}"""
        return f"00:00:5E:00:01:{self.vrid:02X}"

    def attach_bus(self, bus: 'VirtualNetworkBus'):
        self.network_bus = bus

    def start(self):
        self.running = True
        with self._lock:
            # Transisi awal RFC: Jika priority == 255 (IP Owner) langsung MASTER, jika tidak -> BACKUP
            if self.current_priority == VRRP_PRIORITY_OWNER:
                self.transition_to_master()
            else:
                self.transition_to_backup()
        
        self.worker_thread = threading.Thread(target=self._run_loop, name=f"Thread-{self.name}", daemon=True)
        self.worker_thread.start()
        logger.info(f"[{self.name}] Node started in state {self.state} with Priority={self.current_priority}")

    def stop(self):
        self.running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=1.0)
        logger.info(f"[{self.name}] Node stopped.")

    def transition_to_master(self):
        self.state = "MASTER"
        vmac = self.calculate_virtual_mac()
        logger.warning(f"*** [{self.name}] STATUS TRANSITION -> MASTER! ***")
        logger.warning(f"[{self.name}] Broadcasting Gratuitous ARP: IP {self.virtual_ip} is at MAC {vmac}")
        self._send_advertisement()

    def transition_to_backup(self):
        self.state = "BACKUP"
        self.last_heard_master_time = time.time()
        # Recalculate Master Down Timer: (3 * Adv_Interval) + Skew_Time
        skew_time = ((256 - self.current_priority) / 256.0) * self.adv_interval
        self.master_down_interval = (3 * self.adv_interval) + skew_time
        logger.info(f"[{self.name}] STATUS TRANSITION -> BACKUP. Master Down Timer: {self.master_down_interval:.2f}s")

    def _send_advertisement(self):
        if not self.wan_uplink_up:
            return  # Jangan kirim jika interface mati total
        adv = VRRPAdvertisement(
            vrid=self.vrid,
            priority=self.current_priority,
            adv_interval=self.adv_interval,
            virtual_ip=self.virtual_ip,
            source_ip=self.real_ip
        )
        if self.network_bus:
            self.network_bus.broadcast(adv, sender=self)

    def receive_advertisement(self, adv: VRRPAdvertisement):
        with self._lock:
            if not self.running:
                return

            if adv.vrid != self.vrid:
                return  # Abaikan VRID lain

            now = time.time()

            if self.state == "BACKUP":
                if adv.priority == 0:
                    # Master mengumumkan pelepasan jabatan (graceful shutdown)
                    self.master_down_interval = ((256 - self.current_priority) / 256.0) * self.adv_interval
                    logger.info(f"[{self.name}] Master sent priority 0 (shutdown). Preempting quickly...")
                elif not self.preempt or adv.priority >= self.current_priority:
                    # Master valid terdeteksi, reset timer
                    self.last_heard_master_time = now
                else:
                    # Priority pengirim lebih rendah dari kita, dan preempt aktif
                    logger.info(f"[{self.name}] Ignored lower priority ({adv.priority}) adv from {adv.source_ip}. Our priority: {self.current_priority}")

            elif self.state == "MASTER":
                if adv.priority > self.current_priority:
                    logger.warning(f"[{self.name}] Higher priority master detected ({adv.priority} > {self.current_priority}) from {adv.source_ip}.")
                    self.transition_to_backup()
                elif adv.priority == self.current_priority and adv.source_ip > self.real_ip:
                    # Tie-breaking rule RFC 5798: IP lebih tinggi menang
                    logger.warning(f"[{self.name}] Tie-breaker: Master with identical priority but higher IP detected ({adv.source_ip}). Stepping down.")
                    self.transition_to_backup()
                else:
                    logger.debug(f"[{self.name}] Superior Master ignoring lower advertisement from {adv.source_ip}")

    def trigger_wan_failure(self):
        """Simulasi WAN Interface Down: Trigger decrement priority"""
        with self._lock:
            if not self.wan_uplink_up:
                print(f"[{self.name}] WAN is already down.")
                return
            self.wan_uplink_up = False
            self.current_priority = max(1, self.current_priority - self.wan_track_decrement)
            logger.error(f"[{self.name}] CRITICAL: Uplink WAN DOWN! Object Track 1 triggered decrement -{self.wan_track_decrement}.")
            logger.info(f"[{self.name}] New Effective Priority: {self.current_priority}")
            
            # Jika kita master, umumkan priority baru segera
            if self.state == "MASTER":
                self._send_advertisement()

    def trigger_wan_recovery(self):
        """Simulasi WAN Interface Pulih: Restore priority"""
        with self._lock:
            if self.wan_uplink_up:
                print(f"[{self.name}] WAN is already UP.")
                return
            self.wan_uplink_up = True
            self.current_priority = self.base_priority
            logger.info(f"[{self.name}] OK: Uplink WAN RECOVERED! Priority restored to {self.current_priority}.")
            if self.state == "MASTER":
                self._send_advertisement()

    def _run_loop(self):
        last_adv_time = 0.0
        while self.running:
            time.sleep(0.05)
            now = time.time()

            with self._lock:
                if self.state == "MASTER":
                    if now - last_adv_time >= self.adv_interval:
                        self._send_advertisement()
                        last_adv_time = now

                elif self.state == "BACKUP":
                    # Evaluasi Master Down Timer
                    if now - self.last_heard_master_time > self.master_down_interval:
                        logger.error(f"[{self.name}] MASTER DOWN TIMER EXPIRED! No advertisement heard for {self.master_down_interval:.2f}s")
                        self.transition_to_master()
                        last_adv_time = now


class VirtualNetworkBus:
    """Simulasi segmen kabel LAN (Broadcast Domain) tempat frame VRRP dipertukarkan."""
    def __init__(self):
        self.nodes = []

    def register_node(self, node: VirtualRouter):
        self.nodes.append(node)
        node.attach_bus(self)

    def broadcast(self, adv: VRRPAdvertisement, sender: VirtualRouter):
        # Forward advertisement ke seluruh router lain di subnet
        for node in self.nodes:
            if node != sender:
                node.receive_advertisement(adv)


def print_cluster_status(routers):
    print("\n" + "="*70)
    print(f"{'ROUTER':<12} | {'STATE':<10} | {'PRIORITY':<10} | {'WAN UPLINK':<12} | {'VIP':<15}")
    print("-"*70)
    for r in routers:
        print(f"{r.name:<12} | {r.state:<10} | {r.current_priority:<10} | {'UP' if r.wan_uplink_up else 'DOWN':<12} | {r.virtual_ip:<15}")
    print("="*70 + "\n")


def main():
    print("=================================================================")
    print("     SIMULASI ENGINE PROTOKOL VRRPv3 & OBJECT TRACKING FAILOVER  ")
    print("=================================================================")
    
    # 1. Inisialisasi Bus Jaringan LAN
    lan_bus = VirtualNetworkBus()

    # 2. Definisikan dua Router di Subnet yang sama (192.168.10.0/24)
    # R1: Priority 110 (Akan menjadi Master awal)
    r1 = VirtualRouter(name="R1-Primary", real_ip="192.168.10.2", vrid=10, 
                       virtual_ip="192.168.10.1", base_priority=110, preempt=True)
    # R2: Priority 100 (Backup awal)
    r2 = VirtualRouter(name="R2-Backup", real_ip="192.168.10.3", vrid=10, 
                       virtual_ip="192.168.10.1", base_priority=100, preempt=True)

    lan_bus.register_node(r1)
    lan_bus.register_node(r2)

    # 3. Nyalakan engine VRRP pada kedua router
    r1.start()
    r2.start()

    # Beri waktu konvergensi awal
    time.sleep(2.0)
    print_cluster_status([r1, r2])

    menu = """
PILIHAN PERINTAH SIMULASI:
 [1] Putus WAN Uplink R1 (Trigger Tracking Decrement -30) -> Uji Failover ke R2
 [2] Pulihkan WAN Uplink R1 -> Uji Preemption Recovery (R1 kembali Master)
 [3] Matikan R1 Total (Simulasi Crash/Power Failure)
 [4] Nyalakan Kembali R1
 [s] Tampilkan Status Cluster
 [q] Keluar (Quit)
"""
    print(menu)

    try:
        while True:
            cmd = input("vrrp-sim> ").strip().lower()
            if cmd == '1':
                print("\n[ACTION] Mematikan link WAN Uplink pada R1...")
                r1.trigger_wan_failure()
                time.sleep(2.0)
                print_cluster_status([r1, r2])
            elif cmd == '2':
                print("\n[ACTION] Memulihkan link WAN Uplink pada R1...")
                r1.trigger_wan_recovery()
                time.sleep(2.0)
                print_cluster_status([r1, r2])
            elif cmd == '3':
                print("\n[ACTION] Mematikan Node R1 sepenuhnya (Power Outage)...")
                r1.stop()
                time.sleep(3.5)
                print_cluster_status([r1, r2])
            elif cmd == '4':
                print("\n[ACTION] Menyalakan kembali Node R1...")
                r1.start()
                time.sleep(3.5)
                print_cluster_status([r1, r2])
            elif cmd == 's':
                print_cluster_status([r1, r2])
            elif cmd == 'q':
                print("\nMenghentikan simulasi VRRP...")
                break
            else:
                print("Perintah tidak dikenal.")
                print(menu)
    except KeyboardInterrupt:
        print("\nInterupsi diterima, mematikan...")
    finally:
        r1.stop()
        r2.stop()
        print("Simulasi selesai.")

if __name__ == "__main__":
    main()

---