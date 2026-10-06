#!/usr/bin/env python3
"""
Kubernetes Storage Persistence & Container Storage Interface (CSI) Lab Simulator
BAB-07: Storage Persistence dan CSI Driver Architecture Simulation
Standard Library Only - No external dependencies required.
"""

import sys
import time
import json
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class AnsiColor:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    CYAN = "\033[36m"
    BLUE = "\033[34m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    RED = "\033[31m"
    MAGENTA = "\033[35m"
    WHITE = "\033[37m"
    BG_BLUE = "\033[44m"
    BG_GREEN = "\033[42m"
    BG_MAGENTA = "\033[45m"


def print_banner():
    banner = f"""
{AnsiColor.CYAN}{AnsiColor.BOLD}╔════════════════════════════════════════════════════════════════════════════╗
║         K8S ADVANCED STORAGE PERSISTENCE & CSI SUBSYSTEM SIMULATOR          ║
║               BAB-07: CSI RPC Lifecycle & Volume Management                ║
╚════════════════════════════════════════════════════════════════════════════╝{AnsiColor.RESET}
"""
    print(banner)


def log_event(component: str, message: str, level: str = "INFO"):
    color_map = {
        "INFO": AnsiColor.CYAN,
        "CSI-CTL": AnsiColor.BLUE,
        "CSI-NODE": AnsiColor.MAGENTA,
        "KUBELET": AnsiColor.YELLOW,
        "SUCCESS": AnsiColor.GREEN,
        "WARN": AnsiColor.YELLOW,
        "ERROR": AnsiColor.RED,
    }
    col = color_map.get(level, AnsiColor.WHITE)
    t = time.strftime("%H:%M:%S")
    print(f"{AnsiColor.DIM}[{t}]{AnsiColor.RESET} {col}[{component:<16}] {level:<7}{AnsiColor.RESET} {message}")


class VolumeBindingMode(Enum):
    IMMEDIATE = "Immediate"
    WAIT_FOR_FIRST_CONSUMER = "WaitForFirstConsumer"


class ReclaimPolicy(Enum):
    DELETE = "Delete"
    RETAIN = "Retain"


class VolumePhase(Enum):
    PENDING = "Pending"
    BOUND = "Bound"
    RELEASED = "Released"
    FAILED = "Failed"


@dataclass
class StorageClass:
    name: str
    provisioner: str
    reclaim_policy: ReclaimPolicy
    binding_mode: VolumeBindingMode
    allow_volume_expansion: bool = True
    parameters: Dict[str, str] = field(default_factory=dict)


@dataclass
class VolumeSnapshot:
    name: str
    snapshot_class: str
    source_pvc: str
    snapshot_id: str
    ready_to_use: bool = False
    size_gib: int = 0


@dataclass
class PersistentVolumeClaim:
    name: str
    namespace: str
    storage_class: str
    requested_size_gib: int
    access_modes: List[str]
    phase: VolumePhase = VolumePhase.PENDING
    bound_pv_name: Optional[str] = None


@dataclass
class PersistentVolume:
    name: str
    capacity_gib: int
    access_modes: List[str]
    reclaim_policy: ReclaimPolicy
    storage_class: str
    volume_handle: str
    phase: VolumePhase = VolumePhase.BOUND
    claim_ref: Optional[str] = None
    node_affinity_zone: str = "us-east-1a"


class CSIDriverSimulator:
    """Simulates gRPC interactions defined by the Container Storage Interface specification."""

    def __init__(self, driver_name: str = "ebs.csi.aws.com"):
        self.driver_name = driver_name
        self.raw_cloud_disks: Dict[str, dict] = {}
        self.node_attachments: Dict[str, List[str]] = {}  # node -> list of volume_handles
        self.node_staging: Dict[str, Dict[str, str]] = {}  # node -> {volume_handle: staging_path}
        self.pod_mounts: Dict[str, Dict[str, str]] = {}   # node -> {volume_handle: target_path}

    def csi_create_volume(self, name: str, size_gib: int, parameters: dict) -> str:
        vol_handle = f"vol-{random.randint(10000000, 99999999):x}"
        log_event("csi-provisioner", f"RPC Controller.CreateVolume(Name={name}, Cap={size_gib}GiB)", "CSI-CTL")
        time.sleep(0.4)
        self.raw_cloud_disks[vol_handle] = {
            "name": name,
            "size_gib": size_gib,
            "params": parameters,
            "status": "Available",
        }
        log_event("csi-driver", f"Allocated backend cloud block device: {vol_handle} ({size_gib} GiB)", "SUCCESS")
        return vol_handle

    def csi_controller_publish(self, volume_handle: str, node_id: str) -> bool:
        log_event("csi-attacher", f"RPC Controller.ControllerPublishVolume(Vol={volume_handle}, Node={node_id})", "CSI-CTL")
        time.sleep(0.3)
        if node_id not in self.node_attachments:
            self.node_attachments[node_id] = []
        self.node_attachments[node_id].append(volume_handle)
        self.raw_cloud_disks[volume_handle]["status"] = f"Attached({node_id})"
        log_event("csi-driver", f"Block device {volume_handle} attached to EC2 instance {node_id}", "SUCCESS")
        return True

    def csi_node_stage_volume(self, volume_handle: str, node_id: str, staging_path: str) -> bool:
        log_event("csi-node-driver", f"RPC Node.NodeStageVolume(Vol={volume_handle}, StagingDir={staging_path})", "CSI-NODE")
        time.sleep(0.3)
        log_event("csi-node-driver", f"Format mkfs.ext4 on /dev/disk/by-id/{volume_handle} & global mount", "CSI-NODE")
        if node_id not in self.node_staging:
            self.node_staging[node_id] = {}
        self.node_staging[node_id][volume_handle] = staging_path
        return True

    def csi_node_publish_volume(self, volume_handle: str, node_id: str, target_path: str) -> bool:
        log_event("kubelet", f"RPC Node.NodePublishVolume(Vol={volume_handle}, TargetDir={target_path})", "KUBELET")
        time.sleep(0.2)
        log_event("kubelet", f"Bind-mount: {self.node_staging[node_id][volume_handle]} -> {target_path}", "SUCCESS")
        if node_id not in self.pod_mounts:
            self.pod_mounts[node_id] = {}
        self.pod_mounts[node_id][volume_handle] = target_path
        return True

    def csi_controller_expand_volume(self, volume_handle: str, new_size_gib: int) -> bool:
        log_event("csi-resizer", f"RPC Controller.ControllerExpandVolume(Vol={volume_handle}, NewCap={new_size_gib}GiB)", "CSI-CTL")
        time.sleep(0.3)
        self.raw_cloud_disks[volume_handle]["size_gib"] = new_size_gib
        log_event("csi-resizer", f"Cloud API confirmed block device resized to {new_size_gib} GiB", "SUCCESS")
        return True

    def csi_node_expand_volume(self, volume_handle: str, node_id: str, target_path: str) -> bool:
        log_event("kubelet", f"RPC Node.NodeExpandVolume(Vol={volume_handle}, Dir={target_path})", "KUBELET")
        time.sleep(0.2)
        log_event("kubelet", f"Online resize2fs / xfs_growfs executed on filesystem mounted at {target_path}", "SUCCESS")
        return True

    def csi_create_snapshot(self, source_handle: str, snapshot_name: str) -> str:
        snap_id = f"snap-{random.randint(10000000, 99999999):x}"
        log_event("csi-snapshotter", f"RPC Controller.CreateSnapshot(SourceVol={source_handle}, Name={snapshot_name})", "CSI-CTL")
        time.sleep(0.4)
        log_event("csi-driver", f"Storage snapshot created successfully: ID={snap_id}", "SUCCESS")
        return snap_id


class KubernetesStorageSubsystem:
    """Simulates API Server, KCM (PersistentVolumeController), VolumeManager & CSI sidecars."""

    def __init__(self):
        self.storage_classes: Dict[str, StorageClass] = {}
        self.pv_store: Dict[str, PersistentVolume] = {}
        self.pvc_store: Dict[str, PersistentVolumeClaim] = {}
        self.snapshots: Dict[str, VolumeSnapshot] = {}
        self.csi = CSIDriverSimulator()

    def bootstrap_default_storage_classes(self):
        self.storage_classes["gp3-immediate"] = StorageClass(
            name="gp3-immediate",
            provisioner="ebs.csi.aws.com",
            reclaim_policy=ReclaimPolicy.DELETE,
            binding_mode=VolumeBindingMode.IMMEDIATE,
            parameters={"type": "gp3", "iops": "3000", "throughput": "125"},
        )
        self.storage_classes["io2-topology-aware"] = StorageClass(
            name="io2-topology-aware",
            provisioner="ebs.csi.aws.com",
            reclaim_policy=ReclaimPolicy.RETAIN,
            binding_mode=VolumeBindingMode.WAIT_FOR_FIRST_CONSUMER,
            parameters={"type": "io2", "iopsPerGB": "50"},
        )

    def provision_pvc(self, pvc_name: str, ns: str, sc_name: str, size_gib: int, access_modes: List[str]) -> PersistentVolumeClaim:
        if sc_name not in self.storage_classes:
            raise ValueError(f"StorageClass '{sc_name}' not found!")

        sc = self.storage_classes[sc_name]
        pvc = PersistentVolumeClaim(
            name=pvc_name,
            namespace=ns,
            storage_class=sc_name,
            requested_size_gib=size_gib,
            access_modes=access_modes,
            phase=VolumePhase.PENDING,
        )
        self.pvc_store[f"{ns}/{pvc_name}"] = pvc
        log_event("kube-apiserver", f"Created PVC: {ns}/{pvc_name} ({size_gib} GiB, Mode={sc.binding_mode.value})")

        if sc.binding_mode == VolumeBindingMode.IMMEDIATE:
            log_event("pv-controller", f"Immediate binding triggered for PVC {ns}/{pvc_name}")
            self._execute_dynamic_provisioning(pvc, selected_node_zone="us-east-1a")
        else:
            log_event("pv-controller", f"PVC {ns}/{pvc_name} kept in Pending: waiting for pod scheduling", "WARN")

        return pvc

    def _execute_dynamic_provisioning(self, pvc: PersistentVolumeClaim, selected_node_zone: str):
        sc = self.storage_classes[pvc.storage_class]
        vol_name = f"pvc-{random.randint(10000000, 99999999)}"
        vol_handle = self.csi.csi_create_volume(vol_name, pvc.requested_size_gib, sc.parameters)

        pv = PersistentVolume(
            name=vol_name,
            capacity_gib=pvc.requested_size_gib,
            access_modes=pvc.access_modes,
            reclaim_policy=sc.reclaim_policy,
            storage_class=sc.name,
            volume_handle=vol_handle,
            phase=VolumePhase.BOUND,
            claim_ref=f"{pvc.namespace}/{pvc.name}",
            node_affinity_zone=selected_node_zone,
        )
        self.pv_store[vol_name] = pv

        pvc.phase = VolumePhase.BOUND
        pvc.bound_pv_name = vol_name
        log_event("pv-controller", f"Bound PV {vol_name} <---> PVC {pvc.namespace}/{pvc.name}", "SUCCESS")

    def schedule_and_attach_pod(self, pod_name: str, pvc_key: str, target_node: str, mount_path: str):
        if pvc_key not in self.pvc_store:
            raise KeyError(f"PVC {pvc_key} does not exist.")

        pvc = self.pvc_store[pvc_key]
        sc = self.storage_classes[pvc.storage_class]

        log_event("kube-scheduler", f"Pod '{pod_name}' bound to Node '{target_node}'")

        if pvc.phase == VolumePhase.PENDING and sc.binding_mode == VolumeBindingMode.WAIT_FOR_FIRST_CONSUMER:
            log_event("pv-controller", f"Delayed volume binding triggered for {pvc_key} on node {target_node}")
            self._execute_dynamic_provisioning(pvc, selected_node_zone="us-east-1b")

        pv = self.pv_store[pvc.bound_pv_name]

        # 1. Attachment phase
        log_event("attach-detach-ctl", f"Creating VolumeAttachment object for {pv.volume_handle} -> {target_node}")
        self.csi.csi_controller_publish(pv.volume_handle, target_node)

        # 2. Node Staging phase
        staging_dir = f"/var/lib/kubelet/plugins/kubernetes.io/csi/pv/{pv.name}/globalmount"
        self.csi.csi_node_stage_volume(pv.volume_handle, target_node, staging_dir)

        # 3. Node Publish phase
        pod_dir = f"/var/lib/kubelet/pods/pod-uuid-{pod_name}/volumes/kubernetes.io~csi/{pv.name}/mount"
        self.csi.csi_node_publish_volume(pv.volume_handle, target_node, pod_dir)
        log_event("kubelet", f"Container container-0 started. Volume available at container path: {mount_path}", "SUCCESS")

    def expand_pvc_volume(self, pvc_key: str, new_size_gib: int, active_node: Optional[str] = None):
        pvc = self.pvc_store[pvc_key]
        if new_size_gib <= pvc.requested_size_gib:
            log_event("apiserver", "New size must be strictly greater than current capacity", "ERROR")
            return

        old_size = pvc.requested_size_gib
        pvc.requested_size_gib = new_size_gib
        pv = self.pv_store[pvc.bound_pv_name]
        log_event("pv-controller", f"Volume expansion requested for {pvc_key}: {old_size}GiB -> {new_size_gib}GiB")

        # Controller resize
        self.csi.csi_controller_expand_volume(pv.volume_handle, new_size_gib)
        pv.capacity_gib = new_size_gib

        # Node filesystem resize
        if active_node and active_node in self.csi.pod_mounts and pv.volume_handle in self.csi.pod_mounts[active_node]:
            target_path = self.csi.pod_mounts[active_node][pv.volume_handle]
            self.csi.csi_node_expand_volume(pv.volume_handle, active_node, target_path)

        log_event("pv-controller", f"PVC {pvc_key} successfully expanded to {new_size_gib} GiB", "SUCCESS")

    def snapshot_pvc(self, snapshot_name: str, pvc_key: str, snapshot_class: str = "csi-aws-vsc"):
        pvc = self.pvc_store[pvc_key]
        pv = self.pv_store[pvc.bound_pv_name]
        snap_id = self.csi.csi_create_snapshot(pv.volume_handle, snapshot_name)
        snapshot = VolumeSnapshot(
            name=snapshot_name,
            snapshot_class=snapshot_class,
            source_pvc=pvc_key,
            snapshot_id=snap_id,
            ready_to_use=True,
            size_gib=pv.capacity_gib,
        )
        self.snapshots[snapshot_name] = snapshot
        log_event("snapshot-ctl", f"VolumeSnapshot {snapshot_name} ReadyToUse=True (ID: {snap_id})", "SUCCESS")

    def display_cluster_storage_table(self):
        print(f"\n{AnsiColor.BOLD}{AnsiColor.CYAN}--- ACTIVE PERSISTENT VOLUME CLAIMS (PVC) ---{AnsiColor.RESET}")
        print(f"{'NAMESPACE':<12} {'NAME':<20} {'STATUS':<10} {'VOLUME':<22} {'CAPACITY':<10} {'STORAGECLASS':<20}")
        print("-" * 96)
        for key, pvc in self.pvc_store.items():
            vol_str = pvc.bound_pv_name if pvc.bound_pv_name else "<none>"
            print(f"{pvc.namespace:<12} {pvc.name:<20} {pvc.phase.value:<10} {vol_str:<22} {str(pvc.requested_size_gib)+'Gi':<10} {pvc.storage_class:<20}")

        print(f"\n{AnsiColor.BOLD}{AnsiColor.MAGENTA}--- REGISTERED PERSISTENT VOLUMES (PV) ---{AnsiColor.RESET}")
        print(f"{'NAME':<22} {'CAPACITY':<10} {'RECLAIM':<10} {'STATUS':<10} {'CSI VOLUME HANDLE':<22} {'ZONE':<12}")
        print("-" * 96)
        for name, pv in self.pv_store.items():
            print(f"{pv.name:<22} {str(pv.capacity_gib)+'Gi':<10} {pv.reclaim_policy.value:<10} {pv.phase.value:<10} {pv.volume_handle:<22} {pv.node_affinity_zone:<12}")

        if self.snapshots:
            print(f"\n{AnsiColor.BOLD}{AnsiColor.GREEN}--- VOLUME SNAPSHOTS ---{AnsiColor.RESET}")
            print(f"{'NAME':<20} {'READY':<8} {'SOURCE PVC':<20} {'SNAPSHOT ID':<22} {'RESTORE SIZE':<12}")
            print("-" * 96)
            for sname, snap in self.snapshots.items():
                print(f"{snap.name:<20} {str(snap.ready_to_use):<8} {snap.source_pvc:<20} {snap.snapshot_id:<22} {str(snap.size_gib)+'Gi':<12}")
        print()


def run_full_lab_simulation():
    print_banner()
    k8s = KubernetesStorageSubsystem()
    k8s.bootstrap_default_storage_classes()

    print(f"{AnsiColor.BOLD}>>> Skenario 1: Dynamic Provisioning (Immediate vs WaitForFirstConsumer){AnsiColor.RESET}")
    log_event("init", "Loaded StorageClasses: 'gp3-immediate' & 'io2-topology-aware'")

    # Step 1: Immediate Provisioning
    print(f"\n{AnsiColor.WHITE}{AnsiColor.BG_BLUE} 1. Provisioning PVC dengan VolumeBindingMode: Immediate {AnsiColor.RESET}")
    pvc1 = k8s.provision_pvc(
        pvc_name="db-cache-pvc",
        ns="production",
        sc_name="gp3-immediate",
        size_gib=20,
        access_modes=["ReadWriteOnce"],
    )

    # Step 2: WaitForFirstConsumer Provisioning
    print(f"\n{AnsiColor.WHITE}{AnsiColor.BG_BLUE} 2. Provisioning PVC dengan VolumeBindingMode: WaitForFirstConsumer {AnsiColor.RESET}")
    pvc2 = k8s.provision_pvc(
        pvc_name="postgres-master-pvc",
        ns="production",
        sc_name="io2-topology-aware",
        size_gib=100,
        access_modes=["ReadWriteOnce"],
    )

    # Step 3: Pod Scheduling triggers Delayed Binding & CSI Node Mounts
    print(f"\n{AnsiColor.WHITE}{AnsiColor.BG_BLUE} 3. Menjalankan Pod Database, Trigger CSI Attach & Mount RPCs {AnsiColor.RESET}")
    k8s.schedule_and_attach_pod(
        pod_name="postgres-0",
        pvc_key="production/postgres-master-pvc",
        target_node="ip-10-0-2-45.ec2.internal",
        mount_path="/var/lib/postgresql/data",
    )

    # Step 4: Online Volume Expansion
    print(f"\n{AnsiColor.WHITE}{AnsiColor.BG_BLUE} 4. Melakukan Dynamic Online Volume Expansion (100Gi -> 250Gi) {AnsiColor.RESET}")
    k8s.expand_pvc_volume(
        pvc_key="production/postgres-master-pvc",
        new_size_gib=250,
        active_node="ip-10-0-2-45.ec2.internal",
    )

    # Step 5: CSI Volume Snapshot
    print(f"\n{AnsiColor.WHITE}{AnsiColor.BG_BLUE} 5. Mengambil Point-In-Time VolumeSnapshot {AnsiColor.RESET}")
    k8s.snapshot_pvc(
        snapshot_name="pg-backup-snapshot-20261006",
        pvc_key="production/postgres-master-pvc",
    )

    # Final State Visualization
    print(f"\n{AnsiColor.WHITE}{AnsiColor.BG_GREEN} 6. Ringkasan Status Storage Cluster Kubernetes {AnsiColor.RESET}")
    k8s.display_cluster_storage_table()

    print(f"{AnsiColor.GREEN}{AnsiColor.BOLD}✔ Simulasi Arsitektur Kubernetes Storage & CSI berhasil diselesaikan tanpa error!{AnsiColor.RESET}\n")


if __name__ == "__main__":
    try:
        run_full_lab_simulation()
    except KeyboardInterrupt:
        print("\n[!] Simulasi dihentikan oleh user.")
        sys.exit(0)
