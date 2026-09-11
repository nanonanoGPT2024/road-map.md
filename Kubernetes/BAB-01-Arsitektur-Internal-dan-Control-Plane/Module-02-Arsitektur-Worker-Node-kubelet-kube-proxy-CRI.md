# Module 02: Arsitektur Worker Node (Kubelet, Kube-Proxy, CRI containerd, dan Cgroup Driver)

---
[⬅️ Module 01: Arsitektur Control Plane](./Module-01-Arsitektur-Control-Plane-apiserver-etcd-controller-scheduler.md) | [📋 Silabus Induk](../README.md) | [Evaluasi & Quiz BAB 01 ➡️](./BAB-01-Quiz-dan-Challenge.md)
---

## 1. Learning Objective
Setelah menyelesaikan modul ini, pembelajar diharapkan mampu:
1. Memahami arsitektur internal **Worker Node** Kubernetes dan tanggung jawab dari setiap komponennya: `kubelet`, `kube-proxy`, dan **Container Runtime Interface (CRI)**.
2. Menjelaskan mekanisme kerja `kubelet`: penerimaan PodSpec, siklus rekonsiliasi lokal, pelaporan status node via **NodeLease**, dan eksekusi health probes via PLEG (**Pod Lifecycle Event Generator**).
3. Menguasai arsitektur gRPC pada **CRI (Container Runtime Interface)** antara `kubelet` dan container runtime modern (`containerd` / `CRI-O`) yang terdiri dari `RuntimeService` dan `ImageService`.
4. Memahami krusialnya penyelarasan **Cgroup Driver** (`cgroupfs` vs `systemd`) untuk mencegah instabilitas kernel host dan node out-of-memory crash.
5. Menjelaskan peran `kube-proxy` dalam mengimplementasikan abstraksi Service di level sistem operasi host menggunakan mode **iptables** dan mode **IPVS**.

---

## 2. Prerequisite
- Memahami konsep arsitektur Control Plane Kubernetes ([Module 01 BAB 01](Module-01-Arsitektur-Control-Plane-apiserver-etcd-controller-scheduler.md)).
- Memahami konsep Linux Namespaces, Cgroups v2, dan Container Runtime (`containerd`, `runc`) ([Docker BAB 01](../../Docker/BAB-01-Fondasi-dan-Arsitektur-Docker/)).
- Pemahaman dasar Linux networking (`iptables`, routing tables).

---

## 3. Concept
Jika Control Plane adalah "otak" dari kluster Kubernetes, maka **Worker Node** adalah "otot" atau pekerja fisik/virtual yang bertugas mengeksekusi kontainer beban kerja (workload).

Setiap worker node menjalankan tiga komponen utama:
1. **`kubelet`**: Agen utama yang berjalan di level OS Linux host (bukan sebagai kontainer biasa). Bertindak sebagai pengawas lapangan yang menerima instruksi `PodSpec` dari `kube-apiserver` dan memastikan kontainer yang dideskripsikan benar-benar hidup dan sehat di node tersebut.
2. **Container Runtime (CRI)**: Software tingkat rendah (umumnya `containerd` atau `CRI-O`) yang bertanggung jawab menarik image, membuat Linux namespaces, mengalokasikan cgroups, dan mengeksekusi kontainer via OCI runtime (`runc` / `crun`).
3. **`kube-proxy`**: Agen jaringan yang memantau penambahan atau perubahan Service dan Endpoints di `kube-apiserver`, lalu menerjemahkannya menjadi aturan firewall Linux host (`iptables` atau `IPVS`) agar traffic jaringan dapat diarahkan ke Pod target secara merata.

---

## 4. Why?
Mengapa arsitektur Worker Node dirancang dengan abstraksi antarmuka seperti CRI dan CNI?
1. **Ekosistem Agnostik Runtime (CRI Independence)**: Kubernetes tidak lagi terikat pada satu vendor kontainer tertentu (seperti Docker shim lawas yang di-deprecate di v1.24). Siapa pun yang mengimplementasikan protokol gRPC CRI (seperti `containerd`, `CRI-O`, Kata Containers) dapat digunakan secara transparan.
2. **Kemandirian Kegagalan Node (Node Failure Isolation)**: Jika satu worker node terbakar atau kehilangan koneksi jaringan, `kubelet` di node lain tidak terpengaruh, dan control plane dapat segera menjadwalkan ulang pod yang hilang ke node yang sehat.
3. **Efisiensi Routing Kernel Host**: `kube-proxy` tidak bertindak sebagai reverse proxy user-space yang lambat; sebaliknya, ia memprogram langsung subsistem filtering kernel Linux (`netfilter` / `IPVS`) untuk routing berkecepatan kawat (*wire-speed*).

---

## 5. What?
### Rincian Komponen Worker Node:

| Komponen | Tipe Eksekusi | Protokol Komunikasi | Tanggung Jawab Utama |
|---|---|---|---|
| **`kubelet`** | Linux Systemd Daemon (`systemctl status kubelet`) | gRPC ke CRI (`/run/containerd/containerd.sock`), HTTPS ke `kube-apiserver` | Registrasi node, watch PodSpec, eksekusi probes, pelaporan heartbeat (`coordination.k8s.io/v1 NodeLease`). |
| **`containerd` (CRI)** | Linux Systemd Daemon | OCI Spec via `runc` socket | Manajemen siklus hidup container (`RunPodSandbox`, `CreateContainer`, `StartContainer`), image pull & unpacking. |
| **`kube-proxy`** | DaemonSet (Pod) di namespace `kube-system` | Watch API ke `kube-apiserver`, manipulasi kernel via Netlink/iptables | Translasi Virtual ClusterIP ke Pod IP aktual, load-balancing TCP/UDP round-robin. |
| **`cni-plugins`** | Biner executable di `/opt/cni/bin/` | Dipanggil oleh CRI saat PodSandbox dibuat | Alokasi veth pair interface, IPAM (IP Address Management), dan konfigurasi gateway Pod. |

---

## 6. How? Alur Kerja Kubelet Menjalankan Pod (CRI Sync Flow)

```text
  [ kube-apiserver ] (Event: Pod assigned to this Node)
          |
          v (Watch PodSpec)
  [ kubelet (Node Agent) ]
          |
          | 1. gRPC: RunPodSandboxRequest
          v
  [ CRI: containerd-cri plugin ]
          |
          | 2. Panggil CNI Plugin (/opt/cni/bin/calico)
          |    -> Buat Network Namespace & assign Pod IP
          |
          | 3. Buat Pause Container (Infra Container penahan Network Namespace)
          |
          | 4. gRPC: PullImageRequest (jika belum ada)
          |
          | 5. gRPC: CreateContainerRequest (Spesifikasi CPU/RAM cgroups, env, volume)
          |
          | 6. gRPC: StartContainerRequest
          v
  [ OCI Runtime: runc / containerd-shim ]
          |
          v
  [ User Application Containers Running! ]
          |
          v (Continuous monitoring)
  [ kubelet PLEG (Pod Lifecycle Event Generator) ]
          | -> Melakukan probe (HTTP/TCP/Exec)
          | -> Mengirimkan status Pod ke kube-apiserver
```

---

## 7. Analogy
Bayangkan Worker Node seperti sebuah pabrik manufaktur cabang:
- **`kubelet`** adalah **Kepala Mandor Pabrik**. Ia menerima surat perintah kerja dari kantor pusat (`kube-apiserver`), memeriksa apakah mesin siap, menginstruksikan operator mesin, dan setiap 10 detik menelepon kantor pusat untuk mengonfirmasi: "Pabrik cabang kami masih beroperasi aman!" (NodeLease).
- **CRI (`containerd`)** adalah **Mesin Pencetak Pabrik**. Mandor tidak mencetak barang sendiri; ia menekan tombol mesin cetak CRI untuk merakit kotak kontainer dan menyalakan proses di dalamnya.
- **`kube-proxy`** adalah **Petugas Pengatur Rambu Lalu Lintas Truk Ekspedisi**. Saat ada pesanan masuk ke alamat umum gudang (`Service ClusterIP`), ia memasang plang jalan yang mengarahkan truk langsung ke pintu dermaga spesifik (`Pod IP`).

---

## 8. Diagram: Masalah Cgroup Driver (Systemd vs Cgroupfs)

```text
Konfigurasi Salah: Konflik Dua Manajer Cgroups (Instabilitas & Crash)
+-------------------------------------------------------------------------+
| Host OS Linux (Init System: Systemd)                                    |
|   +--------------------------+          +-----------------------------+ |
|   | Systemd (Manager 1)      |          | cgroupfs (Manager 2)        | |
|   | Mengelola cgroup host OS |          | Digunakan kubelet/docker    | |
|   +--------------------------+          +-----------------------------+ |
|                 \                            /                          |
|                  v                          v                           |
|       [ Konflik Resource Kernel Linux: /sys/fs/cgroup ]                 |
|       (Kedua proses saling menimpa kuota CPU/Memory! Node Freeze)       |
+-------------------------------------------------------------------------+

Konfigurasi Standar Industri Modern: Unified Cgroup Driver (Systemd)
+-------------------------------------------------------------------------+
| Host OS Linux (Init System: Systemd)                                    |
|   +-------------------------------------------------------------------+ |
|   | Systemd Cgroup Manager (Single Source of Truth)                   | |
|   | - Kubelet: cgroupDriver: systemd                                  | |
|   | - containerd: SystemdCgroup = true                                | |
|   +-------------------------------------------------------------------+ |
|                                   |                                     |
|                                   v                                     |
|              Kernel Linux Cgroups v2 Terpadu & Stabil                   |
+-------------------------------------------------------------------------+
```

---

## 9. Simple Example: Memeriksa Status Kubelet dan Driver Cgroup

```bash
# 1. Periksa status service kubelet di Linux host
sudo systemctl status kubelet

# 2. Periksa cgroup driver yang digunakan kubelet
sudo cat /var/lib/kubelet/config.yaml | grep cgroupDriver
# Output yang benar: cgroupDriver: systemd

# 3. Periksa konfigurasi containerd untuk systemd cgroup
sudo grep -i SystemdCgroup /etc/containerd/config.toml
# Output yang benar: SystemdCgroup = true

# 4. Periksa log interaksi kubelet secara real-time
journalctl -u kubelet -f --no-tail
```

---

## 10. Practical Example: Konfigurasi Kube-Proxy (iptables vs IPVS)

Konfigurasi mode kube-proxy dikelola via ConfigMap `kube-proxy` di namespace `kube-system`:

```bash
# Cek ConfigMap kube-proxy
kubectl get cm kube-proxy -n kube-system -o yaml
```

### Konfigurasi Mode IPVS (Disarankan untuk kluster > 1.000 service):
```yaml
apiVersion: kubeproxy.config.k8s.io/v1alpha1
kind: KubeProxyConfiguration
mode: "ipvs" # Default lawas: "iptables"
ipvs:
  scheduler: "rr" # Round-Robin (opsi lain: lc, dh, sh, sed, nq)
  strictARP: true # Wajib jika menggunakan MetalLB atau Cilium
```

### Mengapa IPVS Lebih Cepat Dibanding iptables?
- **iptables**: Menggunakan algoritma *linear search* $O(N)$. Jika kluster memiliki 10.000 service dengan puluhan ribu endpoint, setiap paket data yang masuk harus melewati belasan ribu baris rule rantai firewall, memicu lonjakan latensi paket jaringan.
- **IPVS (IP Virtual Server)**: Menggunakan struktur data *Hash Table* $O(1)$. Waktu pencarian endpoint tetap instan konstan (beberapa mikrodetik) terlepas dari apakah kluster memiliki 10 service atau 100.000 service.

---

## 11. Real World Example: PLEG is not healthy Incident
Sebuah kluster e-commerce besar mengalami insiden: beberapa worker node tiba-tiba berganti status menjadi `NotReady`. Saat diperiksa via `kubectl describe node`, event log menunjukkan:
```text
NodeNotReady: PLEG is not healthy: pleg was last seen active 3m20s ago; threshold is 3m0s
```
- **Penyebab**: **PLEG (Pod Lifecycle Event Generator)** adalah subsistem internal kubelet yang secara berkala memanggil CRI (`containerd`) untuk memeriksa state seluruh kontainer di node. Karena terjadi I/O bottleneck parah di disk host (akibat log container tanpa rotasi), panggilan gRPC CRI mengalami timeout (hang). Kubelet menganggap dirinya tidak sehat dan melaporkan `NotReady` ke control plane.
- **Mitigasi**: Menerapkan disk log rotation dan membersihkan beban I/O, seketika PLEG kembali sehat dan node kembali `Ready`.

---

## 12. Trade-offs: kube-proxy iptables vs IPVS

| Karakteristik | `kube-proxy` iptables | `kube-proxy` IPVS |
|---|---|---|
| **Kompleksitas Setup** | Bawaan default Linux kernel, tanpa modul tambahan | Membutuhkan modul kernel Linux: `ip_vs`, `ip_vs_rr`, `ip_vs_wrr`, dll. |
| **Kompleksitas Algoritma** | $O(N)$ (Evaluasi rantai rule sekuensial) | $O(1)$ (Pencarian hash table efisien) |
| **Kapasitas Skalabilitas** | Efisien hingga ~1.000 service | Efisien hingga 50.000+ service |
| **Pilihan Algoritma Balancing** | Hanya random weighted | Round-Robin, Least Connection, Source Hashing, dll. |

---

## 13. When To Use
- Pastikan selalu menggunakan `cgroupDriver: systemd` di seluruh instalasi Linux modern (Ubuntu 22.04+, RHEL 9+, Debian 12).
- Beralihlah ke `mode: ipvs` pada `kube-proxy` jika kluster Anda berkembang melampaui 1.000 Service atau memiliki traffic throughput masif.
- Gunakan `containerd` sebagai container runtime standar industri yang ringan dan stabil.

---

## 14. When NOT To Use
- Jangan gunakan `cgroupDriver: cgroupfs` pada OS Linux yang dikelola oleh systemd. Ini adalah anti-pattern yang dapat memicu freeze pada proses kontroler kernel.
- Jangan gunakan mode `kube-proxy: userspace` (sudah usang dan sangat lambat).

---

## 15. Common Mistakes
1. **Ketidakcocokan Cgroup Driver antara Kubelet dan Containerd**: Kubelet disetel ke `systemd`, tetapi containerd dibiarkan `cgroupfs` (atau sebaliknya). Hasilnya: Kubelet akan langsung crash-loop saat boot.
2. **Menonaktifkan service Kubelet di host**: Mengira kubelet berjalan sebagai pod biasa di Kubernetes. Ingat: Kubelet adalah proses systemd native di host!
3. **Mengabaikan Node Heartbeat (NodeLease)**: Jika beban CPU worker node mencapai 100%, kubelet tidak sempat memperbarui Lease object di `kube-node-lease` namespace, menyebabkan control plane salah mengira node telah mati dan memicu eviksi pod massal.

---

## 16. Best Practices
### Must Have
- Selalu setel `SystemdCgroup = true` di file `/etc/containerd/config.toml`.
- Pastikan resource reservasi OS (`system-reserved` dan `kube-reserved`) dikonfigurasi di kubelet agar proses OS Linux dan Kubelet tidak kehabisan RAM oleh beban kerja Pod.

### Recommended
- Konfigurasikan Node Eviction Thresholds pada kubelet (misal: `imagefs.available<15%` memicu pembersihan image otomatis).
- Pantau metrik Kubelet: `kubelet_pleg_relist_duration_seconds` menggunakan Prometheus.

### Advanced
- Di kluster modern dengan eBPF (Cilium), Anda dapat menonaktifkan `kube-proxy` sepenuhnya (`kubeProxyReplacement: true`) untuk eliminasi overhead iptables secara total.

---

## 17. Troubleshooting Guide
### Problem 1: Node berstatus `NotReady`
- **Penyebab**: Kubelet berhenti berjalan atau gagal mengirim heartbeat Lease ke apiserver.
- **Diagnosa**:
  ```bash
  # 1. Di mesin lokal admin:
  kubectl describe node <node-name>
  
  # 2. Login via SSH ke worker node:
  sudo systemctl status kubelet
  sudo journalctl -u kubelet -e --no-pager
  ```
- **Solusi**: Periksa apakah disk root penuh (`DiskPressure`) atau sertifikat kubelet client expired di `/var/lib/kubelet/pki/`.

### Problem 2: Service ClusterIP tidak bisa dihubungi dari dalam Pod
- **Penyebab**: `kube-proxy` di node tersebut mengalami crash atau tabel iptables corrupt.
- **Diagnosa**:
  ```bash
  kubectl get pods -n kube-system -l k8s-app=kube-proxy -o wide
  kubectl logs -n kube-system <pod-kube-proxy-di-node-tersebut>
  ```
- **Solusi**: Restart pod kube-proxy yang bermasalah.

---

## 18. Exercises
### Level: Easy
1. Jalankan perintah `kubectl get nodes -o wide` dan identifikasi kolom `CONTAINER-RUNTIME`, `OS-IMAGE`, dan `KERNEL-VERSION`.
2. Periksa status Lease heartbeat node menggunakan:
   `kubectl get leases -n kube-node-lease`

### Level: Medium
1. Login via SSH atau terminal ke salah satu worker node (atau Minikube/Kind container).
2. Periksa socket containerd menggunakan CLI `crictl`:
   `sudo crictl info`
   `sudo crictl pods`
3. Periksa bahwa cgroup driver bernilai `systemd`.

### Level: Hard
1. Periksa aturan firewall yang dibuat oleh kube-proxy di Linux host:
   `sudo iptables-save | grep KUBE-SERVICES | head -n 30`
2. Telusuri bagaimana satu Service memetakan traffic ke rantai `KUBE-SVC-*` lalu ke `KUBE-SEP-*` (Service Endpoints).

---

## 19. Challenge
Rancang arsitektur worker node high-throughput untuk platform streaming:
- 50 worker node bare-metal dengan network 25 Gbps.
- Kube-proxy dikonfigurasi menggunakan mode IPVS dengan algoritma Least-Connection (`lc`).
- Konfigurasi `kube-reserved` dan `system-reserved` di `/var/lib/kubelet/config.yaml` agar 4GB RAM dan 2 Core CPU diamankan khusus untuk kernel dan kubelet daemon.
Tuliskan potongan konfigurasi YAML kubelet dan verifikasinya.

---

## 20. Summary
- **Worker Node** bertindak sebagai eksekutor fisik beban kerja yang dipimpin oleh **`kubelet`**.
- **CRI (Container Runtime Interface)** memisahkan logika orkestrasi Kubelet dari implementasi container runtime (`containerd`).
- **`systemd` Cgroup Driver** adalah standar wajib untuk menjamin satu otoritas pengelola cgroups kernel yang stabil.
- **`kube-proxy`** memprogram tabel firewall Linux host (`iptables` atau hash table `IPVS`) untuk mewujudkan load balancing internal Service.

---
[⬅️ Module 01: Arsitektur Control Plane](./Module-01-Arsitektur-Control-Plane-apiserver-etcd-controller-scheduler.md) | [📋 Silabus Induk](../README.md) | [Evaluasi & Quiz BAB 01 ➡️](./BAB-01-Quiz-dan-Challenge.md)
---
