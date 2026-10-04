#!/usr/bin/env python3
"""
Global Traffic Steering & Load Balancing Engine Simulator
Simulates Cloudflare's Edge Anycast L7 Steering, Health Probing, 
Session Affinity Draining, and Argo Smart Routing Optimization.

Author: Cloud & SRE Curriculum Architect
Language: Python 3.9+ (Zero External Dependencies)
"""

import time
import math
import random
import hashlib
import json
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple

# --- DATA MODELS ---

@dataclass
class Origin:
    name: str
    ip_address: str
    weight: float
    healthy: bool = True
    active_connections: int = 0
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    drain_mode: bool = False

@dataclass
class OriginPool:
    id: str
    name: str
    region: str
    origins: List[Origin]
    minimum_origins: int = 1
    fallback: bool = False

    @property
    def healthy_origins(self) -> List[Origin]:
        return [o for o in self.origins if o.healthy and not o.drain_mode]

    @property
    def is_healthy(self) -> bool:
        if self.fallback:
            return True
        return len(self.healthy_origins) >= self.minimum_origins

@dataclass
class HealthMonitor:
    path: str
    expected_code: int
    expected_body: str
    timeout_sec: float
    interval_sec: float
    consecutive_fails_threshold: int = 3
    consecutive_success_threshold: int = 2

@dataclass
class ClientSession:
    session_id: str
    target_pool_id: str
    target_origin_name: str
    created_at: float
    ttl_seconds: float

# --- SIMULATOR ENGINE ---

class CloudflareGLBSimulator:
    def __init__(self, steering_policy: str = "dynamic_latency"):
        self.steering_policy = steering_policy  # geo, dynamic_latency, or off
        self.pools: Dict[str, OriginPool] = {}
        self.fallback_pool_id: Optional[str] = None
        self.monitor: Optional[HealthMonitor] = None
        self.geo_mappings: Dict[str, List[str]] = {}  # Country -> [Pool IDs]
        self.sessions: Dict[str, ClientSession] = {}
        self.argo_enabled: bool = True
        self.tiered_cache_enabled: bool = True

        # Mock synthetic network latency matrix (Edge Region -> Pool Region) in ms
        self.base_latency_matrix = {
            "ID_JKT": {"APAC": 15, "EU": 180, "US": 220},
            "US_EAST": {"APAC": 210, "EU": 85, "US": 20},
            "EU_WEST": {"APAC": 190, "EU": 15, "US": 90},
        }

    def add_pool(self, pool: OriginPool, is_fallback: bool = False):
        self.pools[pool.id] = pool
        if is_fallback:
            self.fallback_pool_id = pool.id

    def set_monitor(self, monitor: HealthMonitor):
        self.monitor = monitor

    def map_geo_country(self, country_code: str, pool_ids: List[str]):
        self.geo_mappings[country_code] = pool_ids

    # --- HEALTH PROBING LOGIC ---

    def execute_health_probe(self, origin_simulation_responses: Dict[str, Tuple[int, str, float]]):
        """
        Simulates active probes sent from multiple colos to each origin.
        origin_simulation_responses: Dict[origin_name -> (status_code, body, response_time)]
        """
        print("\n" + "="*50)
        print(" [MONITOR] Executing Synthetic Active Health Probes...")
        print("="*50)
        
        for pool_id, pool in self.pools.items():
            if pool.fallback:
                continue
            for origin in pool.origins:
                status, body, rtt = origin_simulation_responses.get(
                    origin.name, (200, self.monitor.expected_body, 0.05)
                )

                # Evaluasi kriteria kesehatan L7
                is_probe_passing = (
                    status == self.monitor.expected_code and
                    self.monitor.expected_body in body and
                    rtt <= self.monitor.timeout_sec
                )

                if is_probe_passing:
                    origin.consecutive_successes += 1
                    origin.consecutive_failures = 0
                    if origin.consecutive_successes >= self.monitor.consecutive_success_threshold:
                        if not origin.healthy:
                            print(f" [+] Origin RESTORED: {origin.name} in {pool.name} is now HEALTHY.")
                        origin.healthy = True
                else:
                    origin.consecutive_failures += 1
                    origin.consecutive_successes = 0
                    if origin.consecutive_failures >= self.monitor.consecutive_fails_threshold:
                        if origin.healthy:
                            print(f" [!] Origin FAILING: {origin.name} in {pool.name} marked UNHEALTHY (Fails={origin.consecutive_failures})")
                        origin.healthy = False

    # --- LATENCY & ARGO ENGINE ---

    def calculate_effective_latency(self, edge_region: str, pool_region: str) -> float:
        base_rtt = self.base_latency_matrix.get(edge_region, {}).get(pool_region, 250)
        if self.argo_enabled:
            # Argo Smart Routing reduces latency by 33% and mitigates public internet packet drops
            optimization_factor = 0.67
            effective_rtt = base_rtt * optimization_factor
        else:
            effective_rtt = base_rtt
        return round(effective_rtt, 2)

    # --- TRAFFIC STEERING ALGORITHMS ---

    def select_pool(self, edge_region: str, country_code: str) -> OriginPool:
        # 1. Geo-Steering Check
        if self.steering_policy == "geo" and country_code in self.geo_mappings:
            for pid in self.geo_mappings[country_code]:
                candidate = self.pools.get(pid)
                if candidate and candidate.is_healthy:
                    return candidate

        # 2. Dynamic Latency Steering
        if self.steering_policy == "dynamic_latency":
            healthy_pools = [p for p in self.pools.values() if p.is_healthy and not p.fallback]
            if healthy_pools:
                # Pilih pool dengan effective RTT terendah ke edge colo
                best_pool = min(
                    healthy_pools,
                    key=lambda p: self.calculate_effective_latency(edge_region, p.region)
                )
                return best_pool

        # 3. Off / Priority Steering
        for pool in self.pools.values():
            if pool.is_healthy and not pool.fallback:
                return pool

        # 4. Fallback Triggered if all pools unhealthy
        print(" [CRITICAL] All Primary Origin Pools Unhealthy! Routing to Fallback Pool.")
        return self.pools[self.fallback_pool_id]

    def select_origin_weighted(self, pool: OriginPool) -> Origin:
        healthy_origins = pool.healthy_origins
        if not healthy_origins:
            if pool.fallback and pool.origins:
                return pool.origins[0]
            raise RuntimeError(f"No origins available in pool {pool.name}")

        weights = [o.weight for o in healthy_origins]
        total_weight = sum(weights)
        if total_weight == 0:
            return random.choice(healthy_origins)

        # Weighted Random Distribution
        normalized_weights = [w / total_weight for w in weights]
        return random.choices(healthy_origins, weights=normalized_weights, k=1)[0]

    # --- INGRESS REQUEST HANDLING ---

    def handle_request(self, request_id: str, client_ip: str, edge_colo: str, country: str, 
                       cookie_token: Optional[str] = None) -> Dict:
        now = time.time()
        selected_origin: Optional[Origin] = None
        selected_pool: Optional[OriginPool] = None
        session_reused = False

        # 1. Session Affinity Check
        if cookie_token and cookie_token in self.sessions:
            sess = self.sessions[cookie_token]
            if (now - sess.created_at) < sess.ttl_seconds:
                # Check if affinity target pool & origin are still healthy
                target_pool = self.pools.get(sess.target_pool_id)
                if target_pool and target_pool.is_healthy:
                    origin_match = next((o for o in target_pool.origins if o.name == sess.target_origin_name), None)
                    # Even if draining, allow session to finish
                    if origin_match and (origin_match.healthy or origin_match.drain_mode):
                        selected_pool = target_pool
                        selected_origin = origin_match
                        session_reused = True

        # 2. Dynamic Routing if No Session or Session Target Dead
        if not selected_origin or not selected_pool:
            selected_pool = self.select_pool(edge_colo, country)
            selected_origin = self.select_origin_weighted(selected_pool)
            
            # Generate new session affinity token
            raw_hash = f"{client_ip}:{selected_origin.name}:{now}"
            cookie_token = hashlib.sha256(raw_hash.encode()).hexdigest()[:16]
            self.sessions[cookie_token] = ClientSession(
                session_id=cookie_token,
                target_pool_id=selected_pool.id,
                target_origin_name=selected_origin.name,
                created_at=now,
                ttl_seconds=3600
            )

        latency = self.calculate_effective_latency(edge_colo, selected_pool.region)

        return {
            "request_id": request_id,
            "edge_colo": edge_colo,
            "client_country": country,
            "pool_selected": selected_pool.name,
            "origin_selected": selected_origin.name,
            "latency_ms": latency,
            "session_affinity_active": session_reused,
            "cookie_token": cookie_token,
            "argo_smart_routing": self.argo_enabled
        }

# --- SIMULATION RUNNER ---

def main():
    print("==================================================================")
    print(" CLOUDFLARE GLOBAL LOAD BALANCER & ARGO SMART ROUTING SIMULATOR  ")
    print("==================================================================")

    # Inisialisasi Simulator
    glb = CloudflareGLBSimulator(steering_policy="dynamic_latency")

    # Inisialisasi Monitors
    monitor = HealthMonitor(
        path="/healthz",
        expected_code=200,
        expected_body="OK",
        timeout_sec=1.5,
        interval_sec=10.0,
        consecutive_fails_threshold=2,
        consecutive_success_threshold=2
    )
    glb.set_monitor(monitor)

    # Inisialisasi Pools
    pool_apac = OriginPool(
        id="pool_apac",
        name="APAC-Primary-Pool",
        region="APAC",
        origins=[
            Origin(name="sin-node-01", ip_address="10.0.1.1", weight=0.7),
            Origin(name="jkt-node-01", ip_address="10.0.1.2", weight=0.3)
        ],
        minimum_origins=1
    )

    pool_us = OriginPool(
        id="pool_us",
        name="US-East-Pool",
        region="US",
        origins=[
            Origin(name="iad-node-01", ip_address="10.0.2.1", weight=1.0)
        ],
        minimum_origins=1
    )

    pool_fallback = OriginPool(
        id="pool_fallback",
        name="Emergency-Static-Maintenance",
        region="APAC",
        origins=[
            Origin(name="s3-maintenance-page", ip_address="192.168.99.99", weight=1.0)
        ],
        minimum_origins=1,
        fallback=True
    )

    glb.add_pool(pool_apac)
    glb.add_pool(pool_us)
    glb.add_pool(pool_fallback, is_fallback=True)

    # Simulasi 1: Baseline Request Normal dari Klien Jakarta
    print("\n--- SKENARIO 1: Traffic Datang dari Jakarta (Dynamic Latency) ---")
    res1 = glb.handle_request("REQ-001", "203.0.113.15", "ID_JKT", "ID")
    print(json.dumps(res1, indent=2))

    # Simulasi 2: Sticky Session (Session Affinity)
    print("\n--- SKENARIO 2: Klien yang Sama Mengirim Request Kedua (Sticky Session) ---")
    res2 = glb.handle_request("REQ-002", "203.0.113.15", "ID_JKT", "ID", cookie_token=res1["cookie_token"])
    print(json.dumps(res2, indent=2))
    assert res2["origin_selected"] == res1["origin_selected"], "Affinity Failed!"

    # Simulasi 3: Degradasi Server APAC (Health Probes Mendeteksi Kegagalan)
    print("\n--- SKENARIO 3: Kegagalan Origin APAC & Otomatis Failover ke US-Pool ---")
    mock_responses = {
        "sin-node-01": (500, "Internal Server Error", 0.05),
        "jkt-node-01": (503, "Service Unavailable", 0.05),
        "iad-node-01": (200, "OK", 0.04)
    }
    # Probe 1
    glb.execute_health_probe(mock_responses)
    # Probe 2 (Mencapai batas consecutive_fails_threshold = 2)
    glb.execute_health_probe(mock_responses)

    res3 = glb.handle_request("REQ-003", "203.0.113.15", "ID_JKT", "ID")
    print("\nHasil Request Setelah APAC Mati Total:")
    print(json.dumps(res3, indent=2))
    assert res3["pool_selected"] == "US-East-Pool", "Failover ke US Pool Gagal!"

    # Simulasi 4: Seluruh Origin Padam Total -> Fallback Pool Menyerap Beban
    print("\n--- SKENARIO 4: Seluruh Origin Global Down (Bencana Total) ---")
    mock_responses["iad-node-01"] = (504, "Gateway Timeout", 2.0) # Timeout > 1.5s
    glb.execute_health_probe(mock_responses)
    glb.execute_health_probe(mock_responses)

    res4 = glb.handle_request("REQ-004", "203.0.113.15", "ID_JKT", "ID")
    print("\nHasil Request Saat Semua Pool Padam:")
    print(json.dumps(res4, indent=2))
    assert res4["pool_selected"] == "Emergency-Static-Maintenance", "Fallback Pool Gagal Aktif!"

    print("\n[V] Seluruh Simulasi Logika Traffic Steering & Failover Berhasil Diuji!")

if __name__ == "__main__":
    main()