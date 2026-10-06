#!/usr/bin/env python3
"""
Lab Exercise: Rails ActionCable & WebSocket Streaming Simulator
BAB-06: Real-Time Streaming & WebSocket Architecture (Ruby on Rails)

Simulasi mandiri arsitektur ActionCable, Redis Pub/Sub Broker, Connection Auth,
Channel Subscriptions, dan Turbo Stream DOM mutations.
"""

import sys
import time
import json
import uuid
from typing import Dict, List, Optional, Set, Callable
from dataclasses import dataclass, field

# --- ANSI Terminal Color Palette ---
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

BG_DARK = "\033[40m"
BG_BLUE = "\033[44m"


def header(title: str) -> None:
    print(f"\n{BOLD}{CYAN}{'=' * 68}{RESET}")
    print(f"{BOLD}{WHITE}  {title}{RESET}")
    print(f"{BOLD}{CYAN}{'=' * 68}{RESET}")


def step_log(tag: str, msg: str, color: str = BLUE) -> None:
    print(f"{color}[{tag}]{RESET} {msg}")


# --- Redis Pub/Sub Broker Simulation ---
class RedisPubSubBroker:
    """
    Mensimulasikan Redis Pub/Sub adapter yang digunakan oleh ActionCable
    untuk mendistribusikan frame pesan antar server worker multi-process.
    """

    def __init__(self):
        self._subscribers: Dict[str, Set[Callable[[dict], None]]] = {}
        self.message_history: List[dict] = []

    def subscribe(self, stream_name: str, callback: Callable[[dict], None]) -> None:
        if stream_name not in self._subscribers:
            self._subscribers[stream_name] = set()
        self._subscribers[stream_name].add(callback)
        step_log("REDIS", f"Registered subscriber to key {BOLD}'{stream_name}'{RESET}", MAGENTA)

    def unsubscribe(self, stream_name: str, callback: Callable[[dict], None]) -> None:
        if stream_name in self._subscribers and callback in self._subscribers[stream_name]:
            self._subscribers[stream_name].remove(callback)
            step_log("REDIS", f"Removed subscriber from {BOLD}'{stream_name}'{RESET}", DIM)

    def publish(self, stream_name: str, payload: dict) -> int:
        self.message_history.append({"stream": stream_name, "payload": payload, "ts": time.time()})
        subscribers = self._subscribers.get(stream_name, set())
        step_log("REDIS", f"PUBLISH stream={stream_name} payload={json.dumps(payload)}", YELLOW)
        for sub in list(subscribers):
            sub(payload)
        return len(subscribers)


# --- ActionCable Connection Layer ---
@dataclass
class ActionCableConnection:
    """
    Mensimulasikan ApplicationCable::Connection
    Bertanggung jawab atas autentikasi cookie / Devise warden token saat handshake WebSocket.
    """

    connection_id: str
    cookies: Dict[str, str]
    current_user: Optional[str] = None
    connected: bool = False
    subscriptions: Dict[str, "ChannelSubscription"] = field(default_factory=dict)

    def authenticate(self) -> bool:
        session_token = self.cookies.get("user_session")
        if session_token and session_token.startswith("valid_user_"):
            self.current_user = session_token.replace("valid_user_", "User#")
            self.connected = True
            step_log("AUTH", f"Connection {self.connection_id[:8]} authorized as {BOLD}{GREEN}{self.current_user}{RESET}", GREEN)
            return True
        else:
            self.connected = False
            step_log("AUTH", f"Connection {self.connection_id[:8]} REJECTED (Unauthorized)", RED)
            return False

    def transmit(self, data: dict) -> None:
        """Mengirim frame WebSocket ke client."""
        raw = json.dumps(data)
        print(f"    {CYAN}<< [WS Frame to {self.current_user or 'Anon'}]{RESET} {raw}")


# --- ActionCable Channel & Turbo Stream Layer ---
class ChannelSubscription:
    """
    Mensimulasikan ApplicationCable::Channel dan Turbo Stream broadcast.
    """

    def __init__(self, channel_name: str, connection: ActionCableConnection, broker: RedisPubSubBroker):
        self.channel_name = channel_name
        self.connection = connection
        self.broker = broker
        self.stream_keys: Set[str] = set()

    def stream_from(self, stream_name: str) -> None:
        self.stream_keys.add(stream_name)
        self.broker.subscribe(stream_name, self._on_broadcast)
        step_log("CHANNEL", f"{self.connection.current_user} subscribed to stream '{stream_name}' in {self.channel_name}", BLUE)

    def _on_broadcast(self, message: dict) -> None:
        # ActionCable membungkus broadcast sebelum diteruskan via frame WebSocket
        envelope = {
            "identifier": self.channel_name,
            "message": message
        }
        self.connection.transmit(envelope)

    def perform_action(self, action: str, data: dict) -> None:
        step_log("ACTION", f"Invoking {self.channel_name}#{action} with data: {data}", CYAN)
        if action == "speak":
            room_id = data.get("room_id", "lobby")
            content = data.get("content", "")
            stream_key = f"chat_room_{room_id}"
            
            # Simulasi Turbo Stream payload (DOM mutation: append)
            turbo_html = (
                f'<turbo-stream action="append" target="messages_room_{room_id}">'
                f'<template><div class="chat-msg"><b>{self.connection.current_user}</b>: {content}</div></template>'
                f'</turbo-stream>'
            )
            
            payload = {
                "sender": self.connection.current_user,
                "content": content,
                "turbo_stream": turbo_html,
                "timestamp": time.strftime("%H:%M:%S")
            }
            self.broker.publish(stream_key, payload)

        elif action == "signal_typing":
            room_id = data.get("room_id", "lobby")
            stream_key = f"chat_room_{room_id}"
            payload = {
                "type": "typing_indicator",
                "user": self.connection.current_user,
                "status": data.get("status", "typing")
            }
            self.broker.publish(stream_key, payload)

    def close(self) -> None:
        for sk in list(self.stream_keys):
            self.broker.unsubscribe(sk, self._on_broadcast)
        self.stream_keys.clear()
        step_log("CHANNEL", f"Unsubscribed {self.channel_name} for {self.connection.current_user}", DIM)


# --- Simulation Orchestrator & Interactive UI ---
class RailsWebSocketSimulator:
    def __init__(self):
        self.broker = RedisPubSubBroker()
        self.active_connections: Dict[str, ActionCableConnection] = {}

    def simulate_handshake(self, user_alias: str, is_valid: bool = True) -> Optional[ActionCableConnection]:
        cid = str(uuid.uuid4())
        cookie_val = f"valid_user_{user_alias}" if is_valid else "corrupted_token"
        conn = ActionCableConnection(connection_id=cid, cookies={"user_session": cookie_val})
        
        step_log("WS_UPGRADE", f"GET /cable HTTP/1.1 Upgrade: websocket for {user_alias}", WHITE)
        if conn.authenticate():
            self.active_connections[cid] = conn
            return conn
        return None

    def run_automated_showcase(self) -> None:
        header("Rails ActionCable Architecture Showcase")
        print(f"{DIM}Memulai simulasi interaktif end-to-end WebSocket + Redis Pub/Sub + Turbo Streams{RESET}\n")

        # 1. Handshake connections
        step_log("SETUP", "1. Menguji Handshake & Authentication (ApplicationCable::Connection)")
        alice_conn = self.simulate_handshake("Alice", is_valid=True)
        bob_conn = self.simulate_handshake("Bob", is_valid=True)
        eve_conn = self.simulate_handshake("Eve_Attacker", is_valid=False)

        assert alice_conn is not None and alice_conn.connected
        assert bob_conn is not None and bob_conn.connected
        assert eve_conn is None

        # 2. Subscriptions
        header("Subscribing to RoomChannel (stream_from 'chat_room_42')")
        alice_sub = ChannelSubscription("RoomChannel", alice_conn, self.broker)
        alice_sub.stream_from("chat_room_42")
        alice_conn.subscriptions["RoomChannel"] = alice_sub

        bob_sub = ChannelSubscription("RoomChannel", bob_conn, self.broker)
        bob_sub.stream_from("chat_room_42")
        bob_conn.subscriptions["RoomChannel"] = bob_sub

        # 3. Action execution & Real-Time Broadcast
        header("Executing Real-Time Action: Alice sends a message")
        alice_sub.perform_action("speak", {"room_id": "42", "content": "Halo rails developers! Turbo Streams active!"})

        header("Typing Notification: Bob typing indicator")
        bob_sub.perform_action("signal_typing", {"room_id": "42", "status": "typing"})

        header("Turbo Stream DOM Mutation Demonstration")
        print(f"{BOLD}{GREEN}Mutasi DOM yang di-stream ke browser client:{RESET}")
        last_msg = self.broker.message_history[-2]["payload"]
        print(f"{YELLOW}{last_msg.get('turbo_stream')}{RESET}\n")

        # 4. Teardown
        header("Connection Teardown & Unsubscribe")
        alice_sub.close()
        bob_sub.close()
        step_log("SUMMARY", f"Total messages brokered via Redis Pub/Sub: {len(self.broker.message_history)}", GREEN)
        print(f"{BOLD}{GREEN}✓ Lab Exercise: Simulasi ActionCable WebSocket Selesai Berhasil!{RESET}\n")


def interactive_menu():
    sim = RailsWebSocketSimulator()
    header("ActionCable Terminal Interactive Workbench")
    print(f"1. Jalankan Automated Architecture Test & Broadcast")
    print(f"2. Simulasikan Custom Room Chat Manual")
    print(f"3. Keluar")
    
    choice = "1"
    if sys.stdin.isatty():
        try:
            choice = input(f"\n{BOLD}{CYAN}Pilih opsi (1-3) [default: 1]: {RESET}").strip() or "1"
        except EOFError:
            choice = "1"

    if choice == "1":
        sim.run_automated_showcase()
    elif choice == "2":
        header("Custom Room Chat Simulation")
        alice = sim.simulate_handshake("Developer_A", True)
        bob = sim.simulate_handshake("Developer_B", True)
        sub_a = ChannelSubscription("DevChannel", alice, sim.broker)
        sub_b = ChannelSubscription("DevChannel", bob, sim.broker)
        sub_a.stream_from("dev_standup")
        sub_b.stream_from("dev_standup")
        
        sub_a.perform_action("speak", {"room_id": "standup", "content": "Deployment ke staging sukses!"})
        sub_b.perform_action("speak", {"room_id": "standup", "content": "Confirmed, background jobs via SolidCable siap."})
        sub_a.close()
        sub_b.close()
    else:
        print(f"{YELLOW}Sesi ditutup.{RESET}")


if __name__ == "__main__":
    interactive_menu()
