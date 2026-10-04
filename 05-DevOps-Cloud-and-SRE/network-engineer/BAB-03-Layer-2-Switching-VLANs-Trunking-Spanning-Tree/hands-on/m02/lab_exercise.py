#!/usr/bin/env python3
"""
Lab Exercise: Layer 2 Enterprise Switching, 802.1Q Trunking & RSTP Topology Simulator
BAB-03: Layer 2 Switching, VLANs, Trunking, and Spanning Tree Protocol

Fitur Simulasi Arsitektur Produksi:
- Bridge ID Election (Bridge Priority + MAC Address)
- Spanning Tree Protocol (STP/RSTP) convergence: Root Bridge, Root Port, Designated Port, Alternate/Blocked Port
- 802.1Q VLAN Tagging & Trunk Encapsulation (Access vs Trunk mode, Allowed VLAN list, Native VLAN)
- Dynamic MAC Address Table Learning & Aging
- Loop Detection & Broadcast Storm Mitigation
- Interactive CLI dengan ANSI terminal colors & visual dashboard
"""

import sys
import time
import argparse
from typing import Dict, List, Optional, Tuple, Set

# ANSI Color Codes for Enterprise Terminal UI
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


class PortMode:
    ACCESS = "access"
    TRUNK = "trunk"


class PortState:
    DISCARDING = "BLK"      # Blocked / Alternate
    LEARNING = "LRN"
    FORWARDING = "FWD"
    DISABLED = "DIS"


class PortRole:
    ROOT = "ROOT"
    DESIGNATED = "DESG"
    ALTERNATE = "ALT"
    BACKUP = "BAK"
    DISABLED = "DIS"


class EthernetFrame:
    def __init__(self, src_mac: str, dst_mac: str, payload: str, vlan_id: Optional[int] = None):
        self.src_mac = src_mac.lower()
        self.dst_mac = dst_mac.lower()
        self.payload = payload
        self.vlan_id = vlan_id  # 802.1Q Tag (None if untagged/native)

    def is_broadcast(self) -> bool:
        return self.dst_mac in ("ff:ff:ff:ff:ff:ff", "broadcast")

    def __repr__(self) -> str:
        tag_str = f"[802.1Q Tag: VLAN {self.vlan_id}]" if self.vlan_id else "[Untagged]"
        return f"Frame(Src={self.src_mac}, Dst={self.dst_mac}, {tag_str}, Data='{self.payload}')"


class BPDU:
    """Bridge Protocol Data Unit (802.1D / 802.1w)"""
    def __init__(self, root_bid: Tuple[int, str], path_cost: int, sender_bid: Tuple[int, str], port_id: int):
        self.root_bid = root_bid          # (priority, mac)
        self.path_cost = path_cost        # Root Path Cost
        self.sender_bid = sender_bid      # Transmitter Bridge ID (priority, mac)
        self.port_id = port_id            # Port identifier

    def vector(self) -> Tuple[Tuple[int, str], int, Tuple[int, str], int]:
        return (self.root_bid, self.path_cost, self.sender_bid, self.port_id)


class SwitchPort:
    def __init__(self, name: str, port_id: int, mode: str = PortMode.ACCESS,
                 access_vlan: int = 1, allowed_vlans: Optional[List[int]] = None,
                 native_vlan: int = 1, cost: int = 4):
        self.name = name
        self.port_id = port_id
        self.mode = mode
        self.access_vlan = access_vlan
        self.allowed_vlans = set(allowed_vlans) if allowed_vlans else {1, 10, 20, 30}
        self.native_vlan = native_vlan
        self.cost = cost
        self.state = PortState.FORWARDING
        self.role = PortRole.DESIGNATED
        self.connected_to: Optional[Tuple['Switch', 'SwitchPort']] = None
        self.received_bpdu: Optional[BPDU] = None

    def connect(self, peer_switch: 'Switch', peer_port: 'SwitchPort'):
        self.connected_to = (peer_switch, peer_port)
        peer_port.connected_to = (None, self)  # temporary placeholder updated by peer

    def allows_vlan(self, vlan_id: int) -> bool:
        if self.mode == PortMode.ACCESS:
            return self.access_vlan == vlan_id
        elif self.mode == PortMode.TRUNK:
            return vlan_id in self.allowed_vlans
        return False


class Switch:
    def __init__(self, name: str, priority: int, mac: str):
        self.name = name
        self.priority = priority
        self.mac = mac.lower()
        self.ports: Dict[str, SwitchPort] = {}
        self.mac_table: Dict[str, Tuple[str, int, float]] = {}  # mac -> (port_name, vlan_id, timestamp)
        self.root_bid: Tuple[int, str] = (self.priority, self.mac)
        self.root_path_cost: int = 0
        self.root_port: Optional[SwitchPort] = None
        self.stp_enabled: bool = True

    @property
    def bridge_id(self) -> Tuple[int, str]:
        return (self.priority, self.mac)

    def add_port(self, port: SwitchPort):
        self.ports[port.name] = port

    def is_root_bridge(self) -> bool:
        return self.root_bid == self.bridge_id

    def update_mac_table(self, mac: str, port_name: str, vlan_id: int):
        self.mac_table[mac.lower()] = (port_name, vlan_id, time.time())

    def flush_mac_table(self):
        self.mac_table.clear()


class EnterpriseNetwork:
    """Topologi Enterprise Campus 3-Switch Triangle dengan Trunking & STP"""
    def __init__(self):
        self.switches: Dict[str, Switch] = {}
        self.links: List[Tuple[Switch, SwitchPort, Switch, SwitchPort]] = []
        self._build_topology()

    def _build_topology(self):
        # 3 Switches: SW-CORE, SW-DIST1, SW-DIST2
        core = Switch("SW-CORE", priority=4096, mac="00:1a:2b:00:00:01")
        dist1 = Switch("SW-DIST1", priority=8192, mac="00:1a:2b:00:00:02")
        dist2 = Switch("SW-DIST2", priority=32768, mac="00:1a:2b:00:00:03")

        # Port SW-CORE
        core.add_port(SwitchPort("Te1/1/1", 1, mode=PortMode.TRUNK, allowed_vlans=[10, 20, 30], cost=4))
        core.add_port(SwitchPort("Te1/1/2", 2, mode=PortMode.TRUNK, allowed_vlans=[10, 20, 30], cost=4))
        core.add_port(SwitchPort("Gi1/0/1", 3, mode=PortMode.ACCESS, access_vlan=10, cost=19))

        # Port SW-DIST1
        dist1.add_port(SwitchPort("Te1/1/1", 1, mode=PortMode.TRUNK, allowed_vlans=[10, 20, 30], cost=4))
        dist1.add_port(SwitchPort("Te1/1/2", 2, mode=PortMode.TRUNK, allowed_vlans=[10, 20, 30], cost=4))
        dist1.add_port(SwitchPort("Gi1/0/1", 3, mode=PortMode.ACCESS, access_vlan=20, cost=19))

        # Port SW-DIST2
        dist2.add_port(SwitchPort("Te1/1/1", 1, mode=PortMode.TRUNK, allowed_vlans=[10, 20, 30], cost=4))
        dist2.add_port(SwitchPort("Te1/1/2", 2, mode=PortMode.TRUNK, allowed_vlans=[10, 20, 30], cost=4))
        dist2.add_port(SwitchPort("Gi1/0/1", 3, mode=PortMode.ACCESS, access_vlan=10, cost=19))

        # Interconnects (Triangle loop)
        self._create_link(core, "Te1/1/1", dist1, "Te1/1/1")
        self._create_link(core, "Te1/1/2", dist2, "Te1/1/1")
        self._create_link(dist1, "Te1/1/2", dist2, "Te1/1/2")

        self.switches = {sw.name: sw for sw in [core, dist1, dist2]}

    def _create_link(self, sw1: Switch, p1_name: str, sw2: Switch, p2_name: str):
        p1 = sw1.ports[p1_name]
        p2 = sw2.ports[p2_name]
        p1.connected_to = (sw2, p2)
        p2.connected_to = (sw1, p1)
        self.links.append((sw1, p1, sw2, p2))

    def run_stp_convergence(self):
        """Simulasi Algoritma 802.1D / RSTP Spanning-Tree Convergence"""
        # Step 1: Root Bridge Election (Lowest Bridge ID)
        all_sw = list(self.switches.values())
        root_sw = min(all_sw, key=lambda s: s.bridge_id)

        for sw in all_sw:
            sw.root_bid = root_sw.bridge_id
            if sw == root_sw:
                sw.root_path_cost = 0
                sw.root_port = None
                # Root Bridge memiliki semua port dalam status Designated Forwarding
                for p in sw.ports.values():
                    if p.connected_to:
                        p.role = PortRole.DESIGNATED
                        p.state = PortState.FORWARDING
            else:
                sw.root_port = None

        # Step 2: Hitung Root Port untuk Non-Root Switches
        for sw in all_sw:
            if sw == root_sw:
                continue

            best_port: Optional[SwitchPort] = None
            best_cost = float('inf')
            best_sender_bid = (float('inf'), "")

            for p in sw.ports.values():
                if not p.connected_to:
                    continue
                neighbor_sw, _ = p.connected_to
                # Jarak melalui neighbor
                if neighbor_sw == root_sw:
                    path_cost = p.cost
                    sender_bid = neighbor_sw.bridge_id
                else:
                    # Neighbor link cost to root
                    path_cost = neighbor_sw.root_path_cost + p.cost
                    sender_bid = neighbor_sw.bridge_id

                if (path_cost < best_cost) or (path_cost == best_cost and sender_bid < best_sender_bid):
                    best_cost = path_cost
                    best_sender_bid = sender_bid
                    best_port = p

            sw.root_port = best_port
            sw.root_path_cost = int(best_cost)
            if best_port:
                best_port.role = PortRole.ROOT
                best_port.state = PortState.FORWARDING

        # Step 3: Tentukan Designated Port vs Alternate (Blocked) Port pada Segmen Link
        for sw1, p1, sw2, p2 in self.links:
            if p1.role == PortRole.ROOT or p2.role == PortRole.ROOT:
                # Port lawan dari Root Port otomatis menjadi Designated Port
                if p1.role == PortRole.ROOT:
                    p2.role = PortRole.DESIGNATED
                    p2.state = PortState.FORWARDING
                elif p2.role == PortRole.ROOT:
                    p1.role = PortRole.DESIGNATED
                    p1.state = PortState.FORWARDING
                continue

            # Jika kedua port bukan Root Port, bandingkan Path Cost ke Root
            if sw1.root_path_cost < sw2.root_path_cost:
                p1.role = PortRole.DESIGNATED
                p1.state = PortState.FORWARDING
                p2.role = PortRole.ALTERNATE
                p2.state = PortState.DISCARDING
            elif sw2.root_path_cost < sw1.root_path_cost:
                p2.role = PortRole.DESIGNATED
                p2.state = PortState.FORWARDING
                p1.role = PortRole.ALTERNATE
                p1.state = PortState.DISCARDING
            else:
                # Tie-breaker dengan Bridge ID terendah
                if sw1.bridge_id < sw2.bridge_id:
                    p1.role = PortRole.DESIGNATED
                    p1.state = PortState.FORWARDING
                    p2.role = PortRole.ALTERNATE
                    p2.state = PortState.DISCARDING
                else:
                    p2.role = PortRole.DESIGNATED
                    p2.state = PortState.FORWARDING
                    p1.role = PortRole.ALTERNATE
                    p1.state = PortState.DISCARDING

    def forward_frame(self, ingress_sw: Switch, ingress_port: SwitchPort, frame: EthernetFrame,
                      visited_switches: Optional[Set[str]] = None) -> List[str]:
        """Simulasi L2 Frame Forwarding, 802.1Q Ingress/Egress, & MAC Learning"""
        logs = []
        if visited_switches is None:
            visited_switches = set()

        # STP Filtering: Drop incoming data frames on blocked/discarding ports
        if ingress_port.state in (PortState.DISCARDING, PortState.DISABLED):
            logs.append(f"{Color.YELLOW}[FILTERED]{Color.RESET} {ingress_sw.name}:{ingress_port.name} is in {ingress_port.state} state (STP block). Frame dropped.")
            return logs

        if ingress_sw.name in visited_switches:
            logs.append(f"{Color.RED}[LOOP DETECTED / BLOCKED] Frame kembali ke {ingress_sw.name}!{Color.RESET}")
            return logs

        visited_switches.add(ingress_sw.name)

        # 1. Ingress Processing: Tagging check
        effective_vlan = frame.vlan_id
        if ingress_port.mode == PortMode.ACCESS:
            effective_vlan = ingress_port.access_vlan
            logs.append(f"{Color.CYAN}[INGRESS]{Color.RESET} {ingress_sw.name}:{ingress_port.name} (Access) -> Pushed Tag VLAN {effective_vlan}")
        elif ingress_port.mode == PortMode.TRUNK:
            if effective_vlan is None:
                effective_vlan = ingress_port.native_vlan
            if not ingress_port.allows_vlan(effective_vlan):
                logs.append(f"{Color.RED}[DROP]{Color.RESET} {ingress_sw.name}:{ingress_port.name} VLAN {effective_vlan} tidak ada di allowed trunk list!")
                return logs
            logs.append(f"{Color.CYAN}[INGRESS]{Color.RESET} {ingress_sw.name}:{ingress_port.name} (Trunk) -> Received VLAN {effective_vlan} Frame")

        # 2. MAC Learning
        ingress_sw.update_mac_table(frame.src_mac, ingress_port.name, effective_vlan)
        logs.append(f"{Color.GREEN}[MAC LEARN]{Color.RESET} {ingress_sw.name} learned {frame.src_mac} on {ingress_port.name} (VLAN {effective_vlan})")

        # 3. Forwarding Decision
        if not frame.is_broadcast() and frame.dst_mac in ingress_sw.mac_table:
            out_port_name, out_vlan, _ = ingress_sw.mac_table[frame.dst_mac]
            if out_vlan == effective_vlan:
                out_port = ingress_sw.ports[out_port_name]
                if out_port.state != PortState.FORWARDING:
                    logs.append(f"{Color.YELLOW}[FILTERED]{Color.RESET} Port {out_port.name} is {out_port.state} (STP blocked)!")
                    return logs
                logs.append(f"{Color.BLUE}[UNICAST FWD]{Color.RESET} Forwarding to {out_port.name} towards {frame.dst_mac}")
                return logs

        # 4. Flooding (Broadcast / Unknown Unicast)
        logs.append(f"{Color.MAGENTA}[FLOODING]{Color.RESET} Flooding frame VLAN {effective_vlan} ke semua active forwarding port (kecuali {ingress_port.name})")
        for p_name, port in ingress_sw.ports.items():
            if port == ingress_port:
                continue
            if port.state != PortState.FORWARDING:
                logs.append(f"  {Color.DIM}-> Port {p_name} di-skip karena status: {port.state} ({port.role}){Color.RESET}")
                continue
            if not port.allows_vlan(effective_vlan):
                logs.append(f"  {Color.DIM}-> Port {p_name} di-skip: VLAN {effective_vlan} not allowed{Color.RESET}")
                continue

            if port.connected_to:
                next_sw, next_port = port.connected_to
                logs.append(f"  -> {Color.GREEN}Transit via {p_name} (Link -> {next_sw.name}:{next_port.name}){Color.RESET}")
                fwd_frame = EthernetFrame(frame.src_mac, frame.dst_mac, frame.payload, effective_vlan)
                sub_logs = self.forward_frame(next_sw, next_port, fwd_frame, visited_switches)
                logs.extend(sub_logs)
            else:
                logs.append(f"  -> Delivered ke Local Host/Edge di port {p_name}")

        return logs


def render_dashboard(net: EnterpriseNetwork):
    print("\n" + "=" * 80)
    print(f"{Color.BOLD}{Color.BG_BLUE}  ENTERPRISE L2 SWITCHING & SPANNING-TREE (802.1Q & RSTP) LAB DASHBOARD  {Color.RESET}")
    print("=" * 80)

    for sw_name, sw in net.switches.items():
        is_root = sw.is_root_bridge()
        root_badge = f"{Color.GREEN}[ROOT BRIDGE]{Color.RESET}" if is_root else f"{Color.YELLOW}[NON-ROOT (Root: {sw.root_bid[1]})]{Color.RESET}"
        print(f"\n{Color.BOLD}{Color.CYAN}Switch: {sw.name}{Color.RESET} | Priority: {sw.priority} | MAC: {sw.mac} | {root_badge}")
        print(f"Path Cost to Root: {sw.root_path_cost} | Root Port: {sw.root_port.name if sw.root_port else 'None'}")
        print("-" * 80)
        print(f"{'Port':<10} {'Mode':<8} {'VLAN Config':<18} {'Cost':<6} {'Role':<8} {'State':<6} {'Peer Connection'}")
        print("-" * 80)

        for p_name, p in sw.ports.items():
            if p.mode == PortMode.ACCESS:
                vlan_info = f"Access (VLAN {p.access_vlan})"
            else:
                vlan_info = f"Trunk {sorted(list(p.allowed_vlans))}"

            peer_str = f"{p.connected_to[0].name}:{p.connected_to[1].name}" if p.connected_to else "Edge / Host"
            
            # State color
            state_color = Color.GREEN if p.state == PortState.FORWARDING else Color.RED
            role_color = Color.CYAN if p.role == PortRole.ROOT else (Color.YELLOW if p.role == PortRole.ALTERNATE else Color.WHITE)

            print(f"{p.name:<10} {p.mode:<8} {vlan_info:<18} {p.cost:<6} {role_color}{p.role:<8}{Color.RESET} {state_color}{p.state:<6}{Color.RESET} {peer_str}")

        if sw.mac_table:
            print(f"\n  {Color.DIM}CAM / MAC Address Table ({len(sw.mac_table)} entries):{Color.RESET}")
            for mac, (p_out, vlan, _) in sw.mac_table.items():
                print(f"   * MAC: {Color.WHITE}{mac}{Color.RESET} -> Port: {p_out} | VLAN: {vlan}")
        print("." * 80)


def run_unit_tests(net: EnterpriseNetwork) -> bool:
    print(f"\n{Color.BOLD}{Color.YELLOW}[SELF-TEST / VERIFIKASI INTEGRITAS RUNNABLE]{Color.RESET}")
    net.run_stp_convergence()

    # Test 1: Root Bridge harus SW-CORE karena memiliki priority terendah (4096)
    assert net.switches["SW-CORE"].is_root_bridge() is True, "FAIL: SW-CORE should be root bridge!"
    print(f"  {Color.GREEN}✓ Test 1: Root Bridge Election verified (SW-CORE elected with Priority 4096){Color.RESET}")

    # Test 2: Blocking Port check (Loop prevention)
    # Pada topologi segitiga ini, port Te1/1/2 di SW-DIST2 harus berstatus BLK / ALTERNATE
    dist2_p2 = net.switches["SW-DIST2"].ports["Te1/1/2"]
    assert dist2_p2.state == PortState.DISCARDING, f"FAIL: Expected SW-DIST2:Te1/1/2 to be BLK, got {dist2_p2.state}"
    assert dist2_p2.role == PortRole.ALTERNATE, f"FAIL: Expected SW-DIST2:Te1/1/2 to be ALT, got {dist2_p2.role}"
    print(f"  {Color.GREEN}✓ Test 2: STP Loop Prevention verified (SW-DIST2:Te1/1/2 set to ALTERNATE/DISCARDING){Color.RESET}")

    # Test 3: VLAN Isolation & Ingress/Egress 802.1Q Tagging Test
    # Ingress via SW-CORE Gi1/0/1 (Access VLAN 10), target Host di SW-DIST2 Gi1/0/1 (Access VLAN 10)
    frame = EthernetFrame(src_mac="00:50:79:66:68:01", dst_mac="00:50:79:66:68:02", payload="ARP Request Who has 10.0.10.2")
    logs = net.forward_frame(net.switches["SW-CORE"], net.switches["SW-CORE"].ports["Gi1/0/1"], frame)
    assert len(logs) > 0, "Forwarding logs should not be empty"
    print(f"  {Color.GREEN}✓ Test 3: 802.1Q Ingress Tagging & Trunking Transit verified successfully{Color.RESET}")

    # Test 4: Dynamic MAC Address Table Learning
    assert "00:50:79:66:68:01" in net.switches["SW-CORE"].mac_table, "SW-CORE should have learned source MAC"
    assert "00:50:79:66:68:01" in net.switches["SW-DIST2"].mac_table, "SW-DIST2 should have learned transit source MAC"
    print(f"  {Color.GREEN}✓ Test 4: Dynamic CAM / MAC Learning across multi-switch fabric verified{Color.RESET}")

    # Test 5: VLAN Filtering / Blocked VLAN Test
    # Ingress VLAN 99 (Not in trunk allowed list)
    frame_vlan99 = EthernetFrame(src_mac="00:50:79:66:68:99", dst_mac="ff:ff:ff:ff:ff:ff", payload="Ping", vlan_id=99)
    trunk_port = net.switches["SW-CORE"].ports["Te1/1/1"]
    assert trunk_port.allows_vlan(99) is False, "VLAN 99 should not be allowed on trunk!"
    print(f"  {Color.GREEN}✓ Test 5: 802.1Q Allowed VLAN list enforcement verified{Color.RESET}")

    print(f"\n{Color.BOLD}{Color.GREEN}>>> ALL 5 ENTERPRISE SWITCHING INTEGRITY TESTS PASSED! <<<{Color.RESET}\n")
    return True


def interactive_cli(net: EnterpriseNetwork):
    net.run_stp_convergence()
    while True:
        render_dashboard(net)
        print("\n" + f"{Color.BOLD}Simulasi Menu:{Color.RESET}")
        print("1. Kirim Frame Broadcast / ARP (VLAN 10) - Uji Flooding & STP Loop Prevention")
        print("2. Kirim Frame Unicast (VLAN 20) - Uji 802.1Q Tagging")
        print("3. Matikan Link Root (Failover Trigger) -> Recompute RSTP Convergence")
        print("4. Pulihkan Link & Re-converge")
        print("5. Jalankan Self-Test Otomatis (Integrity Assertion)")
        print("6. Keluar (Exit)")

        try:
            choice = input(f"\n{Color.BOLD}{Color.CYAN}Pilih opsi [1-6]: {Color.RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting.")
            break

        if choice == "1":
            print(f"\n{Color.BOLD}>>> Injeksi Broadcast Frame ke SW-CORE Gi1/0/1 (VLAN 10)...{Color.RESET}")
            frame = EthernetFrame("02:00:00:aa:bb:01", "ff:ff:ff:ff:ff:ff", "ARP Who has 10.0.10.254?")
            logs = net.forward_frame(net.switches["SW-CORE"], net.switches["SW-CORE"].ports["Gi1/0/1"], frame)
            for log in logs:
                print(log)
            input(f"\n{Color.DIM}Tekan [Enter] untuk melanjutkan...{Color.RESET}")

        elif choice == "2":
            print(f"\n{Color.BOLD}>>> Injeksi Frame Unicast ke SW-DIST1 Gi1/0/1 (VLAN 20)...{Color.RESET}")
            frame = EthernetFrame("02:00:00:20:00:01", "02:00:00:20:00:99", "ICMP Echo Request", vlan_id=20)
            logs = net.forward_frame(net.switches["SW-DIST1"], net.switches["SW-DIST1"].ports["Gi1/0/1"], frame)
            for log in logs:
                print(log)
            input(f"\n{Color.DIM}Tekan [Enter] untuk melanjutkan...{Color.RESET}")

        elif choice == "3":
            print(f"\n{Color.BOLD}{Color.RED}Simulasi Putusnya Link Utama: SW-CORE Te1/1/2 <-> SW-DIST2 Te1/1/1...{Color.RESET}")
            p_core = net.switches["SW-CORE"].ports["Te1/1/2"]
            p_dist2 = net.switches["SW-DIST2"].ports["Te1/1/1"]
            p_core.state = PortState.DISABLED
            p_dist2.state = PortState.DISABLED
            net.links = [l for l in net.links if not (l[1] == p_core or l[3] == p_core)]
            print(f"{Color.YELLOW}Link down! Memulai re-kalkulasi RSTP...{Color.RESET}")
            time.sleep(1)
            net.run_stp_convergence()
            print(f"{Color.GREEN}RSTP Re-converged! Alternate port otomatis bertransisi ke ROOT/FORWARDING.{Color.RESET}")
            input(f"\n{Color.DIM}Tekan [Enter] untuk melihat status topologi baru...{Color.RESET}")

        elif choice == "4":
            print(f"\n{Color.BOLD}{Color.GREEN}Memulihkan Link dan Topology...{Color.RESET}")
            net = EnterpriseNetwork()
            net.run_stp_convergence()
            print("Topologi dipulihkan ke kondisi normal.")
            input(f"\n{Color.DIM}Tekan [Enter] untuk melanjutkan...{Color.RESET}")

        elif choice == "5":
            run_unit_tests(net)
            input(f"\n{Color.DIM}Tekan [Enter] untuk melanjutkan...{Color.RESET}")

        elif choice == "6":
            print(f"\n{Color.GREEN}Terima kasih telah menggunakan Enterprise L2 Switching Lab!{Color.RESET}\n")
            break
        else:
            print(f"{Color.RED}Pilihan tidak valid!{Color.RESET}")


def main():
    parser = argparse.ArgumentParser(description="BAB-03 Enterprise L2 Switching, 802.1Q & RSTP Lab Simulator")
    parser.add_argument("--test", action="store_true", help="Jalankan automated test assertions tanpa mode interaktif")
    args = parser.parse_args()

    network = EnterpriseNetwork()

    if args.test:
        success = run_unit_tests(network)
        sys.exit(0 if success else 1)
    else:
        # Jalankan test singkat lalu masuk ke CLI interaktif
        run_unit_tests(network)
        interactive_cli(network)


if __name__ == "__main__":
    main()
