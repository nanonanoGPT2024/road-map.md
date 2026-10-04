#!/usr/bin/env python3
"""
Simulasi Pemilihan STP Root Bridge, Penentuan Port Roles, dan Konvergensi RSTP.
Standar Kurikulum: GEMINI-NETWORK-ENGINEER-V3
Kategori: Layer 2 Switching & Spanning Tree Protocol

Skrip ini mensimulasikan protokol kontrol terdistribusi STP (IEEE 802.1D/802.1w):
1. Inisialisasi node Switch dengan Bridge ID (Priority + MAC).
2. Pertukaran Bridge Protocol Data Units (BPDU).
3. Pemilihan Root Bridge berbasis BID terendah.
4. Perhitungan Root Path Cost menuju Root Bridge.
5. Penentuan Port Roles (Root Port, Designated Port, Alternate/Blocked Port).
6. Penanganan anomali penambahan Rogue Root Bridge (Rogue Attack) & Simulasi Root Guard.
"""

import copy
import sys
import time
from typing import Dict, List, Optional, Tuple


class BPDU:
    def __init__(self, root_bid: Tuple[int, str], root_path_cost: int, sender_bid: Tuple[int, str], port_id: int):
        self.root_bid = root_bid          # (Priority, MAC)
        self.root_path_cost = root_path_cost
        self.sender_bid = sender_bid      # (Priority, MAC)
        self.port_id = port_id

    def __lt__(self, other: 'BPDU') -> bool:
        """
        Operator pembanding untuk menentukan BPDU superior:
        1. Root Bridge ID terendah
        2. Root Path Cost terendah
        3. Sender Bridge ID terendah
        4. Port ID terendah
        """
        if self.root_bid != other.root_bid:
            return self.root_bid < other.root_bid
        if self.root_path_cost != other.root_path_cost:
            return self.root_path_cost < other.root_path_cost
        if self.sender_bid != other.sender_bid:
            return self.sender_bid < other.sender_bid
        return self.port_id < other.port_id

    def __repr__(self) -> str:
        return (f"BPDU(Root={self.root_bid[0]}.{self.root_bid[1]}, "
                f"Cost={self.root_path_cost}, "
                f"Sender={self.sender_bid[0]}.{self.sender_bid[1]})")


class Interface:
    def __init__(self, name: str, port_id: int, link_cost: int = 4):
        self.name = name
        self.port_id = port_id
        self.link_cost = link_cost
        self.connected_to: Optional['Interface'] = None
        self.role: str = "DESIGNATED"  # ROOT, DESIGNATED, ALTERNATE, ROOT_INCONSISTENT
        self.state: str = "DISCARDING"  # FORWARDING, DISCARDING
        self.root_guard_enabled: bool = False
        self.bpdu_guard_enabled: bool = False
        self.is_err_disabled: bool = False
        self.last_received_bpdu: Optional[BPDU] = None

    def connect(self, peer_interface: 'Interface'):
        self.connected_to = peer_interface
        peer_interface.connected_to = self


class Switch:
    def __init__(self, name: str, priority: int, mac: str):
        self.name = name
        self.priority = priority
        self.mac = mac
        self.bridge_id = (priority, mac)
        self.interfaces: Dict[str, Interface] = {}
        
        # State STP Internal
        self.root_bid = self.bridge_id
        self.root_path_cost = 0
        self.root_port: Optional[str] = None

    def add_interface(self, name: str, port_id: int, link_cost: int = 4) -> Interface:
        iface = Interface(name, port_id, link_cost)
        self.interfaces[name] = iface
        return iface

    def create_bpdu(self, port_name: str) -> BPDU:
        iface = self.interfaces[port_name]
        return BPDU(
            root_bid=self.root_bid,
            root_path_cost=self.root_path_cost,
            sender_bid=self.bridge_id,
            port_id=iface.port_id
        )

    def process_bpdus(self) -> bool:
        """
        Memproses BPDU masuk dari seluruh port aktif.
        Mengembalikan True jika terjadi perubahan status topologi (perlu iterasi konvergensi lanjut).
        """
        changed = False

        # Langkah 1: Evaluasi calon Root Bridge dari BPDU superior yang diterima
        best_root_bid = self.bridge_id
        best_cost = 0
        best_root_port: Optional[str] = None

        for iface_name, iface in self.interfaces.items():
            if iface.is_err_disabled or not iface.connected_to:
                continue

            bpdu = iface.last_received_bpdu
            if not bpdu:
                continue

            # Periksa Root Guard: Jika menerima BPDU superior pada port yang dilindungi
            if iface.root_guard_enabled:
                if bpdu.root_bid < self.bridge_id:
                    if iface.role != "ROOT_INCONSISTENT":
                        print(f"  [!] SECURITY ALERT on {self.name}:{iface.name}: "
                              f"Superior BPDU received with Root Guard enabled! Moving port to ROOT_INCONSISTENT.")
                        iface.role = "ROOT_INCONSISTENT"
                        iface.state = "DISCARDING"
                        changed = True
                    continue

            # Periksa BPDU Guard
            if iface.bpdu_guard_enabled:
                print(f"  [CRITICAL] SECURITY VIOLATION on {self.name}:{iface.name}: "
                      f"BPDU received on BPDU-Guard protected port! Disabling interface (err-disable).")
                iface.is_err_disabled = True
                iface.state = "DISCARDING"
                iface.role = "DISABLED"
                changed = True
                continue

            total_cost = bpdu.root_path_cost + iface.link_cost
            candidate_bpdu_eval = (bpdu.root_bid, total_cost, bpdu.sender_bid, bpdu.port_id)
            current_best_eval = (best_root_bid, best_cost, self.bridge_id, 0)

            if candidate_bpdu_eval < current_best_eval:
                best_root_bid = bpdu.root_bid
                best_cost = total_cost
                best_root_port = iface_name

        # Update identitas Root Bridge jika ditemukan yang lebih superior
        if best_root_bid != self.root_bid or best_cost != self.root_path_cost or best_root_port != self.root_port:
            self.root_bid = best_root_bid
            self.root_path_cost = best_cost
            self.root_port = best_root_port
            changed = True

        # Langkah 2: Tentukan Role Port (Root Port, Designated Port, Alternate Port)
        for iface_name, iface in self.interfaces.items():
            if iface.is_err_disabled or not iface.connected_to:
                continue
            if iface.role == "ROOT_INCONSISTENT":
                continue

            if iface_name == self.root_port:
                if iface.role != "ROOT":
                    iface.role = "ROOT"
                    iface.state = "FORWARDING"
                    changed = True
            else:
                # Evaluasi apakah port ini Designated atau Alternate
                my_bpdu = self.create_bpdu(iface_name)
                neighbor_bpdu = iface.last_received_bpdu

                if neighbor_bpdu is None or my_bpdu < neighbor_bpdu:
                    if iface.role != "DESIGNATED":
                        iface.role = "DESIGNATED"
                        iface.state = "FORWARDING"
                        changed = True
                else:
                    if iface.role != "ALTERNATE":
                        iface.role = "ALTERNATE"
                        iface.state = "DISCARDING"
                        changed = True

        return changed


class NetworkSimulator:
    def __init__(self):
        self.switches: Dict[str, Switch] = {}

    def add_switch(self, switch: Switch):
        self.switches[switch.name] = switch

    def run_convergence(self, max_iterations: int = 15):
        print("\n[*] Memulai Siklus Konvergensi STP Terdistribusi...")
        iteration = 1
        while iteration <= max_iterations:
            print(f"--- Iterasi Konvergensi #{iteration} ---")
            network_changed = False

            # Fase A: Transmisi BPDU melintasi seluruh link fisik yang terhubung
            for sw_name, sw in self.switches.items():
                for iface_name, iface in sw.interfaces.items():
                    if iface.connected_to and not iface.is_err_disabled:
                        # Buat dan kirimkan BPDU ke tetangga
                        bpdu_out = sw.create_bpdu(iface_name)
                        iface.connected_to.last_received_bpdu = bpdu_out

            # Fase B: Evaluasi lokal setiap switch terhadap BPDU yang masuk
            for sw_name, sw in self.switches.items():
                if sw.process_bpdus():
                    network_changed = True

            if not network_changed:
                print(f"[✓] Konvergensi Selesai dan Stabil pada Iterasi #{iteration}.\n")
                break
            iteration += 1

    def display_topology_state(self):
        print("=" * 85)
        print(f"{'Switch':<12} | {'Bridge ID':<22} | {'Port':<8} | {'Role':<14} | {'State':<12} | {'Cost'}")
        print("-" * 85)
        for sw_name, sw in sorted(self.switches.items()):
            bid_str = f"{sw.priority}.{sw.mac}"
            for iface_name, iface in sorted(sw.interfaces.items()):
                print(f"{sw.name:<12} | {bid_str:<22} | {iface.name:<8} | {iface.role:<14} | "
                      f"{iface.state:<12} | {iface.link_cost}")
        print("=" * 85)


def build_triangle_topology() -> NetworkSimulator:
    sim = NetworkSimulator()

    # Inisialisasi Switch
    sw1 = Switch("SW-CORE-01", priority=4096, mac="00:11:22:aa:bb:01")
    sw2 = Switch("SW-DIST-02", priority=8192, mac="00:11:22:aa:bb:02")
    sw3 = Switch("SW-ACC-03", priority=32768, mac="00:11:22:aa:bb:03")

    # Inisialisasi Port
    sw1_p1 = sw1.add_interface("Eth1/1", port_id=1, link_cost=4)
    sw1_p2 = sw1.add_interface("Eth1/2", port_id=2, link_cost=4)

    sw2_p1 = sw2.add_interface("Eth1/1", port_id=1, link_cost=4)
    sw2_p2 = sw2.add_interface("Eth1/2", port_id=2, link_cost=4)

    sw3_p1 = sw3.add_interface("Eth1/1", port_id=1, link_cost=4)
    sw3_p2 = sw3.add_interface("Eth1/2", port_id=2, link_cost=4)

    # Interkoneksi Fisik (Topologi Segitiga)
    # Link SW1 <-> SW2
    sw1_p1.connect(sw2_p1)
    # Link SW1 <-> SW3
    sw1_p2.connect(sw3_p1)
    # Link SW2 <-> SW3
    sw2_p2.connect(sw3_p2)

    sim.add_switch(sw1)
    sim.add_switch(sw2)
    sim.add_switch(sw3)

    return sim


def main():
    print("=======================================================================")
    print("  SIMULATOR ALGORITMA SPANNING TREE (IEEE 802.1D / 802.1w RSTP)       ")
    print("=======================================================================")

    # 1. Bangun Topologi Segitiga Standar
    sim = build_triangle_topology()
    sim.run_convergence()
    sim.display_topology_state()

    print("\n[ANALISIS HASIL]")
    print("1. SW-CORE-01 memiliki Priority 4096 (Terkecil) -> Terpilih sebagai ROOT BRIDGE.")
    print("2. Semua port di SW-CORE-01 berada pada status DESIGNATED - FORWARDING.")
    print("3. Port Eth1/2 pada SW-ACC-03 diblokir (ALTERNATE - DISCARDING) untuk memutus loop fisik.")

    # 2. Skenario Serangan: Pasang Rogue Switch dengan Priority 0
    print("\n" + "#" * 75)
    print("SKENARIO SIMULASI: Serangan Rogue Switch (Injeksi Superior BPDU)")
    print("#" * 75)

    sw_rogue = Switch("SW-ROGUE", priority=0, mac="de:ad:be:ef:00:01")
    rogue_port = sw_rogue.add_interface("Eth1/1", port_id=1, link_cost=4)

    # Colokkan Rogue Switch ke port edge SW-ACC-03
    acc_sw = sim.switches["SW-ACC-03"]
    edge_port = acc_sw.add_interface("Eth1/3", port_id=3, link_cost=4)
    
    # Tes A: Tanpa Proteksi BPDU Guard / Root Guard
    print("[+] Menyambungkan Rogue Switch tanpa mekanisme STP Protection...")
    rogue_port.connect(edge_port)
    sim.add_switch(sw_rogue)
    sim.run_convergence()
    sim.display_topology_state()
    print("[!] BAHAYA: SW-ROGUE merebut tahta Root Bridge karena Priority bernilai 0!")

    # Tes B: Terapkan Root Guard pada Port Edge
    print("\n" + "#" * 75)
    print("MITIGASI: Mengaktifkan STP Root Guard pada port edge ACCESS SWITCH")
    print("#" * 75)
    print("[+] Mengaktifkan: spanning-tree guard root pada SW-ACC-03:Eth1/3")
    edge_port.root_guard_enabled = True
    
    # Reset identitas root pada switch asli untuk menguji re-election
    for sw in sim.switches.values():
        sw.root_bid = sw.bridge_id
        sw.root_path_cost = 0
        sw.root_port = None
        for iface in sw.interfaces.values():
            iface.last_received_bpdu = None
            iface.role = "DESIGNATED"

    sim.run_convergence()
    sim.display_topology_state()
    print("[✓] SUKSES: Rogue BPDU dinetralkan! SW-ACC-03:Eth1/3 masuk status ROOT_INCONSISTENT (DISCARDING).")
    print("[✓] SW-CORE-01 kembali menjadi Root Bridge resmi yang sah.")


if __name__ == "__main__":
    main()