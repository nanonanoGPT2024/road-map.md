# Module 02: Embedded DNS, User-Defined Bridges, & Network Segmentation

## 1. Learning Objective
Setelah menyelesaikan modul ini, pembelajar diharapkan mampu:
- Membedakan secara tajam antara **Default Bridge (`docker0`)** dan **User-Defined Bridge Network**.
- Memahami arsitektur **Docker Embedded DNS Server (`127.0.0.11`)** untuk penemuan layanan otomatis (*Service Discovery by Container Name*).
- Menghilangkan anti-pattern legacy flag `--link` dan menggantinya dengan jaringan kustom deklaratif.
- Merancang **Network Segmentation** untuk mengisolasi tier aplikasi (Frontend Network vs Backend Network) guna mencegah pergerakan lateral penyerang (*Lateral Movement*).
- Mengoperasikan perintah CLI manajemen jaringan: `docker network create`, `connect`, `disconnect`, dan `inspect`.

---

## 2. Prerequisite
- Memahami konsep dasar driver bridge dan port forwarding iptables (BAB 05 Module 01).
- Mengetahui cara kerja protokol Domain Name System (DNS) query A-Record (BAB 02 Module 01 DevOps).
- Pemahaman dasar tentang arsitektur Three-Tier (Web -> API -> Database).

---

## 3. Concept
Salah satu jebakan terbesar bagi pemula Docker adalah berasumsi bahwa dua container yang dijalankan tanpa flag network dapat saling memanggil nama domain masing-masing (misal `ping my-db`). Pada **Default Bridge (`docker0`)**, resolusi nama otomatis **TIDAK DIDUKUNG** (kecuali menggunakan flag usang `--link`).

Ketika Anda membuat **User-Defined Bridge Network** (`docker network create my-net`), Docker Engine secara otomatis mengaktifkan server DNS internal berkecepatan tinggi pada alamat IP **`127.0.0.11`**. Setiap container yang bergabung ke dalam jaringan ini dapat memanggil container lain hanya dengan menyebutkan **nama container** atau **network alias-nya**, tanpa pernah memedulikan perubahan alamat IP dinamis.

```
       USER-DEFINED BRIDGE & EMBEDDED DNS ARCHITECTURE
 ┌─────────────────────────────────────────────────────────────────────────────┐
 │ CUSTOM DOCKER NETWORK: 'app-network' (Subnet: 172.20.0.0/16)                │
 │                                                                             │
 │  ┌───────────────────────────────────────────────────────────────────────┐  │
 │  │ DOCKER EMBEDDED DNS SERVER (127.0.0.11)                               │  │
 │  │  Routing Table:                                                       │  │
 │  │   - "order-api"  ──> 172.20.0.2                                       │  │
 │  │   - "postgres-db"──> 172.20.0.3                                       │  │
 │  └───────────────────▲───────────────────────────────▲───────────────────┘  │
 │                      │ DNS Query: "postgres-db"      │                      │
 │                      │ Answer: "172.20.0.3"          │                      │
 │                      │                               │                      │
 │  ┌───────────────────┴───────────┐       ┌───────────┴───────────────────┐  │
 │  │ Container: order-api          │       │ Container: postgres-db        │  │
 │  │ IP: 172.20.0.2                │       │ IP: 172.20.0.3                │  │
 │  │ (Connects to 'postgres-db')   │──────>│ (Listens on port 5432)        │  │
 │  └───────────────────────────────┘       └───────────────────────────────┘  │
 └─────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Why?
1. **Eliminasi IP Hardcoding**: Di lingkungan cloud, container dapat di-restart kapan saja dan mendapatkan IP baru (`172.20.0.5` berubah menjadi `172.20.0.8`). Menggunakan DNS berbasis nama container membuat konfigurasi database di kode aplikasi bersifat statis dan tahan banting: `DATABASE_URL=postgres://user:pass@postgres-db:5432/main`.
2. **Segmentasi Keamanan Multi-Tier (*Defense in Depth*)**: Di default bridge, seluruh container di server berbagi subnet yang sama. Jika container blog WordPress diretas, penyerang dapat memindai port database perbankan internal di subnet tersebut. Dengan User-Defined Bridges, kita dapat memisahkan jaringan sehingga container web publik **secara fisik tidak bisa mengirim paket jaringan apa pun** ke database internal.
3. **Pemberian Alias Fleksibel (*Service Aliasing*)**: Sebuah container database dapat memiliki alias `db`, `primary-db`, dan `analytics-db` sekaligus tanpa mengubah nama container fisiknya.

---

## 5. What?
### Default Bridge vs User-Defined Bridge:

| Fitur | Default Bridge (`bridge` / `docker0`) | User-Defined Bridge (`custom-net`) |
|---|---|---|
| **Resolusi DNS Otomatis** | ❌ **TIDAK DIDUKUNG** (Hanya via IP) | ✅ **DIDUKUNG PENUH via 127.0.0.11** |
| **Isolasi Lingkungan** | Seluruh container bercampur di satu subnet | Terisolasi per jaringan (Keamanan tinggi) |
| **Koneksi On-the-Fly** | Harus restart container untuk ganti network | Bisa `docker network connect` saat container jalan |
| **Kustomisasi Subnet & Gateway** | Kaku (Dikelola otomatis oleh daemon) | Bebas (Bisa atur `--subnet` dan `--gateway`) |
| **Dukungan Lingkungan Produksi** | Sangat Tidak Disarankan | **Standar Wajib Produksi** |

---

## 6. How?
### Implementasi Segmentasi Jaringan 3-Tier:
Tujuan: Container `web` bisa berbicara ke `api`. Container `api` bisa berbicara ke `db`. Namun container `web` **TIDAK BISA** berbicara langsung ke `db`.

1. **Buat 2 Jaringan Terpisah**:
   ```bash
   docker network create frontend-net
   docker network create backend-net
   ```
2. **Jalankan Database hanya di `backend-net`**:
   ```bash
   docker run -d --name database --network backend-net postgres:alpine
   ```
3. **Jalankan API dan Sambungkan ke KEDUA Jaringan**:
   ```bash
   docker run -d --name backend-api --network backend-net my-api:prod
   # Sambungkan juga ke frontend-net sebagai perantara
   docker network connect frontend-net backend-api
   ```
4. **Jalankan Web Server hanya di `frontend-net`**:
   ```bash
   docker run -d --name web-frontend --network frontend-net -p 80:80 nginx:alpine
   ```

Hasil Pengujian Jaringan:
- `web-frontend` -> `ping backend-api` : **SUCCESS (Resolved by DNS)**
- `backend-api` -> `ping database`     : **SUCCESS (Resolved by DNS)**
- `web-frontend` -> `ping database`    : **FAILED / BLOCKED (Network unreachable)**

---

## 7. Analogy
Bayangkan **Segmentasi Jaringan Docker** seperti **Akses Kartu RFID di Gedung Bank**:
- **Default Bridge** seperti Aula Pasar Terbuka: Pengunjung pasar, kasir bank, dan petugas brankas uang berdiri di satu ruangan tanpa sekat. Sangat rawan perampokan.
- **User-Defined Bridge**:
  - **`frontend-net`** adalah **Lobi Pelayanan Nasabah**: Nasabah umum (**Web**) dan Teller (**API**) bisa saling berbicara di lobi.
  - **`backend-net`** adalah **Ruang Brankas Besi Bawah Tanah**: Hanya Teller (**API**) dan Manajer Brankas (**Database**) yang memiliki kartu RFID untuk masuk ke ruangan ini.
  - Nasabah umum di lobi tidak memiliki kartu akses dan tidak bisa melangkahkan kaki 1 meter pun ke ruang brankas!

---

## 8. Diagram
```
+-----------------------------------------------------------------------------------+
|               THREE-TIER SECURE NETWORK SEGMENTATION ARCHITECTURE                 |
+-----------------------------------------------------------------------------------+

 ┌─────────────────────────────────────────────────────────────┐
 │ NETWORK: frontend-net                                       │
 │                                                             │
 │  ┌──────────────────────┐         ┌──────────────────────┐  │
 │  │ Container: web-front │         │ Container: api-gw    │  │
 │  │ (Public Facing: -p 80)────────>│ (Dual-Homed Node)    │  │
 │  └──────────────────────┘         └──────────┬───────────┘  │
 └──────────────────────────────────────────────┼──────────────┘
                                                │ Connected to both!
 ┌──────────────────────────────────────────────┼──────────────┐
 │ NETWORK: backend-net                         │              │
 │                                              ▼              │
 │                                   ┌──────────────────────┐  │
 │                                   │ Container: postgres  │  │
 │                                   │ (Isolated from Web!) │  │
 │                                   └──────────────────────┘  │
 └─────────────────────────────────────────────────────────────┘
  ❌ Direct connection from 'web-front' to 'postgres' is IMPOSSIBLE!
```

---

## 9. Simple Example: Demonstrasi Embedded DNS Resolving
Membuktikan penemuan service otomatis:

```bash
# 1. Buat custom bridge network
docker network create internal-net

# 2. Jalankan container database dengan nama 'my-redis'
docker run -d --name my-redis --network internal-net redis:alpine

# 3. Jalankan container Alpine sementara untuk menguji DNS
docker run --rm --network internal-net alpine ping -c 2 my-redis

# Output:
# PING my-redis (172.18.0.2): 56 data bytes
# 64 bytes from 172.18.0.2: seq=0 ttl=64 time=0.082 ms
# 64 bytes from 172.18.0.2: seq=1 ttl=64 time=0.076 ms
```

---

## 10. Practical Example: Menginspeksi IP dan Memberi Alias
Menambahkan alias jaringan pada container:

```bash
# Menghubungkan container dengan alias 'auth-service' dan 'identity'
docker network connect --alias auth-service --alias identity internal-net my-app

# Menginspeksi alokasi IP di dalam network
docker network inspect internal-net | jq '.[0].Containers'
```

---

## 11. Real World Example: Menghentikan Infeksi Malware Lateral di SaaS Fintech
Sebuah celah keamanan zero-day remote code execution (RCE) ditemukan pada plugin CMS blog publik perusahaan:
- **Konfigurasi Buruk Sebelumnya**: Seluruh container berjalan di default bridge `docker0`. Penyerang mengeksekusi script nmap di dalam container blog dan berhasil menemukan port database PostgreSQL produksi (port 5432) di IP `172.17.0.4`.
- **Mitigasi dengan Segmentasi User-Defined Bridge**:
  1. Blog dipindahkan ke jaringan terisolasi `public-blog-net`.
  2. Database produksi diisolasi murni di `core-banking-net`.
- **Hasil**: Ketika penyerang membobol blog dan mencoba memindai jaringan, kernel Linux langsung menolak paket jaringan karena tidak ada rute dan jembatan virtual antara kedua subnet tersebut. Sistem perbankan aman dari pencurian data.

---

## 12. Trade-offs

| Aspek | Single Shared Network | Segmented Networks (Multi-Bridge) |
|---|---|---|
| **Keamanan Data** | Rendah (Semua container bisa saling telusuri) | Sangat Tinggi (Isolasi antar-tier ketat) |
| **Kemudahan Setup** | Sangat Mudah (Cukup jalankan tanpa opsi) | Butuh perencanaan subnet & topologi |
| **Manajemen Koneksi** | Sederhana | Harus menghubungkan container perantara ke 2 network |
| **Kepatuhan Audit (Compliance)** | Sering ditolak auditor PCI-DSS/ISO | Memenuhi standar arsitektur keamanan zero-trust |

---

## 13. When To Use
- Seluruh arsitektur microservices dan multi-tier applications di lingkungan produksi.
- Selalu gunakan User-Defined Bridge untuk komunikasi antar-container via hostname/DNS.

---

## 14. When NOT To Use
- Jangan gunakan flag usang `--link` (fitur deprecated warisan Docker masa lalu yang memerlukan hardcode dan reboot container).
- Jangan menghubungkan container database secara langsung ke jaringan publik jika tidak ada kebutuhan akses luar.

---

## 15. Common Mistakes
1. **Mengira Default Bridge Memiliki DNS**: Menjalankan dua container di default bridge dan heran mengapa `ping app2` menghasilkan error `bad address 'app2'`. Default bridge **tidak memiliki embedded DNS**! Selalu buat custom network.
2. **Overlapping Subnet dengan Jaringan Fisik Kantor**: Mengonfigurasi `docker network create --subnet 192.168.1.0/24`. Jika subnet tersebut sama dengan subnet Wi-Fi kantor Anda, server tidak akan bisa mengakses router internet kantor karena tabel routing bentrok.
3. **Lupa Melepas Network Sebelum Menghapus**: Menghapus container tanpa memutuskan koneksi dari network khusus tertentu saat troubleshooting, meninggalkan interface virtual yang menggantung.

---

## 16. Best Practices
### Must Have
- Buat minimal satu User-Defined Bridge untuk setiap project aplikasi (`docker network create <project>-net`).
- Gunakan nama container atau network alias sebagai hostname di string koneksi aplikasi (misal `redis:6379`).
- Pisahkan jaringan backend dari jaringan ingress publik.

### Recommended
- Konfigurasikan subnet eksplisit jika mengelola banyak jaringan: `docker network create --subnet 10.200.1.0/24 secure-net`.
- Dokumentasikan topologi jaringan di file arsitektur atau Docker Compose.

### Advanced
- Gabungkan dengan Docker Network Encryption (`--opt encrypted`) saat menggunakan driver Overlay di Docker Swarm untuk mengenkripsi seluruh traffic antar-host via IPSec.

---

## 17. Troubleshooting
- **Masalah**: `nslookup my-service` menghasilkan `server can't find my-service: NXDOMAIN`.
  - *Penyebab*: Kedua container berada di jaringan yang berbeda, atau container tujuan belum berstatus *Running*.
  - *Solusi*: Jalankan `docker network inspect <net_name>` dan pastikan kedua container terdaftar di blok `Containers`.
- **Masalah**: `Error response from daemon: network with name ... already exists`.
  - *Solusi*: Gunakan `docker network rm <net_name>` jika ingin membuat ulang, atau langsung sambungkan container ke network yang sudah ada.

---

## 18. Exercise
1. Buat dua jaringan Docker: `dmz-net` dan `data-net`.
2. Jalankan container Web di `dmz-net` dan container DB di `data-net`.
3. Jalankan container API dan hubungkan ke KEDUA jaringan tersebut. Buktikan via ping bahwa API bisa menghubungi Web dan DB, namun Web tidak bisa menghubungi DB!

---

## 19. Challenge
Rancang arsitektur High-Security Multi-Tier dengan Automated Discovery:
- Buat 3 jaringan: `public-edge`, `internal-api`, dan `secure-db`.
- Terapkan alur Nginx Reverse Proxy -> Node.js API -> Redis Cache & Postgres DB.
- Buktikan bahwa Nginx hanya bisa berkomunikasi dengan API, dan Redis/Postgres hanya bisa diakses oleh API.
- Tampilkan konfigurasi routing DNS internal dan verifikasi integritas pemisahan paket jaringan.

---

## 20. Summary
- **User-Defined Bridge** menyediakan server **Embedded DNS (`127.0.0.11`)** untuk penemuan layanan otomatis berdasarkan nama container.
- Menghindari hardcoded IP adalah prinsip utama membangun container yang tahan banting terhadap restart dan re-deployment.
- **Network Segmentation** membatasi radius ledakan (*blast radius*) jika terjadi peretasan pada tier aplikasi publik.
