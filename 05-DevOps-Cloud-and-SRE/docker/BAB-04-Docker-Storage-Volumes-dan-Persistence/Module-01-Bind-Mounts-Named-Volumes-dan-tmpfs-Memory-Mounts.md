# Module 01: Bind Mounts, Named Volumes, & tmpfs Memory Mounts

## 1. Learning Objective
Setelah menyelesaikan modul ini, pembelajar diharapkan mampu:
- Menguasai 3 tipe penyimpanan data utama di Docker: **Named Volumes**, **Bind Mounts**, dan **tmpfs Mounts**.
- Memahami letak penyimpanan fisik dan siklus hidup (*lifecycle*) masing-masing tipe storage.
- Menjelaskan mengapa database produksi (PostgreSQL, MySQL, Redis) wajib menggunakan Named Volume dan dilarang keras menulis ke layer Copy-on-Write (CoW).
- Mengonfigurasi mount point menggunakan sintaks modern deklaratif `--mount` vs sintaks legacy `-v` / `--volume`.
- Menangani permasalahan perizinan berkas (*file permissions*) antara User ID host dan container pada Bind Mount.
- Mengamankan data sensitif dan file sementara menggunakan penyimpanan memori in-memory **`tmpfs`**.

---

## 2. Prerequisite
- Memahami konsep arsitektur storage driver OverlayFS dan Copy-on-Write (BAB 01 Module 02).
- Mengetahui cara kerja permission Linux (UID, GID, `chown`, `chmod`).
- Pengetahuan dasar tentang sistem berkas virtual Linux (`/tmp`, RAM disk).

---

## 3. Concept
Secara default, seluruh file yang dibuat di dalam container disimpan di layer read-write container (**UpperDir** di OverlayFS). Penyimpanan bawaan ini memiliki dua kelemahan fatal:
1. **Efimeral (Sementara)**: Saat container dihapus (`docker rm`), layer tersebut lenyap seketika bersama seluruh data di dalamnya.
2. **Degradasi Performa I/O**: Setiap operasi penulisan harus melalui abstraksi storage driver Copy-on-Write yang lambat untuk database transaksi tinggi.

Docker menyediakan 3 mekanisme penyimpanan eksternal yang **melewati (*bypass*) storage driver OverlayFS** dan langsung membaca/menulis ke kernel filesystem host dengan performa native:

```
       DOCKER STORAGE ARCHITECTURE COMPARISON
 ┌─────────────────────────────────────────────────────────────┐
 │ HOST MACHINE FILESYSTEM                                     │
 │                                                             │
 │  ┌────────────────────────┐      ┌───────────────────────┐  │
 │  │ NAMED VOLUMES          │      │ BIND MOUNTS           │  │
 │  │ /var/lib/docker/volumes│      │ /home/user/my-project │  │
 │  │ (Managed by Docker)    │      │ (Managed by User)     │  │
 │  └───────────┬────────────┘      └───────────┬───────────┘  │
 │              │                               │              │
 │              ▼                               ▼              │
 │   ┌──────────────────────────────────────────────────────┐  │
 │   │ CONTAINER FILESYSTEM (Bypasses OverlayFS CoW Layer)  │  │
 │   │  - /var/lib/postgresql/data <── (Named Volume)       │  │
 │   │  - /app/src                 <── (Bind Mount)         │  │
 │   │  - /app/cache               <── (tmpfs in Host RAM)  │  │
 │   └──────────────────────────────────────────▲───────────┘  │
 │                                              │              │
 │  ┌───────────────────────────────────────────┴───────────┐  │
 │  │ TMPFS MOUNTS (Stored only in Host System RAM Memory)  │  │
 │  └───────────────────────────────────────────────────────┘  │
 └─────────────────────────────────────────────────────────────┘
```

---

## 4. Why?
1. **Persistensi Data Mutlak**: Data database, log audit, dan file upload nasabah harus tetap selamat meskipun container di-restart, di-upgrade ke versi baru, atau bahkan dihancurkan. Named Volumes memiliki siklus hidup independen dari container.
2. **Efisiensi Siklus Pengembangan (*Live Reload*)**: Dengan Bind Mounts, developer dapat memetakan folder source code di laptop langsung ke dalam container. Saat file `.js` atau `.py` disimpan di IDE (VS Code), aplikasi di dalam container langsung ter-reload secara instan tanpa perlu melakukan `docker build` ulang.
3. **Keamanan Tanpa Jejak (*Zero Footprint Secrets*)**: Menyimpan session tokens, kunci privat sementara, atau temporary cache di `tmpfs` menjamin data tersebut hanya hidup di RAM host dan tidak pernah tersimpan di disk storage fisik yang bisa diekstraksi penyerang.

---

## 5. What?
### Komparasi Mendalam 3 Tipe Penyimpanan:

| Karakteristik | Named Volumes | Bind Mounts | tmpfs Mounts |
|---|---|---|---|
| **Lokasi Fisik di Host** | `/var/lib/docker/volumes/<nama>/_data` | Direktori bebas mana saja di host (`/home/user/...`) | Memori RAM host (Virtual Memory) |
| **Dikelola Oleh** | Docker Engine sepenuhnya | Pengguna / Sistem Host | Kernel Linux Memory Manager |
| **Kinerja I/O** | Native Host Performance (Sangat Cepat) | Native Host Performance | Super Cepat (Kecepatan Bus RAM) |
| **Portabilitas Multi-Host** | Tinggi (Mendukung Volume Driver Cloud/NFS) | Rendah (Tergantung struktur path folder host) | Tidak Portabel (Lokal RAM) |
| **Kasus Penggunaan Utama** | Database (Postgres, MySQL), Media Uploads | Local Dev Hot-Reloading, Host config file injection | File cache sementara, Token otentikasi rahasia |

---

## 6. How?
### Sintaks CLI: Legacy `-v` vs Modern `--mount`:
Docker merekomendasikan sintaks `--mount` karena lebih eksplisit, tidak ambigu, dan melempar error jika path sumber tidak ditemukan (sedangkan `-v` secara otomatis membuat folder kosong baru di host jika path salah ketik).

#### 1. Named Volume (Produksi Database):
```bash
# Membuat volume bernama
docker volume create postgres_data

# Memasang volume ke container
docker run -d \
  --name db-prod \
  --mount type=volume,source=postgres_data,target=/var/lib/postgresql/data \
  -e POSTGRES_PASSWORD=secret \
  postgres:16-alpine
```

#### 2. Bind Mount (Development Live-Reload):
```bash
# Memetakan folder project lokal ke /app di container (Read-Write)
docker run -d \
  --name web-dev \
  -p 3000:3000 \
  --mount type=bind,source="$(pwd)",target=/app \
  node:20-alpine sh -c "cd /app && npm run dev"
```

#### 3. Read-Only Mount (`readonly`):
```bash
# Menginjeksi file konfigurasi host secara aman tanpa izin ubah
docker run -d \
  --mount type=bind,source=/etc/nginx/nginx.conf,target=/etc/nginx/nginx.conf,readonly \
  nginx:alpine
```

#### 4. tmpfs Mount (Memori RAM):
```bash
# Menugaskan 128MB RAM host sebagai temporary directory
docker run -d \
  --mount type=tmpfs,target=/app/cache,tmpfs-size=134217728,tmpfs-mode=1777 \
  my-app:prod
```

---

## 7. Analogy
Bayangkan **3 Tipe Docker Storage** seperti **Menyimpan Barang Berharga Anda**:
- **Named Volume** seperti **Brankas Deposit Box di Bank**: Brankas tersebut disediakan, dirawat, dan dijaga keamanannya oleh pihak bank (**Docker Engine**). Jika Anda pindah apartemen (**Container Destroyed**), brankas Anda di bank tetap utuh dan aman selamanya.
- **Bind Mount** seperti **Membawa Koper Pribadi dari Rumah**: Anda menaruh koper pribadi langsung di kamar hotel. Jika ada barang di koper yang diubah, koper di rumah Anda juga berubah karena barangnya sama persis.
- **tmpfs Mount** seperti **Papan Tulis Spidol Whiteboard**: Anda menulis catatan rahasia di papan tulis. Informasi bisa dibaca super cepat, namun begitu Anda menyeka papan tulis atau mematikan lampu ruangan (**Container stopped**), seluruh tulisan terhapus bersih tanpa meninggalkan jejak fisik di kertas.

---

## 8. Diagram
```
+-----------------------------------------------------------------------------------+
|               NAMED VOLUME PERSISTENCE ACROSS CONTAINER REBUILD                   |
+-----------------------------------------------------------------------------------+

 1. Initial State: Run Postgres Container v15
    [ Container: postgres:15 ] ──(Write SQL Data)──> [ Named Volume: pg_data ]
                                                     (/var/lib/docker/volumes/pg_data)
                                                              │
 2. Upgrade Action: Container Destroyed                       │
    [ docker rm -f postgres:15 ]                              │ Data REMAINS
    (UpperDir container erased)                               │ 100% PERSISTENT!
                                                              │
 3. New State: Run Postgres Container v16                     ▼
    [ Container: postgres:16 ] ──(Mounts existing)──> [ Named Volume: pg_data ]
    ↳ Instantly boots with all historical database tables intact!
```

---

## 9. Simple Example: Demonstrasi Persistensi Volume
Membuktikan data tetap ada setelah container dihancurkan:

```bash
# 1. Buat volume dan simpan file di dalamnya
docker run --rm \
  -v my-test-volume:/data \
  alpine sh -c "echo 'Docker Storage is awesome!' > /data/message.txt"

# 2. Container di atas sudah hancur (--rm). Sekarang jalankan container BARU:
docker run --rm \
  -v my-test-volume:/data \
  alpine cat /data/message.txt

# Output:
# Docker Storage is awesome!
```

---

## 10. Practical Example: Mengatasi Masalah File Permission pada Bind Mount
Saat menggunakan Bind Mount di Linux host, file yang dibuat oleh container seringkali dimiliki oleh `root` (UID 0), sehingga developer tidak bisa mengedit file tersebut di VS Code host.

Solusi: Teruskan UID dan GID user host saat menjalankan container:

```bash
# Menjalankan container dengan identitas user host aktif
docker run -d \
  --name dev-app \
  --user $(id -u):$(id -g) \
  --mount type=bind,source="$(pwd)",target=/app \
  node:20-alpine npm run dev
```

---

## 11. Real World Example: Migrasi Database E-Commerce (Zero Data Loss)
Sebuah platform e-commerce dengan volume database PostgreSQL sebesar 450 Gigabyte:
- **Masalah**: Versi PostgreSQL 14 harus di-upgrade ke PostgreSQL 16 tanpa boleh memindahkan file data raksasa lewat jaringan.
- **Solusi Menggunakan Named Volume**:
  1. Hentikan container lama secara anggun: `docker stop -t 60 postgres-v14`.
  2. Hapus container lama: `docker rm postgres-v14` (Volume `ecommerce_db_data` tetap utuh di disk host).
  3. Jalankan container baru PostgreSQL 16 dan pasang volume yang sama:
     `docker run -d --name postgres-v16 --mount source=ecommerce_db_data,target=/var/lib/postgresql/data postgres:16-alpine`.
- **Hasil**: Proses upgrade dan re-attachment database 450GB selesai dalam waktu **12 detik** tanpa menyalin 1 byte pun data, dan zero data loss.

---

## 12. Trade-offs

| Aspek | Named Volumes | Bind Mounts |
|---|---|---|
| **Kemudahan Manajemen** | Sangat Mudah (`docker volume ls`, `inspect`) | Manual (Harus ingat path absolut host) |
| **Isolasi Keamanan** | Terisolasi di dalam direktori internal Docker | Berisiko (Container nakal bisa timpa `/etc/shadow` host) |
| **Performa macOS & Windows** | Cepat (Berjalan di VM Linux Docker Desktop) | Sangat Lambat (Overhead sinkronisasi osxfs/VirtioFS) |
| **Akses Langsung dari Host IDE** | Tidak langsung (Tersimpan di direktori root) | Sangat Mudah (File langsung terlihat di VS Code) |

---

## 13. When To Use
- **Named Volumes**: Seluruh database produksi, message broker (Kafka/RabbitMQ log), dan media penyimpanan persisten.
- **Bind Mounts**: Lingkungan development frontend/backend untuk hot-reload source code, atau menginjeksi file konfigurasi statis (`nginx.conf`, `prometheus.yml`).
- **tmpfs Mounts**: Menyimpan session ID sementara, file cache komputasi, atau token secret JWT sementara yang sensitif.

---

## 14. When NOT To Use
- Jangan gunakan Bind Mount di server produksi Kubernetes/Swarm multi-node (karena direktori fisik host belum tentu ada di node worker lain).
- Jangan menyimpan file database yang membutuhkan ACID compliance di atas jaringan network mount (NFS) dengan latency tinggi tanpa fsync lock yang tepat.

---

## 15. Common Mistakes
1. **Salah Ketik Path pada Flag `-v`**: Mengetik `docker run -v /wrong/path:/app`. Docker secara otomatis membuat folder kosong di host tanpa ada peringatan error. Gunakan sintaks `--mount type=bind,...` yang akan langsung melempar pesan error jika folder tidak ditemukan.
2. **Menimpa File Container dengan Folder Kosong**: Mem-bind mount folder kosong dari host ke direktori container yang sudah berisi file bawaan (misal mem-mount folder kosong ke `/usr/share/nginx/html`). Akibatnya, seluruh file HTML bawaan Nginx tertimpa dan menjadi kosong (*shadowing effect*).
3. **Menghapus Container Tanpa Mengetahui Nasib Volume**: Menghapus container dengan `docker rm -v`. Flag `-v` akan ikut menghapus anonymous volume yang terikat pada container tersebut!

---

## 16. Best Practices
### Must Have
- Gunakan sintaks `--mount` alih-alih `-v` pada skrip produksi dan pipeline otomatisasi.
- Selalu pasang flag `readonly` pada Bind Mount konfigurasi untuk mencegah aplikasi container memodifikasi file konfigurasi host secara tidak sengaja.
- Berikan nama yang jelas pada Named Volume (misal `prod_postgres_data_v1` bukan anonymous volume acak).

### Recommended
- Buat user non-root di Dockerfile dengan UID 1000 agar serasi dengan UID default sebagian besar user Linux desktop untuk menghindari konflik file permission.

### Advanced
- Gunakan plugin Volume Driver pihak ketiga (seperti RexRay atau AWS EFS Driver) untuk memasang network block storage yang dapat dipindahkan antar-server fisik secara otomatis.

---

## 17. Troubleshooting
- **Masalah**: `permission denied` saat container mencoba menulis file ke Bind Mount host.
  - *Penyebab*: User di dalam container (misal UID 1000) tidak memiliki izin tulis ke folder host yang dimiliki oleh `root`.
  - *Solusi*: Ubah kepemilikan folder host dengan `sudo chown -R 1000:1000 ./my-data` atau gunakan flag `--user $(id -u):$(id -g)`.
- **Masalah**: Ruang harddisk server tiba-tiba penuh akibat volume yatim piatu (*orphaned volumes*).
  - *Solusi*: Temukan dan bersihkan volume tak terpakai dengan `docker volume ls -qf dangling=true` lalu `docker volume prune`.

---

## 18. Exercise
1. Buat Named Volume bernama `shared_data`. Jalankan dua container Alpine secara bersamaan yang keduanya me-mount volume tersebut, dan buktikan bahwa file yang ditulis oleh Container A dapat langsung dibaca oleh Container B!
2. Jalankan container dengan `tmpfs` mount berukuran 64MB di `/mnt/ramdisk`. Tulis file ke dalamnya, hentikan container, dan buktikan bahwa data tersebut hilang seketika saat container baru dinyalakan.

---

## 19. Challenge
Rancang pipeline data storage terisolasi:
- Buat volume persisten untuk aplikasi database.
- Tulis konfigurasi mount dengan hak akses `readonly` untuk file konfigurasi `database.conf`.
- Siapkan `tmpfs` mount berukuran 32MB untuk folder `/tmp` aplikasi.
- Buktikan bahwa data transaksi tersimpan aman di volume, konfigurasi tidak bisa diubah dari dalam container, dan memori RAM terisolasi dari disk host.

---

## 20. Summary
- **Named Volumes** adalah standar de facto penyimpanan persisten database di Docker yang dikelola mandiri oleh daemon.
- **Bind Mounts** menghubungkan folder host ke container, ideal untuk local development dan hot-reloading.
- **tmpfs Mounts** menyediakan media penyimpanan super cepat di RAM host untuk file efimeral dan data rahasia.
- Sintaks modern `--mount` menawarkan deklarasi yang lebih aman, eksplisit, dan minim kesalahan dibanding flag legacy `-v`.
