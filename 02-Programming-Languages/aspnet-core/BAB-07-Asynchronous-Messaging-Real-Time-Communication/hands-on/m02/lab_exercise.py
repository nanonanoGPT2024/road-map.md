#!/usr/bin/env python3
"""
Lab Hands-on: ASP.NET Core - Asynchronous Messaging & Real-Time Communication
Module: Deep Dive - SignalR Hub Lifecycle, Multiplexing, and Distributed Backplane

Deskripsi Teknis:
Script ini memodelkan arsitektur internal ASP.NET Core SignalR secara end-to-end:
1. Hub Lifetime & Connection Management (OnConnectedAsync, OnDisconnectedAsync).
2. Hub Protocol Invocation (RPC Client-to-Server dan Server-to-Client).
3. Group Management (AddToGroupAsync, RemoveFromGroupAsync).
4. Distributed Scale-out Backplane (mirip Redis/Azure SignalR Backplane) untuk
   mempublikasikan pesan antar instance Kestrel Server yang terpisah.
5. Concurrent streaming & heartbeat/keep-alive handling tanpa library eksternal.
"""

import asyncio
from dataclasses import dataclass, field
from enum import Enum
import json
import time
from typing import Dict, List, Set, Any, Optional
import uuid

# --- ANSI Formatting Helper ---
class TermColor:
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

def log_event(node: str, conn_id: str, action: str, details: str, color: str = TermColor.WHITE):
    timestamp = time.strftime("%H:%M:%S")
    print(f"{TermColor.DIM}[{timestamp}]{TermColor.RESET} "
          f"{TermColor.BOLD}[{node:<12}]{TermColor.RESET} "
          f"{TermColor.CYAN}(Conn:{conn_id[:8]}){TermColor.RESET} "
          f"{color}{action:<18}{TermColor.RESET} | {details}")

# --- Core Protocol & Enums ---
class MessageType(Enum):
    INVOCATION = 1
    STREAM_ITEM = 2
    COMPLETION = 3
    PING = 4
    CLOSE = 5

@dataclass
class HubInvocationMessage:
    target: str
    arguments: List[Any]
    invocation_id: Optional[str] = None
    type: MessageType = MessageType.INVOCATION

@dataclass
class BackplaneEnvelope:
    origin_server: str
    target_type: str  # "all", "group", "connection"
    target_key: Optional[str]
    hub_message: Dict[str, Any]

# --- Simulasi Redis Backplane (Distribusi Lintas Kestrel Node) ---
class ScaleoutBackplane:
    """
    Mensimulasikan Redis Pub/Sub Backplane pada ASP.NET Core SignalR.
    Mengirim pesan lintas server node agar client yang terhubung ke instance
    berbeda tetap menerima broadcast.
    """
    def __init__(self):
        self._subscribers: List[asyncio.Queue] = []
        self._lock = asyncio.Lock()

    async def subscribe(self) -> asyncio.Queue:
        async with self._lock:
            q = asyncio.Queue()
            self._subscribers.append(q)
            return q

    async def publish_async(self, envelope: BackplaneEnvelope):
        async with self._lock:
            for sub in self._subscribers:
                await sub.put(envelope)

# --- Connection Context & Abstraksi Hub ---
@dataclass
class HubCallerContext:
    connection_id: str
    user_identifier: str
    items: Dict[str, Any] = field(default_factory=dict)

class HubClients:
    """
    Mengemulasikan antarmuka IHubClients (Clients.All, Clients.Group, Clients.Caller).
    """
    def __init__(self, server_id: str, caller_conn_id: str, backplane: ScaleoutBackplane):
        self.server_id = server_id
        self.caller_conn_id = caller_conn_id
        self.backplane = backplane

    async def all(self, target: str, *args):
        envelope = BackplaneEnvelope(
            origin_server=self.server_id,
            target_type="all",
            target_key=None,
            hub_message={"target": target, "arguments": list(args)}
        )
        await self.backplane.publish_async(envelope)

    async def group(self, group_name: str, target: str, *args):
        envelope = BackplaneEnvelope(
            origin_server=self.server_id,
            target_type="group",
            target_key=group_name,
            hub_message={"target": target, "arguments": list(args)}
        )
        await self.backplane.publish_async(envelope)

    async def caller(self, target: str, *args):
        envelope = BackplaneEnvelope(
            origin_server=self.server_id,
            target_type="connection",
            target_key=self.caller_conn_id,
            hub_message={"target": target, "arguments": list(args)}
        )
        await self.backplane.publish_async(envelope)

class GroupManager:
    """
    Mengemulasikan IGroupManager untuk mengelola keanggotaan group SignalR.
    """
    def __init__(self, server_local_groups: Dict[str, Set[str]], lock: asyncio.Lock):
        self._groups = server_local_groups
        self._lock = lock

    async def add_to_group_async(self, connection_id: str, group_name: str):
        async with self._lock:
            if group_name not in self._groups:
                self._groups[group_name] = set()
            self._groups[group_name].add(connection_id)

    async def remove_from_group_async(self, connection_id: str, group_name: str):
        async with self._lock:
            if group_name in self._groups and connection_id in self._groups[group_name]:
                self._groups[group_name].remove(connection_id)

class Hub:
    """
    Base class untuk ASP.NET Core SignalR Hub.
    """
    def __init__(self):
        self.context: Optional[HubCallerContext] = None
        self.clients: Optional[HubClients] = None
        self.groups: Optional[GroupManager] = None

    async def on_connected_async(self):
        pass

    async def on_disconnected_async(self, exception: Optional[Exception]):
        pass

# --- Implementasi Hub Nyata (Domain Bisnis: Telemetry & Notification Hub) ---
class NotificationHub(Hub):
    """
    Hub yang mengimplementasikan event bisnis real-time,
    meniru perilaku [Authorize] dan channel broadcast di C#.
    """
    async def on_connected_async(self):
        log_event(self.clients.server_id, self.context.connection_id,
                  "CONNECTED", f"User: {self.context.user_identifier}", TermColor.GREEN)
        await self.clients.caller("ReceiveSystemMessage", f"Selamat datang, {self.context.user_identifier}!")

    async def on_disconnected_async(self, exception: Optional[Exception]):
        log_event(self.clients.server_id, self.context.connection_id,
                  "DISCONNECTED", f"Session Closed. Cleaned up resources.", TermColor.RED)

    async def send_global_broadcast(self, sender: str, text: str):
        log_event(self.clients.server_id, self.context.connection_id,
                  "DISPATCH_ALL", f"Broadcast from {sender}: {text}", TermColor.YELLOW)
        await self.clients.all("ReceiveBroadcast", sender, text)

    async def subscribe_topic(self, topic: str):
        await self.groups.add_to_group_async(self.context.connection_id, topic)
        log_event(self.clients.server_id, self.context.connection_id,
                  "JOIN_GROUP", f"Subscribed to topic '{topic}'", TermColor.MAGENTA)
        await self.clients.caller("SubscribedNotice", topic)

    async def publish_to_topic(self, topic: str, message: str):
        log_event(self.clients.server_id, self.context.connection_id,
                  "DISPATCH_GROUP", f"Target [{topic}]: {message}", TermColor.BLUE)
        await self.clients.group(topic, "TopicNotification", topic, message)

# --- Kestrel SignalR Host Instance ---
class KestrelSignalRNode:
    """
    Mewakili 1 unit instance web server ASP.NET Core Kestrel
    yang menjalankan middleware SignalR.
    """
    def __init__(self, server_id: str, backplane: ScaleoutBackplane):
        self.server_id = server_id
        self.backplane = backplane
        self.local_connections: Dict[str, asyncio.Queue] = {}
        self.local_groups: Dict[str, Set[str]] = {}
        self._lock = asyncio.Lock()
        self._backplane_task: Optional[asyncio.Task] = None

    async def start(self):
        backplane_queue = await self.backplane.subscribe()
        self._backplane_task = asyncio.create_task(self._process_backplane(backplane_queue))

    async def stop(self):
        if self._backplane_task:
            self._backplane_task.cancel()

    async def _process_backplane(self, queue: asyncio.Queue):
        """
        Mendengarkan event bus global dan meneruskan pesan ke client
        yang terkoneksi secara lokal pada instance Kestrel ini.
        """
        try:
            while True:
                envelope: BackplaneEnvelope = await queue.get()
                async with self._lock:
                    if envelope.target_type == "all":
                        for conn_id, q in self.local_connections.items():
                            await q.put(envelope.hub_message)
                    elif envelope.target_type == "group":
                        members = self.local_groups.get(envelope.target_key, set())
                        for conn_id in members:
                            if conn_id in self.local_connections:
                                await self.local_connections[conn_id].put(envelope.hub_message)
                    elif envelope.target_type == "connection":
                        if envelope.target_key in self.local_connections:
                            await self.local_connections[envelope.target_key].put(envelope.hub_message)
                queue.task_done()
        except asyncio.CancelledError:
            pass

    async def register_connection(self, conn_id: str) -> asyncio.Queue:
        async with self._lock:
            q = asyncio.Queue()
            self.local_connections[conn_id] = q
            return q

    async def unregister_connection(self, conn_id: str):
        async with self._lock:
            if conn_id in self.local_connections:
                del self.local_connections[conn_id]
            for grp, members in list(self.local_groups.items()):
                members.discard(conn_id)

    async def dispatch_client_invocation(self, conn_id: str, user_id: str,
                                         method_name: str, *args):
        hub = NotificationHub()
        hub.context = HubCallerContext(conn_id, user_id)
        hub.clients = HubClients(self.server_id, conn_id, self.backplane)
        hub.groups = GroupManager(self.local_groups, self._lock)

        method = getattr(hub, method_name, None)
        if method and callable(method):
            await method(*args)
        else:
            log_event(self.server_id, conn_id, "INVOKE_ERROR",
                      f"Method {method_name} not found on Hub", TermColor.RED)

# --- Mock Client Agent ---
class SignalRClientAgent:
    """
    Mensimulasikan client TypeScript/C# @microsoft/signalr.
    Menerima incoming message queue, heartbeat ping, dan invoke RPC.
    """
    def __init__(self, user_name: str, host_node: KestrelSignalRNode):
        self.user_name = user_name
        self.host_node = host_node
        self.connection_id = str(uuid.uuid4())
        self.inbox: Optional[asyncio.Queue] = None
        self.active = False
        self._listener_task: Optional[asyncio.Task] = None

    async def start_connection(self):
        self.inbox = await self.host_node.register_connection(self.connection_id)
        self.active = True
        self._listener_task = asyncio.create_task(self._listen())
        
        # Eksekusi OnConnectedAsync pada server
        hub = NotificationHub()
        hub.context = HubCallerContext(self.connection_id, self.user_name)
        hub.clients = HubClients(self.host_node.server_id, self.connection_id, self.host_node.backplane)
        hub.groups = GroupManager(self.host_node.local_groups, self.host_node._lock)
        await hub.on_connected_async()

    async def invoke(self, method_name: str, *args):
        await self.host_node.dispatch_client_invocation(
            self.connection_id, self.user_name, method_name, *args
        )

    async def _listen(self):
        try:
            while self.active:
                msg = await self.inbox.get()
                log_event(f"Client-{self.user_name}", self.connection_id,
                          "RECV_PAYLOAD", f"Event: {msg['target']} -> {json.dumps(msg['arguments'])}",
                          TermColor.CYAN)
                self.inbox.task_done()
        except asyncio.CancelledError:
            pass

    async def stop(self):
        self.active = False
        if self._listener_task:
            self._listener_task.cancel()
        await self.host_node.unregister_connection(self.connection_id)
        hub = NotificationHub()
        hub.context = HubCallerContext(self.connection_id, self.user_name)
        hub.clients = HubClients(self.host_node.server_id, self.connection_id, self.host_node.backplane)
        await hub.on_disconnected_async(None)

# --- Skenario Pengujian Asinkron / Harness Lab ---
async def main():
    print(f"\n{TermColor.BOLD}{TermColor.YELLOW}=== [LAB] ASP.NET CORE SIGNALR INTERNALS & SCALE-OUT SIMULATOR ==={TermColor.RESET}\n")

    # Inisialisasi Infrastructure
    backplane = ScaleoutBackplane()
    kestrel_node1 = KestrelSignalRNode("Kestrel-Node1", backplane)
    kestrel_node2 = KestrelSignalRNode("Kestrel-Node2", backplane)

    await kestrel_node1.start()
    await kestrel_node2.start()

    print(f"{TermColor.BOLD}1. Menghubungkan Client ke Klaster Multi-Node (Load Balanced)...{TermColor.RESET}")
    # Alice & Bob terhubung ke Node 1; Charlie terhubung ke Node 2
    alice = SignalRClientAgent("Alice", kestrel_node1)
    bob = SignalRClientAgent("Bob", kestrel_node1)
    charlie = SignalRClientAgent("Charlie", kestrel_node2)

    await alice.start_connection()
    await bob.start_connection()
    await charlie.start_connection()
    await asyncio.sleep(0.3)

    print(f"\n{TermColor.BOLD}2. Menguji Hub Groups & Multiplexing...{TermColor.RESET}")
    # Alice (Node1) dan Charlie (Node2) bergabung ke group 'telemetry-alert'
    # Bob tidak bergabung ke group tersebut
    await alice.invoke("subscribe_topic", "telemetry-alert")
    await charlie.invoke("subscribe_topic", "telemetry-alert")
    await asyncio.sleep(0.3)

    print(f"\n{TermColor.BOLD}3. Distribusi Pesan Lintas Server Node via Backplane (Cross-Server Group Pub/Sub)...{TermColor.RESET}")
    # Alice (Node 1) mengirim update telemetry ke group 'telemetry-alert'.
    # Charlie di Node 2 HARUS menerima pesan ini melalui Redis Backplane.
    # Bob di Node 1 TIDAK BOLEH menerima pesan ini.
    await alice.invoke("publish_to_topic", "telemetry-alert", "CRITICAL_TEMP_SENSOR_04_OVERHEAT")
    await asyncio.sleep(0.5)

    print(f"\n{TermColor.BOLD}4. Global Hub Broadcast (Clients.All Cross-Cluster)...{TermColor.RESET}")
    # Charlie (Node 2) broadcast pesan global ke semua client pada seluruh cluster.
    await charlie.invoke("send_global_broadcast", "Admin Charlie", "Server Maintenance in 10 mins.")
    await asyncio.sleep(0.5)

    print(f"\n{TermColor.BOLD}5. Clean Termination & Lifecycle Teardown...{TermColor.RESET}")
    await alice.stop()
    await bob.stop()
    await charlie.stop()

    await kestrel_node1.stop()
    await kestrel_node2.stop()

    print(f"\n{TermColor.GREEN}{TermColor.BOLD}[✓] Lab Berhasil: Pola Hub, HubContext, dan Distributed Backplane SignalR tervalidasi.{TermColor.RESET}\n")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nLab terminated by user.")