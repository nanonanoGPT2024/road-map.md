# Module 01: Arsitektur Kernel Linux, Manajemen Proses, & Konkurensi

## 1. Learning Objective
Setelah menyelesaikan modul ini, pembelajar akan mampu:
1. Memahami arsitektur internal sistem operasi Linux (User Space vs Kernel Space, System Calls, dan VFS).
2. Menganalisis siklus hidup proses (*Process Lifecycle*): States, PID, PPID, Fork/Exec, dan proses Zombie/Orphan.
3. Menguasai mekanisme komunikasi antar-proses (*Inter-Process Communication / IPC*) dan penanganan sinyal UNIX (`SIGTERM`, `SIGKILL`, `SIGHUP`).
4. Membedakan eksekusi proses multi-threading vs multi-processing serta implikasinya terhadap performa server produksi.

---

## 2. Prerequisite
- Memahami konsep dasar komputer (CPU, RAM, Storage).
- Pernah menggunakan terminal/command line dasar.

---

## 3. Concept
Linux adalah tulang punggung (*backbone*) infrastruktur cloud global. Lebih dari 90% beban kerja container, server cloud (AWS/GCP/Azure), dan cluster Kubernetes berjalan di atas kernel Linux.

Sebagai seorang DevOps Engineer atau SRE, Anda tidak hanya menjalankan perintah di terminal, melainkan harus memahami **bagaimana Linux mengelola sumber daya fisik mesin**:
- **Kernel Space**: Ruang memori istimewa (*privileged ring 0*) tempat kernel Linux mengontrol hardware (CPU scheduling, virtual memory paging, disk I/O, network driver).
- **User Space**: Ruang memori tempat aplikasi berjalan (Nginx, Node.js, Docker, JVM). Aplikasi user space **tidak boleh** mengakses hardware langsung; mereka harus meminta bantuan kernel melalui **System Calls (syscalls)** seperti `fork()`, `execve()`, `read()`, dan `write()`.

Setiap program yang berjalan di Linux direpresentasikan sebagai **Proses** dengan nomor identitas unik (**PID - Process ID**), ruang memori terisolasi, dan struktur data `task_struct` di kernel.

---

## 4. Why?
Mengapa pemahaman kernel dan proses sangat vital bagi DevOps?
1. **Root Cause Analysis & Troubleshooting**: Ketika sebuah container di Kubernetes tiba-tiba mati dengan status `OOMKilled (Exit Code 137)` atau proses `CrashLoopBackOff`, pemahaman tentang sinyal Linux dan memori paging memungkinkan Anda mendiagnosis akar masalah dalam hitungan menit.
2. **Optimasi Resource & Efisiensi Biaya**: Mengetahui perbedaan proses vs thread membantu Anda mengonfigurasi worker pool Nginx, Node.js cluster, atau Gunicorn Python secara akurat sesuai jumlah vCPU host.
3. **Pondasi Containerization**: Docker dan Kubernetes bukanlah mesin virtual ajaib; mereka hanyalah proses Linux biasa yang dibatasi menggunakan fitur kernel bawaan: **Namespaces** dan **Cgroups**.

---

## 5. What?
Komponen fundamental sistem operasi Linux yang wajib dikuasai:
- **System Call Interface (SCI)**: Gerbang jembatan antara aplikasi user space dan kernel (contoh: `clone()`, `epoll_wait()`, `kill()`).
- **Process State Machine**:
  - `R (Running/Runnable)`: Proses sedang dieksekusi CPU atau berada di run-queue siap jalan.
  - `S (Interruptible Sleep)`: Menunggu event (seperti network packet atau user input), dapat dibangunkan oleh sinyal.
  - `D (Uninterruptible Sleep)`: Menunggu operasi I/O disk hardware; **tidak dapat dimatikan bahkan dengan `kill -9`**!
  - `Z (Zombie)`: Proses anak (*child*) telah selesai (`exit()`), tetapi orang tuanya (*parent*) belum membaca exit status-nya via `waitpid()`.
  - `T (Stopped)`: Dijeda oleh sinyal (seperti `SIGSTOP` atau `Ctrl+Z`).
- **Signals**: Mekanisme notifikasi asinkron tingkat OS ke proses (contoh: `SIGTERM (15)` untuk graceful shutdown, `SIGKILL (9)` untuk pemutusan paksa oleh kernel).

---

## 6. How?
Bagaimana proses baru dibuat dan dijalankan di Linux?

```text
[ Parent Process (misal: Bash / PID 100) ]
                   │
                   │ 1. Memanggil syscall fork() / clone()
                   ▼
[ Kernel Menduplikasi task_struct & Address Space ]
                   │
                   │ Kembalian fork():
                   ├─ Ke Parent: PID Anak (misal: 101)
                   └─ Ke Child : 0
                   │
                   ▼
[ Child Process (PID 101) ]
                   │
                   │ 2. Memanggil syscall execve("/usr/bin/nginx")
                   ▼
[ Kernel Me-replace Kode Memori Child dengan Binari Baru ]
                   │
                   ▼
[ Child Berjalan sebagai Program Nginx ]
                   │
                   │ 3. Child Selesai -> Memanggil exit(0)
                   ▼
[ Status Child Berubah Jadi ZOMBIE ]
  - Memori RAM dilepas
  - task_struct & exit code tetap ada di process table
                   │
                   │ 4. Parent Memanggil waitpid(101) (Reaping)
                   ▼
[ Entry PID 101 Dihapus Bersih dari Process Table ]
```

---

## 7. Analogy
Bayangkan sistem operasi Linux seperti **Restoran Bintang Lima**:
- **Pelanggan di Meja (User Space Applications)**: Ingin makan dan minum, tetapi dilarang masuk langsung ke dapur atau memegang kompor gas.
- **Pelayan Resmi (System Calls)**: Pelanggan memanggil pelayan untuk memesan makanan (`syscall`).
- **Dapur & Chef Eksekutif (Kernel Space)**: Memegang otoritas penuh atas kompor, gas, dan bahan baku (hardware).
- **Meja Pelanggan (Proses)**: Setiap rombongan pelanggan memiliki nomor meja unik (PID). Jika pelanggan selesai makan tetapi pelayan belum membersihkan piring kotor dan struknya, meja tersebut menjadi **Meja Kosong Piring Kotor (Zombie Process)** yang memakan jatah kapasitas restoran.

---

## 8. Diagram
```text
+-------------------------------------------------------------------+
|                           USER SPACE                              |
|   +-------------------+    +-----------------+    +-----------+   |
|   |  Nginx Web Server |    | Node.js API App |    | Bash CLI  |   |
|   +-------------------+    +-----------------+    +-----------+   |
|             \                      |                     /        |
|              \                     |                    /         |
|               +--------------------+-------------------+          |
|                                    |                              |
|                         System Calls (POSIX API)                  |
+------------------------------------|------------------------------+
                                     v
+-------------------------------------------------------------------+
|                          KERNEL SPACE                             |
|  +-------------------------------------------------------------+  |
|  |                System Call Interface (SCI)                  |  |
|  +-------------------------------------------------------------+  |
|  | Process Scheduler | Memory Manager | VFS (Files) | Net Stack|  |
|  +-------------------------------------------------------------+  |
|  |                 Device Drivers & Hardware Rings             |  |
+------------------------------------|------------------------------+
                                     v
                        [ CPU / RAM / DISK / NIC ]
```

---

## 9. Simple Example
Perintah Linux esensial untuk inspeksi proses:

```bash
# 1. Melihat pohon proses hierarki (Parent-Child)
pstree -p -s $$

# 2. Melihat seluruh proses dengan rincian state, user, dan resource
ps aux | grep nginx

# 3. Mengirim sinyal graceful shutdown (SIGTERM)
kill -15 <PID>

# 4. Mengirim sinyal reload konfigurasi tanpa mematikan proses (SIGHUP)
kill -1 <PID>

# 5. Memeriksa proses yang sedang berada dalam status Zombie (State Z)
ps -eo pid,ppid,stat,cmd | grep ' Z'
```

---

## 10. Practical Example
Simulasi pembuatan proses anak (*Fork*) dan penanganan sinyal graceful shutdown di Node.js:

```javascript
const { fork } = require('child_process');

console.log(`[PARENT] Running on PID: ${process.pid}`);

// Tangani sinyal SIGTERM dari Docker / Kubernetes
process.on('SIGTERM', () => {
  console.log('[PARENT] Menerima sinyal SIGTERM! Memulai graceful cleanup...');
  // 1. Berhenti menerima koneksi baru
  // 2. Tunggu request yang sedang berjalan selesai
  // 3. Keluar dengan kode 0
  setTimeout(() => {
    console.log('[PARENT] Cleanup selesai. Shutdown.');
    process.exit(0);
  }, 1000);
});
```

---

## 11. Real World Example
### Kasus: Kubernetes Pod Mengabaikan SIGTERM & Mengalami Forced SIGKILL
1. Developer membuat aplikasi backend Node.js yang dijalankan di Kubernetes pod.
2. Ketika deployment di-update (*Rolling Update*), Kubernetes mengirimkan sinyal `SIGTERM` ke PID 1 di dalam container.
3. Aplikasi Node.js tidak memasang listener `process.on('SIGTERM')`.
4. Akibatnya, aplikasi tidak melakukan flush transaksi database yang sedang berlangsung.
5. Setelah batas `terminationGracePeriodSeconds` (default: 30 detik) habis, Kubernetes mengirim `SIGKILL (kill -9)`.
6. Terjadi inkonsistensi data transaksi di database dan puluhan request client mengalami HTTP 502 Bad Gateway.
7. **Solusi SRE**: Pasang signal handler `SIGTERM` eksplisit untuk menutup koneksi database secara tertib sebelum proses berhenti.

---

## 12. Trade-offs
| Pendekatan | Multi-Threading | Multi-Processing |
|---|---|---|
| **Memory Isolation** | Rendah (semua thread berbagi ruang alamat memori yang sama) | Tinggi (setiap proses memiliki virtual address space terpisah) |
| **Crash Blast Radius** | Tinggi (jika 1 thread corrupt, seluruh proses bisa crash) | Rendah (jika 1 worker crash, worker lain tetap hidup) |
| **Overhead Context Switch** | Ringan (cepat berganti thread) | Lebih berat (harus switch memory context register) |
| **Contoh Penggunaan** | Java JVM, Golang Goroutines, C++ multi-thread | Nginx worker processes, Python Gunicorn, PostgreSQL |

---

## 13. When To Use
- **Multi-Processing**: Layanan yang membutuhkan isolasi fault-tolerance tinggi (misal: web server multi-tenant, worker isolasi job).
- **Multi-Threading / Async I/O**: Aplikasi yang didominasi oleh operasi network I/O (seperti microservice API gateway atau proxy).

---

## 14. When NOT To Use
- Jangan membuat ratusan *heavy processes* secara manual tanpa pooling; hal ini akan memicu *fork bomb* yang menghabiskan memori RAM dan tabel PID kernel.

---

## 15. Common Mistakes
1. **Menggunakan `kill -9` (`SIGKILL`) Sebagai Solusi Pertama**: Langsung membunuh proses dengan `kill -9` tidak memberi kesempatan aplikasi menutup file, melepas database lock, atau menghapus socket PID file, memicu file korup.
2. **Mengabaikan Zombie Processes**: Membiarkan ribuan zombie menumpuk. Meski zombie tidak memakan RAM, zombie menghabiskan jatah nomor PID di tabel kernel (`/proc/sys/kernel/pid_max`).
3. **Aplikasi Sebagai PID 1 di Container Tanpa Init Process**: Di dalam Docker container, PID 1 memiliki tanggung jawab khusus me-*reap* orphan process dan meneruskan sinyal. Jika aplikasi Anda bukan init system dan tidak meng-handle sinyal, container akan sulit dimatikan secara graceful.

---

## 16. Best Practices
### Must Have
- Selalu tangani sinyal `SIGTERM` dan `SIGINT` di aplikasi produksi untuk menjamin *graceful shutdown*.
- Monitor metrik penggunaan PID (`ps -e | wc -l`) di server produksi.
- Selalu gunakan `kill -15` terlebih dahulu, berikan jeda grace period, baru gunakan `kill -9` jika proses benar-benar hang.

### Recommended
- Gunakan `tini` atau `dumb-init` sebagai PID 1 di Docker container jika aplikasi Anda men-spawn child processes.
- Atur batas proses (`ulimit -u` / `nproc`) di `/etc/security/limits.conf` untuk mencegah *fork bomb*.

### Avoid / Overengineering
- Jangan melakukan tuning manual kernel sysctl (`/etc/sysctl.conf`) tanpa metrik pengukuran baseline yang jelas.

---

## 17. Troubleshooting
| Gejala | Kemungkinan Penyebab | Solusi |
|---|---|---|
| Perintah `kill -9 <PID>` tidak mempan mematikan proses | Proses berada di state `D` (Uninterruptible Sleep) menunggu respons hardware/NFS mount | Periksa koneksi disk I/O / storage; proses hanya bisa hilang jika I/O selesai atau server di-reboot |
| Server menolak membuat proses baru (*fork: Cannot allocate memory*) | Batas `pid_max` atau memori swap habis | Periksa zombie process dengan `ps aux | grep 'Z'`, lalu bunuh parent process-nya |
| Load average CPU melonjak tinggi tapi CPU % idle | Banyak proses antre di disk I/O (*I/O wait*) | Periksa disk throughput dengan `iostat -xz 1` atau `iotop` |

---

## 18. Exercise
1. Jalankan sebuah proses background di terminal, lalu catat PID dan PPID-nya menggunakan perintah `ps`.
2. Kirim sinyal `SIGSTOP` untuk menjeda proses, periksa statusnya, lalu kirim `SIGCONT` untuk melanjutkannya kembali.

---

## 19. Challenge
Rancang arsitektur simulasi **Process Lifecycle & Zombie Reaper Engine**:
- Buat parent process yang men-spawn 3 child process pekerja.
- Biarkan salah satu child exit tanpa dipanggil `waitpid()` untuk mengamati transisi ke state `ZOMBIE`.
- Terapkan fungsi *Reaper* untuk membersihkan proses zombie tersebut dari tabel proses sebelum kehabisan slot PID.

---

## 20. Summary
- Kernel Linux mengisolasi aplikasi di User Space dan mengeksekusi kontrol perangkat keras di Kernel Space melalui System Calls.
- Memahami siklus hidup proses, status (`R`, `S`, `D`, `Z`), serta sinyal (`SIGTERM`, `SIGKILL`) adalah fondasi mutlak troubleshooting container dan Kubernetes di lingkungan produksi.
- Modul praktikum lab dapat dijalankan langsung di [hands-on/m01/linux_process_manager.js](file:///d:/explore/roadmap.sh%20materi/DevOps/BAB-01-Sistem-Operasi-dan-Linux-Automation/hands-on/m01/linux_process_manager.js).
