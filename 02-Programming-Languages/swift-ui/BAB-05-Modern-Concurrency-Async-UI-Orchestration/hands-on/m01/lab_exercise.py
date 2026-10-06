#!/usr/bin/env python3
"""
Lab Exercise: SwiftUI Modern Concurrency & Async UI Orchestration Simulator
BAB-05: Modern Concurrency & Async UI Orchestration

Simulates core Swift Concurrency paradigms inside Python 3:
1. @MainActor thread isolation and UI state dispatching.
2. Structured concurrency with TaskGroups (parallel fetch aggregation).
3. Cooperative Task cancellation (.task lifecycle hook simulation).
4. AsyncSequence / AsyncStream real-time telemetry streaming to UI.
"""

import asyncio
import random
import sys
import time
from typing import AsyncGenerator, List, Dict, Any

# ANSI Color Codes for terminal UI
C_RESET = "\033[0m"
C_BOLD = "\033[1m"
C_DIM = "\033[2m"
C_RED = "\033[91m"
C_GREEN = "\033[92m"
C_YELLOW = "\033[93m"
C_BLUE = "\033[94m"
C_MAGENTA = "\033[95m"
C_CYAN = "\033[96m"


def print_banner():
    banner = f"""
{C_CYAN}{C_BOLD}======================================================================
  SWIFTUI MODERN CONCURRENCY & ASYNC UI ORCHESTRATION LAB
  Interactive Terminal Architecture Simulation (Swift 5.9+ / 6 Model)
======================================================================{C_RESET}
"""
    print(banner)


class MainActorDispatcher:
    """
    Simulates @MainActor behavior.
    Ensures UI state mutations happen exclusively on the designated 'Main' thread context.
    """
    def __init__(self):
        self.ui_state: Dict[str, Any] = {"status": "Idle", "render_count": 0, "data": []}

    async def run_on_main(self, action_name: str, payload: Any):
        # Simulate main thread isolation check
        current_task = asyncio.current_task()
        task_name = current_task.get_name() if current_task else "Task-Unknown"
        
        print(f"  {C_MAGENTA}[@MainActor]{C_RESET} Switching context to Main Dispatcher for: {C_BOLD}{action_name}{C_RESET}")
        await asyncio.sleep(0.05)  # Frame render tick
        self.ui_state["status"] = action_name
        self.ui_state["render_count"] += 1
        self.ui_state["data"].append(payload)
        
        print(f"  {C_GREEN}✓ State Updated on MainActor:{C_RESET} Render #{self.ui_state['render_count']} | Latest Payload: {payload}")


async def simulate_main_actor_workflow():
    """Demo 1: Background data retrieval with hop back to @MainActor."""
    print(f"\n{C_YELLOW}{C_BOLD}--- [1] @MainActor Isolation & Thread Hopping ---{C_RESET}")
    print(f"{C_DIM}Background async task fetches remote network payload, then updates UI state on @MainActor.{C_RESET}\n")
    
    main_actor = MainActorDispatcher()
    
    async def background_fetcher():
        print(f"  {C_BLUE}[Background Worker]{C_RESET} Initiating asynchronous HTTP network session...")
        await asyncio.sleep(0.8)
        print(f"  {C_BLUE}[Background Worker]{C_RESET} Data received (104.2 KB JSON). Hopping to @MainActor...")
        await main_actor.run_on_main("ProfileDataReceived", {"username": "alumni_swift", "role": "Architect"})

    await background_fetcher()


async def simulate_task_group():
    """Demo 2: Structured Concurrency using withTaskGroup."""
    print(f"\n{C_YELLOW}{C_BOLD}--- [2] Structured Concurrency: withTaskGroup Pattern ---{C_RESET}")
    print(f"{C_DIM}Spawns multiple child tasks in parallel, waiting for all results without data races.{C_RESET}\n")

    endpoints = [
        ("UserProfile", 0.4),
        ("UserFeedPosts", 0.9),
        ("FriendList", 0.6),
        ("Notifications", 0.3)
    ]
    
    start_time = time.perf_counter()
    results = []

    async def fetch_endpoint(name: str, delay: float) -> str:
        print(f"  {C_CYAN}[TaskGroup Child]{C_RESET} Spawning task: Fetching {name} (expected {delay}s)...")
        await asyncio.sleep(delay)
        print(f"  {C_GREEN}[TaskGroup Child]{C_RESET} Completed: {name}")
        return f"{name}:OK"

    print(f"  {C_BOLD}Launching withTaskGroup(of: String.self) ...{C_RESET}")
    tasks = [asyncio.create_task(fetch_endpoint(name, delay)) for name, delay in endpoints]
    
    # Wait for all child tasks (structured join)
    for t in asyncio.as_completed(tasks):
        res = await t
        results.append(res)
        
    elapsed = time.perf_counter() - start_time
    print(f"\n  {C_GREEN}{C_BOLD}All TaskGroup children finished in {elapsed:.2f}s!{C_RESET}")
    print(f"  Aggregated Results: {results}")


async def simulate_task_cancellation():
    """Demo 3: Cooperative Task Cancellation (.task onDisappear lifecycle)."""
    print(f"\n{C_YELLOW}{C_BOLD}--- [3] Cooperative Task Cancellation (.task View Lifecycle) ---{C_RESET}")
    print(f"{C_DIM}Simulating navigation away from SwiftUI View triggering Task.cancel() cooperative cancellation.{C_RESET}\n")

    async def long_running_sync_task():
        try:
            print(f"  {C_CYAN}[SwiftUI .task]{C_RESET} View appeared: starting long download job...")
            for step in range(1, 11):
                # Cooperative cancellation checkpoint: Task.checkCancellation()
                await asyncio.sleep(0.2)
                print(f"  {C_CYAN}[SwiftUI .task]{C_RESET} Processing file chunk {step}/10...")
            print(f"  {C_GREEN}[SwiftUI .task]{C_RESET} Task fully completed!")
        except asyncio.CancelledError:
            print(f"  {C_RED}{C_BOLD}[SwiftUI .task]{C_RESET} {C_RED}Cancellation detected! View dismissed before finishing.{C_RESET}")
            print(f"  {C_DIM}Performing swift clean-up (releasing sockets & buffers)...{C_RESET}")
            raise

    job = asyncio.create_task(long_running_sync_task())
    await asyncio.sleep(0.65)  # User navigates away after 0.65s
    
    print(f"\n  {C_MAGENTA}[Navigation Event]{C_RESET} User pressed Back Button -> .onDisappear triggers job.cancel()")
    job.cancel()
    
    try:
        await job
    except asyncio.CancelledError:
        print(f"  {C_GREEN}✓ Task terminated cooperatively without hanging memory.{C_RESET}")


async def simulate_async_stream():
    """Demo 4: AsyncSequence / AsyncStream continuous UI binding."""
    print(f"\n{C_YELLOW}{C_BOLD}--- [4] AsyncStream Real-Time Telemetry to SwiftUI View ---{C_RESET}")
    print(f"{C_DIM}Consuming an AsyncSequence for continuous live chart / metrics rendering.{C_RESET}\n")

    async def telemetry_stream() -> AsyncGenerator[Dict[str, Any], None]:
        for i in range(1, 6):
            await asyncio.sleep(0.25)
            yield {
                "sequence_id": i,
                "cpu_load": round(random.uniform(15.0, 78.5), 1),
                "fps": random.choice([59.8, 60.0, 120.0])
            }

    print(f"  {C_BOLD}for await metric in telemetryStream.makeAsyncIterator() ...{C_RESET}")
    async for packet in telemetry_stream():
        seq = packet["sequence_id"]
        cpu = packet["cpu_load"]
        fps = packet["fps"]
        bar = "█" * int(cpu // 5)
        print(f"  {C_CYAN}Tick #{seq:02d}{C_RESET} | FPS: {C_GREEN}{fps}{C_RESET} | CPU: {C_YELLOW}{cpu:4.1f}%{C_RESET} [{C_BLUE}{bar:<16}{C_RESET}]")
    
    print(f"  {C_GREEN}✓ AsyncSequence finished stream emission.{C_RESET}")


async def interactive_menu():
    """CLI Menu Loop."""
    print_banner()
    
    while True:
        print(f"\n{C_BOLD}Pilih Modul Simulasi Swift Concurrency:{C_RESET}")
        print(f"  {C_CYAN}1.{C_RESET} @MainActor UI Thread Isolation & Hopping")
        print(f"  {C_CYAN}2.{C_RESET} Structured Concurrency (withTaskGroup)")
        print(f"  {C_CYAN}3.{C_RESET} Cooperative Cancellation (.task Lifecycle)")
        print(f"  {C_CYAN}4.{C_RESET} AsyncStream / AsyncSequence to UI Feed")
        print(f"  {C_CYAN}5.{C_RESET} Jalankan SEMUA Modul Berurutan")
        print(f"  {C_RED}0.{C_RESET} Keluar (Exit)")
        
        try:
            choice = input(f"\n{C_BOLD}Masukkan pilihan (0-5): {C_RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting...")
            break

        if choice == "1":
            await simulate_main_actor_workflow()
        elif choice == "2":
            await simulate_task_group()
        elif choice == "3":
            await simulate_task_cancellation()
        elif choice == "4":
            await simulate_async_stream()
        elif choice == "5":
            await simulate_main_actor_workflow()
            await simulate_task_group()
            await simulate_task_cancellation()
            await simulate_async_stream()
            print(f"\n{C_GREEN}{C_BOLD}>>> Seluruh simulasi selesai dijalankan dengan sukses! <<<{C_RESET}")
        elif choice == "0":
            print(f"\n{C_GREEN}Terima kasih telah menjalankan Swift Concurrency Lab.{C_RESET}")
            break
        else:
            print(f"{C_RED}Pilihan tidak valid, silakan coba lagi.{C_RESET}")


def main():
    try:
        asyncio.run(interactive_menu())
    except KeyboardInterrupt:
        print("\nShutdown requested by user. Bye!")
        sys.exit(0)


if __name__ == "__main__":
    main()
