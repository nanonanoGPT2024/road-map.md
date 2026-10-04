# Module 01: BuildKit Engine, Secret Mounts, Cache Mounts, & SSH Forwarding

## 1. Learning Objective
Setelah menyelesaikan modul ini, pembelajar diharapkan mampu:
- Memahami arsitektur internal **BuildKit**, mesin builder generasi baru di Docker Engine yang berbasis Directed Acyclic Graph (DAG).
- Memanfaatkan **Parallel Stage Execution** untuk mengompilasi beberapa stage independen secara simultan.
- Menggunakan **Secret Mounts (`--mount=type=secret`)** untuk mengakses API keys atau token privat tanpa meninggalkan jejak di layer image.
- Mempercepat instalasi dependensi hingga 10x menggunakan **Cache Mounts (`--mount=type=cache`)** untuk package manager (npm, pip, go build).
- Mengonfigurasi **SSH Agent Forwarding (`--mount=type=ssh`)** untuk melakukan clone private Git repository saat build tanpa menyalin private key ke container.

---

## 2. Prerequisite
- Memahami konsep anatomi Dockerfile layers dan multi-stage build (BAB 03).
- Memahami konsep dasar kriptografi SSH keys dan autentikasi token API.
- Mengetahui struktur dependensi graph (*Directed Acyclic Graph / DAG*).

---

## 3. Concept
Builder bawaan Docker versi terdahulu (Legacy Builder) mengeksekusi instruksi Dockerfile secara linier dari atas ke bawah secara sekuensial. Jika Anda memiliki 3 stage independen di Dockerfile, builder lama akan menjalankannya satu per satu secara lambat, tidak bisa menyimpan cache package manager antar-build, dan rawan membocorkan password jika menggunakan `ARG` untuk token rahasia.

**BuildKit** adalah mesin builder generasi baru resmi Docker (diadopsi penuh secara default sejak Docker Engine 23+). BuildKit menganalisis Dockerfile menjadi grafik dependensi (**DAG**), mengeksekusi stage-stage yang tidak saling bergantung secara **paralel murni**, mengabaikan stage yang tidak terpakai (*dead code elimination*), serta menyediakan mount sementara tingkat lanjut (*Advanced Mounts*) yang tidak pernah tersimpan di sistem berkas image akhir.

```
       BUILDKIT GRAPH-BASED (DAG) PARALLEL EXECUTION
 ┌─────────────────────────────────────────────────────────────┐
 │ DOCKERFILE ANALYSIS (PARALLEL STAGES)                       │
 │                                                             │
 │  ┌───────────────────────────────┐                          │
 │  │ STAGE A: Frontend Assets      │──┐                       │
 │  │ (npm run build)               │  │                       │
 │  └───────────────────────────────┘  │ Executed in PARALLEL! │
 │                                     ├──────────────────────>│ [ FINAL IMAGE ]
 │  ┌───────────────────────────────┐  │                       │ (Combines both)
 │  │ STAGE B: Backend Binary       │──┘                       │
 │  │ (go build)                    │                          │
 │  └───────────────────────────────┘                          │
 └─────────────────────────────────────────────────────────────┘
  BuildKit compiles Frontend & Backend SIMULTANEOUSLY on multi-core CPUs!
```

---

## 4. Why?
1. **Zero Secret Leakage**: Sebelumnya, developer sering menggunakan `ARG GITHUB_TOKEN=xyz` untuk mengunduh package privat. Nilai `ARG` tersebut tersimpan permanen di metadata layer dan dapat dibaca oleh siapapun via `docker history`. Dengan BuildKit Secret Mount, rahasia hanya dipasang di RAM sementara selama instruksi `RUN` berlangsung dan **100% lenyap dari image final**.
2. **Eliminasi Unduhan Dependensi Berulang di CI/CD**: Di runner CI seperti GitHub Actions yang ephemeral, setiap build baru biasanya mengunduh ulang ratusan megabyte modul Go atau wheel Python. Cache Mounts mempertahankan direktori cache compiler melintasi berbagai proses build.
3. **Pemberian Akses SSH yang Aman**: Anda tidak perlu lagi melakukan `COPY ~/.ssh/id_rsa /root/.ssh/` (yang merupakan bencana keamanan). BuildKit dapat meminjam sesi SSH host yang aktif melalui socket forwarding.

---

## 5. What?
### 4 Tipe Mount Canggih di BuildKit:

| Tipe Mount | Sintaks Instruksi | Manfaat Utama |
|---|---|---|
| **Secret Mount** | `RUN --mount=type=secret,id=mytoken ...` | Membaca token rahasia dari host tanpa tersimpan di layer image |
| **Cache Mount** | `RUN --mount=type=cache,target=/root/.cache ...` | Mempertahankan folder cache package manager antar-build |
| **SSH Mount** | `RUN --mount=type=ssh ...` | Menggunakan SSH agent host untuk git clone private repo |
| **Bind Mount (Build-time)**| `RUN --mount=type=bind,source=.,target=/src ...`| Membaca file host langsung saat kompilasi tanpa perintah `COPY` |

---

## 6. How?
### 1. Menggunakan Secret Mounts:
Menyediakan token rahasia secara aman saat build:

File `Dockerfile`:
```dockerfile
# syntax=docker/dockerfile:1
FROM alpine

RUN apk add --no-cache curl

# Rahasia dipasang di /run/secrets/api_key hanya selama baris ini berjalan!
RUN --mount=type=secret,id=api_key \
    curl -H "Authorization: Bearer $(cat /run/secrets/api_key)" https://internal.company.net/enterprise-asset.tar.gz -o /asset.tar.gz
```

Perintah Build di Terminal Host:
```bash
docker build --secret id=api_key,src=./local_secret.txt -t secure-app:v1 .
```

### 2. Menggunakan Cache Mounts (Percepatan Kompilasi Go):
File `Dockerfile`:
```dockerfile
# syntax=docker/dockerfile:1
FROM golang:1.22-alpine AS builder

WORKDIR /src
COPY go.mod go.sum ./

# Cache direktori modul download Go
RUN --mount=type=cache,target=/go/pkg/mod \
    go mod download

COPY . .

# Cache direktori kompilasi build cache Go
RUN --mount=type=cache,target=/go/pkg/mod \
    --mount=type=cache,target=/root/.cache/go-build \
    CGO_ENABLED=0 go build -o /bin/app .
```

### 3. Menggunakan SSH Forwarding:
Melakukan clone private repositori tanpa menyalin kunci SSH privat:
```bash
# Pastikan ssh-agent aktif di host
eval $(ssh-agent) && ssh-add ~/.ssh/id_ed25519

# Build dengan meneruskan socket SSH
docker build --ssh default -t private-repo-app .
```

File `Dockerfile`:
```dockerfile
# syntax=docker/dockerfile:1
FROM alpine

RUN apk add --no-cache git openssh-client

# Tambahkan GitHub ke known_hosts
RUN mkdir -p -m 0700 ~/.ssh && ssh-keyscan github.com >> ~/.ssh/known_hosts

# Clone private repo menggunakan SSH agent host
RUN --mount=type=ssh git clone git@github.com:mycompany/proprietary-core.git /app
```

---

## 7. Analogy
Bayangkan **Fitur Canggih BuildKit**:
- **Secret Mount** seperti **Memasukkan Kode PIN ATM di Depan Mesin Kasir**: Anda memasukkan kartu dan mengetik PIN 6-digit di tombol mesin EDC (**Secret Mounted in RAM**). Mesin kasir memproses transaksi bank, mencetak struk, dan PIN Anda langsung dihapus dari memori layar mesin (**Zero Secret Leakage di Struk Belanjaan / Layer Image**).
- **Cache Mount** seperti **Kotak Perkakas Mekanik di Bengkel**: Mekanik tidak membuang obeng dan kunci pas ke tempat sampah setiap kali selesai memperbaiki satu mobil. Kotak perkakas tetap berada di sudut meja bengkel dan langsung dipakai kembali saat mobil berikutnya masuk.
- **SSH Forwarding** seperti **Satpam Kantor yang Mengawal Tamu VIP**: Tamu tidak perlu menyerahkan dompet atau KTP aslinya ke resepsionis; satpam yang mengenali wajah tamu cukup menggesekkan kartu staf satpam di pintu lift agar tamu bisa naik ke lantai atas.

---

## 8. Diagram
```
+-----------------------------------------------------------------------------------+
|               BUILDKIT SECRET MOUNT (ZERO-LEAK GUARANTEE)                         |
+-----------------------------------------------------------------------------------+

 Host Machine:
   $ docker build --secret id=vault_token,src=./vault_token.txt .
             │
             ▼
 ┌─────────────────────────────────────────────────────────────────────────────┐
 │ BuildKit Engine Sandbox                                                     │
 │                                                                             │
 │  Step: RUN --mount=type=secret,id=vault_token curl ...                      │
 │                                                                             │
 │  1. In-Memory Virtual Filesystem Mount created at /run/secrets/vault_token  │
 │  2. Curl command executes and downloads proprietary binary asset            │
 │  3. Step completes!                                                         │
 │  4. In-Memory Mount is UNMOUNTED & DISCARDED immediately!                   │
 └──────────────────────────────────────┬──────────────────────────────────────┘
                                        │
                                        ▼
 ┌─────────────────────────────────────────────────────────────────────────────┐
 │ Final OCI Image Layer Produced:                                             │
 │  - /asset.tar.gz (Present)                                                  │
 │  - /run/secrets/vault_token (COMPLETELY EMPTY / NON-EXISTENT)               │
 └─────────────────────────────────────────────────────────────────────────────┘
  Audit with `docker history` or `dive`: 0% Secret Leakage!
```

---

## 9. Simple Example: Perintah Mengaktifkan BuildKit
Secara default BuildKit sudah aktif di Docker modern. Namun di server CI legacy, Anda dapat mengaktifkannya via environment variable:

```bash
# Mengaktifkan BuildKit untuk sesi CLI saat ini
export DOCKER_BUILDKIT=1

# Atau jadikan permanen di /etc/docker/daemon.json host:
# { "features": { "buildkit": true } }

# Menjalankan build dengan visualisasi terminal modern BuildKit
docker build -t my-app .
```

---

## 10. Practical Example: Multi-Stage Parallel Frontend & Backend Build
Contoh `Dockerfile` di mana Frontend dan Backend dikompilasi secara paralel murni:

```dockerfile
# syntax=docker/dockerfile:1

# ==========================================
# STAGE 1: Frontend Build (Node.js)
# ==========================================
FROM node:20-alpine AS frontend-builder
WORKDIR /web
COPY web/package*.json ./
RUN --mount=type=cache,target=/root/.npm npm ci
COPY web/ .
RUN npm run build # Menghasilkan /web/dist

# ==========================================
# STAGE 2: Backend Build (Go) - JALAN BERSAMAAN!
# ==========================================
FROM golang:1.22-alpine AS backend-builder
WORKDIR /api
COPY api/go.mod api/go.sum ./
RUN --mount=type=cache,target=/go/pkg/mod go mod download
COPY api/ .
RUN --mount=type=cache,target=/go/pkg/mod \
    --mount=type=cache,target=/root/.cache/go-build \
    CGO_ENABLED=0 go build -o /bin/api-server .

# ==========================================
# STAGE 3: Final Production Image
# ==========================================
FROM alpine:3.19
WORKDIR /app

# Salin hasil kompilasi dari kedua stage independen
COPY --from=backend-builder /bin/api-server /app/api-server
COPY --from=frontend-builder /web/dist /app/public

EXPOSE 8080
CMD ["/app/api-server"]
```

---

## 11. Real World Example: Pangkas Waktu Build Monorepo (8 Menit -> 45 Detik)
Sebuah perusahaan logistik memiliki monorepo berisi frontend React dan 3 microservices backend Go:
- **Kondisi Awal**: Menggunakan legacy Docker builder. Seluruh tahapan berjalan linier (Frontend selesai -> Backend 1 -> Backend 2 -> Backend 3). Total durasi build 8 menit 20 detik di CI runner.
- **Implementasi BuildKit**:
  1. Mengaktifkan BuildKit engine dan mengonfigurasi directive `# syntax=docker/dockerfile:1`.
  2. Mengonfigurasi 4 stage independen dalam satu Dockerfile.
  3. Menambahkan cache mounts untuk NPM dan Go compilation.
- **Hasil**: BuildKit mendeteksi 4 stage independen dan menjalankannya secara paralel pada runner dengan 8 vCPU. Cache mount membuat kompilasi ulang hanya memproses file yang berubah. Durasi build terpangkas menjadi **45 detik** (Percepatan 11x lipat).

---

## 12. Trade-offs

| Aspek | Legacy Docker Builder | BuildKit Engine |
|---|---|---|
| **Pola Eksekusi** | Sekuensial Linier (Satu per satu) | Konkurensi Paralel berbasis DAG |
| **Penanganan Kredensial** | Bocor di `ARG` / history layer | Bersih via Secret Mount di RAM |
| **Caching Dependensi** | Hanya layer-level cache | Persistent Mount Cache per toolchain |
| **Output Log Terminal** | Teks biasa membosankan | TUI dinamis real-time (Interactive progress) |

---

## 13. When To Use
- Wajib digunakan untuk seluruh proses build modern di laptop lokal maupun pipeline CI/CD.
- Gunakan Secret Mount saat perlu mendownload artefak privat (JFrog Artifactory, private NPM, private Go proxy).
- Gunakan SSH Mount saat Dockerfile perlu meng-clone repositori Git privat internal perusahaan.

---

## 14. When NOT To Use
- Jangan gunakan cache mount untuk data yang harus bersifat deterministik dan wajib diisolasi total di setiap run (misal pengujian integritas rilis final di mana Anda ingin memastikan kompilasi berjalan bersih dari nol tanpa sisa cache lama).

---

## 15. Common Mistakes
1. **Lupa Menambahkan `# syntax=docker/dockerfile:1` di Baris Pertama**: Fitur-fitur canggih BuildKit (seperti `--mount=type=secret` atau `--mount=type=cache`) membutuhkan Dockerfile frontend parser versi 1. Lupa menyertakan directive ini dapat menyebabkan error sintaks pada versi Docker lama.
2. **Menggunakan `ARG` untuk Password / Private Key**: Mengirimkan token GitHub menggunakan `--build-arg GITHUB_TOKEN=ghp_xxxx`. Token tersebut tersimpan permanen di riwayat metadata image dan dapat diekstraksi dengan `docker history --no-trunc <image>`. Selalu gunakan `--mount=type=secret`!
3. **Menghapus Direktori Cache di dalam Perintah RUN**: Menulis `RUN --mount=type=cache,target=/root/.cache rm -rf /root/.cache`. Perintah ini merusak tujuan penggunaan cache mount karena Anda menghapus folder yang ingin dipertahankan!

---

## 16. Best Practices
### Must Have
- Pastikan `# syntax=docker/dockerfile:1` selalu berada di baris paling atas Dockerfile.
- Gunakan Secret Mounts untuk seluruh kredensial build-time.
- Pasang Cache Mounts pada direktori standar package manager: `/root/.cache/pip`, `/root/.npm`, `/go/pkg/mod`.

### Recommended
- Pisahkan build frontend dan backend ke dalam stage terpisah agar BuildKit dapat mengeksekusinya secara paralel.
- Gunakan SSH agent forwarding alih-alih membuat token deployment sementara jika membangun image di mesin lokal developer.

### Advanced
- Gabungkan BuildKit dengan remote cache exporter (`--cache-to=type=registry`, `--cache-from=type=registry`) di pipeline CI GitHub Actions agar cache build dapat dibagikan ke seluruh anggota tim secara terpusat.

---

## 17. Troubleshooting
- **Masalah**: `Error: could not parse expression: "--mount=type=secret,id=token"` saat `docker build`.
  - *Penyebab*: BuildKit belum aktif pada daemon Docker Anda, atau versi Docker Engine terlalu usang (<18.09).
  - *Solusi*: Jalankan dengan `DOCKER_BUILDKIT=1 docker build ...` dan pastikan baris `# syntax=docker/dockerfile:1` ada di baris pertama file.
- **Masalah**: `ssh: connect to host github.com port 22: Connection refused` saat build dengan `--mount=type=ssh`.
  - *Penyebab*: SSH agent di host belum memuat kunci privat yang sah.
  - *Solusi*: Jalankan `ssh-add -l` di host untuk memverifikasi kunci telah dimuat, dan pastikan file `known_hosts` sudah dikonfigurasi di container.

---

## 18. Exercise
1. Tulis Dockerfile yang menggunakan Secret Mount untuk membaca file token rahasia dan mencetak panjang karakternya ke terminal tanpa menyalin file tersebut ke filesystem container!
2. Buat Dockerfile Go atau Python yang mengimplementasikan Cache Mount untuk direktori modul dan bandingkan waktu eksekusi build pertama vs build kedua saat 1 baris kode diubah!

---

## 19. Challenge
Rancang pipeline BuildKit Paralel Monorepo:
- Stage 1: Build static frontend (React) dengan NPM cache mount.
- Stage 2: Build binary backend (Go) dengan Go compiler cache mount.
- Stage 3: Image rilis produksi minimalis yang hanya menyalin biner backend dan folder aset frontend.
- Buktikan bahwa kedua stage pertama berjalan secara paralel dan buktikan dengan `docker history` bahwa tidak ada sisa kredensial atau toolchain compiler di image akhir.

---

## 20. Summary
- **BuildKit** menghadirkan komputasi builder modern berbasis Directed Acyclic Graph (DAG) dengan eksekusi paralel.
- **Secret Mounts** menjamin nol kebocoran kredensial (*zero secret leak*) pada layer image hasil build.
- **Cache Mounts** mempercepat durasi kompilasi berulang dengan mempertahankan cache compiler di luar image layer.
- **SSH Forwarding** meminjam sesi autentikasi host secara aman untuk akses repositori privat tanpa kunci statis.
