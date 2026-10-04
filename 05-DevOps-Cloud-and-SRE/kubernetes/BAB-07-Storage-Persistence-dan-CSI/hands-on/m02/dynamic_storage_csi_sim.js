/**
 * Dynamic Provisioning & CSI Driver gRPC Lifecycle Simulator
 * 
 * Mensimulasikan arsitektur Out-of-Tree Container Storage Interface (CSI):
 * 1. StorageClass dengan volumeBindingMode: WaitForFirstConsumer.
 * 2. CSI Controller Sidecars (csi-provisioner, csi-attacher, csi-resizer, csi-snapshotter).
 * 3. CSI Node gRPC lifecycle (NodeStageVolume -> NodePublishVolume).
 * 4. Dynamic Online Volume Expansion (resize2fs/xfs_growfs).
 * 5. VolumeSnapshot & Restore flow.
 */

const ANSI = {
  reset: "\x1b[0m",
  bold: "\x1b[1m",
  green: "\x1b[32m",
  cyan: "\x1b[36m",
  yellow: "\x1b[33m",
  red: "\x1b[31m",
  magenta: "\x1b[35m"
};

function log(component, message, color = ANSI.reset) {
  console.log(`${color}[${component}] ${message}${ANSI.reset}`);
}

class CSIDriverMock {
  constructor(name) {
    this.name = name;
    this.volumes = new Map(); // volId -> details
    this.snapshots = new Map();
  }

  // Controller Service RPCs
  createVolume(name, capacityBytes, parameters, topology) {
    const volId = `vol-${Math.random().toString(36).substring(2, 10)}`;
    const volDetails = {
      id: volId,
      name,
      capacityBytes,
      parameters,
      zone: topology.zone,
      attachedNode: null,
      fsType: parameters.fsType || "ext4",
      stagedPath: null,
      publishedPath: null
    };
    this.volumes.set(volId, volDetails);
    log("csi-plugin", `gRPC RPC: CreateVolume(name=${name}, size=${capacityBytes / (1024**3)}Gi, zone=${topology.zone}) -> OK, VolId: ${volId}`, ANSI.green);
    return volDetails;
  }

  controllerPublishVolume(volId, nodeId) {
    const vol = this.volumes.get(volId);
    if (!vol) throw new Error(`Volume ${volId} not found`);
    vol.attachedNode = nodeId;
    const devicePath = `/dev/nvme_${volId.substring(4, 8)}`;
    log("csi-plugin", `gRPC RPC: ControllerPublishVolume(vol=${volId}, node=${nodeId}) -> OK, Attached as ${devicePath}`, ANSI.green);
    return { devicePath };
  }

  controllerExpandVolume(volId, newSizeBytes) {
    const vol = this.volumes.get(volId);
    if (!vol) throw new Error(`Volume ${volId} not found`);
    vol.capacityBytes = newSizeBytes;
    log("csi-plugin", `gRPC RPC: ControllerExpandVolume(vol=${volId}, newSize=${newSizeBytes / (1024**3)}Gi) -> Storage LUN Resized in Cloud`, ANSI.green);
    return { nodeExpansionRequired: true };
  }

  createSnapshot(volId, snapshotName) {
    const snapId = `snap-${Math.random().toString(36).substring(2, 10)}`;
    const snapshot = {
      id: snapId,
      name: snapshotName,
      sourceVolId: volId,
      creationTime: new Date().toISOString()
    };
    this.snapshots.set(snapId, snapshot);
    log("csi-plugin", `gRPC RPC: CreateSnapshot(sourceVol=${volId}, name=${snapshotName}) -> OK, SnapId: ${snapId}`, ANSI.magenta);
    return snapshot;
  }

  // Node Service RPCs (Worker Node Plane)
  nodeStageVolume(volId, stagingTargetPath, devicePath, fsType) {
    const vol = this.volumes.get(volId);
    vol.stagedPath = stagingTargetPath;
    log("csi-node-driver", `gRPC RPC: NodeStageVolume(vol=${volId}, dev=${devicePath}, fs=${fsType})`, ANSI.cyan);
    log("csi-node-driver", `Linux Command Executed: mkfs.${fsType} ${devicePath}`, ANSI.cyan);
    log("csi-node-driver", `Linux Command Executed: mount ${devicePath} ${stagingTargetPath}`, ANSI.cyan);
    return true;
  }

  nodePublishVolume(volId, stagingTargetPath, targetPath) {
    const vol = this.volumes.get(volId);
    vol.publishedPath = targetPath;
    log("csi-node-driver", `gRPC RPC: NodePublishVolume(staging=${stagingTargetPath}, podMount=${targetPath})`, ANSI.cyan);
    log("csi-node-driver", `Linux Command Executed: mount --bind ${stagingTargetPath} ${targetPath}`, ANSI.cyan);
    return true;
  }

  nodeExpandVolume(volId, stagingTargetPath) {
    const vol = this.volumes.get(volId);
    log("csi-node-driver", `gRPC RPC: NodeExpandVolume(vol=${volId}, path=${stagingTargetPath})`, ANSI.cyan);
    log("csi-node-driver", `Linux Command Executed: resize2fs ${stagingTargetPath}`, ANSI.cyan);
    return true;
  }
}

class KubernetesCluster {
  constructor(csiDriver) {
    this.driver = csiDriver;
    this.storageClasses = new Map();
  }

  registerStorageClass(sc) {
    this.storageClasses.set(sc.name, sc);
    log("k8s-apiserver", `StorageClass terdaftar: ${sc.name} (Driver: ${sc.provisioner}, BindingMode: ${sc.volumeBindingMode})`, ANSI.yellow);
  }

  handleWorkflow() {
    // 1. User membuat PVC
    log("user-action", `User membuat PVC 'redis-data-pvc' (Request: 20Gi, StorageClass: 'ebs-sc')`, ANSI.bold);
    const pvc = {
      name: "redis-data-pvc",
      namespace: "prod",
      requestedSizeGi: 20,
      storageClass: "ebs-sc",
      status: "Pending"
    };

    const sc = this.storageClasses.get(pvc.storageClass);

    if (sc.volumeBindingMode === "WaitForFirstConsumer") {
      log("csi-provisioner", `VolumeBindingMode adalah WaitForFirstConsumer. Pembuatan disk ditahan hingga Pod dijadwalkan...`, ANSI.yellow);
    }

    // 2. Scheduler menjadwalkan Pod
    log("kube-scheduler", `Pod 'redis-master-0' dijadwalkan ke Node: 'worker-node-02' di AZ 'ap-southeast-1a'`, ANSI.cyan);
    const targetNode = "worker-node-02";
    const targetZone = "ap-southeast-1a";

    // 3. csi-provisioner memanggil gRPC CreateVolume
    log("csi-provisioner", `Mendeteksi Pod terpasang. Memanggil driver CSI untuk alokasi disk fisik...`, ANSI.yellow);
    const vol = this.driver.createVolume(
      pvc.name,
      pvc.requestedSizeGi * 1024 * 1024 * 1024,
      sc.parameters,
      { zone: targetZone }
    );

    // 4. csi-attacher membuat VolumeAttachment dan memanggil ControllerPublishVolume
    log("csi-attacher", `Membuat objek VolumeAttachment dan meng-attach disk ke node VM '${targetNode}'...`, ANSI.yellow);
    const publishResult = this.driver.controllerPublishVolume(vol.id, targetNode);

    // 5. Kubelet di Worker Node mengeksekusi Staging & Publishing
    log("kubelet", `Kubelet di ${targetNode} mendeteksi device terpasang di ${publishResult.devicePath}`, ANSI.cyan);
    const stagingPath = `/var/lib/kubelet/plugins/kubernetes.io/csi/ebs.csi.aws.com/${vol.id}/globalmount`;
    const podMountPath = `/var/lib/kubelet/pods/pod-uid-456/volumes/kubernetes.io~csi/${vol.id}/mount`;

    this.driver.nodeStageVolume(vol.id, stagingPath, publishResult.devicePath, sc.parameters.fsType || "ext4");
    this.driver.nodePublishVolume(vol.id, stagingPath, podMountPath);

    log("kubelet", `Volume sukses di-mount ke container path '/data'. Pod berstatus Running!`, ANSI.green);

    // 6. Online Volume Expansion
    console.log(`\n${ANSI.bold}--- Skenario Ekspansi Volume Dinamis (Resize 20Gi -> 40Gi) ---${ANSI.reset}`);
    log("user-action", `User mengedit PVC: resources.requests.storage diubah menjadi 40Gi`, ANSI.bold);
    
    // csi-resizer trigger
    log("csi-resizer", `csi-resizer mendeteksi peningkatan ukuran PVC. Memanggil ControllerExpandVolume...`, ANSI.yellow);
    const expandResult = this.driver.controllerExpandVolume(vol.id, 40 * 1024 * 1024 * 1024);

    if (expandResult.nodeExpansionRequired) {
      log("kubelet", `Kubelet mendeteksi LUN fisik membesar. Mengeksekusi online filesystem resize...`, ANSI.cyan);
      this.driver.nodeExpandVolume(vol.id, stagingPath);
      log("kubelet", `Filesystem berhasil diperluas menjadi 40Gi secara online tanpa restart Pod!`, ANSI.green);
    }

    // 7. Volume Snapshot
    console.log(`\n${ANSI.bold}--- Skenario Pencadangan VolumeSnapshot ---${ANSI.reset}`);
    log("user-action", `User membuat manifest VolumeSnapshot 'redis-backup-snapshot'`, ANSI.bold);
    log("csi-snapshotter", `csi-snapshotter mendeteksi VolumeSnapshot. Memanggil CreateSnapshot...`, ANSI.magenta);
    const snap = this.driver.createSnapshot(vol.id, "redis-backup-snapshot");
    log("csi-snapshotter", `Snapshot ${snap.name} (ID: ${snap.id}) status: ReadyToUse=true`, ANSI.magenta);
  }
}

// ================= EKSEKUSI SIMULASI =================
console.log(`${ANSI.bold}================================================================${ANSI.reset}`);
console.log(`${ANSI.bold}   CONTAINER STORAGE INTERFACE (CSI) & STORAGECLASS SIMULATOR   ${ANSI.reset}`);
console.log(`${ANSI.bold}================================================================${ANSI.reset}\n`);

const ebsDriver = new CSIDriverMock("ebs.csi.aws.com");
const cluster = new KubernetesCluster(ebsDriver);

cluster.registerStorageClass({
  name: "ebs-sc",
  provisioner: "ebs.csi.aws.com",
  volumeBindingMode: "WaitForFirstConsumer",
  allowVolumeExpansion: true,
  parameters: {
    type: "gp3",
    iops: "3000",
    fsType: "ext4"
  }
});

cluster.handleWorkflow();

console.log(`\n${ANSI.bold}Semua tahapan arsitektur CSI gRPC tervalidasi dengan sempurna!${ANSI.reset}`);
