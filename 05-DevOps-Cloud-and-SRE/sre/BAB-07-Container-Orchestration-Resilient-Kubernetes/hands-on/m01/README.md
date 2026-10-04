# Panduan Hands-on: Kubernetes Operational Resilience & Chaos Simulation

## 1. Ikhtisar Laboratorium
Lab ini bertujuan membuktikan secara operasional bagaimana prinsip-prinsip ketahanan Kubernetes bekerja di bawah kondisi kegagalan nyata, yang mencakup:
- Pengujian penolakan penggusuran (*eviction rejection*) oleh **Pod Disruption Budget (PDB)**.
- Simulasi daur hidup **Node Drain** dan eksekusi sinyal `preStop` hook.
- Simulasi pemicuan **Kernel Linux OOM Killer (Exit Code 137)** akibat pelanggaran limit cgroup memori.

---

## 2. Struktur File Lab
```
hands-on/m01/
├── README.md                  # Panduan langkah demi langkah
└── k8s_resilience_pdb_sim.py   # Script simulator ketahanan K8s berbasis event loop
```

---

## 3. Langkah Pelaksanaan Hands-on Simulator (Python)

### Persyaratan Lingkungan:
- Python 3.8+ terpasang di sistem operasi Anda.
- Tanpa dependensi pihak ketiga (*pure standard library*).

### Langkah 1: Eksekusi Simulator
Jalankan simulator menggunakan terminal:
```bash
python3 hands-on/m01/k8s_resilience_pdb_sim.py
```

### Langkah 2: Observasi Hasil Evaluasi
Perhatikan log eksekusi terminal:
1. **PDB Enforcement**: Amati bagaimana simulator mengizinkan penggusuran pod pertama, namun langsung **menolak penggusuran pod kedua** pada node yang sama karena melanggar aturan `minAvailable: 2`.
2. **Graceful Lifecycle**: Perhatikan penundaan eksekusi hook `preStop` sebelum pengiriman sinyal `SIGTERM` dimulai.
3. **OOMKill Execution**: Saksikan simulasi lonjakan alokasi memori yang melebihi cgroup limit dan bagaimana exit code `137` terpicu.

---

## 4. Langkah Pengujian Lanjutan pada Klaster Nyata (Kind / Minikube)

Jika Anda memiliki akses ke klaster Kubernetes lokal:

### Langkah 1: Buat Klaster Multi-Node (Kind)
```bash
cat <<EOF > kind-resilience-cluster.yaml
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
- role: control-plane
- role: worker
- role: worker
EOF

kind create cluster --config kind-resilience-cluster.yaml --name resilience-lab
```

### Langkah 2: Terapkan Deployment dengan PDB
Simpan manifest berikut sebagai `app-resilience.yaml`:
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: resilient-web
  namespace: default
spec:
  replicas: 3
  selector:
    matchLabels:
      app: resilient-web
  template:
    metadata:
      labels:
        app: resilient-web
    spec:
      terminationGracePeriodSeconds: 30
      containers:
      - name: nginx
        image: nginx:alpine
        resources:
          limits:
            memory: "64Mi"
            cpu: "250m"
          requests:
            memory: "64Mi"
            cpu: "250m"
        lifecycle:
          preStop:
            exec:
              command: ["/bin/sh", "-c", "sleep 10"]
---
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: web-pdb
  namespace: default
spec:
  minAvailable: 2
  selector:
    matchLabels:
      app: resilient-web
```

Terapkan manifest:
```bash
kubectl apply -f app-resilience.yaml
kubectl wait --for=condition=Ready pod -l app=resilient-web --timeout=60s
```

### Langkah 3: Uji Coba Node Drain
Buka dua terminal terpisah:
- **Terminal 1** (Pantau Event & Status Pod):
  ```bash
  kubectl get pods -l app=resilient-web -o wide -w
  ```
- **Terminal 2** (Eksekusi Drain):
  ```bash
  WORKER_NODE=$(kubectl get nodes -l node-role.kubernetes.io/control-plane!="" -o jsonpath='{.items[0].metadata.name}')
  kubectl drain $WORKER_NODE --ignore-daemonsets --delete-emptydir-data
  ```

Amati bahwa proses drain mematuhi PDB dan tidak membunuh pod sebelum pod pengganti aktif di node lainnya.

### Langkah 4: Cleanup Lingkungan
```bash
kind delete cluster --name resilience-lab
```