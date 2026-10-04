#!/usr/bin/env python3
"""
ASP.NET Core Simulation: Asynchronous Messaging & Real-Time Communication (SignalR & Channels)
BAB-07: Asynchronous-Messaging-Real-Time-Communication

Simulasi teknis independen arsitektur:
1. SignalR Hub Lifecycle (OnConnectedAsync, OnDisconnectedAsync, Groups.AddToGroupAsync)
2. HubContext & Clients Dispatcher (Clients.All, Clients.Group, Clients.Caller)
3. In-Process Async Queue via System.Threading.Channels.Channel<T> (Bounded Channel)
4. IHostedService / BackgroundService Worker Consumer Pattern
"""

import sys
import time
import uuid
import queue
import threading
from typing import Dict, Set, List, Optional

# ANSI Color Codes for terminal formatting
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
WHITE = "\033[37m"
BG_BLUE = "\033[44m"
BG_DARK = "\033[40m"


def timestamp() -> str:
    return time.strftime("%H:%M:%S")


def log_hub(prefix: str, msg: str, color: str = CYAN) -> None:
    print(f"{DIM}[{timestamp()}]{RESET} {BOLD}{color}[{prefix}]{RESET} {msg}")


class SignalRConnection:
    """Represents a HubConnectionContext in ASP.NET Core SignalR."""
    def __init__(self, connection_id: str, user_name: str):
        self.connection_id = connection_id
        self.user_name = user_name
        self.groups: Set[str] = set()
        self.connected_at = time.time()

    def __repr__(self) -> str:
        return f"Client({self.user_name} | ID:{self.connection_id[:8]}..)"


class HubClients:
    """Simulates IHubCallerClients interface."""
    def __init__(self, hub: "NotificationHub", caller_id: str):
        self._hub = hub
        self._caller_id = caller_id

    def all(self, method: str, *args):
        payload = f"{method}({', '.join(str(a) for a in args)})"
        for conn_id, conn in self._hub.connections.items():
            print(f"  {GREEN}➔ [WS Push -> {conn.user_name}]:{RESET} {payload}")

    def caller(self, method: str, *args):
        conn = self._hub.connections.get(self._caller_id)
        if conn:
            payload = f"{method}({', '.join(str(a) for a in args)})"
            print(f"  {YELLOW}➔ [WS Push -> Caller ({conn.user_name})]:{RESET} {payload}")

    def group(self, group_name: str, method: str, *args):
        payload = f"{method}({', '.join(str(a) for a in args)})"
        target_ids = self._hub.groups.get(group_name, set())
        if not target_ids:
            print(f"  {DIM}(Group '{group_name}' is empty or does not exist){RESET}")
            return
        for conn_id in target_ids:
            conn = self._hub.connections.get(conn_id)
            if conn:
                print(f"  {MAGENTA}➔ [WS Push -> {conn.user_name} @ Group '{group_name}']:{RESET} {payload}")


class NotificationHub:
    """
    Simulates Microsoft.AspNetCore.SignalR.Hub
    Handles real-time WebSocket client sessions and group routing.
    """
    def __init__(self):
        self.connections: Dict[str, SignalRConnection] = {}
        self.groups: Dict[str, Set[str]] = {}
        self._lock = threading.Lock()

    def on_connected(self, user_name: str) -> SignalRConnection:
        with self._lock:
            conn_id = str(uuid.uuid4())
            conn = SignalRConnection(conn_id, user_name)
            self.connections[conn_id] = conn
            log_hub("SignalR:Hub", f"Client Connected: {GREEN}{conn.user_name}{RESET} (ID: {conn.connection_id})", GREEN)
            clients = HubClients(self, conn_id)
            clients.all("UserConnected", conn.user_name, conn_id[:8])
            return conn

    def on_disconnected(self, conn_id: str) -> Optional[SignalRConnection]:
        with self._lock:
            conn = self.connections.pop(conn_id, None)
            if conn:
                for grp in list(conn.groups):
                    self.groups[grp].discard(conn_id)
                    if not self.groups[grp]:
                        del self.groups[grp]
                log_hub("SignalR:Hub", f"Client Disconnected: {RED}{conn.user_name}{RESET}", RED)
                clients = HubClients(self, conn_id)
                clients.all("UserDisconnected", conn.user_name)
            return conn

    def add_to_group(self, conn_id: str, group_name: str):
        with self._lock:
            conn = self.connections.get(conn_id)
            if not conn:
                return
            if group_name not in self.groups:
                self.groups[group_name] = set()
            self.groups[group_name].add(conn_id)
            conn.groups.add(group_name)
            log_hub("SignalR:GroupManager", f"Added {YELLOW}{conn.user_name}{RESET} to group '{MAGENTA}{group_name}{RESET}'", MAGENTA)
            clients = HubClients(self, conn_id)
            clients.group(group_name, "SystemAlert", f"Welcome {conn.user_name} to {group_name}")

    def send_broadcast(self, caller_id: str, message: str):
        with self._lock:
            conn = self.connections.get(caller_id)
            sender_name = conn.user_name if conn else "Anonymous"
            log_hub("SignalR:Broadcast", f"Message from {sender_name}: '{message}'", CYAN)
            clients = HubClients(self, caller_id)
            clients.all("ReceiveBroadcast", sender_name, message)

    def send_to_group(self, caller_id: str, group_name: str, message: str):
        with self._lock:
            conn = self.connections.get(caller_id)
            sender_name = conn.user_name if conn else "Anonymous"
            log_hub("SignalR:GroupMsg", f"[{group_name}] {sender_name}: '{message}'", MAGENTA)
            clients = HubClients(self, caller_id)
            clients.group(group_name, "ReceiveGroupMessage", group_name, sender_name, message)


class BoundedChannel:
    """
    Simulates System.Threading.Channels.Channel<T> in ASP.NET Core
    Provides thread-safe async bounded messaging queue for background processing.
    """
    def __init__(self, capacity: int = 10):
        self.capacity = capacity
        self.queue: queue.Queue = queue.Queue(maxsize=capacity)

    def write(self, item: dict) -> bool:
        try:
            self.queue.put_nowait(item)
            return True
        except queue.Full:
            return False

    def read(self, timeout: float = 0.5) -> Optional[dict]:
        try:
            return self.queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def task_done(self):
        self.queue.task_done()


class BackgroundOrderProcessor(threading.Thread):
    """
    Simulates BackgroundService / IHostedService in ASP.NET Core
    Consumes messages from BoundedChannel<T> and dispatches notifications via IHubContext<NotificationHub>.
    """
    def __init__(self, channel: BoundedChannel, hub: NotificationHub):
        super().__init__(daemon=True, name="OrderProcessorWorker")
        self.channel = channel
        self.hub = hub
        self._running = True

    def stop(self):
        self._running = False

    def run(self):
        log_hub("IHostedService", "BackgroundService is starting and listening to Channel<OrderEvent>...", BLUE)
        while self._running:
            item = self.channel.read(timeout=0.3)
            if item:
                order_id = item.get("order_id")
                customer = item.get("customer")
                amount = item.get("amount")
                log_hub("BackgroundService", f"Processing Order #{order_id} for {customer} (${amount})", BLUE)
                time.sleep(0.4)  # Simulate async I/O or DB commit
                
                # Push real-time event to SignalR hub group 'OrderNotifications'
                with self.hub._lock:
                    log_hub("IHubContext", f"Broadcast OrderCompleted event for #{order_id}", GREEN)
                    clients = HubClients(self.hub, caller_id="")
                    clients.group("Orders", "OrderCompleted", order_id, customer, f"Processed ${amount}")
                    clients.all("LiveFeedUpdate", f"Order #{order_id} fulfilled")
                self.channel.task_done()


def print_banner():
    banner = f"""{BOLD}{CYAN}
======================================================================
  ASP.NET Core - Real-Time Communication & Messaging Simulator
  [BAB-07: SignalR Hubs + Channel<T> + BackgroundService Worker]
======================================================================{RESET}"""
    print(banner)


def show_menu():
    print(f"\n{BOLD}{WHITE}--- INTERACTIVE CONTROL PANEL ---{RESET}")
    print(f"{CYAN}1.{RESET} Connect New Client (Simulate WebSocket Connection)")
    print(f"{CYAN}2.{RESET} Disconnect Client (Simulate OnDisconnectedAsync)")
    print(f"{CYAN}3.{RESET} Join Room / Group (Groups.AddToGroupAsync)")
    print(f"{CYAN}4.{RESET} Send Broadcast Message (Clients.All.SendAsync)")
    print(f"{CYAN}5.{RESET} Send Group Message (Clients.Group.SendAsync)")
    print(f"{CYAN}6.{RESET} Publish Order to Channel<T> (Simulate BackgroundService async queue)")
    print(f"{CYAN}7.{RESET} View Connected Clients & Group Hierarchy")
    print(f"{CYAN}8.{RESET} Run Automated End-to-End Stress Test")
    print(f"{RED}0.{RESET} Exit Simulation")
    print(f"{BOLD}---------------------------------{RESET}")


def run_e2e_stress_test(hub: NotificationHub, channel: BoundedChannel):
    print(f"\n{BOLD}{YELLOW}>>> Running Automated E2E SignalR & Channel<T> Test Suite...{RESET}")
    time.sleep(0.5)
    
    # 1. Spawn test clients
    c1 = hub.on_connected("Alice_VIP")
    c2 = hub.on_connected("Bob_Trader")
    c3 = hub.on_connected("Charlie_Auditor")
    
    # 2. Add to groups
    hub.add_to_group(c1.connection_id, "VIP_Lounge")
    hub.add_to_group(c2.connection_id, "VIP_Lounge")
    hub.add_to_group(c1.connection_id, "Orders")
    hub.add_to_group(c3.connection_id, "Orders")
    
    # 3. Broadcast and group messaging
    hub.send_broadcast(c1.connection_id, "Hello everyone on the network!")
    hub.send_to_group(c2.connection_id, "VIP_Lounge", "Exclusive market tip shared.")
    
    # 4. Enqueue background channel events
    for i in range(1, 4):
        evt = {"order_id": 9000 + i, "customer": f"VIP_User_{i}", "amount": 150.0 * i}
        success = channel.write(evt)
        log_hub("ChannelProducer", f"Enqueue Order #{evt['order_id']} [Success: {success}]", YELLOW)

    # Allow worker thread to drain
    time.sleep(1.8)
    
    # Clean up test connections
    hub.on_disconnected(c1.connection_id)
    hub.on_disconnected(c2.connection_id)
    hub.on_disconnected(c3.connection_id)
    print(f"{BOLD}{GREEN}>>> Automated E2E Test Suite Completed Successfully!{RESET}\n")


def main():
    print_banner()
    hub = NotificationHub()
    channel = BoundedChannel(capacity=20)
    worker = BackgroundOrderProcessor(channel, hub)
    worker.start()

    # Pre-seed sample clients for immediate experimentation
    seed1 = hub.on_connected("Dev_Admin")
    seed2 = hub.on_connected("Mobile_App_User")
    hub.add_to_group(seed1.connection_id, "Orders")
    hub.add_to_group(seed2.connection_id, "PublicRoom")

    order_seq = 1001

    try:
        while True:
            show_menu()
            choice = input(f"{BOLD}Pilih opsi [0-8]: {RESET}").strip()

            if choice == "1":
                uname = input(f"{WHITE}Masukkan Nama Client/User: {RESET}").strip()
                if not uname:
                    uname = f"User_{len(hub.connections) + 1}"
                hub.on_connected(uname)

            elif choice == "2":
                if not hub.connections:
                    print(f"{RED}Tidak ada client terhubung.{RESET}")
                    continue
                print(f"{WHITE}Daftar Client Terhubung:{RESET}")
                for idx, (cid, conn) in enumerate(hub.connections.items(), 1):
                    print(f"  {idx}. {conn.user_name} ({cid[:8]}..)")
                sel = input(f"{WHITE}Pilih nomor client untuk disconnect: {RESET}").strip()
                if sel.isdigit() and 1 <= int(sel) <= len(hub.connections):
                    target_cid = list(hub.connections.keys())[int(sel) - 1]
                    hub.on_disconnected(target_cid)
                else:
                    print(f"{RED}Pilihan tidak valid.{RESET}")

            elif choice == "3":
                if not hub.connections:
                    print(f"{RED}Tidak ada client terhubung.{RESET}")
                    continue
                conns = list(hub.connections.items())
                for idx, (cid, conn) in enumerate(conns, 1):
                    print(f"  {idx}. {conn.user_name} (Current: {list(conn.groups)})")
                sel = input(f"{WHITE}Pilih nomor client: {RESET}").strip()
                if sel.isdigit() and 1 <= int(sel) <= len(conns):
                    target_cid = conns[int(sel) - 1][0]
                    grp_name = input(f"{WHITE}Nama Group/Room (misal: Orders, VIP_Lounge): {RESET}").strip()
                    if grp_name:
                        hub.add_to_group(target_cid, grp_name)
                else:
                    print(f"{RED}Pilihan tidak valid.{RESET}")

            elif choice == "4":
                if not hub.connections:
                    print(f"{RED}Tidak ada client terhubung.{RESET}")
                    continue
                caller_id = list(hub.connections.keys())[0]
                msg = input(f"{WHITE}Pesan broadcast: {RESET}").strip()
                if msg:
                    hub.send_broadcast(caller_id, msg)

            elif choice == "5":
                if not hub.connections:
                    print(f"{RED}Tidak ada client terhubung.{RESET}")
                    continue
                grp_name = input(f"{WHITE}Target Group: {RESET}").strip()
                caller_id = list(hub.connections.keys())[0]
                msg = input(f"{WHITE}Pesan group: {RESET}").strip()
                if grp_name and msg:
                    hub.send_to_group(caller_id, grp_name, msg)

            elif choice == "6":
                cust = input(f"{WHITE}Nama Customer [default: Alice]: {RESET}").strip() or "Alice"
                amt_str = input(f"{WHITE}Nominal Order ($) [default: 250.0]: {RESET}").strip() or "250.0"
                try:
                    amt = float(amt_str)
                except ValueError:
                    amt = 250.0
                order_seq += 1
                evt = {"order_id": order_seq, "customer": cust, "amount": amt}
                ok = channel.write(evt)
                if ok:
                    log_hub("ChannelProducer", f"Order #{order_seq} queued into Channel<OrderEvent> [Capacity: {channel.capacity}]", YELLOW)
                else:
                    print(f"{RED}Channel is FULL! Backpressure applied.{RESET}")

            elif choice == "7":
                print(f"\n{BOLD}{CYAN}=== STATE AKTIF SIGNALR HUB ==={RESET}")
                print(f"Total Connections: {len(hub.connections)}")
                for cid, conn in hub.connections.items():
                    print(f" - {BOLD}{conn.user_name}{RESET} (ID: {cid})")
                    print(f"   Groups: {list(conn.groups) if conn.groups else 'No groups'}")
                print(f"\nGroup Registry:")
                for grp, members in hub.groups.items():
                    member_names = [hub.connections[m].user_name for m in members if m in hub.connections]
                    print(f" * Group '{MAGENTA}{grp}{RESET}': {len(members)} member(s) -> {member_names}")

            elif choice == "8":
                run_e2e_stress_test(hub, channel)

            elif choice == "0":
                print(f"\n{YELLOW}Menghentikan Background Worker dan mematikan simulasi...{RESET}")
                worker.stop()
                break
            else:
                print(f"{RED}Opsi tidak dikenali. Silakan pilih 0-8.{RESET}")

    except KeyboardInterrupt:
        print(f"\n{RED}Interrupt diterima. Menutup simulasi...{RESET}")
        worker.stop()

    print(f"{GREEN}Simulasi ASP.NET Core SignalR & Messaging selesai.{RESET}")


if __name__ == "__main__":
    main()
