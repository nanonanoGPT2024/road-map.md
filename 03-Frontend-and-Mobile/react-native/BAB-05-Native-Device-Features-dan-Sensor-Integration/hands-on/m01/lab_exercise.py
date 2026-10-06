#!/usr/bin/env python3
"""
Lab Exercise: React Native Native Device Features & Sensor Integration Simulator
Author: Mobile Engineering Curriculum
Focus: Permissions, Sensor Streams (Accelerometer/Gyroscope), Geolocation Watcher,
       and Native Module Event Bridge Simulation.
"""

import sys
import time
import math
import random
from enum import Enum
from dataclasses import dataclass
from typing import Dict, List, Callable, Optional


class AnsiColor:
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


class PermissionStatus(Enum):
    UNAVAILABLE = "UNAVAILABLE"
    DENIED = "DENIED"
    BLOCKED = "BLOCKED"
    GRANTED = "GRANTED"


@dataclass
class SensorReading:
    timestamp: float
    x: float
    y: float
    z: float


class NativeEventEmitter:
    """Simulates React Native NativeEventEmitter bridging sensor events from C++/Java to JS."""
    def __init__(self):
        self._listeners: Dict[str, List[Callable]] = {}

    def add_listener(self, event_name: str, callback: Callable):
        if event_name not in self._listeners:
            self._listeners[event_name] = []
        self._listeners[event_name].append(callback)

    def remove_all_listeners(self, event_name: str):
        if event_name in self._listeners:
            self._listeners[event_name] = []

    def emit(self, event_name: str, payload: dict):
        if event_name in self._listeners:
            for cb in self._listeners[event_name]:
                cb(payload)


class ReactNativeBridgeSimulator:
    def __init__(self):
        self.emitter = NativeEventEmitter()
        self.permissions: Dict[str, PermissionStatus] = {
            "CAMERA": PermissionStatus.DENIED,
            "ACCESS_FINE_LOCATION": PermissionStatus.DENIED,
            "ACTIVITY_RECOGNITION": PermissionStatus.GRANTED,
        }
        self.low_pass_alpha = 0.2
        self.last_filtered_accel = {"x": 0.0, "y": 0.0, "z": 9.8}

    def request_permission(self, permission_key: str) -> PermissionStatus:
        print(f"\n{AnsiColor.CYAN}--- [Native Bridge] Requesting permission: {permission_key} ---{AnsiColor.RESET}")
        time.sleep(0.3)
        current = self.permissions.get(permission_key, PermissionStatus.UNAVAILABLE)
        
        if current == PermissionStatus.GRANTED:
            print(f"{AnsiColor.GREEN}✓ Permission already granted.{AnsiColor.RESET}")
            return current

        # Simulate user dialog prompt
        prompt = f"{AnsiColor.YELLOW}Simulate Android/iOS OS Dialog: Grant '{permission_key}'? (y/n): {AnsiColor.RESET}"
        user_choice = input(prompt).strip().lower()
        if user_choice == 'y':
            self.permissions[permission_key] = PermissionStatus.GRANTED
            print(f"{AnsiColor.GREEN}✓ Native Callback: PermissionsAndroid.RESULTS.GRANTED{AnsiColor.RESET}")
        else:
            self.permissions[permission_key] = PermissionStatus.BLOCKED
            print(f"{AnsiColor.RED}✗ Native Callback: PermissionsAndroid.RESULTS.BLOCKED / DENIED{AnsiColor.RESET}")

        return self.permissions[permission_key]

    def trigger_haptic(self, style: str = "medium"):
        styles = {
            "light": f"{AnsiColor.MAGENTA}[Haptic: Light Tick (10ms)]{AnsiColor.RESET}",
            "medium": f"{AnsiColor.MAGENTA}[Haptic: Medium Impact (25ms)]{AnsiColor.RESET}",
            "heavy": f"{AnsiColor.MAGENTA}[Haptic: Heavy Vibration (50ms) >>> BAM! <<<]{AnsiColor.RESET}",
            "error": f"{AnsiColor.RED}[Haptic: Double Pulse Error (Bzz-Bzz)]{AnsiColor.RESET}",
        }
        output = styles.get(style, f"{AnsiColor.MAGENTA}[Haptic: Default]{AnsiColor.RESET}")
        print(f" {output}")

    def simulate_accelerometer_stream(self, ticks: int = 8, update_interval_ms: int = 150):
        print(f"\n{AnsiColor.BOLD}{AnsiColor.BG_BLUE} [SENSOR STREAM] Subscribing to Accelerometer (updateInterval={update_interval_ms}ms) {AnsiColor.RESET}")
        print(f"{AnsiColor.DIM}Applying Real-Time Low-Pass Filter: y[k] = α * x[k] + (1 - α) * y[k-1]{AnsiColor.RESET}\n")

        for step in range(1, ticks + 1):
            # Raw hardware readings with noise
            t = time.time()
            raw_x = math.sin(step * 0.4) * 2.0 + random.uniform(-0.15, 0.15)
            raw_y = math.cos(step * 0.4) * 1.5 + random.uniform(-0.10, 0.10)
            raw_z = 9.806 + random.uniform(-0.25, 0.25)

            # Low pass filter calculation
            alpha = self.low_pass_alpha
            f_x = alpha * raw_x + (1.0 - alpha) * self.last_filtered_accel["x"]
            f_y = alpha * raw_y + (1.0 - alpha) * self.last_filtered_accel["y"]
            f_z = alpha * raw_z + (1.0 - alpha) * self.last_filtered_accel["z"]
            self.last_filtered_accel = {"x": f_x, "y": f_y, "z": f_z}

            # Magnitude calculation for shake detection
            magnitude = math.sqrt(raw_x**2 + raw_y**2 + raw_z**2)
            shake_alert = ""
            if magnitude > 10.8:
                shake_alert = f" {AnsiColor.RED}{AnsiColor.BOLD}[SHAKE TRIGGERED!]{AnsiColor.RESET}"
                self.trigger_haptic("heavy")

            print(
                f"{AnsiColor.CYAN}[Tick {step:02d}]{AnsiColor.RESET} "
                f"Raw: (X={raw_x:+.2f}, Y={raw_y:+.2f}, Z={raw_z:+.2f}) | "
                f"{AnsiColor.GREEN}Filtered: (X={f_x:+.2f}, Y={f_y:+.2f}, Z={f_z:+.2f}){AnsiColor.RESET} | "
                f"|g|={magnitude:.2f} m/s²{shake_alert}"
            )
            time.sleep(update_interval_ms / 1000.0)

    def simulate_geolocation_watch(self):
        if self.permissions.get("ACCESS_FINE_LOCATION") != PermissionStatus.GRANTED:
            print(f"{AnsiColor.RED}Geolocation Error: Location permission is NOT granted. Call request_permission first.{AnsiColor.RESET}")
            return

        print(f"\n{AnsiColor.BOLD}{AnsiColor.BG_BLUE} [GEOLOCATION WATCHPOSITION] High-Accuracy GPS Active {AnsiColor.RESET}")
        lat_base = -6.2088  # Jakarta CBD coordinate
        lon_base = 106.8456
        for i in range(1, 6):
            time.sleep(0.4)
            drift_lat = lat_base + (i * 0.00012)
            drift_lon = lon_base + (i * 0.00008)
            accuracy = random.uniform(3.5, 8.0)
            speed = 12.5 + random.uniform(-1.0, 1.5)
            print(
                f"{AnsiColor.YELLOW}• PosUpdate #{i}:{AnsiColor.RESET} "
                f"Lat: {drift_lat:.6f}, Lon: {drift_lon:.6f}, "
                f"Accuracy: ±{accuracy:.1f}m, Speed: {speed:.1f} km/h"
            )
        print(f"{AnsiColor.GREEN}✓ Geolocation watch cycle completed.{AnsiColor.RESET}")


def print_banner():
    banner = f"""
{AnsiColor.CYAN}{AnsiColor.BOLD}========================================================================
 REACT NATIVE NATIVE DEVICE FEATURES & SENSOR INTEGRATION SIMULATOR
 BAB 05: Permissions, Hardware Sensors, Geolocation & Event Bridge
========================================================================{AnsiColor.RESET}
"""
    print(banner)


def interactive_menu():
    simulator = ReactNativeBridgeSimulator()
    print_banner()

    menu = f"""
{AnsiColor.WHITE}{AnsiColor.BOLD}Select a Simulation Module:{AnsiColor.RESET}
  {AnsiColor.YELLOW}1.{AnsiColor.RESET} Request Camera & Location Permissions (Async Native Dialogue)
  {AnsiColor.YELLOW}2.{AnsiColor.RESET} Stream Accelerometer & Filter Noise (Shake Detection & Haptic)
  {AnsiColor.YELLOW}3.{AnsiColor.RESET} Watch Geolocation Stream (Hardware GPS Coordinates)
  {AnsiColor.YELLOW}4.{AnsiColor.RESET} Run Full Automated Sensor & Bridge Diagnostic
  {AnsiColor.RED}5. Exit Lab{AnsiColor.RESET}
"""

    while True:
        print(menu)
        choice = input(f"{AnsiColor.BOLD}Enter choice (1-5): {AnsiColor.RESET}").strip()

        if choice == "1":
            simulator.request_permission("CAMERA")
            simulator.request_permission("ACCESS_FINE_LOCATION")
        elif choice == "2":
            simulator.simulate_accelerometer_stream(ticks=10, update_interval_ms=100)
        elif choice == "3":
            simulator.simulate_geolocation_watch()
        elif choice == "4":
            print(f"\n{AnsiColor.MAGENTA}=== Running End-to-End Diagnostics ==={AnsiColor.RESET}")
            simulator.permissions["ACCESS_FINE_LOCATION"] = PermissionStatus.GRANTED
            simulator.simulate_accelerometer_stream(ticks=5, update_interval_ms=80)
            simulator.simulate_geolocation_watch()
            print(f"\n{AnsiColor.GREEN}All Native Modules & Sensors validated successfully.{AnsiColor.RESET}")
        elif choice == "5" or choice.lower() == "exit":
            print(f"\n{AnsiColor.GREEN}Exiting React Native Sensor Lab. Happy coding!{AnsiColor.RESET}")
            sys.exit(0)
        else:
            print(f"{AnsiColor.RED}Invalid selection. Please choose from 1 to 5.{AnsiColor.RESET}")


if __name__ == "__main__":
    interactive_menu()
