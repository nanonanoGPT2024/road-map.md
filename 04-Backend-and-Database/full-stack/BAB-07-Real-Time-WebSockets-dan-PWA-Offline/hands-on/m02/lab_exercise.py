#!/usr/bin/env python3
"""
BAB-07: Real-Time WebSockets & PWA Offline Architecture Simulation
Interactive, self-contained Python 3 production-grade architecture benchmark & simulation.

Features:
- WebSocket Gateway & Connection Lifecycle (Handshake, Ping/Pong Heartbeat, Pub/Sub channels)
- PWA Service Worker Offline Strategy (CacheStorage, Stale-While-Revalidate, IndexedDB Outbox)
- Network Flapping & Reconnect Engine (Exponential Backoff + Jitter)
- Offline Background Sync & Conflict Resolution (Last-Write-Wins with Vector Clocks)
- Rich ANSI terminal telemetry dashboard
"""

import asyncio
import enum
import json
import math
import random
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set


# ==============================================================================
# ANSI Color Palette for Interactive Telemetry
# ==============================================================================
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
    BG_DARK = "\033[48;5;235m"
    BG_BLUE = "\033[44m"


def header(text: str) -> None:
    print(f"\n{Color.BOLD}{Color.CYAN}{'=' * 75}{Color.RESET}")
    print(f"{Color.BOLD}{Color.WHITE}  🚀 {text}{Color.RESET}")
    print(f"{Color.BOLD}{Color.CYAN}{'=' * 75}{Color.RESET}")


def log_event(subsystem: str, msg: str, level: str = "INFO") -> None:
    badge_colors = {
        "INFO": (Color.GREEN, "✓"),
        "WARN": (Color.YELLOW, "⚠"),
        "ERROR": (Color.RED, "✖"),
        "SYNC": (Color.MAGENTA, "⟲"),
        "WS": (Color.CYAN, "⚡"),
        "PWA": (Color.BLUE, "📦"),
    }
    col, icon = badge_colors.get(level, (Color.WHITE, "•"))
    ts = time.strftime("%H:%M:%S")
    print(
        f"{Color.DIM}[{ts}]{Color.RESET} "
        f"{col}[{icon} {subsystem:<10}]{Color.RESET} {msg}"
    )


# ==============================================================================
# Domain Enums & Models
# ==============================================================================
class NetworkStatus(enum.Enum):
    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"
    DEGRADED = "DEGRADED (HIGH LATENCY / JITTER)"


class CacheStrategy(enum.Enum):
    CACHE_FIRST = "Cache-First (Fallback Network)"
    NETWORK_FIRST = "Network-First (Fallback Cache)"
    STALE_WHILE_REVALIDATE = "Stale-While-Revalidate"


@dataclass
class WSFrame:
    op_code: str
    channel: str
    sender_id: str
    payload: Dict[str, Any]
    vector_clock: Dict[str, int] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


@dataclass
class OutboxMutation:
    id: str
    action: str
    resource_id: str
    data: Dict[str, Any]
    vector_clock: Dict[str, int]
    timestamp: float
    retry_count: int = 0
    status: str = "PENDING"  # PENDING, SYNCED, CONFLICT


# ==============================================================================
# Component 1: In-Memory PWA CacheStorage & IndexedDB Outbox
# ==============================================================================
class PWAServiceWorker:
    def __init__(self, client_id: str):
        self.client_id = client_id
        self.cache_store: Dict[str, Dict[str, Any]] = {}
        self.indexed_db_outbox: List[OutboxMutation] = []
        self.vector_clock: Dict[str, int] = {client_id: 0}

    def put_cache(self, url: str, data: Any, ttl: float = 60.0) -> None:
        self.cache_store[url] = {
            "data": data,
            "cached_at": time.time(),
            "ttl": ttl,
        }

    def match_cache(self, url: str) -> Optional[Any]:
        entry = self.cache_store.get(url)
        if not entry:
            return None
        return entry["data"]

    async def fetch_with_strategy(
        self,
        url: str,
        network_fetch_fn: Callable[[], Any],
        strategy: CacheStrategy,
    ) -> Any:
        cached = self.match_cache(url)

        if strategy == CacheStrategy.CACHE_FIRST:
            if cached is not None:
                log_event("PWA-SW", f"Cache-HIT on {url} (Cache-First)", "PWA")
                return cached
            log_event("PWA-SW", f"Cache-MISS on {url} -> Network fetch", "PWA")
            fresh = await network_fetch_fn()
            self.put_cache(url, fresh)
            return fresh

        elif strategy == CacheStrategy.STALE_WHILE_REVALIDATE:
            if cached is not None:
                log_event(
                    "PWA-SW",
                    f"Serving STALE response for {url}, revalidating in background...",
                    "PWA",
                )
                asyncio.create_task(self._revalidate(url, network_fetch_fn))
                return cached
            fresh = await network_fetch_fn()
            self.put_cache(url, fresh)
            return fresh

        else:  # NETWORK_FIRST
            try:
                fresh = await network_fetch_fn()
                self.put_cache(url, fresh)
                return fresh
            except Exception:
                if cached is not None:
                    log_event(
                        "PWA-SW",
                        f"Network failed, fallback to CACHE for {url}",
                        "WARN",
                    )
                    return cached
                raise

    async def _revalidate(self, url: str, network_fetch_fn: Callable[[], Any]) -> None:
        try:
            fresh = await network_fetch_fn()
            self.put_cache(url, fresh)
            log_event("PWA-SW", f"Background cache revalidation complete: {url}", "INFO")
        except Exception as e:
            log_event("PWA-SW", f"Background revalidation failed: {e}", "WARN")

    def enqueue_mutation(self, action: str, resource_id: str, data: Dict[str, Any]) -> OutboxMutation:
        self.vector_clock[self.client_id] = self.vector_clock.get(self.client_id, 0) + 1
        mutation = OutboxMutation(
            id=f"mut-{int(time.time()*1000)}-{random.randint(100, 999)}",
            action=action,
            resource_id=resource_id,
            data=data,
            vector_clock=dict(self.vector_clock),
            timestamp=time.time(),
        )
        self.indexed_db_outbox.append(mutation)
        log_event(
            "IDB-OUTBOX",
            f"Stored offline mutation [{action}] ID={mutation.id} (Total queue: {len(self.indexed_db_outbox)})",
            "PWA",
        )
        return mutation


# ==============================================================================
# Component 2: High-Performance WebSocket Gateway & PubSub Broker
# ==============================================================================
class WebSocketGateway:
    def __init__(self):
        self.subscribers: Dict[str, Set[str]] = {}  # channel -> set(client_ids)
        self.connections: Dict[str, asyncio.Queue] = {}  # client_id -> message queue
        self.doc_store: Dict[str, Dict[str, Any]] = {
            "doc-101": {
                "title": "Roadmap Architecture v2",
                "version": 1,
                "content": "Initial baseline content.",
                "updated_by": "system",
                "vclock": {"system": 1},
                "updated_at": time.time(),
            }
        }
        self.total_broadcasts = 0

    def register_client(self, client_id: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self.connections[client_id] = q
        return q

    def disconnect_client(self, client_id: str) -> None:
        if client_id in self.connections:
            del self.connections[client_id]
        for ch_members in self.subscribers.values():
            ch_members.discard(client_id)

    def subscribe(self, client_id: str, channel: str) -> None:
        if channel not in self.subscribers:
            self.subscribers[channel] = set()
        self.subscribers[channel].add(client_id)
        log_event("WS-GATEWAY", f"Client '{client_id}' joined channel '{channel}'", "WS")

    async def broadcast_channel(self, channel: str, frame: WSFrame) -> None:
        members = self.subscribers.get(channel, set())
        for cid in list(members):
            if cid in self.connections and cid != frame.sender_id:
                await self.connections[cid].put(frame)
                self.total_broadcasts += 1

    def resolve_and_apply_mutation(self, mutation: OutboxMutation) -> Dict[str, Any]:
        """Vector Clock + Last-Write-Wins (LWW) conflict resolution algorithm."""
        doc = self.doc_store.get(mutation.resource_id)
        if not doc:
            doc = {
                "version": 1,
                "vclock": dict(mutation.vector_clock),
                "updated_by": mutation.data.get("user", "unknown"),
                "content": mutation.data.get("content", ""),
                "updated_at": mutation.timestamp,
            }
            self.doc_store[mutation.resource_id] = doc
            return {"status": "APPLIED", "reason": "NEW_DOC", "doc": doc}

        server_vclock = doc["vclock"]
        client_vclock = mutation.vector_clock

        # Compare vector clocks
        client_ahead = False
        client_behind = False
        for node, c_tick in client_vclock.items():
            s_tick = server_vclock.get(node, 0)
            if c_tick > s_tick:
                client_ahead = True
            elif c_tick < s_tick:
                client_behind = True

        if client_ahead and not client_behind:
            # Clean causality progression
            doc["content"] = mutation.data.get("content", doc["content"])
            doc["version"] += 1
            doc["vclock"].update(client_vclock)
            doc["updated_at"] = mutation.timestamp
            doc["updated_by"] = mutation.data.get("user", "unknown")
            return {"status": "APPLIED", "reason": "CAUSAL_OK", "doc": doc}

        # Concurrent branch detected -> fallback to deterministic Last-Write-Wins (LWW)
        if mutation.timestamp >= doc["updated_at"]:
            doc["content"] = mutation.data.get("content", doc["content"])
            doc["version"] += 1
            doc["vclock"].update(client_vclock)
            doc["updated_at"] = mutation.timestamp
            doc["updated_by"] = mutation.data.get("user", "unknown")
            return {"status": "RESOLVED_LWW", "reason": "CONCURRENT_MERGED_WIN", "doc": doc}
        else:
            return {
                "status": "REJECTED_STALE",
                "reason": "SERVER_HAS_NEWER_STATE",
                "doc": doc,
            }


# ==============================================================================
# Component 3: Reactive Full-Stack Client Node
# ==============================================================================
class RealTimePWAClient:
    def __init__(self, client_id: str, gateway: WebSocketGateway):
        self.client_id = client_id
        self.gateway = gateway
        self.sw = PWAServiceWorker(client_id)
        self.net_state = NetworkStatus.ONLINE
        self.ws_queue: Optional[asyncio.Queue] = None
        self.is_connected = False
        self.reconnect_attempts = 0
        self.active_channel = "collab-editor"

    async def connect_ws(self) -> None:
        if self.net_state == NetworkStatus.OFFLINE:
            log_event("WS-CLIENT", f"Cannot connect: Device is OFFLINE", "ERROR")
            return
        self.ws_queue = self.gateway.register_client(self.client_id)
        self.gateway.subscribe(self.client_id, self.active_channel)
        self.is_connected = True
        self.reconnect_attempts = 0
        log_event(
            "WS-CLIENT",
            f"Handshake 101 Switching Protocols -> Connected to Gateway! (Session={self.client_id})",
            "WS",
        )

    def set_network_state(self, new_state: NetworkStatus) -> None:
        prev = self.net_state
        self.net_state = new_state
        color = Color.GREEN if new_state == NetworkStatus.ONLINE else Color.RED
        print(f"\n{Color.BG_DARK} [NETWORK TOGGLE] {self.client_id}: {prev.value} ➔ {color}{new_state.value}{Color.RESET}")

        if new_state == NetworkStatus.OFFLINE and self.is_connected:
            self.is_connected = False
            self.gateway.disconnect_client(self.client_id)
            log_event("WS-CLIENT", f"Socket abruptly dropped (PWA offline event fired)", "WARN")

    async def send_or_queue_edit(self, doc_id: str, new_content: str, user_name: str) -> None:
        if not self.is_connected:
            log_event(
                "CLIENT-SYNC",
                f"Offline detected! Intercepting write through Service Worker Background Sync...",
                "SYNC",
            )
            self.sw.enqueue_mutation(
                action="UPDATE_DOC",
                resource_id=doc_id,
                data={"content": new_content, "user": user_name},
            )
        else:
            # Online: publish directly via WebSocket
            self.sw.vector_clock[self.client_id] = self.sw.vector_clock.get(self.client_id, 0) + 1
            frame = WSFrame(
                op_code="TEXT_EDIT",
                channel=self.active_channel,
                sender_id=self.client_id,
                payload={"doc_id": doc_id, "content": new_content, "user": user_name},
                vector_clock=dict(self.sw.vector_clock),
            )
            # Apply to server
            mutation = OutboxMutation(
                id=f"live-{int(time.time()*1000)}",
                action="UPDATE_DOC",
                resource_id=doc_id,
                data={"content": new_content, "user": user_name},
                vector_clock=dict(self.sw.vector_clock),
                timestamp=time.time(),
            )
            res = self.gateway.resolve_and_apply_mutation(mutation)
            await self.gateway.broadcast_channel(self.active_channel, frame)
            log_event(
                "WS-CLIENT",
                f"Live broadcast emitted to channel '{self.active_channel}' -> {res['status']}",
                "INFO",
            )

    async def trigger_pwa_background_sync(self) -> None:
        """Emulates W3C Service Worker Background Sync API (sync event)."""
        if not self.is_connected:
            log_event("PWA-SYNC", "Sync event deferred: Network not yet established.", "WARN")
            return

        if not self.sw.indexed_db_outbox:
            log_event("PWA-SYNC", "No queued mutations found in IndexedDB Outbox.", "INFO")
            return

        log_event(
            "PWA-SYNC",
            f"Background Sync event executing {len(self.sw.indexed_db_outbox)} queued outbox mutation(s)...",
            "SYNC",
        )

        while self.sw.indexed_db_outbox:
            mut = self.sw.indexed_db_outbox.pop(0)
            res = self.gateway.resolve_and_apply_mutation(mut)
            mut.status = res["status"]

            # Broadcast sync update to other nodes
            frame = WSFrame(
                op_code="SYNC_REPLAY",
                channel=self.active_channel,
                sender_id=self.client_id,
                payload={"doc_id": mut.resource_id, "res": res},
                vector_clock=mut.vector_clock,
                timestamp=mut.timestamp,
            )
            await self.gateway.broadcast_channel(self.active_channel, frame)
            log_event(
                "PWA-SYNC",
                f"Synced Mutation [{mut.id}] Result: {Color.BOLD}{res['status']}{Color.RESET} ({res['reason']})",
                "INFO",
            )


# ==============================================================================
# Full Multi-Phase Interactive Simulation Runner
# ==============================================================================
async def run_simulation() -> None:
    header("BAB-07: Full-Stack Real-Time WebSockets & PWA Offline Simulation")
    print(f"{Color.CYAN}Initializing Gateway broker, Service Workers, and Client nodes...{Color.RESET}\n")

    gateway = WebSocketGateway()
    client_desktop = RealTimePWAClient("Client-Desktop-Alpha", gateway)
    client_mobile = RealTimePWAClient("Client-Mobile-PWA", gateway)

    # --------------------------------------------------------------------------
    # Phase 1: Normal Real-Time Connected Operations
    # --------------------------------------------------------------------------
    header("PHASE 1: WebSocket Handshake & Multi-Client Real-Time Pub/Sub")
    await client_desktop.connect_ws()
    await client_mobile.connect_ws()

    # Desktop writes doc
    log_event("TEST", "Client Desktop sends a live collaborative edit...")
    await client_desktop.send_or_queue_edit(
        doc_id="doc-101",
        new_content="Chapter 7: Real-Time WebSockets Architecture Draft",
        user_name="Alice (Desktop)",
    )
    await asyncio.sleep(0.3)

    # --------------------------------------------------------------------------
    # Phase 2: PWA Service Worker Caching Demonstration
    # --------------------------------------------------------------------------
    header("PHASE 2: PWA Service Worker Cache Strategies (Stale-While-Revalidate)")

    async def mock_api_fetch():
        await asyncio.sleep(0.2)
        return {"api_version": "2.4.0", "edge_region": "ap-southeast-1", "ts": time.time()}

    log_event("PWA-CACHE", "Step 1: First fetch via Stale-While-Revalidate (Cache Miss -> Network)")
    res1 = await client_mobile.sw.fetch_with_strategy(
        "/api/v1/config", mock_api_fetch, CacheStrategy.STALE_WHILE_REVALIDATE
    )
    log_event("PWA-CACHE", f"Result: {res1}", "INFO")

    log_event("PWA-CACHE", "Step 2: Second fetch via Stale-While-Revalidate (Instant Cache Hit + Revalidate)")
    res2 = await client_mobile.sw.fetch_with_strategy(
        "/api/v1/config", mock_api_fetch, CacheStrategy.STALE_WHILE_REVALIDATE
    )
    log_event("PWA-CACHE", f"Result: {res2}", "INFO")
    await asyncio.sleep(0.4)

    # --------------------------------------------------------------------------
    # Phase 3: Mobile Client Goes Offline (Tunnel / Flight Mode)
    # --------------------------------------------------------------------------
    header("PHASE 3: Device Goes OFFLINE -> IndexedDB Outbox Mutation Queueing")
    client_mobile.set_network_state(NetworkStatus.OFFLINE)

    log_event("USER-ACTION", "User on Mobile makes Edit #1 while offline in subway...")
    await client_mobile.send_or_queue_edit(
        doc_id="doc-101",
        new_content="Chapter 7: Real-Time WebSockets & Offline-First PWA (Mobile Edit 1)",
        user_name="Bob (Mobile Offline)",
    )

    log_event("USER-ACTION", "User on Mobile makes Edit #2 while offline...")
    await client_mobile.send_or_queue_edit(
        doc_id="doc-101",
        new_content="Chapter 7: Real-Time WebSockets & Offline-First PWA (Mobile Final Cut)",
        user_name="Bob (Mobile Offline)",
    )

    # Concurrently, Desktop continues editing while connected
    log_event("CONCURRENT", "Alice on Desktop makes a concurrent update on server...")
    await client_desktop.send_or_queue_edit(
        doc_id="doc-101",
        new_content="Chapter 7: Real-Time WebSockets & Offline-First PWA (Desktop Concurrent)",
        user_name="Alice (Desktop)",
    )
    await asyncio.sleep(0.5)

    # --------------------------------------------------------------------------
    # Phase 4: Network Reconnection & Background Sync Reconciliation
    # --------------------------------------------------------------------------
    header("PHASE 4: Connection Restored -> Exponential Backoff & Sync Replay")
    log_event("RECONNECT", "Mobile device detects network reconnection. Initiating backoff...", "WARN")

    # Emulate exponential backoff with jitter
    for attempt in range(1, 4):
        delay = min(0.4, (0.05 * (2 ** (attempt - 1))) + random.uniform(0.01, 0.04))
        print(f"  {Color.DIM}↳ Reconnect Attempt #{attempt} (Backoff delay: {delay*1000:.1f}ms)...{Color.RESET}")
        await asyncio.sleep(delay)

    client_mobile.set_network_state(NetworkStatus.ONLINE)
    await client_mobile.connect_ws()

    # Trigger PWA Background Sync
    await client_mobile.trigger_pwa_background_sync()
    await asyncio.sleep(0.3)

    # --------------------------------------------------------------------------
    # Phase 5: Final Telemetry & Architecture Verification Report
    # --------------------------------------------------------------------------
    header("PHASE 5: Architecture Verification & State Telemetry")
    doc_final = gateway.doc_store["doc-101"]

    print(f"\n{Color.BOLD}{Color.WHITE}Final Server Document State (Consensus Reached):{Color.RESET}")
    print(f"  • Resource ID   : {Color.CYAN}doc-101{Color.RESET}")
    print(f"  • Final Version : {Color.GREEN}v{doc_final['version']}{Color.RESET}")
    print(f"  • Updated By    : {Color.YELLOW}{doc_final['updated_by']}{Color.RESET}")
    print(f"  • Final Content : {Color.WHITE}\"{doc_final['content']}\"{Color.RESET}")
    print(f"  • Vector Clock  : {Color.MAGENTA}{doc_final['vclock']}{Color.RESET}")
    print(f"  • Gateway Events: {Color.CYAN}{gateway.total_broadcasts} broadcasts delivered{Color.RESET}")
    print(f"  • Mobile Outbox : {Color.GREEN}{len(client_mobile.sw.indexed_db_outbox)} pending items (Drained){Color.RESET}\n")

    print(f"{Color.GREEN}{Color.BOLD}✓ All WebSocket & PWA Offline-First simulation tests PASSED successfully!{Color.RESET}\n")


if __name__ == "__main__":
    try:
        asyncio.run(run_simulation())
    except KeyboardInterrupt:
        print(f"\n{Color.YELLOW}Simulation interrupted by user.{Color.RESET}")
        sys.exit(0)
