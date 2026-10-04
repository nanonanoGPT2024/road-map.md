# Module 01: Container Network Interface (CNI), Overlay vs Flat Routing, dan Perbandingan Calico vs Cilium (eBPF)

---
[⬅️ Evaluasi & Quiz BAB 05](../BAB-05-Networking-Service-Discovery-dan-Ingress/BAB-05-Quiz-dan-Challenge.md) | [📋 Silabus Induk](../README.md) | [Module 02: NetworkPolicies & Microsegmentation ➡️](./Module-02-NetworkPolicies-Default-Deny-dan-Microsegmentation.md)
---

## 1. Learning Objective
Setelah menyelesaikan modul ini, pembelajar diharapkan mampu:
1. Memahami arsitektur spesifikasi **Container Network Interface (CNI)** dan filosofi jaringan datar Kubernetes (*Flat Network Model*).
2. Membedakan mekanisme **Overlay Networking** (VXLAN, IP-in-IP) vs **Direct / Flat Routing** (BGP, VPC-Native CNI) beserta penalti MTU-nya.
3. Membandingkan dua raksasa CNI industri: **Project Calico** (berbasis iptables/BGP) vs **Cilium** (berbasis teknologi revolusioner **Linux eBPF**).
4. Menjelaskan bagaimana **eBPF (Extended Berkeley Packet Filter)** membypass tumpukan protokol jaringan kernel Linux lawas (*netfilter/iptables*) untuk mencapai performa *wire-speed* dan visibilitas keamanan Layer 7.
5. Memilih CNI yang tepat berdasarkan karakteristik beban kerja (throughput, skala kluster, dan kepatuhan keamanan).

---

## 2. Prerequisite
- Memahami konsep Service ClusterIP dan kube-proxy iptables ([BAB 05 Module 01](../BAB-05-Networking-Service-Discovery-dan-Ingress/Module-01-Service-Types-kube-proxy-IPVS-dan-CoreDNS.md)).
- Memahami Linux Network Namespaces dan `veth` pair ([Docker BAB 01 & BAB 05](../../Docker/BAB-05-Docker-Networking-Deep-Dive/)).
- Pemahaman dasar konsep enkapsulasi paket jaringan, MTU (Maximum Transmission Unit), dan BGP (Border Gateway Protocol).

---

## 3. Concept
Secara filosofis, Kubernetes menetapkan aturan jaringan yang sangat mendasar:
> **"Setiap Pod di dalam kluster harus memiliki alamat IP unik sendiri yang dapat dihubungi langsung oleh seluruh Pod lain di seluruh worker node tanpa memerlukan Network Address Translation (NAT)."**

Namun, Kubernetes sendiri **tidak menyediakan implementasi jaringan bawaan** di dalam kode intinya. Sebaliknya, Kubernetes mendelegasikan tanggung jawab alokasi antarmuka jaringan dan rute IP kepada plugin pihak ketiga melalui standar **Container Network Interface (CNI)**.

Ketika Kubelet meminta CRI untuk membuat Pod baru (`RunPodSandbox`), runtime akan mengeksekusi biner CNI di direktori `/opt/cni/bin/`:
1. CNI membuat sepasang kabel virtual (**veth pair**).
2. Memindahkan satu ujung ke dalam Network Namespace milik Pod.
3. Menetapkan alamat IP dari pool IPAM (IP Address Management).
4. Mengonfigurasi gateway dan rute keluar Pod.

---

## 4. Why?
1. **Dukungan Skalabilitas Tanpa NAT**: Menghilangkan overhead translasi port (port exhaustion) yang umum terjadi pada arsitektur Docker konvensional.
2. **Eliminasi Penalti Enkapsulasi Paket (Throughput)**: Memahami perbedaan Overlay (VXLAN) vs Direct Routing (BGP/VPC) memungkinkan platform engineer memangkas latensi jaringan hingga 20-30% pada workload intensif (Kafka, Cassandra).
3. **Revolusi eBPF (Bypass iptables)**: Di kluster dengan ribuan pod, tabel iptables membengkak menjadi puluhan ribu aturan yang membebani CPU kernel. Cilium dengan eBPF memproses paket langsung di socket buffer kernel secara konstan $O(1)$.

---

## 5. What?
### Spektrum Pendekatan Routing Jaringan CNI:

| Model Routing | Mekanisme Kerja | Kelebihan | Kekurangan | Contoh CNI |
|---|---|---|---|---|
| **Overlay (VXLAN / Geneve)** | Membungkus paket asli Pod di dalam paket UDP standar host (Enkapsulasi L2 over L3). | Bekerja di jaringan apa pun tanpa perlu konfigurasi router fisik (Zero config). | Penalti MTU (overhead 50 byte per paket), konsumsi CPU tinggi untuk enkapsulasi. | Flannel (VXLAN), Weave Net, Calico VXLAN mode. |
| **Flat / Direct Routing (BGP)** | Pod IP dapat dirutekan langsung oleh router fisik data center via protokol BGP (Peering). | Performa 100% native (Line rate), tanpa penalti enkapsulasi, MTU standar 1500/9000. | Membutuhkan dukungan infrastruktur switch/router jaringan fisik (ToR Switch). | Calico (BGP mode). |
| **Cloud VPC-Native** | Menggunakan Secondary IP dari antarmuka Elastic Network Interface (ENI) cloud langsung ke Pod. | Terintegrasi native dengan Security Groups dan VPC cloud provider. | Terbatas oleh kuota IP subnet VPC dan batasan ENI per instance VM cloud. | AWS VPC CNI, Azure CNI, GCP GKE VPC-Native. |

---

## 6. How? Perbandingan Calico (iptables) vs Cilium (eBPF)

```text
Arsitektur Calico Konvensional (Netfilter / iptables):
Pod Traffic ---> veth pair ---> Linux TCP/IP Stack ---> iptables / conntrack ---> Wire
(Setiap paket harus melintasi ratusan evaluasi baris rule iptables di kernel space!)

Arsitektur Cilium Modern (eBPF Socket-Level Bypass):
Pod Traffic ---> Socket Layer ---> [ eBPF Program Hook ] -----------------------> Wire
                                         |
                                         v
                         (Bypass seluruh tumpukan iptables!
                          Rute langsung via eBPF Map Lookup O(1))
```

### Keunggulan Teknologi Cilium eBPF:
1. **Kinerja Wire-Speed**: Melewatkan tumpukan netfilter kernel Linux, mengurangi *context switching* CPU.
2. **Pengganti Kube-Proxy Sepenuhnya (`kubeProxyReplacement: true`)**: Menghilangkan service `kube-proxy` sama sekali dan menangani virtual service ClusterIP langsung di eBPF socket.
3. **Observabilitas Keamanan Transparan (Hubble)**: Menampilkan diagram aliran jaringan Layer 3 hingga Layer 7 (HTTP method, DNS query, gRPC status code) secara real-time tanpa memasang sidecar proxy Envoy!

---

## 7. Analogy
Bayangkan dua cara mengirimkan paket dokumen:
- **Overlay Network (VXLAN)**: Anda ingin mengirimkan surat beramplop cokelat kecil. Tetapi kantor pos mewajibkan Anda membungkus amplop cokelat tersebut ke dalam kardus kardus pos yang lebih tebal (Enkapsulasi). Ini aman dan bisa dikirim ke mana saja, tetapi paket menjadi lebih berat dan memakan tempat (Penalti MTU).
- **Direct Routing (BGP / Flat)**: Kantor pos langsung mengenali kode pos unik penerima dan memiliki jalan tol khusus tanpa perlu membungkus ulang kardus (Native speed).
- **Cilium eBPF**: Seperti memasang pintu portal teleportasi ajaib di dalam rumah. Alih-alih paket berjalan melewati gang-gang sempit dan lampu merah (`iptables`), paket langsung diteleportasikan dari socket pengirim ke socket penerima di memori kernel.

---

## 8. Diagram: Dampak Overhead MTU pada Overlay Network

```text
Standar Ethernet Frame (Native Direct Routing):
+-------------------------+-----------------------------------------+
| IP Header Host (20 B)   | Payload Data Paket (Maksimal 1480 Byte) |  --> Total MTU: 1500
+-------------------------+-----------------------------------------+

Enkapsulasi VXLAN Overlay Frame:
+-------------------+-------------------+-------------------+-------------------+
| Outer IP (20 B)   | UDP Header (8 B)  | VXLAN (8 B)       | Inner IP + TCP    | Payload Kurang!
+-------------------+-------------------+-------------------+-------------------+ (Max 1450 B)
                                                                Overhead 50 Byte!
(Jika MTU tidak disesuaikan, terjadi fragmentasi paket yang merusak throughput!)
```

---

## 9. Simple Example: Memeriksa Status CNI di Kluster

```bash
# 1. Periksa plugin CNI yang terpasang di node
ls -la /etc/cni/net.d/
# Contoh output: 10-calico.conflist atau 05-cilium.conflist

# 2. Periksa biner executable CNI di host
ls /opt/cni/bin/
# Output: bridge, host-local, loopback, portmap, calico, cilium-cni, dll.

# 3. Periksa pod daemon CNI yang aktif
kubectl get pods -n kube-system -l k8s-app=calico-node
# ATAU jika menggunakan Cilium:
kubectl get pods -n kube-system -l k8s-app=cilium
```

---

## 10. Practical Example: Konfigurasi Calico BGP Direct Routing
Mengubah Calico dari mode enkapsulasi VXLAN menjadi mode Direct Routing BGP murni (tanpa enkapsulasi) di subnet lokal:

```yaml
apiVersion: crd.projectcalico.org/v1
kind: IPPool
metadata:
  name: default-ipv4-ippool
spec:
  cidr: 10.244.0.0/16
  # Nonaktifkan VXLAN saat traffic berada di subnet L2 yang sama (Direct Line-Speed!)
  vxlanMode: Never
  ipipMode: Never
  natOutgoing: true
  nodeSelector: all()
```

### Konfigurasi Cilium dengan Kube-Proxy Replacement (eBPF Murni):
```bash
cilium install \
  --set kubeProxyReplacement=true \
  --set k8sServiceHost=192.168.1.10 \
  --set k8sServicePort=6443 \
  --set hubble.ui.enabled=true
```

---

## 11. Real World Example: Migrasi E-Commerce 50.000 QPS dari Calico ke Cilium
Sebuah platform marketplace mengalami lonjakan CPU `system` (kernel space) sebesar 40% di seluruh worker node:
- **Investigasi**: Kluster memiliki 2.500 microservices dengan puluhan ribu endpoint. Perintah `iptables-save | wc -l` menunjukkan terdapat lebih dari **120.000 baris rule netfilter** di setiap server.
- Setiap kali ada pod baru yang auto-scale, Kubelet mengunci tabel iptables (`xtables lock`), memicu spike latensi p99 HTTP dari 15ms menjadi 1.200ms!
- **Solusi**: Tim SRE memigrasikan kluster ke **Cilium eBPF** dengan fitur `kubeProxyReplacement=true`.
- **Hasil**: 
  - Tabel iptables dibersihkan total.
  - Beban CPU kernel turun dari 40% menjadi 4%.
  - Latensi p99 kembali stabil di 12ms flat pada beban 50.000 QPS.

---

## 12. Trade-offs: CNI Matrix

| Kriteria | Calico (Standar Industri) | Cilium (Next-Gen eBPF) | Cloud Native (AWS VPC CNI) |
|---|---|---|---|
| **Mekanisme Inti** | iptables, IPVS, BGP Peering | Linux eBPF Native | Native AWS ENI IPAM |
| **Overhead CPU di Skala Besar** | Tinggi jika > 10.000 iptables rules | Sangat Rendah (Hash Map $O(1)$) | Sangat Rendah |
| **Observabilitas Terintegrasi** | Terbatas pada L3/L4 | Luar Biasa (Cilium Hubble L7 UI) | AWS CloudWatch VPC Flow Logs |
| **Kebutuhan Kernel Linux** | Bekerja di kernel lama (Linux 3.10+) | Membutuhkan kernel modern ($\ge$ 5.4+) | AWS Linux eksklusif |

---

## 13. When To Use
- Gunakan **Cilium** untuk seluruh kluster produksi baru dengan Linux Kernel modern ($\ge 5.4$) yang menginginkan performa terbaik, observabilitas Hubble L7, dan eliminasi kube-proxy.
- Gunakan **Calico** jika Anda membutuhkan BGP peering langsung ke switch fisik data center on-premise atau menjalankan OS Linux dengan kernel legacy.
- Gunakan **AWS VPC CNI** jika compliance perusahaan mewajibkan setiap Pod memiliki alamat IP VPC AWS asli yang dapat diaudit langsung oleh Security Group AWS.

---

## 14. When NOT To Use
- Jangan gunakan mode **Overlay (VXLAN)** jika infrastruktur jaringan Anda mendukung Direct Routing murni di satu subnet L2 yang sama, karena Anda membuang 2-5% throughput untuk komputasi enkapsulasi yang tidak perlu.
- Jangan pasang Cilium pada server Linux tua (seperti CentOS 7 dengan kernel 3.10) karena kernel tersebut tidak memiliki subsistem eBPF yang memadai.

---

## 15. Common Mistakes
1. **Salah Menghitung MTU**: Mengonfigurasi MTU jaringan Pod sebesar 1500 di atas jaringan VXLAN yang membutuhkan 50 byte header enkapsulasi. Akibatnya, paket IP terfragmentasi atau di-drop (`Packet Too Big`), menyebabkan koneksi TLS handshake menggantung (*hung connection*).
2. **Kehabisan IP Subnet pada Cloud VPC CNI**: Menjalankan AWS VPC CNI pada subnet `/24` (256 IP). Dalam hitungan jam, autoscaling Pod menghabiskan seluruh IP subnet VPC, menyebabkan Pod baru stuck di status `ContainerCreating`.
3. **Mengaktifkan dua CNI sekaligus**: Memasang Calico di atas kluster yang sudah memiliki Flannel tanpa menghapus konfigurasi `/etc/cni/net.d/`, menyebabkan konflik routing Pod.

---

## 16. Best Practices
### Must Have
- Selalu sesuaikan nilai MTU interface Pod dengan tipe jaringan Anda:
  - Direct Routing / Native: `MTU = 1500` (atau `9000` untuk Jumbo Frames).
  - VXLAN Overlay: `MTU = 1450` (1500 - 50 byte header VXLAN).
- Konfigurasikan pool IPAM CNI dengan subnet yang cukup luas (misal `/16` untuk menampung puluhan ribu Pod).

### Recommended
- Manfaatkan fitur **eBPF Host Routing** pada Cilium untuk memangkas latensi komunikasi antar-Pod di node yang sama (*same-node routing*).
- Aktifkan **Cilium Hubble** untuk inspeksi grafis aliran traffic antar service di kluster.

### Advanced
- Di data center on-premise, hubungkan Calico node dengan Top-of-Rack (ToR) Switch menggunakan BGP Route Reflector untuk routing Pod IP lintas rack tanpa enkapsulasi overlay.

---

## 17. Troubleshooting Guide
### Problem 1: Pod baru stuck di `ContainerCreating` dengan error `networkPlugin cni failed to set up pod network`
- **Penyebab**: Biner CNI tidak ditemukan di `/opt/cni/bin/` atau pool IPAM kehabisan IP address.
- **Diagnosa**:
  ```bash
  kubectl describe pod <nama-pod>
  # Periksa log Kubelet di worker node
  journalctl -u kubelet -e | grep -i cni
  ```
- **Solusi**: Periksa apakah pod daemon CNI (Calico/Cilium) berjalan sehat di node tersebut (`kubectl get pods -n kube-system -o wide`).

### Problem 2: Koneksi HTTP kecil berhasil, tetapi file download besar (> 1.5KB) macet/timeout
- **Penyebab**: **MTU Mismatch**. Paket besar terfragmentasi dan di-drop oleh switch/overlay.
- **Solusi**: Turunkan nilai MTU di konfigurasi CNI ConfigMap menjadi `1450` atau `1440`.

---

## 18. Exercises
### Level: Easy
1. Periksa file konfigurasi CNI aktif di direktori `/etc/cni/net.d/` pada kluster pengujian Anda.
2. Identifikasi alamat IP yang diberikan CNI kepada salah satu Pod dan periksa interface virtual `veth*` di node Linux host menggunakan perintah `ip link`.

### Level: Medium
1. Jalankan pengujian performa throughput antar-dua Pod di node berbeda menggunakan utilitas `iperf3`.
2. Catat throughput dan bandingkan latensi ping antar Pod.

### Level: Hard
1. Install Cilium CLI di workstation Anda: `cilium status`.
2. Aktifkan Hubble UI dan amati visualisasi traffic Layer 7 (HTTP Request / Response code) secara real-time saat Anda mengakses salah satu Service web di kluster.

---

## 19. Challenge
Rancang arsitektur CNI performa tinggi untuk platform transaksi trading saham frekuensi tinggi (High-Frequency Trading):
- Menuntut throughput masif dan latensi p99 di bawah 5ms.
- 100 worker node bare-metal di data center on-premise.
- Bandingkan desain implementasi antara:
  1. Calico BGP Peering ke Arista ToR Switch dengan Jumbo Frames (MTU 9000).
  2. Cilium eBPF Host Routing dengan Kube-Proxy Replacement.
Tuliskan analisis trade-off, mitigasi bottleneck iptables, dan diagram arsitektur jaringan lengkapnya.

---

## 20. Summary
- **CNI** adalah standar antarmuka terbuka yang bertanggung jawab mengimplementasikan model jaringan datar (*flat network*) Kubernetes.
- **Overlay Networking (VXLAN)** mudah dikonfigurasi tetapi memiliki penalti overhead MTU (50 byte), sedangkan **Direct Routing (BGP)** menawarkan performa line-rate tanpa enkapsulasi.
- **Project Calico** adalah standar industri tangguh berbasis iptables dan BGP routing.
- **Cilium** memimpin generasi baru dengan **Linux eBPF**, menggantikan kube-proxy, memproses paket di level socket dengan kompleksitas $O(1)$, dan memberikan visibilitas keamanan Layer 7 transparan via Hubble.

---
[⬅️ Evaluasi & Quiz BAB 05](../BAB-05-Networking-Service-Discovery-dan-Ingress/BAB-05-Quiz-dan-Challenge.md) | [📋 Silabus Induk](../README.md) | [Module 02: NetworkPolicies & Microsegmentation ➡️](./Module-02-NetworkPolicies-Default-Deny-dan-Microsegmentation.md)
---
