#!/usr/bin/env python3
"""
Lab Exercise: Kubernetes Storage, Persistence, dan CSI Lifecycle Simulator
BAB-07: Storage Persistence dan Container Storage Interface (CSI)

Deskripsi:
Simulasi interaktif teknis arsitektur Kubernetes Storage:
- Dynamic Provisioning via StorageClass
- PersistentVolume (PV) dan PersistentVolumeClaim (PVC) State Machine
- CSI Architecture: External Provisioner, Attacher, Node-Driver Registrar
- Tahapan CSI: CreateVolume, ControllerPublish (Attach), NodeStage, NodePublish (Mount)
- Uji Ketahanan Data (Pod Failover & Volume Reattachment)
- Reclaim Policy Lifecycle: Delete vs Retain
"""

import time
import sys
import os
import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from enum import Enum

class Color:
    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"

class PVStatus(Enum):
    PENDING = "Pending"
    AVAILABLE = "Available"
    BOUND = "Bound"
    RELEASED = "Released"
    FAILED = "Failed"

class ReclaimPolicy(Enum):
    DELETE = "Delete"
    RETAIN = "Retain"

class BindingMode(Enum):
    IMMEDIATE = "Immediate"
    WAIT_FOR_FIRST_CONSUMER = "WaitForFirstConsumer"

@dataclass
class StorageClass:
    name: str
    provisioner: str
    reclaim_policy: ReclaimPolicy
    volume_binding_mode: BindingMode
    parameters: Dict[str, str]

@dataclass
class PersistentVolumeClaim:
    name: str
    namespace: str
    storage_class_name: str
    request_gi: int
    access_modes: List[str]
    status: str = "Pending"
    bound_pv_name: Optional[str] = None

@dataclass
class PersistentVolume:
    name: str
    capacity_gi: int
    storage_class_name: str
    reclaim_policy: ReclaimPolicy
    access_modes: List[str]
    csi_volume_id: str
    status: PVStatus = PVStatus.AVAILABLE
    claim_ref: Optional[str] = None
    node_affinity: Optional[str] = None

@dataclass
class Pod:
    name: str
    namespace: str
    node_name: Optional[str]
    pvc_name: str
    mount_path: str
    is_running: bool = False

class CSIDriverMock:
    """Simulasi CSI Plugin Controller dan Node RPC Calls"""
    def __init__(self, driver_name: str):
        self.driver_name = driver_name
        self.storage_pool = {}  # volume_id -> raw byte content

    def create_volume(self, name: str, size_gi: int, params: Dict[str, str]) -> str:
        vol_id = f"csi-vol-{os.urandom(4).hex()}"
        self.storage_pool[vol_id] = {
            "name": name,
            "size_gi": size_gi,
            "type": params.get("type", "standard-ssd"),
            "data": "INIT_SYSTEM_BLOCK:EXT4_METADATA\n",
            "attached_node": None,
            "staged": False,
            "mounted_path": None
        }
        return vol_id

    def controller_publish_volume(self, vol_id: str, node_id: str) -> bool:
        """CSI ControllerAttach: Memasang LUN/Disk virtual ke Host VM/Node"""
        if vol_id in self.storage_pool:
            self.storage_pool[vol_id]["attached_node"] = node_id
            return True
        return False

    def node_stage_volume(self, vol_id: str, staging_path: str, fs_type: str = "ext4") -> bool:
        """CSI NodeStage: Format filesystem disk global di node (/dev/xxx -> /var/lib/kubelet/plugins/...)"""
        if vol_id in self.storage_pool:
            self.storage_pool[vol_id]["staged"] = True
            self.storage_pool[vol_id]["fs_type"] = fs_type
            return True
        return False

    def node_publish_volume(self, vol_id: str, target_path: str) -> bool:
        """CSI NodePublish: Bind mount dari staging path ke Container rootfs overlay"""
        if vol_id in self.storage_pool and self.storage_pool[vol_id]["staged"]:
            self.storage_pool[vol_id]["mounted_path"] = target_path
            return True
        return False

    def node_unpublish_volume(self, vol_id: str) -> bool:
        if vol_id in self.storage_pool:
            self.storage_pool[vol_id]["mounted_path"] = None
            return True
        return False

    def controller_unpublish_volume(self, vol_id: str) -> bool:
        if vol_id in self.storage_pool:
            self.storage_pool[vol_id]["attached_node"] = None
            return True
        return False

    def delete_volume(self, vol_id: str) -> bool:
        if vol_id in self.storage_pool:
            del self.storage_pool[vol_id]
            return True
        return False

class KubeStorageEngine:
    def __init__(self):
        self.csi = CSIDriverMock("hostpath.csi.k8s.io")
        self.storage_classes: Dict[str, StorageClass] = {}
        self.pvs: Dict[str, PersistentVolume] = {}
        self.pvcs: Dict[str, PersistentVolumeClaim] = {}
        self.pods: Dict[str, Pod] = {}

    def log(self, comp: str, msg: str, color: str = Color.CYAN):
        timestamp = time.strftime("%H:%M:%S")
        print(f"{Color.DIM}[{timestamp}]{Color.RESET} {color}[{comp:^18}]{Color.RESET} {msg}")

    def register_storage_class(self, sc: StorageClass):
        self.storage_classes[sc.name] = sc
        self.log("SC-Controller", f"StorageClass '{sc.name}' terdaftar (Provisioner: {sc.provisioner}, Reclaim: {sc.reclaim_policy.value})", Color.GREEN)

    def apply_pvc(self, pvc: PersistentVolumeClaim):
        self.pvcs[pvc.name] = pvc
        self.log("PVC-Engine", f"PVC '{pvc.namespace}/{pvc.name}' ({pvc.request_gi}Gi) diajukan.", Color.YELLOW)
        
        sc = self.storage_classes.get(pvc.storage_class_name)
        if not sc:
            self.log("PVC-Engine", f"ERROR: StorageClass '{pvc.storage_class_name}' tidak ditemukan!", Color.RED)
            return

        if sc.volume_binding_mode == BindingMode.IMMEDIATE:
            self.log("PVC-Engine", f"BindingMode Immediate: Memulai Dynamic Provisioning seketika...", Color.YELLOW)
            self._trigger_dynamic_provisioning(pvc, sc)
        else:
            self.log("PVC-Engine", f"BindingMode WaitForFirstConsumer: Menunggu Pod dijadwalkan ke Node...", Color.DIM)

    def _trigger_dynamic_provisioning(self, pvc: PersistentVolumeClaim, sc: StorageClass, target_node: Optional[str] = None):
        self.log("CSI-Provisioner", f"RPC Call -> CreateVolume(Name: pvc-{pvc.name}, Size: {pvc.request_gi}Gi)", Color.BLUE)
        vol_id = self.csi.create_volume(pvc.name, pvc.request_gi, sc.parameters)
        
        pv_name = f"pv-{vol_id[-8:]}"
        pv = PersistentVolume(
            name=pv_name,
            capacity_gi=pvc.request_gi,
            storage_class_name=sc.name,
            reclaim_policy=sc.reclaim_policy,
            access_modes=pvc.access_modes,
            csi_volume_id=vol_id,
            status=PVStatus.BOUND,
            claim_ref=f"{pvc.namespace}/{pvc.name}",
            node_affinity=target_node
        )
        self.pvs[pv_name] = pv
        pvc.status = "Bound"
        pvc.bound_pv_name = pv_name
        
        self.log("PV-Controller", f"PV '{pv_name}' berhasil dibuat dan terikat (Bound) dengan PVC '{pvc.name}'", Color.GREEN)

    def schedule_pod(self, pod: Pod, node_name: str):
        self.pods[pod.name] = pod
        self.log("Kube-Scheduler", f"Pod '{pod.name}' ditempatkan pada Node: '{node_name}'", Color.CYAN)
        pod.node_name = node_name

        pvc = self.pvcs.get(pod.pvc_name)
        if not pvc:
            self.log("Kube-Scheduler", f"ERROR: PVC '{pod.pvc_name}' tidak ditemukan!", Color.RED)
            return

        sc = self.storage_classes[pvc.storage_class_name]
        if pvc.status == "Pending" and sc.volume_binding_mode == BindingMode.WAIT_FOR_FIRST_CONSUMER:
            self.log("Kube-Scheduler", f"Memicu deferred provisioning pada Node terpilih '{node_name}'", Color.YELLOW)
            self._trigger_dynamic_provisioning(pvc, sc, node_name)

        # Attaching phase
        pv = self.pvs[pvc.bound_pv_name]
        self.log("AttachDetach-Ctrl", f"RPC Call -> ControllerPublishVolume(Volume: {pv.csi_volume_id}, Node: {node_name})", Color.BLUE)
        self.csi.controller_publish_volume(pv.csi_volume_id, node_name)

        # Kubelet Node Plugin phase
        staging_dir = f"/var/lib/kubelet/plugins/kubernetes.io/csi/{sc.provisioner}/{pv.csi_volume_id}/globalmount"
        mount_dir = f"/var/lib/kubelet/pods/{pod.name}/volumes/kubernetes.io~csi/{pv.name}/mount"
        
        self.log("Kubelet-VolumeMgr", f"RPC Call -> NodeStageVolume(Target: {staging_dir}, FSType: ext4)", Color.BLUE)
        self.csi.node_stage_volume(pv.csi_volume_id, staging_dir)

        self.log("Kubelet-VolumeMgr", f"RPC Call -> NodePublishVolume(Target: {mount_dir} -> {pod.mount_path})", Color.BLUE)
        self.csi.node_publish_volume(pv.csi_volume_id, mount_dir)

        pod.is_running = True
        self.log("ContainerRuntime", f"Container dimulai. Volume aktif di '{pod.mount_path}'", Color.GREEN)

    def write_data(self, pod_name: str, key: str, value: str):
        pod = self.pods.get(pod_name)
        if not pod or not pod.is_running:
            self.log("Workload", f"Gagal tulis: Pod '{pod_name}' tidak aktif.", Color.RED)
            return
        pvc = self.pvcs[pod.pvc_name]
        pv = self.pvs[pvc.bound_pv_name]
        payload = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {key} = {value}\n"
        self.csi.storage_pool[pv.csi_volume_id]["data"] += payload
        self.log("Workload", f"I/O Write ke '{pod.mount_path}/{key}': \"{value}\"", Color.MAGENTA)

    def read_data(self, pod_name: str) -> str:
        pod = self.pods.get(pod_name)
        if not pod or not pod.is_running:
            return "ERROR: Pod is not running"
        pvc = self.pvcs[pod.pvc_name]
        pv = self.pvs[pvc.bound_pv_name]
        return self.csi.storage_pool[pv.csi_volume_id]["data"]

    def evict_pod(self, pod_name: str):
        pod = self.pods.get(pod_name)
        if not pod:
            return
        self.log("Kubelet", f"Menghentikan Pod '{pod_name}'...", Color.YELLOW)
        pvc = self.pvcs[pod.pvc_name]
        pv = self.pvs[pvc.bound_pv_name]

        self.log("Kubelet-VolumeMgr", f"NodeUnpublishVolume({pv.csi_volume_id}) [Unmount]", Color.BLUE)
        self.csi.node_unpublish_volume(pv.csi_volume_id)

        self.log("AttachDetach-Ctrl", f"ControllerUnpublishVolume({pv.csi_volume_id}) [Detach from {pod.node_name}]", Color.BLUE)
        self.csi.controller_unpublish_volume(pv.csi_volume_id)

        pod.is_running = False
        del self.pods[pod_name]
        self.log("Kube-API", f"Pod '{pod_name}' berhasil dihapus.", Color.GREEN)

    def delete_pvc(self, pvc_name: str):
        pvc = self.pvcs.get(pvc_name)
        if not pvc:
            return
        self.log("Kube-API", f"Permintaan penghapusan PVC '{pvc_name}'...", Color.YELLOW)
        pv = self.pvs.get(pvc.bound_pv_name)
        del self.pvcs[pvc_name]
        
        if pv:
            pv.status = PVStatus.RELEASED
            self.log("PV-Controller", f"PV '{pv.name}' status berubah menjadi 'Released'", Color.YELLOW)
            if pv.reclaim_policy == ReclaimPolicy.DELETE:
                self.log("PV-Controller", f"ReclaimPolicy: DELETE -> Menghapus backing physical disk via CSI", Color.RED)
                self.csi.delete_volume(pv.csi_volume_id)
                del self.pvs[pv.name]
                self.log("PV-Controller", f"PV '{pv.name}' dan underlying disk berhasil dimusnahkan.", Color.RED)
            else:
                self.log("PV-Controller", f"ReclaimPolicy: RETAIN -> Data aman di storage pool, PV dipertahankan.", Color.GREEN)


def print_banner():
    banner = f"""
{Color.CYAN}{Color.BOLD}======================================================================
  KUBERNETES CSI & STORAGE PERSISTENCE INTERACTIVE LAB SIMULATOR
  BAB-07: Storage Persistence, StorageClass, PVC/PV, dan Container Storage Interface
======================================================================{Color.RESET}
"""
    print(banner)


def run_interactive_lab():
    print_banner()
    engine = KubeStorageEngine()

    print(f"{Color.BOLD}>>> Tahap 1: Mendefinisikan StorageClass (Fast SSD & Standard Retain){Color.RESET}")
    sc_fast = StorageClass(
        name="fast-nvme",
        provisioner="csi.cloud.example/storage-driver",
        reclaim_policy=ReclaimPolicy.DELETE,
        volume_binding_mode=BindingMode.WAIT_FOR_FIRST_CONSUMER,
        parameters={"type": "io2", "iops": "3000"}
    )
    sc_retained = StorageClass(
        name="cold-retain",
        provisioner="csi.cloud.example/storage-driver",
        reclaim_policy=ReclaimPolicy.RETAIN,
        volume_binding_mode=BindingMode.IMMEDIATE,
        parameters={"type": "st1"}
    )
    engine.register_storage_class(sc_fast)
    engine.register_storage_class(sc_retained)
    print()

    print(f"{Color.BOLD}>>> Tahap 2: Menerapkan PVC dengan 'WaitForFirstConsumer'{Color.RESET}")
    pvc_order = PersistentVolumeClaim(
        name="orders-db-pvc",
        namespace="production",
        storage_class_name="fast-nvme",
        request_gi=50,
        access_modes=["ReadWriteOnce"]
    )
    engine.apply_pvc(pvc_order)
    print(f"{Color.DIM}Status PVC Saat Ini: {pvc_order.status} (Belum ada pod yang mengonsumsi){Color.RESET}\n")

    print(f"{Color.BOLD}>>> Tahap 3: Menjadwalkan Pod Postgres ke Node 'worker-node-1'{Color.RESET}")
    db_pod = Pod(
        name="postgres-0",
        namespace="production",
        node_name=None,
        pvc_name="orders-db-pvc",
        mount_path="/var/lib/postgresql/data"
    )
    engine.schedule_pod(db_pod, "worker-node-1")
    print()

    print(f"{Color.BOLD}>>> Tahap 4: Menguji Operasi I/O Persistence di Volume Terpasang{Color.RESET}")
    engine.write_data("postgres-0", "order_id_1001", "Customer: Budi, Amount: $450")
    engine.write_data("postgres-0", "order_id_1002", "Customer: Siti, Amount: $1200")
    print(f"\n{Color.CYAN}--- Isi Raw Disk Block Device Saat Ini ---{Color.RESET}")
    raw_content = engine.read_data("postgres-0")
    for line in raw_content.strip().split("\n"):
        print(f"  {Color.DIM}|{Color.RESET} {line}")
    print()

    print(f"{Color.BOLD}>>> Tahap 5: Simulasi Node Failure / Pod Eviction & Failover{Color.RESET}")
    print(f"{Color.RED}Simulasi: Node 'worker-node-1' mengalami kernel crash! Evicting Pod...{Color.RESET}")
    engine.evict_pod("postgres-0")
    print()

    print(f"{Color.BOLD}>>> Tahap 6: Membangkitkan Pod Baru di Node 'worker-node-2' (Re-attachment){Color.RESET}")
    recovered_pod = Pod(
        name="postgres-0-recovered",
        namespace="production",
        node_name=None,
        pvc_name="orders-db-pvc",
        mount_path="/var/lib/postgresql/data"
    )
    engine.schedule_pod(recovered_pod, "worker-node-2")
    print(f"\n{Color.GREEN}Verifikasi Integritas Data setelah Failover:{Color.RESET}")
    recovered_data = engine.read_data("postgres-0-recovered")
    print(recovered_data)
    if "order_id_1001" in recovered_data and "order_id_1002" in recovered_data:
        print(f"{Color.GREEN}{Color.BOLD}SUCCESS: Data 100% Persisten & Utuh tanpa kehilangan bit!{Color.RESET}\n")

    print(f"{Color.BOLD}>>> Tahap 7: Reclaim Policy Lifecycle Demonstration{Color.RESET}")
    print(f"Menghapus Pod aktif dan membersihkan PVC 'orders-db-pvc'...")
    engine.evict_pod("postgres-0-recovered")
    engine.delete_pvc("orders-db-pvc")
    print()

    print(f"{Color.CYAN}{Color.BOLD}Simulasi Selesai. Seluruh rantai orkestrasi CSI Kubernetes terverifikasi sempurna.{Color.RESET}")

if __name__ == "__main__":
    run_interactive_lab()
