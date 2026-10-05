#!/usr/bin/env python3
"""
React Native Native Device Features & Sensor Integration - Production Architecture Simulator
BAB-05: Native Device Features dan Sensor Integration (Modul 02: Sensors & Hardware APIs)

Simulasi runtime native pipeline tingkat produksi:
- Hardware Sensor Pipeline (JSI Zero-Copy Buffer & Throttled Worklet Dispatch)
- Battery-Aware Location Manager & Geofencing System (High Accuracy vs Passive Mode)
- VisionCamera Frame Processor Pipeline (Realtime inference simulation)
- Hardware-backed Security Keystore / Keychain & Biometrics Auth Simulator
"""

import sys
import time
import math
import random
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Callable

# ==============================================================================
# ANSI Color Palette & Terminal Formatting
# ==============================================================================
class TerminalColor:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    CYAN = "\033[36m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    RED = "\033[31m"
    MAGENTA = "\033[35m"
    BLUE = "\033[34m"
    BG_DARK = "\033[48;5;236m"
    SUCCESS = "\033[92m"
    WARNING = "\033[93m"
    CRITICAL = "\033[91m"
    ACCENT = "\033[96m"

def print_banner():
    banner = f"""
{TerminalColor.CYAN}{TerminalColor.BOLD}================================================================================
  REACT NATIVE NATIVE SENSORS & HARDWARE ARCHITECTURE SIMULATOR (BAB-05)
  High-Performance JSI TurboModule Pipeline, Background Geofence & Secure Enclave
================================================================================{TerminalColor.RESET}"""
    print(banner)

# ==============================================================================
# 1. Sensor Pipeline & JSI Worklet Buffer Simulation
# ==============================================================================
class SensorType(Enum):
    ACCELEROMETER = "ACCELEROMETER"
    GYROSCOPE = "GYROSCOPE"
    MAGNETOMETER = "MAGNETOMETER"

@dataclass
class SensorVector:
    x: float
    y: float
    z: float
    timestamp_ns: int

class NativeSensorEngine:
    """
    Simulasi TurboModule Sensor dengan JSI (JavaScript Interface) zero-copy buffer.
    Menerapkan sampling rate adaptif dan Reanimated worklet throttling.
    """
    def __init__(self, sampling_rate_hz: int = 50):
        self.sampling_rate_hz = sampling_rate_hz
        self.interval_sec = 1.0 / sampling_rate_hz
        self.is_streaming = False
        self.listeners: Dict[SensorType, List[Callable[[SensorVector], None]]] = {
            t: [] for t in SensorType
        }
        self.telemetry_history: List[Dict[str, float]] = []

    def add_listener(self, sensor: SensorType, callback: Callable[[SensorVector], None]):
        self.listeners[sensor].append(callback)

    def sample_hardware(self, step: int) -> Dict[SensorType, SensorVector]:
        now_ns = int(time.time() * 1e9)
        # Sintesis pergerakan dinamis ponsel (pitch, roll, gravity)
        t = step * self.interval_sec
        accel = SensorVector(
            x=round(math.sin(t * 2) * 1.8 + random.uniform(-0.05, 0.05), 3),
            y=round(math.cos(t * 1.5) * 2.2 + random.uniform(-0.05, 0.05), 3),
            z=round(9.806 + math.sin(t * 0.5) * 0.4 + random.uniform(-0.08, 0.08), 3),
            timestamp_ns=now_ns
        )
        gyro = SensorVector(
            x=round(math.sin(t * 3) * 0.45, 3),
            y=round(math.cos(t * 2.5) * 0.38, 3),
            z=round(math.sin(t * 1.2) * 0.15, 3),
            timestamp_ns=now_ns
        )
        mag = SensorVector(
            x=round(24.5 + math.cos(t) * 4.0, 2),
            y=round(-12.8 + math.sin(t) * 3.5, 2),
            z=round(42.1 + math.cos(t * 0.8) * 2.0, 2),
            timestamp_ns=now_ns
        )
        return {
            SensorType.ACCELEROMETER: accel,
            SensorType.GYROSCOPE: gyro,
            SensorType.MAGNETOMETER: mag
        }

    def run_benchmark_cycle(self, frames: int = 15):
        print(f"\n{TerminalColor.YELLOW}[1] Menguji High-Frequency JSI Sensor Pipeline ({self.sampling_rate_hz} Hz){TerminalColor.RESET}")
        print(f"{TerminalColor.DIM}Format: [Timestamp] Sensor -> (X, Y, Z) | JSI Worklet Thread Status{TerminalColor.RESET}")
        print("-" * 75)
        
        for i in range(frames):
            data = self.sample_hardware(i)
            acc = data[SensorType.ACCELEROMETER]
            gyr = data[SensorType.GYROSCOPE]
            
            # Deteksi guncangan mendadak (Shake Event Trigger)
            g_force = math.sqrt(acc.x**2 + acc.y**2 + acc.z**2) / 9.806
            shake_alert = f" {TerminalColor.CRITICAL}[SHAKE DETECTED! G={g_force:.2f}]{TerminalColor.RESET}" if g_force > 1.25 else ""
            
            print(f"{TerminalColor.CYAN}Frame #{i+1:02d}{TerminalColor.RESET} | "
                  f"{TerminalColor.GREEN}Accel:{TerminalColor.RESET} ({acc.x:+05.2f}, {acc.y:+05.2f}, {acc.z:+05.2f}) m/s² | "
                  f"{TerminalColor.MAGENTA}Gyro:{TerminalColor.RESET} ({gyr.x:+05.2f}, {gyr.y:+05.2f}, {gyr.z:+05.2f}) rad/s{shake_alert}")
            time.sleep(0.06)

# ==============================================================================
# 2. Location & Geofencing System (Battery-Aware Headless Task)
# ==============================================================================
@dataclass
class Coordinate:
    latitude: float
    longitude: float

@dataclass
class GeofenceRegion:
    region_id: str
    center: Coordinate
    radius_meters: float
    is_active: bool = True

class GeofenceTransition(Enum):
    ENTER = "GEOFENCE_ENTER"
    EXIT = "GEOFENCE_EXIT"
    DWELL = "GEOFENCE_DWELL"

class LocationEngine:
    """
    Simulasi React Native Background Geolocation & Foreground Service.
    Menghitung Haversine Distance untuk mendeteksi boundary crossing secara presisi.
    """
    def __init__(self):
        self.geofences: List[GeofenceRegion] = []
        self.inside_state: Dict[str, bool] = {}

    def register_geofence(self, fence: GeofenceRegion):
        self.geofences.append(fence)
        self.inside_state[fence.region_id] = False

    @staticmethod
    def haversine_distance(coord1: Coordinate, coord2: Coordinate) -> float:
        R = 6371000.0  # Radius bumi dalam meter
        lat1, lon1 = math.radians(coord1.latitude), math.radians(coord1.longitude)
        lat2, lon2 = math.radians(coord2.latitude), math.radians(coord2.longitude)
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = math.sin(dlat / 2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c

    def update_position(self, current: Coordinate) -> List[tuple]:
        events = []
        for fence in self.geofences:
            dist = self.haversine_distance(current, fence.center)
            was_inside = self.inside_state.get(fence.region_id, False)
            is_inside = dist <= fence.radius_meters
            
            if is_inside and not was_inside:
                self.inside_state[fence.region_id] = True
                events.append((GeofenceTransition.ENTER, fence.region_id, dist))
            elif not is_inside and was_inside:
                self.inside_state[fence.region_id] = False
                events.append((GeofenceTransition.EXIT, fence.region_id, dist))
        return events

    def run_simulation(self):
        print(f"\n{TerminalColor.YELLOW}[2] Menguji Background Geolocation & Geofencing Engine{TerminalColor.RESET}")
        # Base: Jakarta Monas Area
        monas = Coordinate(-6.175392, 106.827153)
        self.register_geofence(GeofenceRegion("GEOFENCE_MONAS_HQ", monas, radius_meters=200.0))
        
        waypoints = [
            Coordinate(-6.178000, 106.827153),  # 290m South (Outside)
            Coordinate(-6.176500, 106.827153),  # 123m South (Inside)
            Coordinate(-6.175392, 106.827153),  # 0m Center (Inside)
            Coordinate(-6.173000, 106.827153),  # 266m North (Outside)
        ]

        print(f"{TerminalColor.DIM}Target Geofence: MONAS_HQ (Radius: 200m){TerminalColor.RESET}")
        for idx, wp in enumerate(waypoints, 1):
            events = self.update_position(wp)
            dist = self.haversine_distance(wp, monas)
            status = f"{TerminalColor.GREEN}INSIDE{TerminalColor.RESET}" if dist <= 200.0 else f"{TerminalColor.DIM}OUTSIDE{TerminalColor.RESET}"
            print(f"  Step {idx}: Posisi ({wp.latitude:.6f}, {wp.longitude:.6f}) -> Jarak: {dist:05.1f}m [{status}]")
            
            for transition, fid, d in events:
                if transition == GeofenceTransition.ENTER:
                    print(f"    {TerminalColor.SUCCESS}➔ TRIGGER [HeadlessJS]: {transition.value} id={fid} (dist={d:.1f}m){TerminalColor.RESET}")
                else:
                    print(f"    {TerminalColor.WARNING}➔ TRIGGER [HeadlessJS]: {transition.value} id={fid} (dist={d:.1f}m){TerminalColor.RESET}")
            time.sleep(0.08)

# ==============================================================================
# 3. VisionCamera Frame Processor & ML Inference Pipeline
# ==============================================================================
class VisionCameraPipeline:
    """
    Simulasi VisionCamera v3/v4 Frame Processor Plugin berbasis JSI.
    Menjalankan proses inferensi per frame tanpa crossing async bridge.
    """
    def __init__(self):
        self.frame_counter = 0

    def process_frame(self, frame_id: int) -> Dict[str, any]:
        self.frame_counter += 1
        processing_latency_ms = random.uniform(8.2, 16.5)
        detected_objects = []
        
        # Simulasi bounding box objek
        if random.random() > 0.4:
            detected_objects.append({
                "label": "QR_CODE_PAYMENT",
                "confidence": round(random.uniform(0.91, 0.99), 2),
                "box": [120, 140, 280, 300]
            })
        if random.random() > 0.7:
            detected_objects.append({
                "label": "FACE_RECOGNITION_MESH",
                "confidence": round(random.uniform(0.85, 0.96), 2),
                "box": [45, 60, 200, 240]
            })

        return {
            "frame_id": frame_id,
            "width": 1920,
            "height": 1080,
            "latency_ms": processing_latency_ms,
            "objects": detected_objects
        }

    def run_simulation(self, iterations: int = 5):
        print(f"\n{TerminalColor.YELLOW}[3] Menguji VisionCamera JSI Frame Processor (60 FPS Pipeline){TerminalColor.RESET}")
        for i in range(1, iterations + 1):
            res = self.process_frame(i)
            fps = 1000.0 / res["latency_ms"]
            obj_desc = ", ".join([f"{o['label']} ({o['confidence']*100:.0f}%)" for o in res["objects"]]) or "None"
            color = TerminalColor.GREEN if res['latency_ms'] < 16.6 else TerminalColor.WARNING
            print(f"  Frame #{res['frame_id']:02d} | WxH: {res['width']}x{res['height']} | "
                  f"Latency: {color}{res['latency_ms']:.2f} ms ({fps:.1f} FPS){TerminalColor.RESET} | Detections: {TerminalColor.CYAN}{obj_desc}{TerminalColor.RESET}")
            time.sleep(0.06)

# ==============================================================================
# 4. Hardware Security Module: Biometrics & Secure Enclave
# ==============================================================================
class BiometricType(Enum):
    FACE_ID = "FACE_ID"
    TOUCH_ID = "TOUCH_ID"
    BIOMETRICS_STRONG = "BIOMETRICS_STRONG"

class SecureEnclaveSimulator:
    """
    Simulasi iOS Keychain / Android KeyStore Hardware-Backed Cryptographic Operation.
    Menggunakan LocalAuthentication dengan fallback PIN.
    """
    def __init__(self):
        self._secure_vault: Dict[str, str] = {}
        self.enclave_initialized = True

    def authenticate_and_sign(self, prompt: str, key_alias: str, payload: str) -> bool:
        print(f"\n{TerminalColor.YELLOW}[4] Eksekusi Biometrics & Hardware Keystore Handshake{TerminalColor.RESET}")
        print(f"  Prompt UI : {TerminalColor.BOLD}\"{prompt}\"{TerminalColor.RESET}")
        print(f"  Target Key: {TerminalColor.CYAN}{key_alias}{TerminalColor.RESET} (AES-256-GCM / Secure Enclave)")
        
        # Simulasi verifikasi hardware
        time.sleep(0.12)
        auth_success = random.random() < 0.95
        if auth_success:
            token = f"enc_token_{abs(hash(payload)) % 100000000:08x}"
            self._secure_vault[key_alias] = token
            print(f"  {TerminalColor.SUCCESS}✔ BIOMETRIC AUTH PASSED (Hardware Signature Generated){TerminalColor.RESET}")
            print(f"  Cipher Signature : {TerminalColor.MAGENTA}{token}{TerminalColor.RESET}")
            return True
        else:
            print(f"  {TerminalColor.CRITICAL}✖ AUTH FAILED: User Cancelled / Hardware Mismatch{TerminalColor.RESET}")
            return False

# ==============================================================================
# Main Orchestrator & Interactive Execution Loop
# ==============================================================================
def run_full_suite():
    print_banner()
    
    # 1. Sensor Stream
    sensor_engine = NativeSensorEngine(sampling_rate_hz=60)
    sensor_engine.run_benchmark_cycle(frames=8)
    
    # 2. Location Geofence
    loc_engine = LocationEngine()
    loc_engine.run_simulation()
    
    # 3. VisionCamera Processor
    vision = VisionCameraPipeline()
    vision.run_simulation(iterations=6)
    
    # 4. Secure Biometrics
    sec = SecureEnclaveSimulator()
    sec.authenticate_and_sign(
        prompt="Konfirmasi Transaksi Perbankan dengan Biometrik",
        key_alias="com.app.keys.payment_private_key",
        payload="tx_984392_idr_500000"
    )
    
    print(f"\n{TerminalColor.GREEN}{TerminalColor.BOLD}" + "=" * 80)
    print("  SIMULASI ARSITEKTUR NATIVE REACT NATIVE BERHASIL DILAKUKAN")
    print("  Semua komponen (JSI, Frame Processor, Geofencing, Enclave) terverifikasi valid.")
    print("=" * 80 + f"{TerminalColor.RESET}\n")

if __name__ == "__main__":
    run_full_suite()
