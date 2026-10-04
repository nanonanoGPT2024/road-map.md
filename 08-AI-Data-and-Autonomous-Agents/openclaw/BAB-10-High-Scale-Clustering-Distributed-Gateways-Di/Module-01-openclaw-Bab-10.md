# Bab 10: High-Scale Clustering, Distributed Gateways, & Disaster Recovery
## Module 01: Distributed Gateway Architecture, Cluster Membership, & High-Availability Session Routing

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Merancang arsitektur Distributed Gateway** untuk autonomous agent workloads yang memerlukan *sticky execution context*, koneksi persisten (WebSocket/gRPC), dan routing berlatensi rendah.
- **Mengimplementasikan Consistent Hash Ring dengan Virtual Nodes** untuk mendistribusikan beban eksekusi agentic crawler (*openclaw*) secara deterministik tanpa *hotspotting*.
- **Membangun mekanisme Failure Detection dan Cluster Membership** berbasis distributed heartbeats dan lease-renewal (menggunakan model konsensus terdistribusi) guna memitigasi kondisi *split-brain*.
- **Mengembangkan strategi Disaster Recovery (DR)** multi-region dengan parameter RPO (*Recovery Point Objective*) $< 5$ detik dan RTO (*Recovery Time Objective*) $< 30$ detik untuk *stateful browser automation workloads*.
- **Menganalisis dan memitigasi kegagalan kaskade (*cascading failure*)** pada kluster berskala besar menggunakan *circuit breaker*, *exponential backoff with jitter*, dan *graceful task draining*.

---

### 2. Concept Overview

Dalam ekosistem agentic data extraction seperti **OpenClaw**, agent tidak bersifat *stateless* murni layaknya web server konvensional. Satu eksekusi agent dapat memakan waktu beberapa detik hingga beberapa jam, mempertahankan browser context (DOM, cookies, CDP - Chrome DevTools Protocol session), LLM working memory, dan soket streaming real-time.

```
+-----------------------------------------------------------------------------+
|                                MENTAL MODEL                                 |
|                                                                             |
|      Ingress Request (Scrape Task / Interactive Agent Loop)                  |
|                           │                                                 |
|                           ▼                                                 |
|             ┌───────────────────────────┐                                   |
|             │    Distributed Gateway    │ ───► Stateless Ingress Layer      |
|             │       (Proxy Mesh)        │      (TLS, Auth, Rate-Limit)      |
|             └─────────────┬─────────────┘                                   |
|                           │ Hashing via Virtual Nodes Ring                  |
|                           ▼                                                 |
|             ┌───────────────────────────┐                                   |
|             │    Distributed Registry   │ ───► Consensus Plane              |
|             │     (State & Leases)      │      (etcd / Raft Consensus)      |
|             └─────────────┬─────────────┘                                   |
|                           │ Session Routing Token Bound                     |
|                           ▼                                                 |
|             ┌───────────────────────────┐                                   |
|             │    Clustered Agent Pod    │ ───► Stateful Worker Plane        |
|             │ (Browser Instance, Cache) │      (Isolated Contexts)          |
|             └───────────────────────────┘                                   |
+-----------------------------------------------------------------------------+
```

Arsitektur kluster OpenClaw bertumpu pada tiga abstraksi inti:

1. **Distributed Gateway Mesh**: Layer *ingress* yang menerima instruksi agentic run, memvalidasi otentikasi, dan memetakan tugas ke simpul pekerja yang tepat menggunakan skema *consistent hashing*.
2. **Cluster Topology & Membership**: Sistem koordinasi dinamis yang memonitor ketersediaan simpul (*node liveness*) secara real-time melalui *heartbeat lease*. Kegagalan simpul memicu perubahan topologi secara instan.
3. **Session Stickiness & Handover**: Mekanisme yang menjamin agen interaktif tetap terhubung ke *worker node* yang sama selama *browser session* aktif, namun siap melakukan *state dehydration* dan *rehydration* ke simpul cadangan saat terjadi *catastrophic failure*.

---

### 3. Why It Matters

Ketika mengorkestrasi ribuan agen otonom untuk *large-scale distributed crawling*:
- **Bottleneck Sentralisasi**: Arsitektur monolithic scheduler (seperti single Celery Master atau standard HTTP load balancer) runtuh ketika menangani puluhan ribu koneksi duplex WebSocket/gRPC streaming secara persisten.
- **Biaya Kehilangan State**: Jika satu worker node mati di tengah proses navigasi interaktif multi-step (misalnya: bypass challenge, parsing dynamic SPA, checkout emulation), hilangnya session state mewajibkan eksekusi ulang dari awal. Hal ini melipatgandakan konsumsi token LLM dan kuota *residential proxy*.
- **Split-Brain Risk**: Partisi jaringan antar availability zone dapat menyebabkan dua gateway master mengklaim kepemilikan partisi agent task yang sama, memicu *duplicate scraping*, *rate-limit ban* dari target situs, dan korupsi data penyimpanan.
- **Enterprise SLA**: Korporasi menuntut availabilitas $99.99\%$ dengan jaminan kelangsungan operasional lintas region jika seluruh data center penyedia *cloud* utama mengalami pemadaman total (*outage*).

---

### 4. Arsitektur & Diagram Komponen

Berikut adalah topologi Active-Passive Multi-Region Cluster dengan Distributed Gateway Mesh:

```
[ Edge DNS / Anycast IP ]
           │
     ┌─────┴────────────────────────────────┐
     │ Route53 / Cloudflare Geo-Routing     │
     └─────┬──────────────────────────┬─────┘
           │ (Active Region)          │ (Passive/DR Standby)
           ▼                          ▼
=============================   =============================
REGION ALPHA (PRIMARY)          REGION BRAVO (SECONDARY)
=============================   =============================
┌─────────────────────────┐     ┌─────────────────────────┐
│ Layer 4 Load Balancer   │     │ Layer 4 Load Balancer   │
│ (AWS NLB / HAProxy TCP) │     │ (AWS NLB / HAProxy TCP) │
└────────────┬────────────┘     └────────────┬────────────┘
             │                               │
    ┌────────┴────────┐             ┌────────┴────────┐
    ▼                 ▼             ▼                 ▼
┌───────┐         ┌───────┐     ┌───────┐         ┌───────┐
│GW-01  │ ◄─GOSSIP─► GW-02│     │GW-03  │ ◄─GOSSIP─► GW-04│
└───┬───┘         └───┬───┘     └───┬───┘         └───┬───┘
    │                 │             │                 │
    └────────┬────────┘             └────────┬────────┘
             ▼                               ▼
    [ Consistent Hash ]             [ Consistent Hash ]
    [ Ring Topology   ]             [ Ring Topology   ]
             │                               │
    ┌────────┴────────┐                      │
    │  Internal gRPC  │                      │
    ▼                 ▼                      │
┌───────┐         ┌───────┐                  │
│Worker1│         │Worker2│                  │
│(Head- │         │(Head- │                  │
│ less) │         │ less) │                  │
└───┬───┘         └───┬───┘                  │
    │                 │                      │
    └────────┬────────┘                      │
             ▼                               ▼
  ┌─────────────────────┐       ┌─────────────────────┐
  │ etcd Cluster        │       │ etcd Cluster        │
  │ (Region Alpha State)│       │ (Region Bravo State)│
  └──────────┬──────────┘       └──────────▲──────────┘
             │                             │
             │   Asynchronous Replication  │
             └─────────────────────────────┘
             (State Snapshot & WAL Sync via S3/Kafka)
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### Consistent Hash Ring dengan Virtual Nodes
Untuk mencegah redistribusi total sesi agen ketika worker node ditambah atau dikurangi, OpenClaw mengimplementasikan *Consistent Hashing* berbasis algoritma Murmur3 atau SHA-256. Setiap node fisik dipetakan ke $V$ buah *virtual nodes* pada ruang cincin ukuran integer $2^{32}-1$.

$$RingPos = Hash(NodeID + "\#vnode\_" + i) \pmod{2^{32}}$$

Ketika tugas baru dengan `session_id` masuk:
1. Hitung $Hash(session\_id)$.
2. Lakukan pencarian biner (*binary search*) untuk menemukan simpul virtual pertama yang posisinya $\ge Hash(session\_id)$.
3. Rutekan trafik ke simpul fisik pemilik simpul virtual tersebut.
4. Jika simpul tersebut tidak merespon, lanjutkan iterasi searah jarum jam (*successor walk*) ke simpul fisik berikutnya.

#### Lease-Based Failure Detection (Phi Accrual Alternative)
Koneksi agen bersifat kritikal. Sistem menggunakan distributed key-value store (etcd/Consul pattern) dengan *heartbeat lease*:
- Setiap node worker wajib memperbarui *lease* setiap $TTL / 3$ detik (misal: TTL 6 detik, interval heartbeat 2 detik).
- Jika lease kedaluwarsa, gateway mendeteksi *tombstone* event via etcd watcher.
- Node yang bersangkutan dikeluarkan dari *in-memory Hash Ring* seluruh gateway seketika. Sesi yang terdampak didistribusikan ulang ke successor node.

---

### 6. Production-Ready Code Implementation

Berikut adalah implementasi lengkap Distributed Gateway Engine dalam Python 3.12 modern dengan `asyncio`, type-hinting ketat, clean architecture, hash ring terdistribusi, deteksi kegagalan, dan failover session routing.

```python
"""
OpenClaw Distributed Gateway & Dynamic Cluster Membership Engine.
Designed for high-scale agent orchestration with fault tolerance.
"""

from __future__ import annotations

import asyncio
import bisect
import hashlib
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Coroutine, Dict, List, Optional, Set

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s"
)
logger = logging.getLogger("OpenClaw.Gateway")


class NodeStatus(str, Enum):
    HEALTHY = "HEALTHY"
    SUSPECT = "SUSPECT"
    DEAD = "DEAD"
    DRAINING = "DRAINING"


@dataclass(frozen=True)
class AgentSession:
    session_id: str
    tenant_id: str
    target_url: str
    created_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkerNode:
    node_id: str
    host: str
    port: int
    weight: int = 100
    status: NodeStatus = NodeStatus.HEALTHY
    last_heartbeat: float = field(default_factory=time.time)

    @property
    def endpoint(self) -> str:
        return f"{self.host}:{self.port}"


class ConsistentHashRing:
    """
    Consistent Hash Ring implementation with Virtual Nodes to ensure
    equitable distribution of agent workloads without hotspotting.
    """

    def __init__(self, virtual_nodes_count: int = 150) -> None:
        self.virtual_nodes_count: int = virtual_nodes_count
        self.ring: Dict[int, str] = {}  # Hash value -> Node ID
        self.sorted_keys: List[int] = []  # Sorted hash values for binary search
        self.nodes: Dict[str, WorkerNode] = {}
        self._lock: asyncio.Lock = asyncio.Lock()

    def _hash(self, key: str) -> int:
        return int(hashlib.sha256(key.encode("utf-8")).hexdigest()[:8], 16)

    async def add_node(self, node: WorkerNode) -> None:
        async with self._lock:
            if node.node_id in self.nodes:
                logger.warning("Node %s already exists. Updating definition.", node.node_id)
            self.nodes[node.node_id] = node
            
            # Virtual nodes proportional to weight
            vnodes = int(self.virtual_nodes_count * (node.weight / 100.0))
            for i in range(vnodes):
                v_key = f"{node.node_id}#vnode_{i}"
                h_val = self._hash(v_key)
                self.ring[h_val] = node.node_id
                bisect.insort(self.sorted_keys, h_val)
                
            logger.info("Node %s registered with %d vnodes.", node.node_id, vnodes)

    async def remove_node(self, node_id: str) -> None:
        async with self._lock:
            if node_id not in self.nodes:
                return

            vnodes = int(self.virtual_nodes_count * (self.nodes[node_id].weight / 100.0))
            for i in range(vnodes):
                v_key = f"{node_id}#vnode_{i}"
                h_val = self._hash(v_key)
                if h_val in self.ring:
                    del self.ring[h_val]
                    idx = bisect.bisect_left(self.sorted_keys, h_val)
                    if idx < len(self.sorted_keys) and self.sorted_keys[idx] == h_val:
                        self.sorted_keys.pop(idx)

            del self.nodes[node_id]
            logger.warning("Node %s successfully stripped from hash ring.", node_id)

    async def get_node(self, session_key: str, excluded_nodes: Optional[Set[str]] = None) -> Optional[WorkerNode]:
        async with self._lock:
            if not self.ring:
                return None

            excluded = excluded_nodes or set()
            h_val = self._hash(session_key)
            idx = bisect.bisect_right(self.sorted_keys, h_val)

            total_keys = len(self.sorted_keys)
            for step in range(total_keys):
                curr_idx = (idx + step) % total_keys
                target_hash = self.sorted_keys[curr_idx]
                target_node_id = self.ring[target_hash]

                if target_node_id in excluded:
                    continue

                candidate = self.nodes.get(target_node_id)
                if candidate and candidate.status == NodeStatus.HEALTHY:
                    return candidate

            return None


class DistributedClusterGateway:
    """
    Core L7 Gateway router responsible for session lifecycle, health check 
    reconciliation, and automatic failover dispatching.
    """

    def __init__(self, ring: ConsistentHashRing, heartbeat_timeout: float = 5.0) -> None:
        self.ring: ConsistentHashRing = ring
        self.heartbeat_timeout: float = heartbeat_timeout
        self.active_sessions: Dict[str, str] = {}  # session_id -> node_id
        self._is_running: bool = False
        self._monitor_task: Optional[asyncio.Task[None]] = None

    async def start(self) -> None:
        self._is_running = True
        self._monitor_task = asyncio.create_task(self._health_check_reconciliation_loop())
        logger.info("Distributed Gateway Orchestrator online.")

    async def stop(self) -> None:
        self._is_running = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        logger.info("Distributed Gateway Orchestrator halted cleanly.")

    async def register_heartbeat(self, node_id: str) -> bool:
        node = self.ring.nodes.get(node_id)
        if not node:
            logger.error("Heartbeat rejected: Unrecognized node %s", node_id)
            return False

        node.last_heartbeat = time.time()
        if node.status != NodeStatus.HEALTHY:
            node.status = NodeStatus.HEALTHY
            logger.info("Node %s marked HEALTHY via lease renewal.", node_id)
        return True

    async def route_agent_session(self, session: AgentSession) -> WorkerNode:
        """
        Routes an agent session to the appropriate worker. 
        Guarantees fallback if primary node crashes.
        """
        excluded: Set[str] = set()
        
        # Check if existing session was assigned to an alive node
        if session.session_id in self.active_sessions:
            assigned_id = self.active_sessions[session.session_id]
            assigned_node = self.ring.nodes.get(assigned_id)
            if assigned_node and assigned_node.status == NodeStatus.HEALTHY:
                return assigned_node
            else:
                logger.warning(
                    "Assigned node %s for session %s is unhealthy/missing. Triggering failover.",
                    assigned_id, session.session_id
                )
                excluded.add(assigned_id)

        # Resolve node via Hash Ring with failover walking
        selected_node = await self.ring.get_node(session.session_id, excluded_nodes=excluded)
        if not selected_node:
            raise RuntimeError("Fatal: Zero healthy worker nodes available in cluster topology.")

        self.active_sessions[session.session_id] = selected_node.node_id
        logger.info(
            "Session %s bound to worker %s (%s)", 
            session.session_id, selected_node.node_id, selected_node.endpoint
        )
        return selected_node

    async def evict_session(self, session_id: str) -> None:
        if session_id in self.active_sessions:
            node_id = self.active_sessions.pop(session_id)
            logger.info("Evicted session %s previously bound to %s", session_id, node_id)

    async def _health_check_reconciliation_loop(self) -> None:
        """
        Periodically checks lease expiration and evicts dead nodes.
        """
        while self._is_running:
            try:
                await asyncio.sleep(1.0)
                now = time.time()
                nodes_to_evict: List[str] = []

                for node_id, node in list(self.ring.nodes.items()):
                    elapsed = now - node.last_heartbeat
                    if elapsed > self.heartbeat_timeout and node.status == NodeStatus.HEALTHY:
                        node.status = NodeStatus.DEAD
                        logger.error(
                            "Node %s heartbeat timed out (%.2fs elapsed). Evicting from cluster!",
                            node_id, elapsed
                        )
                        nodes_to_evict.append(node_id)

                for dead_node_id in nodes_to_evict:
                    await self.ring.remove_node(dead_node_id)
                    # Rebalance impacted sessions
                    orphaned = [s_id for s_id, n_id in self.active_sessions.items() if n_id == dead_node_id]
                    for s_id in orphaned:
                        del self.active_sessions[s_id]
                        logger.info("Session %s marked for dynamic migration.", s_id)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.critical("Unexpected error in health reconciliation: %s", str(e), exc_info=True)


# Validation & Integration Runner
async def main() -> None:
    ring = ConsistentHashRing(virtual_nodes_count=50)
    gateway = DistributedClusterGateway(ring, heartbeat_timeout=3.0)
    await gateway.start()

    # Initialize 3 worker nodes
    w1 = WorkerNode(node_id="worker-us-east-1", host="10.0.1.10", port=9000, weight=100)
    w2 = WorkerNode(node_id="worker-us-east-2", host="10.0.1.11", port=9000, weight=100)
    w3 = WorkerNode(node_id="worker-us-east-3", host="10.0.1.12", port=9000, weight=100)

    await ring.add_node(w1)
    await ring.add_node(w2)
    await ring.add_node(w3)

    # Dispatched Sessions
    sessions = [
        AgentSession(session_id=f"sess-alpha-{i}", tenant_id="corp-a", target_url="https://example.com/scrape")
        for i in range(5)
    ]

    for sess in sessions:
        node = await gateway.route_agent_session(sess)
        logger.info("Route initial: %s -> %s", sess.session_id, node.node_id)

    # Simulate node-2 crashing (cease heartbeats)
    logger.info(">>> Simulating sudden network partition/crash on worker-us-east-2...")
    for _ in range(4):
        await gateway.register_heartbeat("worker-us-east-1")
        await gateway.register_heartbeat("worker-us-east-3")
        await asyncio.sleep(1.0)

    logger.info(">>> Re-evaluating routing for all sessions...")
    for sess in sessions:
        node = await gateway.route_agent_session(sess)
        logger.info("Route post-failure: %s -> %s", sess.session_id, node.node_id)

    await gateway.stop()


if __name__ == "__main__":
    asyncio.run(main())
```

---

### 7. Edge Cases & Failure Modes

| Failure Mode | Mekanisme Terjadinya | Dampak Sistem | Mitigasi Engineering |
| :--- | :--- | :--- | :--- |
| **Split-Brain Condition** | Partisi jaringan antar AZ memisahkan gateway cluster menjadi dua partisi berukuran setara. | Dua node worker mengeksekusi sub-task agentik yang sama; race condition pada write target database. | Implementasikan *Quorum-based consensus* (misal: Raft di etcd, minimal $\lfloor N/2 \rfloor + 1$ suara node). Partisi minoritas otomatis beralih ke *read-only safe mode*. |
| **Thundering Herd Rehash** | Satu worker besar crash; ribuan sesi browser bersamaan dialihkan (*failover*) ke successor node. | Successor node mengalami lonjakan CPU/Memory instan (*OOM crash*), memicu *cascading collapse* beruntun. | Implementasikan *Bounded Load Consistent Hashing* (RFC algorithm) dan gunakan *Circuit Breaker* dengan rate-limited task handoff queue. |
| **Flapping / Jitter Node** | Node mengalami packet loss intermiten; heartbeat telat secara berkala disusul recovery singkat. | Hash ring terus berubah secara konstan; pemindahan sesi tanpa henti memicu degradasi throughput. | Mekanisme *Decay Penalty Score*: Jika node flap $> 3$ kali dalam 5 menit, tetapkan status `SUSPECT` dan karantina selama 15 menit. |
| **Zombie Execution Context** | Gateway menganggap node DEAD dan memigrasikan tugas, tetapi browser headless di node lama masih berjalan. | Target domain memblokir proxy IP karena duplikasi crawling; penggunaan resource membengkak tak terkontrol. | Gunakan *Fencing Tokens* (monotonically increasing epoch number) pada setiap instruksi mutasi dan request output. |

---

### 8. Trade-offs & Alternatif Solusi

#### 1. Consistent Hashing vs. Centralized Dynamic Directory (Redis/DB Lookup)
- **Consistent Hashing**:
  - *Kelebihan*: Stateless lookup di level gateway ($O(\log V)$ via binary search ring), throughput jutaan request/detik tanpa dependency database tersentral.
  - *Kekurangan*: Rebalancing ring tidak sepenuhnya sempurna secara presisi beban (*load skew* mungkin terjadi pada cluster kecil).
- **Centralized Directory**:
  - *Kelebihan*: Distribusi beban absolut (*least-connection scheduling* sempurna).
  - *Kekurangan*: Single bottleneck dan SPOF; kegagalan cluster Redis menghentikan perutean seluruh gateway.

#### 2. Gossip Protocol (SWIM) vs. Distributed Lease (etcd/Consul)
- **SWIM/Gossip (e.g., HashiCorp Memberlist)**:
  - Skalabilitas sangat tinggi ($O(\log N)$ bandwidth), tidak memerlukan cluster quorum khusus. Namun, sifatnya *eventual consistency*, berisiko terjadi inkonsistensi routing sesaat selama periode partisi.
- **Lease Consensus (etcd)**:
  - *Strong consistency* (linearizable). Keputusan failover bersifat mutlak tanpa tumpang-tindih. Memerlukan infrastruktur etcd berlatensi rendah ($< 10$ ms disk/network sync).

#### 3. Active-Active Multi-Region vs. Active-Passive Cold DR
- **Active-Active**:
  - *Zero downtime*, trafik global langsung dialihkan via DNS latency routing. Biaya komputasi $2\times$ lebih tinggi; sinkronisasi state agent antar-region memerlukan konsistensi replikasi yang sangat kompleks.
- **Active-Passive (Warm Standby)**:
  - Biaya efisien (node pasif berskala kecil, autoscaling saat disaster). RTO berkisar antara 30-120 detik untuk menghidupkan resource browser container.

---

### 9. Best Practices & Standar Industri

1. **Graceful Draining Sebelum Shutdown (`SIGTERM`)**:
   Ketika node worker akan dihentikan untuk deployment (*rolling update*):
   - Kirim sinyal ke Gateway untuk menandai node berstatus `DRAINING`.
   - Node berhenti menerima sesi *agent baru*, tetapi mempertahankan sesi aktif hingga selesai (maksimal timeout, misal 5 menit).
   - Setelah semua browser context ditutup, proses node dihentikan (`SIGKILL`).

2. **Fencing Tokens untuk State Consistency**:
   Setiap alokasi sesi harus membawa epoch ID berurutan dari konsensus store. Simpul penyimpanan data (PostgreSQL/S3) wajib menolak penulisan data dari node yang membawa token lebih rendah daripada token tertinggi yang telah tercatat.

3. **Multi-Region Disaster Recovery Automation**:
   - Backup etcd metadata secara periodik (setiap 1 jam) ke cross-region encrypted S3/GCS bucket.
   - Konfigurasi DNS Health Checks dengan TTL rendah (15-30 detik) yang secara otomatis melakukan failover jika primary region gateway tidak merespons HTTP `200` pada endpoint `/healthz`.

4. **Metrik Observabilitas Minimum (Prometheus)**:
   - `openclaw_gateway_active_connections{protocol="grpc|ws"}`
   - `openclaw_cluster_ring_nodes_total{status="healthy|dead|draining"}`
   - `openclaw_session_failover_total{source_node, target_node, reason}`
   - `openclaw_node_heartbeat_latency_seconds_bucket`

---

### 10. Hands-on Lab Exercise

#### Skenario Lab
Anda diminta untuk men-deploy simulasi Gateway Cluster 3-node, mengarahkan 10 sesi crawling aktif, memicu kegagalan simulasi pada salah satu worker node, dan memverifikasi bahwa failover terjadi otomatis dalam kurun waktu $\le 3$ detik tanpa menjatuhkan state sesi yang tersisa.

#### Langkah 1: Persiapan Environment
Pastikan Anda memiliki runtime Python 3.12+. Simpan kode implementasi pada Section 6 sebagai file `cluster_gateway.py`.

#### Langkah 2: Eksekusi Skenario Failover
Jalankan script menggunakan terminal:
```bash
python3 cluster_gateway.py
```

#### Langkah 3: Modifikasi Verifikasi (Failure Injection)
Buka file `cluster_gateway.py` dan tambahkan skenario pengujian partisi jaringan dinamis pada fungsi `main()`:

```python
    # Tambahan: Injeksi pengujian failover bertingkat
    logger.info("=== LAB TEST: Injeksi Pemadaman Node Masif ===")
    
    # Matikan worker-us-east-1 seketika
    logger.info("Memutuskan koneksi worker-us-east-1...")
    await ring.remove_node("worker-us-east-1")
    
    # Verifikasi apakah sesi yang awalnya di-assign ke worker-us-east-1
    # berhasil dialihkan ke worker-us-east-3 yang tersisa
    for sess in sessions:
        resolved = await gateway.route_agent_session(sess)
        assert resolved.node_id != "worker-us-east-1", f"FAIL: Sesi masih terikat ke dead node {resolved.node_id}"
        logger.info("Assertion Passed: Session %s aman di node %s", sess.session_id, resolved.node_id)
        
    logger.info("=== LAB TEST BERHASIL: Semua state terisolasi & dialihkan ===")
```

#### Langkah 4: Kriteria Evaluasi
- [x] Node yang mengalami kegagalan heartbeat dikeluarkan dari hash ring secara deterministik.
- [x] Sesi agen yang aktif tidak mengalami exception `NoneType` saat di-resolve ulang.
- [x] Log menunjukkan transisi status node dari `HEALTHY` ke `DEAD` tanpa memicu crash pada Gateway orchestrator.
- [x] Distribusi sesi baru terdistribusi secara seimbang ke node yang masih bertahan.