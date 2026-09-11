# Module 01: Rootless Mode, Non-Root Users, Capabilities, & Read-Only Filesystem

## 1. Learning Objective
Setelah menyelesaikan modul ini, pembelajar diharapkan mampu:
- Memahami dan mengonfigurasi **Rootless Docker Mode**, di mana daemon Docker dan container berjalan sepenuhnya di bawah akun pengguna non-root tanpa hak akses `sudo`.
- Menerapkan eksekusi **Non-Root User** di dalam container (`USER 10001`) untuk mencegah serangan *container breakout*.
- Menguasai pemangkasan hak istimewa kernel menggunakan **Linux Capabilities** (`--cap-drop=ALL` dan `--cap-add`).
- Mengamankan integritas sistem berkas container menggunakan flag **`--read-only`** yang dipadukan dengan penyimpanan memori in-memory `tmpfs`.
- Mencegah eskalasi hak istimewa menggunakan opsi keamanan **`no-new-privileges:true`**.

---

## 2. Prerequisite
- Memahami konsep arsitektur User Namespaces dan Cgroups v2 (BAB 01 Module 02).
- Mengetahui konsep User ID (UID 0 = root, UID >= 1000 = normal user) dan grup di Linux.
- Pemahaman dasar tentang izin file sistem POSIX (Read, Write, Execute).

---

## 3. Concept
Secara default, Docker Daemon (`dockerd`) berjalan dengan hak akses **`root` sistem**. Jika seorang pengguna memiliki akses ke soket Docker (`/var/run/docker.sock`), pengguna tersebut secara teknis memiliki **kekuasaan setara root penuh pada host**, karena mereka dapat menjalankan perintah seperti:
`docker run -v /:/host-root ubuntu rm -rf /host-root`

Pengerasan keamanan Docker (*Docker Hardening*) bertumpu pada 3 lapisan pertahanan (*Defense-in-Depth*):
1. **Rootless Docker**: Menjalankan daemon `dockerd` dan container di dalam User Namespace milik pengguna non-root biasa. Jika container berhasil dibobol hacker, hacker tersebut hanya mendapatkan akun biasa tanpa hak root di host.
2. **Principle of Least Privilege (Capabilities)**: Membuang seluruh hak istimewa kernel yang tidak dibutuhkan aplikasi (seperti mengubah jam sistem `CAP_SYS_TIME` atau memodifikasi routing jaringan `CAP_NET_ADMIN`).
3. **Immutability (Read-Only RootFS)**: Mengunci seluruh sistem berkas container menjadi *read-only* sehingga penyerang tidak bisa mengunduh malware atau menyuntikkan script berbahaya ke dalam container.

```
       DOCKER CONTAINER DEFENSE-IN-DEPTH ARCHITECTURE
 ┌─────────────────────────────────────────────────────────────┐
 │ HARDENED CONTAINER RUNTIME ENVIRONMENT                      │
 │                                                             │
 │  ┌───────────────────────────────────────────────────────┐  │
 │  │ USER IDENTITY: UID 10001 (Non-Root User)              │  │
 │  │  - Denies raw access to system files                  │  │
 │  └───────────────────────────┬───────────────────────────┘  │
 │                              │                              │
 │  ┌───────────────────────────┴───────────────────────────┐  │
 │  │ LINUX CAPABILITIES: --cap-drop=ALL                    │  │
 │  │  - Only add: CAP_NET_BIND_SERVICE (if needed)         │  │
 │  └───────────────────────────┬───────────────────────────┘  │
 │                              │                              │
 │  ┌───────────────────────────┴───────────────────────────┐  │
 │  │ SECURITY OPTION: no-new-privileges:true               │  │
 │  │  - Prevents SUID binary escalation (sudo / setuid)    │  │
 │  └───────────────────────────┬───────────────────────────┘  │
 │                              │                              │
 │  ┌───────────────────────────┴───────────────────────────┐  │
 │  │ IMMUTABLE FILESYSTEM: --read-only                     │  │
 │  │  - Entire root (/) is locked (No malware writes!)     │  │
 │  │  - Writable only at ephemeral /tmp (tmpfs in RAM)     │  │
 │  └───────────────────────────────────────────────────────┘  │
 └─────────────────────────────────────────────────────────────┘
```

---

## 4. Why?
1. **Mitigasi Total Serangan Container Escape**: Celah keamanan kernel (seperti *Dirty COW*, *runC vulnerability CVE-2019-5736*) memungkinkan penyerang di dalam container menembus batas isolasi dan mengambil alih kernel host jika proses container berjalan sebagai root (UID 0). Dengan non-root dan rootless mode, dampak serangan terkunci rapat di dalam akun terbatas.
2. **Pencegahan Penyuntikan Malware Persisten**: Penyerang web yang berhasil melakukan eksploitasi RCE (misal mengunggah web shell `.php` atau `.sh`) akan langsung gagal dengan error `Read-only file system` jika container dijalankan dengan flag `--read-only`.
3. **Kepatuhan Regulasi Industri (Compliance)**: Standar audit perbankan (PCI-DSS), kesehatan (HIPAA), dan benchmark keamanan resmi **CIS Docker Benchmark** secara tegas melarang container berjalan sebagai user root di lingkungan produksi.

---

## 5. What?
### Komponen Pengerasan Keamanan Container:
- **Rootless Docker Daemon**: Instalasi Docker yang berjalan di bawah `systemd --user` tanpa memerlukan hak `sudo`.
- **`USER <uid>:<gid>`**: Instruksi Dockerfile atau flag CLI (`--user 10001:10001`) yang menurunkan hak eksekusi dari root ke user biasa.
- **Linux Capabilities (`cap-drop` / `cap-add`)**: Kernel Linux memecah hak akses root menjadi puluhan kemampuan independen (*capabilities*). Docker secara default mengaktifkan 14 capabilities (seperti `CAP_CHOWN`, `CAP_FOWNER`, `CAP_NET_RAW`). Pada sistem hardened, kita membuang semuanya: `--cap-drop=ALL`.
- **`--security-opt=no-new-privileges:true`**: Mematikan kemampuan binary berbendera SUID (seperti perintah `sudo` atau `passwd`) untuk menaikkan privilege proses anak.
- **`--read-only`**: Memasang root filesystem container sebagai read-only, dan menggunakan mount in-memory `--tmpfs /tmp` untuk file sementara.

---

## 6. How?
### Perintah Eksekusi Container dengan Tingkat Keamanan Maksimal:
Perintah standar industri untuk menjalankan web API dengan proteksi pertahanan berlapis:

```bash
docker run -d \
  --name secure-web-api \
  --user 10001:10001 \
  --security-opt=no-new-privileges:true \
  --cap-drop=ALL \
  --cap-add=NET_BIND_SERVICE \
  --read-only \
  --tmpfs /tmp:rw,noexec,nosuid,size=64m \
  --tmpfs /run:rw,noexec,nosuid,size=16m \
  -p 8080:8080 \
  my-hardened-app:v1.0.0
```

Penjelasan Parameter Pengerasan:
1. `--user 10001:10001`: Proses berjalan sebagai akun biasa tanpa izin root.
2. `--security-opt=no-new-privileges:true`: Mencegah eskalasi via binary SUID.
3. `--cap-drop=ALL`: Mencabut seluruh 14 capabilities Linux bawaan.
4. `--cap-add=NET_BIND_SERVICE`: Mengizinkan HANYA hak untuk membuka socket port jaringan di bawah 1024 jika diperlukan.
5. `--read-only`: Mengunci seluruh sistem berkas `/` container.
6. `--tmpfs /tmp:rw,noexec,nosuid`: Menyediakan folder `/tmp` di RAM untuk file temporer aplikasi, dengan proteksi `noexec` (file di dalam `/tmp` tidak bisa dieksekusi sebagai script biner).

---

## 7. Analogy
Bayangkan **Pengerasan Keamanan Container** seperti **Prosedur Keamanan Tamu di Laboratorium Virus Berbahaya**:
- **Default Docker** seperti tamu yang diberi jas dokter lengkap dan kartu akses master yang bisa membuka seluruh pintu laboratorium (**Root User dengan Default Capabilities**). Jika tamu tersebut berniat jahat, seluruh laboratorium bisa dirusak.
- **Non-Root User** seperti mencabut kartu master tamu dan hanya memberinya tiket pengunjung biasa.
- **`--cap-drop=ALL`** seperti meminta tamu meletakkan korek api, gunting, dan obeng di pos satpam depan (**Membuang capabilities yang berbahaya**).
- **`--read-only`** seperti melapisi seluruh tombol instrumen kaca dengan gembok akrilik transparan: tamu bisa melihat data di layar monitor, namun tidak bisa menekan tombol apa pun atau mencoret-coret dinding laboratorium.

---

## 8. Diagram
```
+-----------------------------------------------------------------------------------+
|               CONTAINER BREAKOUT DEFENSE (ATTACK TREE MITIGATION)                 |
+-----------------------------------------------------------------------------------+

 Attacker exploits RCE Vulnerability in Web App
         │
         ├──> Action 1: Attempt to download crypto-miner via `curl` to /tmp
         │      ├── Without Hardening ──> Downloaded & Executed! (Server Infected)
         │      └── With Hardening:
         │            ↳ Blocked by `--read-only` & `--tmpfs noexec`! (Access Denied)
         │
         ├──> Action 2: Attempt to escalate privilege via SUID binary (`sudo`)
         │      ├── Without Hardening ──> Becomes Root on Host!
         │      └── With Hardening:
         │            ↳ Blocked by `no-new-privileges:true`! (Permission Denied)
         │
         └──> Action 3: Attempt Kernel Escape via Dirty COW Syscall
                ├── Without Hardening ──> Attacker compromises Host OS!
                └── With Hardening:
                      ↳ Blocked by `Rootless Docker & User Namespaces`!
                      ↳ Attacker is trapped inside unprivileged user namespace.
```

---

## 9. Simple Example: Demonstrasi Efek `--read-only` dan `--user`
Membuktikan secara langsung di terminal:

```bash
# 1. Menjalankan container biasa (Bisa menulis file bebas)
docker run --rm alpine touch /test.txt
# Sukses tanpa error

# 2. Menjalankan container dengan --read-only
docker run --rm --read-only alpine touch /test.txt
# Output:
# touch: /test.txt: Read-only file system

# 3. Menjalankan container sebagai user non-root (UID 10001)
docker run --rm --user 10001:10001 alpine id
# Output:
# uid=10001 gid=10001
```

---

## 10. Practical Example: Hardened Dockerfile untuk Node.js
Menyiapkan user non-root secara aman di dalam Dockerfile:

```dockerfile
FROM node:20-alpine

# Buat grup dan user non-root terdedikasi
RUN addgroup -g 10001 appgroup && \
    adduser -u 10001 -G appgroup -s /bin/sh -D appuser

WORKDIR /home/appuser/app

# Salin dependensi dan source code
COPY --chown=appuser:appgroup package*.json ./
RUN npm ci --only=production

COPY --chown=appuser:appgroup . .

# Turunkan hak akses ke user non-root sebelum runtime
USER 10001:10001

EXPOSE 3000

# Pastikan aplikasi menulis file sementara hanya ke /tmp
ENV TMPDIR=/tmp

CMD ["node", "src/index.js"]
```

---

## 11. Real World Example: Menggagalkan Serangan RCE Log4Shell pada Container Hardened
Pada saat gelombang serangan exploitasi celah keamanan Log4Shell (CVE-2021-44228) melanda dunia:
- **Perusahaan Tanpa Hardening**: Penyerang menyuntikkan string payload JNDI ke server Java (berjalan sebagai root di container standar). Java mendownload file biner malware ke `/tmp/malware`, menjalankan perintah via shell, dan menanam backdoor permanen di host Linux.
- **Perusahaan dengan Hardened Containers**:
  Container Java dijalankan dengan `--read-only --tmpfs /tmp:noexec --user 10001 --cap-drop=ALL`.
  1. Payload penyerang berhasil masuk ke memori Java.
  2. Java mencoba menulis script shell penyerang ke `/tmp`: penulisan berhasil karena `/tmp` adalah tmpfs.
  3. Namun saat Java mencoba mengeksekusi script tersebut (`/tmp/exploit.sh`), kernel Linux **langsung memblokir eksekusi** dengan error `Permission Denied` berkat flag `noexec`!
  4. Serangan gagal total tanpa ada data yang bocor.

---

## 12. Trade-offs

| Aspek | Container Default (Root) | Hardened Container (Non-Root + ReadOnly) |
|---|---|---|
| **Postur Keamanan** | Rentan (Attack surface besar) | Sangat Kuat (Memenuhi standar CIS Benchmark) |
| **Kemudahan Konfigurasi** | Bebas (Semua file bisa ditulis) | Perlu perencanaan mount `/tmp` dan ownership file |
| **Port Binding Rendah (<1024)**| Langsung jalan di port 80/443 | Butuh `--cap-add=NET_BIND_SERVICE` atau port >1024 |
| **Kemudahan Debugging** | Mudah pasang tool baru | Dibatasi (Tidak bisa `apt-get install` di dalam container) |

---

## 13. When To Use
- Wajib untuk seluruh container yang terhubung ke internet publik (*public-facing containers*).
- Wajib untuk seluruh sistem yang menyimpan data sensitif nasabah, kartu kredit, atau data medis.
- Setiap sistem produksi yang ingin mematuhi standar CIS Docker Benchmark.

---

## 14. When NOT To Use
- Jangan gunakan `--read-only` tanpa menyiapkan mount `tmpfs` untuk aplikasi yang secara internal membutuhkan direktori kerja sementara untuk kompresi file atau caching session lokal.

---

## 15. Common Mistakes
1. **Mengira `USER nonroot` di Dockerfile Cukup**: Meskipun Dockerfile sudah disetel non-root, jika container dijalankan tanpa `--security-opt=no-new-privileges:true`, penyerang masih bisa mengeksploitasi binary berizin SUID di dalam container untuk kembali menjadi root.
2. **Lupa Flag `chown` saat `COPY` di Dockerfile**: Menulis `COPY . .` setelah instruksi `USER appuser`. File yang disalin tetap dimiliki oleh `root`! Akibatnya, `appuser` tidak bisa membaca atau memodifikasi file tersebut. Selalu gunakan `COPY --chown=appuser:appgroup . .`.
3. **Membuka Port di Bawah 1024 Sebagai Non-Root Tanpa Capability**: Menjalankan aplikasi sebagai non-root dan mencoba mendengarkan port 80. Linux melarang user non-root mengikat port di bawah 1024, menghasilkan error `bind: permission denied`. Gunakan port tinggi (seperti 8080 atau 3000) atau tambahkan capability `CAP_NET_BIND_SERVICE`.

---

## 16. Best Practices
### Must Have
- Jalankan container dengan user non-root eksplisit: `USER 10001:10001`.
- Selalu pasang `--security-opt=no-new-privileges:true`.
- Pasang `--cap-drop=ALL` dan hanya tambahkan capability yang benar-benar esensial.

### Recommended
- Gunakan `--read-only` dengan temporary RAM disk: `--tmpfs /tmp:rw,noexec,nosuid,size=64m`.
- Hindari menyertakan binary berbahaya seperti `sudo`, `su`, atau shell yang tidak perlu di dalam image produksi.

### Advanced
- Migrasikan seluruh daemon Docker di server Linux produksi ke **Rootless Docker Mode** untuk mengeliminasi ketergantungan root pada tingkat sistem operasi host.

---

## 17. Troubleshooting
- **Masalah**: Aplikasi crash saat start dengan error `EACCES: permission denied, open '/app/logs/server.log'`.
  - *Penyebab*: Container dijalankan dengan `--read-only` namun aplikasi mencoba menulis file log ke disk lokalnya.
  - *Solusi*: Konfigurasikan aplikasi untuk mencetak log ke `stdout`/`stderr` (bukan ke file lokal), atau pasang volume/tmpfs pada folder log tersebut.
- **Masalah**: Rootless Docker gagal mengikat port 80 atau 443 di host: `bind: permission denied`.
  - *Solusi*: Berikan izin unprivileged port di host Linux: `sudo sysctl -w net.ipv4.ip_unprivileged_port_start=80`.

---

## 18. Exercise
1. Jalankan container Alpine dengan `--user 5000:5000 --read-only --tmpfs /tmp` dan buktikan bahwa penulisan file ke `/root` ditolak, namun penulisan ke `/tmp` berhasil!
2. Uji efektivitas `--cap-drop=ALL`: Jalankan container Alpine tanpa capabilities dan coba jalankan perintah `ping 8.8.8.8` (gagal karena membutuhkan `CAP_NET_RAW`), lalu tambahkan kembali `--cap-add=NET_RAW` dan buktikan ping berhasil!

---

## 19. Challenge
Rancang arsitektur Hardened Container Sandbox:
- Buat image container API yang tidak memiliki shell interpreter (Distroless non-root).
- Tulis perintah `docker run` yang menerapkan 5 lapis pengerasan: non-root user, `no-new-privileges`, `cap-drop: ALL`, `read-only rootfs`, dan `tmpfs` dengan flag `noexec`.
- Simulasikan skenario penyerangan injeksi malware dan buktikan bahwa seluruh vektor eksploitasi berhasil dibendung.

---

## 20. Summary
- **Rootless Docker** dan **Non-Root Execution** mematahkan rantai serangan *container breakout* langsung di akarnya.
- **Linux Capabilities** memotong hak kekuasaan dewa root menjadi izin mikro terukur (`--cap-drop=ALL`).
- **`--read-only` root filesystem** dan **`no-new-privileges:true`** mengubah container menjadi lingkungan imutabel yang kebal terhadap modifikasi malware runtime.
