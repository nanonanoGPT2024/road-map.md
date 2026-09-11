# Module 01: Network Drivers (Bridge, Host, None, Macvlan) & Port Forwarding

## 1. Learning Objective
Setelah menyelesaikan modul ini, pembelajar diharapkan mampu:
- Menguasai arsitektur 5 Network Drivers bawaan Docker: **bridge**, **host**, **none**, **macvlan**, dan **overlay**.
- Memahami isolasi Linux Network Namespace (`NET namespace`) dan pasangan interface virtual ethernet (**veth pair**).
- Membedakan secara presisi mekanisme publikasi port: `-p <host_port>:<container_port>`, `-p <container_port>` (ephemeral), dan pengikatan ke IP lokal (`-p 127.0.0.1:...`).
- Menjelaskan bagaimana Docker Engine memanipulasi aturan **iptables** kernel (`DOCKER` chain & DNAT) untuk merutekan paket data.
- Menentukan kapan driver `host` lebih unggul untuk aplikasi berkecepatan tinggi (*high-throughput*) vs driver `bridge` untuk isolasi aman.

---

## 2. Prerequisite
- Memahami konsep dasar jaringan komputer: IP Address, Subnet mask, Port TCP/UDP, dan NAT (BAB 02 Module 01 DevOps).
- Memahami Linux Network Namespace (BAB 01 Module 02 Docker).
- Mengetahui cara kerja tabel firewall `iptables` di Linux.

---

## 3. Concept
Setiap kali container dibuat menggunakan driver default **bridge**, Docker menciptakan **Network Namespace** mandiri untuk container tersebut. Di dalam container, proses memiliki antarmuka jaringan sendiri (`eth0`), alamat IP privat sendiri (biasanya di subnet `172.17.0.0/16`), tabel routing sendiri, dan firewall iptables sendiri.

Untuk menghubungkan container ke jaringan luar, Docker membuat sepasang kabel jaringan virtual (**veth pair**):
- Ujung kabel satu (`eth0`) dicolokkan ke dalam container namespace.
- Ujung kabel lainnya (`vethxxxx`) dicolokkan ke virtual switch di host yang disebut bridge **`docker0`**.

```
       DOCKER BRIDGE NETWORKING TOPOLOGY
 ┌─────────────────────────────────────────────────────────────────────────────┐
 │ HOST MACHINE                                                                │
 │  Host IP: 192.168.1.50 (eth0)                                               │
 │                                                                             │
 │  ┌───────────────────────────────────────────────────────────────────────┐  │
 │  │ Virtual Bridge: docker0 (IP: 172.17.0.1 / Subnet: 172.17.0.0/16)       │  │
 │  └───────┬───────────────────────────────────────────────────────┬───────┘  │
 │          │ veth_a123 (Host End)                                  │ veth_b456 │
 │          │                                                       │           │
 │          ▼ veth pair tunnel                                      ▼           │
 │  ┌───────────────────────────────┐       ┌───────────────────────────────┐  │
 │  │ CONTAINER 1 (NET Namespace)   │       │ CONTAINER 2 (NET Namespace)   │  │
 │  │  Interface: eth0              │       │  Interface: eth0              │  │
 │  │  IP: 172.17.0.2               │       │  IP: 172.17.0.3               │  │
 │  │  App: Nginx Web (Port 80)     │       │  App: Redis Cache (Port 6379) │  │
 │  └───────────────────────────────┘       └───────────────────────────────┘  │
 └─────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Why?
1. **Pencegahan Konflik Port Antar-Aplikasi**: Dua aplikasi berbeda yang sama-sama ingin mendengarkan port 80 (misal dua web server berbeda) dapat berjalan bersamaan di host yang sama karena masing-masing memiliki IP dan port 80 terisolasi di namespacenya sendiri.
2. **Keamanan Melalui Isolasi Jaringan**: Database di container backend tidak perlu diekspos ke publik; hanya port web gateway yang dipublikasikan ke host, mengurangi drastis *attack surface* sistem.
3. **Performa Ultra-Tinggi dengan Driver `host`**: Untuk aplikasi dengan kebutuhan jutaan paket per detik (seperti pialang telekomunikasi VoIP atau video streaming), network virtualisasi bridge dapat di-bypass sepenuhnya menggunakan `--network host`.

---

## 5. What?
### Komparasi 5 Docker Network Drivers:

| Driver | Tingkat Isolasi | Alamat IP Container | Overhead Performa | Use Case Utama |
|---|---|---|---|---|
| **`bridge`** | Terisolasi Penuh | IP privat di subnet virtual (`172.17.x.x`) | Rendah-Sedang (NAT traversal) | Default untuk aplikasi web & microservices |
| **`host`** | **TIDAK DIISOLASI** | Menggunakan langsung IP & Port host | **Nol (Native Host Speed)** | Aplikasi high-throughput, monitoring agent |
| **`none`** | **ISOLASI TOTAL** | Hanya loopback (`127.0.0.1`) | Nol | Batch crypto, komputasi terisolasi anti-leak |
| **`macvlan`** | Terisolasi | Mendapat MAC & IP fisik di router LAN fisik | Sangat Rendah | Migrasi aplikasi legacy yang butuh IP LAN nyata |
| **`overlay`** | Terisolasi Multi-Host | Virtual subnet melintasi multi-server | Sedang (VXLAN encapsulation) | Docker Swarm & multi-node clusters |

---

## 6. How?
### Cara Kerja Port Publishing (`-p`) dan iptables:
Saat Anda mengeksekusi `docker run -p 8080:80 nginx`, Docker Engine tidak sekadar membuka port. Docker melakukan langkah teknis berikut:
1. **Memasang Aturan DNAT (Destination NAT)**:
   Docker menambahkan aturan ke tabel `iptables` rantai `PREROUTING` dan `DOCKER`:
   ```bash
   -A DOCKER -p tcp -m tcp --dport 8080 -j DNAT --to-destination 172.17.0.2:80
   ```
2. **Rute Paket Masuk**:
   Setiap paket dari luar yang menuju `Host_IP:8080` dicegat oleh kernel Linux, alamat IP tujuannya diubah menjadi `172.17.0.2:80`, dan diteruskan melewati bridge `docker0`.
3. **Penyaringan Binding IP**:
   - `docker run -p 8080:80`: Port 8080 terbuka ke **seluruh dunia** (`0.0.0.0:8080`).
   - `docker run -p 127.0.0.1:8080:80`: Port 8080 **HANYA bisa diakses dari localhost** mesin itu sendiri (Sangat disarankan untuk database atau service internal!).

---

## 7. Analogy
Bayangkan **Docker Network Drivers** seperti **Sistem Telepon Kantor**:
- **Bridge Network** seperti **Sistem Telepon Interkom Extension Kantor (PBX)**: Setiap meja karyawan memiliki nomor extension internal (`101`, `102`). Orang luar tidak bisa menelpon extension 102 langsung tanpa melewati nomor telepon kantor utama dan operator (**Port Forwarding / NAT**).
- **Host Network** seperti **Karyawan yang Membawa HP Satelit Sendiri**: Karyawan tidak menggunakan interkom kantor; mereka langsung terhubung ke tiang pemancar BTS luar tanpa perantara. Sangat cepat, namun jika dua karyawan memakai nomor HP yang sama, akan terjadi bentrok (*Port conflict*).
- **None Network** seperti **Ruang Kedap Suara Tanpa Kabel Telepon**: Siapapun yang ada di dalam ruangan tidak bisa berkomunikasi ke luar sama sekali.

---

## 8. Diagram
```
+-----------------------------------------------------------------------------------+
|               IPTABLES DNAT PACKET FLOW (PORT FORWARDING -p 8080:80)              |
+-----------------------------------------------------------------------------------+

 [ Incoming Packet from Internet ]
   ↳ Destination: 192.168.1.50:8080 (Host IP)
             │
             ▼
 ┌─────────────────────────────────────────────────────────────────────────────┐
 │ Linux Host Kernel (iptables PREROUTING Chain)                               │
 │                                                                             │
 │  Match Rule: If protocol=TCP and dport=8080                                 │
 │  Action: DNAT (Rewrite destination IP to 172.17.0.2:80)                     │
 └──────────────────────────────────────┬──────────────────────────────────────┘
                                        │
                                        ▼ (Forwarded across bridge)
 ┌──────────────────────────────────────┴──────────────────────────────────────┐
 │ Bridge Device: docker0                                                      │
 └──────────────────────────────────────┬──────────────────────────────────────┘
                                        │ (Enters veth tunnel)
                                        ▼
 ┌─────────────────────────────────────────────────────────────────────────────┐
 │ Container eth0 (172.17.0.2)                                                 │
 │  ↳ Nginx receives packet on local port 80 cleanly!                          │
 └─────────────────────────────────────────────────────────────────────────────┘
```

---

## 9. Simple Example: Perintah Mengelola Network Driver
Eksplorasi perintah CLI di terminal:

```bash
# 1. Menampilkan seluruh network yang tersedia di Docker
docker network ls

# 2. Menjalankan container dengan driver none (Isolasi total tanpa internet)
docker run --rm --network none alpine ip addr
# Output: Hanya ada loopback interface (lo: 127.0.0.1), eth0 TIDAK ADA!

# 3. Menjalankan container dengan driver host (Kecepatan native)
docker run -d --name web-host --network host nginx:alpine
# Port 80 otomatis terbuka langsung di IP host tanpa perlu flag -p!

# 4. Mempublikasikan port secara aman hanya ke localhost
docker run -d --name db-secure -p 127.0.0.1:5432:5432 postgres:alpine
```

---

## 10. Practical Example: Memeriksa Konfigurasi iptables Docker
Melihat aturan translasi alamat jaringan yang dibuat oleh Docker di Linux host:

```bash
# Menampilkan rantai DOCKER pada tabel nat
sudo iptables -t nat -L DOCKER -n -v

# Output tipikal:
# Chain DOCKER (2 references)
# pkts bytes target     prot opt in     out     source       destination         
#    0     0 DNAT       tcp  --  !docker0 *     0.0.0.0/0    0.0.0.0/0     tcp dpt:8080 to:172.17.0.2:80
```

---

## 11. Real World Example: Optimalisasi Latensi Video Streaming Media Gateway
Sebuah platform video live-streaming WebRTC mentransmisikan ribuan stream video UDP secara bersamaan:
- **Masalah Awal**: Menggunakan driver default `bridge` dengan ratusan port forwarding UDP (`-p 20000-25000:20000-25000/udp`). Docker Engine mengalami freeze karena kernel Linux harus menulis 5.000 baris aturan iptables, dan overhead NAT menyebabkan latensi jitter video tinggi (*packet loss 8%*).
- **Solusi dengan Driver `host`**:
  Aplikasi gateway dimigrasikan menggunakan `--network host`:
  `docker run -d --name webrtc-gateway --network host my-streaming-app:prod`.
- **Hasil**: Seluruh 5.000 aturan iptables hilang, overhead NAT ditiadakan, penggunaan CPU host turun 35%, dan packet loss berkurang menjadi $0.02\%$ (kualitas video kristal jernih).

---

## 12. Trade-offs

| Aspek | Bridge Driver | Host Driver | None Driver |
|---|---|---|---|
| **Isolasi Keamanan Port** | Sangat Aman (Port dipetakan selektif) | Rendah (Port container langsung terbuka di host) | Maksimal (Tidak ada network) |
| **Pencegahan Port Conflict** | Bebas (Bisa jalankan 10 web di port 80) | Kaku (Hanya 1 container per nomor port host) | N/A |
| **Throughput & Latency** | Sedikit terpotong oleh NAT filter | **100% Native Performance (Tercepat)** | N/A |
| **Kemudahan Port Mapping** | Fleksibel via `-p` | Flag `-p` diabaikan sepenuhnya | Flag `-p` tidak berlaku |

---

## 13. When To Use
- **Driver `bridge`**: 95% dari seluruh aplikasi microservices, database internal, API gateway.
- **Driver `host`**: Aplikasi yang membutuhkan throughput jaringan ekstrem (WebRTC, live streaming, proxy reverse cache raksasa) atau tool pemantauan jaringan host (Prometheus Node Exporter).
- **Driver `none`**: Job pemrosesan data rahasia offline, verifikasi lisensi offline, atau batch job komputasi matematika murni.

---

## 14. When NOT To Use
- Jangan gunakan driver `host` jika Anda menjalankan container yang tidak terpercaya (*untrusted code*), karena container dapat mengakses seluruh socket port loopback dan layanan internal host.
- Jangan gunakan `-p 0.0.0.0:port` untuk database produksi jika server memiliki IP publik; selalu ikat ke private IP atau `127.0.0.1`.

---

## 15. Common Mistakes
1. **Mengira UFW / Firewall Linux Melindungi Port Docker**: Docker memanipulasi aturan `iptables` di rantai `PREROUTING` yang **mendahului (*bypasses*) aturan firewall UFW** bawaan Ubuntu! Jika Anda mengetik `docker run -p 8080:80 nginx`, port 8080 akan langsung terbuka ke seluruh internet publik meskipun UFW berstatus `ufw deny 8080`. Selalu gunakan `-p 127.0.0.1:8080:80` jika port hanya untuk konsumsi internal.
2. **Mencoba Menggunakan Flag `-p` Bersamaan dengan `--network host`**: Docker akan mengeluarkan pesan peringatan: `WARNING: Published ports are discarded when using host network mode`.
3. **Mengandalkan IP Dinamis Bridge Container di Kode Aplikasi**: Menuliskan IP hardcoded `172.17.0.2` di file konfigurasi. Begitu container direstart, IP tersebut bisa berubah menjadi `172.17.0.3`, menyebabkan koneksi putus. Gunakan **User-Defined Bridge dengan DNS**!

---

## 16. Best Practices
### Must Have
- Selalu ikat port internal sensitif ke localhost: `-p 127.0.0.1:<port>:<port>`.
- Jangan menggunakan driver default bridge untuk komunikasi antar-container di produksi (gunakan User-Defined Bridge).
- Nonaktifkan `userland-proxy` di `/etc/docker/daemon.json` (`"userland-proxy": false`) untuk mengurangi overhead proses `docker-proxy` di memori dan membiarkan iptables menangani routing secara langsung.

### Recommended
- Berikan nama yang bermakna pada interface virtual menggunakan fitur kustom network.
- Batasi jumlah container per subnet untuk menghindari exhaustion pool alamat IP.

### Advanced
- Gunakan driver `macvlan` dengan trunking 802.1q VLAN untuk menghubungkan container langsung ke segmen jaringan korporat fisik.

---

## 17. Troubleshooting
- **Masalah**: Container di dalam bridge tidak bisa mengakses internet luar (misal gagal `ping 8.8.8.8`).
  - *Penyebab*: Fitur IP Forwarding pada kernel Linux host dinonaktifkan.
  - *Solusi*: Aktifkan IP forwarding: `sudo sysctl -w net.ipv4.ip_forward=1` dan pastikan permanen di `/etc/sysctl.conf`.
- **Masalah**: `Error starting userland proxy: listen tcp4 0.0.0.0:80: bind: address already in use`.
  - *Penyebab*: Port 80 di host sudah dipakai oleh proses lain (misal Apache atau Nginx host).
  - *Solusi*: Cari proses yang memakan port dengan `sudo netstat -tulpn | grep :80` dan ubah port publikasi container menjadi misal `-p 8080:80`.

---

## 18. Exercise
1. Jalankan container dengan driver `none` dan buktikan dengan perintah `docker exec <id> ping 127.0.0.1` (berhasil) dan `ping 8.8.8.8` (gagal total).
2. Jalankan container web yang dipublikasikan hanya ke interface loopback `127.0.0.1:9090:80`. Buktikan bahwa container bisa diakses via `curl http://127.0.0.1:9090` namun tidak bisa diakses via IP LAN host Anda!

---

## 19. Challenge
Rancang arsitektur segmentasi jaringan Docker:
- Buat container aplikasi yang berjalan pada custom bridge network.
- Inspeksi aturan iptables DNAT dan MASQUERADE yang dihasilkan oleh kernel untuk port tersebut.
- Simulasikan kebocoran port publik dan amankan konfigurasi menggunakan binding eksplisit ke alamat IP privat.

---

## 20. Summary
- Docker menyediakan 5 network drivers utama: **bridge** (standar isolasi), **host** (performa native tanpa isolasi), **none** (isolasi absolut), **macvlan** (IP fisik LAN), dan **overlay** (multi-host).
- Mekanisme port forwarding (`-p`) bekerja melalui manipulasi tabel `iptables` kernel (DNAT).
- Docker bypass aturan firewall UFW secara default, mewajibkan insinyur untuk selalu mengikat port internal secara hati-hati ke `127.0.0.1`.
