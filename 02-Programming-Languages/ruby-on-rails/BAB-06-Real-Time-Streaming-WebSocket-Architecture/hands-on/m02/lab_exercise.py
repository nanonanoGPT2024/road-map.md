#!/usr/bin/env python3
"""
Lab: Deep Dive - Rails Real-Time Streaming & ActionCable Architecture Simulation
Topic: Real-Time Streaming & WebSocket Architecture (Ruby on Rails Core Concepts)

This script simulates the complete internals of Rails ActionCable:
  1. Connection Layer: Connection lifecycle, Devise/Warden authentication & rejection.
  2. Multiplexing Engine: Single transport carrying multiple distinct Channel subscriptions.
  3. Pub/Sub Broker: Emulates the Redis PubSub adapter used by Rails for horizontal scaling.
  4. Channel Abstraction: ApplicationCable::Channel behavior (stream_from, speak, reject).
  5. Background Broadcasting: Simulates ActiveJob broadcasting events asynchronously.
"""

import sys
import time
import json
import uuid
import threading
from queue import Queue, Empty
from typing import Dict, List, Any, Callable, Optional
from dataclasses import dataclass, field

# --- ANSI Terminal Formatting ---
CLR_RESET   = "\033[0m"
CLR_BOLD    = "\033[1m"
CLR_RED     = "\033[91m"
CLR_GREEN   = "\033[92m"
CLR_YELLOW  = "\033[93m"
CLR_BLUE    = "\033[94m"
CLR_MAGENTA = "\033[95m"
CLR_CYAN    = "\033[96m"

def log(tag: str, color: str, message: str) -> None:
    timestamp = time.strftime("%H:%M:%S")
    print(f"{color}[{timestamp}] [{tag:<13}] {message}{CLR_RESET}")


# --- Redis Pub/Sub Adapter Emulation ---
class RedisPubSubAdapter:
    """
    Simulates the Redis engine backing ActionCable's production adapter.
    Handles decoupled, fan-out event distribution across channels.
    """
    def __init__(self):
        self._subscribers: Dict[str, List[Callable[[dict], None]]] = {}
        self._lock = threading.Lock()

    def subscribe(self, broadcast_key: str, callback: Callable[[dict], None]) -> None:
        with self._lock:
            if broadcast_key not in self._subscribers:
                self._subscribers[broadcast_key] = []
            self._subscribers[broadcast_key].append(callback)

    def unsubscribe(self, broadcast_key: str, callback: Callable[[dict], None]) -> None:
        with self._lock:
            if broadcast_key in self._subscribers:
                self._subscribers[broadcast_key] = [
                    cb for cb in self._subscribers[broadcast_key] if cb != callback
                ]
                if not self._subscribers[broadcast_key]:
                    del self._subscribers[broadcast_key]

    def broadcast(self, broadcast_key: str, message: dict) -> int:
        with self._lock:
            subscribers = self._subscribers.get(broadcast_key, []).copy()
        
        for callback in subscribers:
            threading.Thread(target=callback, args=(message,), daemon=True).start()
        return len(subscribers)


# --- ActionCable Connection & Identity ---
@dataclass
class UserSession:
    user_id: int
    username: str
    auth_token: str
    verified: bool = False


class ActionCableConnection:
    """
    Simulates `ApplicationCable::Connection`.
    Responsible for authenticating the WebSocket handshake and multiplexing frames.
    """
    def __init__(self, session: UserSession, pubsub: RedisPubSubAdapter):
        self.connection_id = str(uuid.uuid4())[:8]
        self.session = session
        self.pubsub = pubsub
        self.current_user: Optional[UserSession] = None
        self.channels: Dict[str, 'ActionCableChannel'] = {}
        self.inbox: Queue = Queue()
        self.is_connected = False

    def connect(self) -> bool:
        """Emulates verified_user authentication in Rails."""
        log("CONNECTION", CLR_CYAN, f"Initiating handshake for token: {self.session.auth_token}")
        if self.session.verified:
            self.current_user = self.session
            self.is_connected = True
            log("CONNECTION", CLR_GREEN, 
                f"Accepted: Identifiers [current_user: {self.current_user.username} (ID: {self.current_user.user_id})]")
            self._transmit({"type": "welcome"})
            return True
        else:
            log("CONNECTION", CLR_RED, f"Rejected: Unauthorized credentials. Closing socket.")
            self._transmit({"type": "disconnect", "reason": "unauthorized"})
            return False

    def receive_frame(self, frame_json: str) -> None:
        """Parses incoming WebSocket frames from the client."""
        if not self.is_connected:
            return
        frame = json.loads(frame_json)
        command = frame.get("command")
        identifier = frame.get("identifier")

        if command == "subscribe":
            self._handle_subscribe(identifier)
        elif command == "message":
            data = json.loads(frame.get("data", "{}"))
            self._handle_action(identifier, data)
        elif command == "unsubscribe":
            self._handle_unsubscribe(identifier)

    def _handle_subscribe(self, identifier: str) -> None:
        meta = json.loads(identifier)
        channel_name = meta.get("channel")

        if channel_name == "ChatChannel":
            channel = ChatChannel(self, identifier, meta)
        elif channel_name == "SystemAlertChannel":
            channel = SystemAlertChannel(self, identifier, meta)
        else:
            self._transmit({"identifier": identifier, "type": "reject_subscription"})
            return

        self.channels[identifier] = channel
        channel.subscribed()

    def _handle_action(self, identifier: str, data: dict) -> None:
        channel = self.channels.get(identifier)
        if channel:
            action = data.get("action", "perform")
            channel.dispatch_action(action, data)

    def _handle_unsubscribe(self, identifier: str) -> None:
        channel = self.channels.pop(identifier, None)
        if channel:
            channel.unsubscribed()
            self._transmit({"identifier": identifier, "type": "confirm_unsubscription"})

    def _transmit(self, payload: dict) -> None:
        """Sends data down the physical wire (mocked via internal queue)."""
        self.inbox.put(payload)

    def close(self) -> None:
        self.is_connected = False
        for channel in list(self.channels.values()):
            channel.unsubscribed()
        self.channels.clear()


# --- Base ActionCable Channel ---
class ActionCableChannel:
    """
    Simulates `ApplicationCable::Channel`.
    Encapsulates logic for a single logical channel over a shared connection.
    """
    def __init__(self, connection: ActionCableConnection, identifier: str, params: dict):
        self.connection = connection
        self.identifier = identifier
        self.params = params
        self.streams: Dict[str, Callable[[dict], None]] = {}

    def stream_from(self, broadcast_key: str) -> None:
        """Binds a pubsub broadcast channel directly to this client."""
        def callback(message: dict):
            # Transmit structured frame to the client
            self.connection._transmit({
                "identifier": self.identifier,
                "message": message
            })

        self.streams[broadcast_key] = callback
        self.connection.pubsub.subscribe(broadcast_key, callback)
        log("STREAMING", CLR_BLUE, 
            f"Client '{self.connection.current_user.username}' streaming from key: [{broadcast_key}]")

    def stop_all_streams(self) -> None:
        for key, callback in self.streams.items():
            self.connection.pubsub.unsubscribe(key, callback)
        self.streams.clear()

    def reject(self) -> None:
        self.connection._transmit({"identifier": self.identifier, "type": "reject_subscription"})

    def transmit(self, payload: dict) -> None:
        self.connection._transmit({"identifier": self.identifier, "message": payload})

    def subscribed(self) -> None:
        raise NotImplementedError

    def unsubscribed(self) -> None:
        self.stop_all_streams()

    def dispatch_action(self, action_name: str, data: dict) -> None:
        method = getattr(self, action_name, None)
        if callable(method):
            method(data)
        else:
            log("CHANNEL", CLR_RED, f"Action '{action_name}' not defined on {self.__class__.__name__}")


# --- Concrete Rails Channels ---
class ChatChannel(ActionCableChannel):
    """
    Simulates a multi-tenant ChatRoom Channel.
    Maps to `app/channels/chat_channel.rb`.
    """
    def subscribed(self) -> None:
        room_id = self.params.get("room_id")
        if not room_id:
            self.reject()
            return
        
        self.stream_key = f"chat_room_{room_id}"
        self.stream_from(self.stream_key)
        self.connection._transmit({"identifier": self.identifier, "type": "confirm_subscription"})
        log("CHANNEL", CLR_GREEN, f"ChatChannel confirmed for room: {room_id}")

    def speak(self, data: dict) -> None:
        """RPC action callable by the client."""
        content = data.get("content", "")
        broadcast_payload = {
            "author": self.connection.current_user.username,
            "body": content,
            "timestamp": time.time()
        }
        log("ACTION", CLR_MAGENTA, 
            f"RPC ChatChannel#speak received from {self.connection.current_user.username}: '{content}'")
        
        # ActionCable.server.broadcast(stream_key, payload)
        self.connection.pubsub.broadcast(self.stream_key, broadcast_payload)


class SystemAlertChannel(ActionCableChannel):
    """Global system-wide announcements."""
    def subscribed(self) -> None:
        self.stream_from("system_alerts")
        self.connection._transmit({"identifier": self.identifier, "type": "confirm_subscription"})


# --- Simulation Runner / Client Worker ---
def client_wire_listener(client_name: str, connection: ActionCableConnection, stop_event: threading.Event) -> None:
    """Monitors raw incoming frames on the client side."""
    while not stop_event.is_set():
        try:
            frame = connection.inbox.get(timeout=0.1)
            frame_type = frame.get("type", "message")
            if frame_type == "message":
                body = frame.get("message", {})
                log(f"RECV [{client_name}]", CLR_YELLOW, f"Payload: {json.dumps(body)}")
            else:
                log(f"RECV [{client_name}]", CLR_CYAN, f"Control Frame: [{frame_type.upper()}]")
        except Empty:
            continue


def background_broadcaster_job(pubsub: RedisPubSubAdapter, stop_event: threading.Event) -> None:
    """Simulates an asynchronous Rails ActiveJob broadcasting via ActionCable.server.broadcast."""
    time.sleep(1.2)
    log("ACTIVE_JOB", CLR_MAGENTA, "Job executing: BroadcastSystemAlertJob.perform_now(...)")
    pubsub.broadcast("system_alerts", {
        "level": "WARNING",
        "notice": "Database rolling migration scheduled in 10 minutes."
    })


def main() -> None:
    print(f"{CLR_BOLD}{CLR_CYAN}=== ActionCable & Real-Time Streaming Architecture Simulation ==={CLR_RESET}\n")

    # 1. Initialize PubSub engine (Redis Adapter)
    pubsub_broker = RedisPubSubAdapter()

    # 2. Define User Sessions (Simulating Cookie/Warden Auth)
    alice_session = UserSession(user_id=101, username="Alice", auth_token="token_alice_secret", verified=True)
    bob_session   = UserSession(user_id=102, username="Bob",   auth_token="token_bob_secret",   verified=True)
    mallory_session = UserSession(user_id=999, username="Mallory", auth_token="bad_token",      verified=False)

    stop_event = threading.Event()

    # 3. Connection Establishment & Auth Rejection Demonstration
    print(f"{CLR_BOLD}--- Step 1: Handshake Authentication & Rejection ---{CLR_RESET}")
    conn_mallory = ActionCableConnection(mallory_session, pubsub_broker)
    conn_mallory.connect()  # Should fail

    conn_alice = ActionCableConnection(alice_session, pubsub_broker)
    conn_bob = ActionCableConnection(bob_session, pubsub_broker)

    if not conn_alice.connect() or not conn_bob.connect():
        sys.exit(1)

    # Spin up client listeners
    threads = [
        threading.Thread(target=client_wire_listener, args=("Alice", conn_alice, stop_event), daemon=True),
        threading.Thread(target=client_wire_listener, args=("Bob", conn_bob, stop_event), daemon=True),
    ]
    for t in threads:
        t.start()

    time.sleep(0.3)

    # 4. Channel Subscription Multiplexing
    print(f"\n{CLR_BOLD}--- Step 2: Multiplexed Channel Subscriptions ---{CLR_RESET}")
    # Alice subscribes to room 42 and System alerts
    chat_sub_alice = json.dumps({"channel": "ChatChannel", "room_id": 42})
    alert_sub_alice = json.dumps({"channel": "SystemAlertChannel"})
    
    conn_alice.receive_frame(json.dumps({"command": "subscribe", "identifier": chat_sub_alice}))
    conn_alice.receive_frame(json.dumps({"command": "subscribe", "identifier": alert_sub_alice}))

    # Bob subscribes only to room 42
    chat_sub_bob = json.dumps({"channel": "ChatChannel", "room_id": 42})
    conn_bob.receive_frame(json.dumps({"command": "subscribe", "identifier": chat_sub_bob}))

    time.sleep(0.5)

    # 5. Remote Procedure Calls & Multi-Client Broadcast
    print(f"\n{CLR_BOLD}--- Step 3: Client RPC Invocation & PubSub Fanout ---{CLR_RESET}")
    speak_action_frame = json.dumps({
        "command": "message",
        "identifier": chat_sub_alice,
        "data": json.dumps({"action": "speak", "content": "Hey Rails developers, ActionCable is live!"})
    })
    conn_alice.receive_frame(speak_action_frame)

    # 6. Asynchronous Out-of-Band Broadcast (ActiveJob)
    print(f"\n{CLR_BOLD}--- Step 4: Asynchronous Out-of-Band Broadcast (ActiveJob) ---{CLR_RESET}")
    job_thread = threading.Thread(target=background_broadcaster_job, args=(pubsub_broker, stop_event), daemon=True)
    job_thread.start()

    time.sleep(2.0)

    # 7. Unsubscription & Cleanup
    print(f"\n{CLR_BOLD}--- Step 5: Teardown & Connection Clean Disconnect ---{CLR_RESET}")
    conn_alice.receive_frame(json.dumps({"command": "unsubscribe", "identifier": chat_sub_alice}))
    
    time.sleep(0.3)
    stop_event.set()
    conn_alice.close()
    conn_bob.close()
    
    log("SYSTEM", CLR_GREEN, "Simulation completed cleanly without resource leaks.")


if __name__ == "__main__":
    main()