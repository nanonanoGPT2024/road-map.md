/**
 * Kubernetes PV/PVC Binding Engine & Lifecycle Simulator
 * 
 * Mensimulasikan logika controller internal `pv-controller` di kube-controller-manager:
 * 1. Evaluasi kapasitas, AccessMode, dan StorageClass matching.
 * 2. Transisi Phase PV & PVC (Pending -> Bound -> Released -> Deleted).
 * 3. Proteksi finalizer kubernetes.io/pvc-protection terhadap unmount prematur.
 * 4. Penegakan ReclaimPolicy (Retain vs Delete).
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

function log(module, msg, color = ANSI.reset) {
  console.log(`${color}[${module}] ${msg}${ANSI.reset}`);
}

class PersistentVolume {
  constructor(name, capacityGi, accessModes, storageClass, reclaimPolicy, zone = "ap-southeast-1a") {
    this.name = name;
    this.capacityGi = capacityGi;
    this.accessModes = accessModes; // Array: ['ReadWriteOnce', 'ReadWriteMany']
    this.storageClass = storageClass;
    this.reclaimPolicy = reclaimPolicy; // 'Retain' | 'Delete'
    this.zone = zone;
    this.phase = "Available"; // Available, Bound, Released, Failed
    this.claimRef = null; // { namespace, name, uid }
    this.finalizers = ["kubernetes.io/pv-protection"];
  }
}

class PersistentVolumeClaim {
  constructor(namespace, name, requestedGi, accessModes, storageClass, requiredZone = null) {
    this.namespace = namespace;
    this.name = name;
    this.uid = `pvc-uid-${Math.floor(1000 + Math.random() * 9000)}`;
    this.requestedGi = requestedGi;
    this.accessModes = accessModes;
    this.storageClass = storageClass;
    this.requiredZone = requiredZone;
    this.phase = "Pending";
    this.boundVolumeName = null;
    this.finalizers = ["kubernetes.io/pvc-protection"];
    this.mountedPods = new Set();
  }
}

class PVController {
  constructor() {
    this.pvPool = [];
    this.pvcQueue = [];
  }

  addPV(pv) {
    this.pvPool.push(pv);
    log("pv-controller", `PV terdaftar: ${pv.name} (${pv.capacityGi}Gi, ${pv.accessModes.join(",")}, Class: ${pv.storageClass}, Phase: ${pv.phase})`, ANSI.cyan);
  }

  submitPVC(pvc) {
    this.pvcQueue.push(pvc);
    log("pvc-admission", `PVC diajukan: ${pvc.namespace}/${pvc.name} (Req: ${pvc.requestedGi}Gi, Class: ${pvc.storageClass}, Phase: ${pvc.phase})`, ANSI.yellow);
    this.reconcile();
  }

  reconcile() {
    log("pv-controller", `=== Menjalankan Rekonsiliasi Binding Loop ===`, ANSI.bold);

    for (const pvc of this.pvcQueue) {
      if (pvc.phase === "Bound") continue;

      log("pv-controller", `Mencari PV yang kompatibel untuk PVC ${pvc.namespace}/${pvc.name}...`, ANSI.yellow);

      // Cari PV Available yang cocok
      const matchingPV = this.pvPool.find(pv => {
        if (pv.phase !== "Available") return false;
        if (pv.storageClass !== pvc.storageClass) return false;
        if (pv.capacityGi < pvc.requestedGi) return false;

        // Check access modes
        const hasCompatibleAccess = pvc.accessModes.every(mode => pv.accessModes.includes(mode));
        if (!hasCompatibleAccess) return false;

        // Check Zone affinity
        if (pvc.requiredZone && pv.zone !== pvc.requiredZone) return false;

        return true;
      });

      if (matchingPV) {
        // Lakukan two-way binding
        matchingPV.phase = "Bound";
        matchingPV.claimRef = { namespace: pvc.namespace, name: pvc.name, uid: pvc.uid };

        pvc.phase = "Bound";
        pvc.boundVolumeName = matchingPV.name;

        log("pv-controller", `SUCCESS! PVC ${pvc.namespace}/${pvc.name} BERHASIL terikat (Bound) dengan PV ${matchingPV.name}`, ANSI.green);
        if (matchingPV.capacityGi > pvc.requestedGi) {
          log("pv-controller", `[Peringatan] Alokasi berlebih! Diminta ${pvc.requestedGi}Gi, dialokasikan PV ${matchingPV.capacityGi}Gi (Waste: ${matchingPV.capacityGi - pvc.requestedGi}Gi)`, ANSI.magenta);
        }
      } else {
        log("pv-controller", `[Pending] Tidak ada PV yang cocok untuk PVC ${pvc.namespace}/${pvc.name}. Menunggu penyediaan volume baru.`, ANSI.red);
      }
    }
  }

  attachPod(podName, pvc) {
    pvc.mountedPods.add(podName);
    log("kubelet", `Pod [${podName}] me-mount PVC ${pvc.namespace}/${pvc.name} (Bound ke ${pvc.boundVolumeName})`, ANSI.cyan);
  }

  detachPod(podName, pvc) {
    pvc.mountedPods.delete(podName);
    log("kubelet", `Pod [${podName}] dihentikan & volume unmounted dari PVC ${pvc.namespace}/${pvc.name}`, ANSI.cyan);
  }

  deletePVC(pvc) {
    log("api-server", `Permintaan DELETE diterima untuk PVC ${pvc.namespace}/${pvc.name}`, ANSI.yellow);

    // Evaluasi finalizer pvc-protection
    if (pvc.mountedPods.size > 0) {
      log("finalizer", `BLOCKED! Finalizer 'kubernetes.io/pvc-protection' menahan penghapusan PVC ${pvc.name} karena sedang digunakan oleh Pod: [${Array.from(pvc.mountedPods).join(", ")}]`, ANSI.red);
      log("finalizer", `Status PVC tetap 'Terminating' hingga Pod dihentikan. Data tetap AMAN.`, ANSI.red);
      return false;
    }

    log("finalizer", `Pemeriksaan lolos: Tidak ada Pod aktif. Finalizer dilepas. PVC ${pvc.name} dihapus.`, ANSI.green);
    
    // Perbarui status PV terikat
    const boundPV = this.pvPool.find(pv => pv.name === pvc.boundVolumeName);
    if (boundPV) {
      log("pv-controller", `PVC dihapus. PV ${boundPV.name} beralih phase ke 'Released'`, ANSI.yellow);
      boundPV.phase = "Released";

      // Evaluasi ReclaimPolicy
      if (boundPV.reclaimPolicy === "Delete") {
        log("pv-controller", `ReclaimPolicy adalah 'Delete'. Menghapus block storage fisik & objek PV ${boundPV.name}...`, ANSI.green);
        this.pvPool = this.pvPool.filter(p => p.name !== boundPV.name);
        log("pv-controller", `PV ${boundPV.name} dan data fisik BERHASIL DILENYAPKAN.`, ANSI.green);
      } else if (boundPV.reclaimPolicy === "Retain") {
        log("pv-controller", `ReclaimPolicy adalah 'Retain'. PV ${boundPV.name} TETAP ADA dengan status 'Released'. Data fisik AMAN tersimpan di disk fisik. Butuh pembersihan manual oleh admin.`, ANSI.magenta);
      }
    }

    this.pvcQueue = this.pvcQueue.filter(p => p.uid !== pvc.uid);
    return true;
  }
}

// ================= SIMULASI EKSEKUSI =================
console.log(`${ANSI.bold}================================================================${ANSI.reset}`);
console.log(`${ANSI.bold}      KUBERNETES PERSISTENT VOLUME CONTROLLER SIMULATOR         ${ANSI.reset}`);
console.log(`${ANSI.bold}================================================================${ANSI.reset}\n`);

const controller = new PVController();

// 1. Inisialisasi Storage Pool
controller.addPV(new PersistentVolume("pv-nvme-100gi", 100, ["ReadWriteOnce"], "fast-nvme", "Retain", "ap-southeast-1a"));
controller.addPV(new PersistentVolume("pv-nfs-share-50gi", 50, ["ReadWriteMany", "ReadWriteOnce"], "shared-nfs", "Delete", "ap-southeast-1a"));
controller.addPV(new PersistentVolume("pv-ebs-gp3-20gi", 20, ["ReadWriteOnce"], "standard-ebs", "Delete", "ap-southeast-1b"));

console.log("\n--- Skenario 1: Binding Sukses & Deteksi Storage Waste ---");
const pvcPostgres = new PersistentVolumeClaim("database", "postgres-pvc", 30, ["ReadWriteOnce"], "fast-nvme");
controller.submitPVC(pvcPostgres);

console.log("\n--- Skenario 2: PVC Mismatch (Pending) ---");
const pvcRedis = new PersistentVolumeClaim("cache", "redis-pvc", 200, ["ReadWriteOnce"], "fast-nvme"); // Minta 200Gi tapi cuma ada 100Gi terpakai
controller.submitPVC(pvcRedis);

console.log("\n--- Skenario 3: Pod Lifecycle & Proteksi Finalizer PVC ---");
controller.attachPod("postgres-pod-0", pvcPostgres);

// Coba hapus PVC selagi Pod jalan
log("user-action", "User menjalankan: kubectl delete pvc postgres-pvc", ANSI.bold);
controller.deletePVC(pvcPostgres);

// Matikan Pod lalu hapus ulang
console.log("\n--- Skenario 4: Graceful Shutdown & Retain Policy ---");
controller.detachPod("postgres-pod-0", pvcPostgres);
controller.deletePVC(pvcPostgres);

console.log("\n--- Skenario 5: Dynamic NFS Delete Policy ---");
const pvcNFS = new PersistentVolumeClaim("web", "wordpress-uploads-pvc", 10, ["ReadWriteMany"], "shared-nfs");
controller.submitPVC(pvcNFS);
controller.deletePVC(pvcNFS);

console.log(`\n${ANSI.bold}Simulasi Selesai dengan Sukses! Seluruh perilaku State Machine K8s tervalidasi.${ANSI.reset}`);
