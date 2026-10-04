# Panduan Hands-On Lab: Network Monitoring, Telemetry & Chaos Engineering

## 1. Overview Lab
Lab ini menyediakan simulasi komprehensif tingkat lanjut untuk:
1. Menjalankan NetFlow v9 telemetry collector & analyzer mandiri.
2. Mengonfigurasi virtual network environment menggunakan Linux Network Namespaces.
3. Melakukan injeksi degradasi traffic (*Chaos Engineering*) menggunakan Linux `tc-netem`.
4. Mengidentifikasi, mengisolasi, dan memverifikasi anomali performa TCP MTU Blackhole dan ZeroWindow menggunakan `tcpdump`.

---

## 2. Topologi Lab & Komponen
```
 [ns-client]                      [ns-router]                     [ns-server]
(10.10.1.2/24) <---> [veth-c] (10.10.1.1/24 | 10.10.2.1/24) [veth-s] <---> (10.10.2.2/24)
                           (Linux TC Chaos Injection)
```

---

## 3. Prasyarat Sistem
- OS: Linux (Ubuntu 22.04 LTS / Debian 12 / RHEL 9 direkomendasikan).
- Akses `sudo` / root user.
- Paket yang wajib terpasang:
  ```bash
  sudo apt-get update
  sudo apt-get install -y iproute2 tcpdump python3 iptables iperf3 tshark
  ```

---

## 4. Langkah demi Langkah Pelaksanaan

### Langkah 1: Setup Network Namespaces Sandbox
Jalankan skrip berikut untuk membangun virtual network isolated:
```bash
# 1. Hapus namespace lama jika ada
sudo ip netns del ns-client 2>/dev/null || true
sudo ip netns del ns-router 2>/dev/null || true
sudo ip netns del ns-server 2>/dev/null || true

# 2. Buat Namespaces baru
sudo ip netns add ns-client
sudo ip netns add ns-router
sudo ip netns add ns-server

# 3. Buat Virtual Ethernet Pairs
sudo ip link add veth-c-in type veth peer name veth-c-out
sudo ip link add veth-s-in type veth peer name veth-s-out

# 4. Hubungkan Interface ke Namespace
sudo ip link set veth-c-in netns ns-client
sudo ip link set veth-c-out netns ns-router
sudo ip link set veth-s-out netns ns-router
sudo ip link set veth-s-in netns ns-server

# 5. Konfigurasi Pengalamatan IP & Routing
# Subnet Client-Router: 10.10.1.0/24
sudo ip netns exec ns-client ip addr add 10.10.1.2/24 dev veth-c-in
sudo ip netns exec ns-client ip link set veth-c-in up
sudo ip netns exec ns-client ip link set lo up
sudo ip netns exec ns-client ip route add default via 10.10.1.1

sudo ip netns exec ns-router ip addr add 10.10.1.1/24 dev veth-c-out
sudo ip netns exec ns-router ip link set veth-c-out up

# Subnet Router-Server: 10.10.2.0/24
sudo ip netns exec ns-router ip addr add 10.10.2.1/24 dev veth-s-out
sudo ip netns exec ns-router ip link set veth-s-out up
sudo ip netns exec ns-router ip link set lo up

sudo ip netns exec ns-server ip addr add 10.10.2.2/24 dev veth-s-in
sudo ip netns exec ns-server ip link set veth-s-in up
sudo ip netns exec ns-server ip link set lo up
sudo ip netns exec ns-server ip route add default via 10.10.2.1

# 6. Aktifkan IP Forwarding di Namespace Router
sudo ip netns exec ns-router sysctl -w net.ipv4.ip_forward=1
```

Verifikasi konektivitas:
```bash
sudo ip netns exec ns-client ping -c 3 10.10.2.2
```

---

### Langkah 2: Menjalankan NetFlow Analyzer
Buka terminal baru, jalankan analyzer script:
```bash
chmod +x netflow_collector_analyzer.py
sudo python3 netflow_collector_analyzer.py
```
*Catatan: Analyzer akan siap menerima paket flow UDP pada port 2055.*

---

### Langkah 3: Skenario Chaos Engineering (Simulasi Packet Loss & Latency)
Buka terminal baru dan aplikasikan chaos profile pada `ns-router`:
```bash
# Injeksi 100ms Base Delay + 20ms Jitter + 5% Packet Drop
sudo ip netns exec ns-router tc qdisc add dev veth-s-out root netem delay 100ms 20ms loss 5%

# Jalankan pengujian bandwidth menggunakan iperf3
# Terminal Tab A (Server):
sudo ip netns exec ns-server iperf3 -s

# Terminal Tab B (Client):
sudo ip netns exec ns-client iperf3 -c 10.10.2.2 -t 10
```
Amati bagaimana TCP congestion window (Cubic/BBR) tertekan dan throughput turun secara signifikan akibat retransmission.

---

### Langkah 4: Skenario Triage MTU Blackhole Discovery
Kita akan merekayasa insiden MTU Mismatch dan blokir ICMP (Penyebab umum kegagalan transaksi web).

1. Kecilkan MTU link internal router ke server menjadi 1400:
   ```bash
   sudo ip netns exec ns-router ip link set dev veth-s-out mtu 1400
   ```
2. Blokir pesan ICMP Fragmentation Needed pada router:
   ```bash
   sudo ip netns exec ns-router iptables -A FORWARD -p icmp --icmp-type 3/4 -j DROP
   ```
3. Mulai monitoring packet capture di sisi client:
   ```bash
   sudo ip netns exec ns-client tcpdump -i veth-c-in -nnvv "tcp or icmp" &
   ```
4. Kirimkan paket data besar melebihi 1400 byte dengan flag DF=1 (Don't Fragment):
   ```bash
   sudo ip netns exec ns-client ping -c 2 -M do -s 1450 10.10.2.2
   ```
   *Hasil*: Paket akan hilang tanpa jejak (blackholed), membuktikan bahaya memblokir ICMP type 3/4 secara sembarangan.

---

### Langkah 5: Pemulihan (Cleanup)
Setelah pengujian selesai, bersihkan seluruh resource lab:
```bash
# Hapus rule tc
sudo ip netns exec ns-router tc qdisc del dev veth-s-out root 2>/dev/null || true

# Hapus network namespaces
sudo ip netns del ns-client
sudo ip netns del ns-router
sudo ip netns del ns-server

# Matikan proses background iperf3 dan collector
sudo pkill -f iperf3 || true
sudo pkill -f netflow_collector_analyzer.py || true
```

---

## 5. Kriteria Keberhasilan Verifikasi
1. Namespaces `ns-client` dapat saling berkirim paket ke `ns-server` dengan routing multi-hop.
2. Skrip NetFlow Collector berhasil menginisialisasi listener socket dan merender terminal visualisasi.
3. Injeksi Linux `tc` terbukti memodifikasi latency dan packet loss statistik saat diverifikasi melalui `ping` dan `iperf3`.
4. Anda dapat mereplikasi anomali MTU Blackhole dan membuktikannya via output log `tcpdump`.