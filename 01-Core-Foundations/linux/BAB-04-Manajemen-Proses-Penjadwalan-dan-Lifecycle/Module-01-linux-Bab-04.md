## SEKSI 01 — IDENTITAS MODUL

*   **Kode Modul:** LIN-01-04-01
*   **Nama Modul:** Arsitektur Proses Linux: Lifecycle, Struktur Kernel (`task_struct`), dan Penjadwalan CFS
*   **Kategori:** 01-Core-Foundations
*   **Prasyarat:** 
    *   Pemahaman dasar CLI Linux (Bash navigasi, redirection, piping).
    *   Konsep dasar arsitektur komputer (CPU register, memory virtual, interrupts).
    *   Struktur filesystem Linux dasar (`/proc`, `/sys`).
*   **Estimasi Waktu Penyelesaian:** 180 Menit (Teori: 75 Menit, Praktik Hands-On: 105 Menit)
*   **Tingkat Kesulitan:** Intermediate to Advanced

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

1.  **Menganalisis Arsitektur Proses Kernel:** Mendekonstruksi representasi internal proses di kernel Linux melalui struktur data `task_struct` dan hierarki Process Control Block (PCB).
2.  **Melacak Lifecycle Transisi State:** Mengidentifikasi dan memetakan siklus hidup proses (Running, Interruptible, Uninterruptible/D-state, Stopped, Zombie) serta mengisolasi anomali transisi state.
3.  **Mengevaluasi Algoritma Penjadwalan CFS:** Menjelaskan secara matematis dan operasional cara kerja *Completely Fair Scheduler* (CFS), termasuk konsep `vruntime`, *weight table*, dan struktur data *Red-Black Tree* (`rb_node`).
4.  **Mengoptimasi dan Mengontrol Prioritas:** Mengimplementasikan kontrol eksekusi proses melalui manipulasi nilai *nice* (static priority), manipulasi kelas *Real-Time scheduling* (`SCHED_FIFO`, `SCHED_RR`), serta tuning parameter CFS melalui `sysctl`.
5.  **Melakukan Diagnostik Root-Cause Process Bottlenecks:** Membedah degradasi performa sistem akibat *D-state processes*, *zombie accumulation*, dan *CPU context switching thrashing* menggunakan perangkat analitik modern (`/proc`, `pidstat`, `strace`).

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```
                            [Kernel Space: Linux Core]
                                       |
                +----------------------+----------------------+
                |                                             |
     [Struktur Data Kernel]                         [Sub-sistem Penjadwalan]
                |                                             |
         +------+------+                               +------+------+
         |             |                               |             |
   `task_struct`   PID / Namespaces            Kelas Penjadwalan  Algoritma CFS
   - State         - PID 1 (Init/systemd)      - SCHED_OTHER      - vruntime
   - mm_struct     - PPID (Parent)             - SCHED_FIFO       - RB-Tree (O(log N))
   - files_struct  - TGID (Thread Group)       - SCHED_DEADLINE   - sysctl latency
         |                                             |
         +----------------------+----------------------+
                                |
                     [User Space: Lifecycle]
                                |
        +-----------+-----------+-----------+-----------+
        |           |           |           |           |
     [fork()]   [execve()]   [Running]   [Sleeping]   [exit()]
         |                       |       (S / D State)    |
   Copy-On-Write (COW)     CPU Preemption       |      [Zombie (Z)]
                                                |         |
                                         Event/IO Wait   wait4() reap
```

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

Pada sistem operasi multi-tasking berbasis Linux, abstraksi proses adalah unit fundamental dari isolasi komputasi dan konsumsi sumber daya. Kesalahan persepsi terhadap cara Linux mengelola dan menjadwalkan proses berdampak fatal pada level rekayasa keandalan sistem (SRE), arsitektur cloud/container, dan pengembangan aplikasi performa tinggi:

1.  **Resolusi Masalah Sistem yang Akurat:** Kejadian seperti *High Load Average* sering kali disalahartikan semata-mata sebagai kekurangan CPU. Padahal, proses dalam kondisi `TASK_UNINTERRUPTIBLE` (D-state) yang menunggu I/O disk atau NFS juga berkontribusi pada metrik *Load Average*. Tanpa pemahaman lifecycle, seorang engineer akan salah mendiagnosis kapasitas komputasi.
2.  **Mitigasi Resource Starvation:** Memahami mekanisme CFS (*Completely Fair Scheduler*) mencegah kondisi *thread starvation* pada aplikasi multi-threaded throughput tinggi, dan memberikan kemampuan untuk menentukan prioritas thread kritis (*nice* / *real-time priority*).
3.  **Efisiensi Orkestrasi Container:** Container (Docker/Kubernetes) bukan VM, melainkan proses Linux standar yang dibatasi oleh *cgroups* dan *namespaces*. Memahami lifecycle proses pada host Linux adalah prasyarat mutlak untuk mendiagnosis masalah container seperti *OOMKilled* (Out of Memory), *Zombie process leakage* di dalam Pod, dan propagasi sinyal POSIX (`SIGTERM` vs `SIGKILL`).

---

## SEKSI 05 — APA ITU (WHAT)

### Proses vs. Thread di Linux
Dalam terminologi POSIX, proses adalah program yang sedang dieksekusi dengan ruang alamat memori mandiri, sementara thread adalah unit eksekusi di dalam proses yang berbagi ruang alamat tersebut. 

Namun di dalam Kernel Linux, distingsi ini ditiadakan pada tingkat abstraksi terendah. Kernel Linux memandang keduanya sebagai **Task**. Baik proses single-threaded, thread dari proses multi-threaded, maupun kernel thread, semuanya direpresentasikan oleh entitas struktur yang identik: `struct task_struct`.

*   **Proses Tradisional:** Sebuah task yang memiliki `task_struct` dengan alokasi `mm_struct` (ruang alamat memori virtual) yang unik.
*   **Thread (Lightweight Process - LWP):** Sebuah task yang dibuat via syscall `clone()` dengan flag `CLONE_VM`, `CLONE_FILES`, dan `CLONE_FS` aktif, sehingga berbagi alokasi `mm_struct`, deskriptor file, dan filesystem context yang sama dengan pembuatnya. Task-task ini tergabung di dalam satu Thread Group yang diidentifikasi oleh TGID (*Thread Group ID*), yang oleh *user space* dikenal sebagai Process ID (PID).

### Process Control Block (PCB): `task_struct`
Didefinisikan di `<linux/sched.h>`, `task_struct` adalah salah satu struktur data terbesar di kernel Linux (sering kali berukuran > 5-9 KB tergantung kompilasi kernel). Properti krusialnya mencakup:
*   `volatile long state`: State eksekusi task saat ini.
*   `pid_t pid`: ID unik untuk task individual (pada thread, ini adalah TID).
*   `pid_t tgid`: Thread Group ID (pada user space, ini adalah PID aplikasi).
*   `struct task_struct *parent`: Pointer ke task induk (PPID).
*   `struct mm_struct *mm`: Pointer ke deskriptor memori virtual.
*   `struct files_struct *files`: Pointer ke *file descriptor table*.
*   `struct sched_entity se`: Entitas penjadwalan yang digunakan oleh CFS.

---

## SEKSI 06 — BAGAIMANA CARA KERJA (HOW)

### 1. Mekanisme Pembuatan Proses: `fork()`, COW, dan `execve()`
Linux tidak membuat proses baru dari nol (*from scratch*). Pembuatan proses berbasis duplikasi hierarkis:

```
[Parent Process]
       |
       |-- 1. Invokasi syscall: fork() / clone()
       |
       v
[Kernel Execution]
       |-- Alokasi task_struct baru
       |-- Duplikasi Page Tables Parent (halaman ditandai Read-Only)
       |-- Alokasi PID baru
       |
       +-----------------------+
       |                       |
       v                       v
[Parent Process Resume]  [Child Process (Copy of Parent)]
                               |
                               |-- 2. Memori ditulisi? -> Page Fault -> Copy-On-Write (COW)
                               |-- 3. Invokasi execve("/bin/binary")
                               v
                         [Child Process (New Binary Executable)]
```

*   **Copy-on-Write (COW):** Saat `fork()` dipanggil, kernel tidak menyalin seluruh physical memory parent ke child. Kernel hanya menyalin *page tables* dan menandai physical pages sebagai *Read-Only*. Jika parent atau child mencoba menulis ke salah satu page tersebut, CPU memicu *Page Fault*. Kernel kemudian menginterupsi eksekusi, mengalokasikan physical frame memori baru, menyalin data dari frame lama ke baru, menandainya sebagai *Read-Write*, dan melanjutkan instruksi. Hal ini membuat operasi `fork()` berlangsung sangat cepat dan hemat memori.
*   **`execve()`:** Syscall ini menimpa segmen memori (text, data, bss, heap, stack) dari proses pemanggil dengan binary baru, mereset konteks eksekusi register CPU, namun tetap mempertahankan PID, PPID, serta file descriptor yang tidak diatur dengan flag `FD_CLOEXEC`.

### 2. State Machine Proses Linux
Setiap task berada di salah satu state berikut:
*   **TASK_RUNNING (R):** Task sedang dieksekusi di CPU core atau sedang berada di *runqueue* menunggu giliran CPU.
*   **TASK_INTERRUPTIBLE (S):** Task dalam kondisi tidur (*blocked/sleeping*), menunggu sebuah event (I/O, timeout, sinyal). Task dapat segera dibangunkan jika menerima sinyal POSIX.
*   **TASK_UNINTERRUPTIBLE (D):** Task sedang tidur dan **tidak dapat diinterupsi oleh sinyal apa pun** (termasuk `SIGKILL`). Biasa terjadi ketika task menunggu respon perangkat keras secara sinkron (misal: read blok dari disk atau remote NFS lock). Jika disk hang, proses di D-state akan bertahan sampai I/O selesai.
*   **TASK_STOPPED (T):** Task dihentikan sementara akibat penerimaan sinyal `SIGSTOP`, `SIGTSTP`, atau kontrol debugger (`ptrace`).
*   **EXIT_ZOMBIE (Z):** Task telah menyelesaikan eksekusi (`exit()`), memori dan deskriptor filenya telah dilepas, namun `task_struct`-nya tetap dipertahankan di kernel task list agar proses parent dapat membaca status terminasinya via `wait4()`.

### 3. Penjadwalan CFS (Completely Fair Scheduler)
Diperkenalkan pada Kernel 2.6.23, CFS menggantikan *O(1) Scheduler*. CFS menggunakan konsep matematis berupa *Virtual Runtime* (`vruntime`).

#### a. Konsep Virtual Runtime (`vruntime`)
`vruntime` mengukur seberapa banyak waktu CPU yang telah dikonsumsi oleh sebuah task, dinormalisasi berdasarkan prioritas (*nice level*). Task dengan nilai `vruntime` terendah adalah task yang paling berhak mendapatkan giliran CPU berikutnya untuk menjamin keadilan (*fairness*).

Peningkatan `vruntime` dihitung melalui formula:
$$\Delta vruntime = \Delta exec\_time \times \frac{W_{NICE\_0}}{W_{p}}$$

Di mana:
*   $\Delta exec\_time$ = Waktu fisik aktual task berjalan di CPU.
*   $W_{NICE\_0}$ = Bobot untuk nice level 0 (konstanta kernel: 1024).
*   $W_{p}$ = Bobot task berdasarkan nilai nice saat ini (diambil dari tabel array `sched_prio_to_weight`).

Setiap penurunan tingkat nice (semakin bernilai negatif / prioritas lebih tinggi) meningkatkan bobot $W_p$ secara eksponensial (~1.25x per level). Akibatnya, pembagi menjadi lebih besar, pertambahan `vruntime` menjadi lebih lambat, dan task mendapatkan porsi waktu eksekusi CPU yang jauh lebih besar.

#### b. Struktur Data Red-Black Tree (`rb_node`)
CFS tidak menggunakan antrean FIFO sederhana untuk melacak task yang siap jalan. CFS menyimpan semua task yang berada dalam state `TASK_RUNNING` di dalam struktur data **Self-Balancing Red-Black Tree (RB-Tree)**:

*   **Key Penentu Node:** Nilai `vruntime`.
*   **Task yang Dipilih:** Node paling kiri (*leftmost node*), yang memiliki `vruntime` paling kecil.
*   **Kompleksitas Seleksi:** Mengambil task berikutnya adalah $O(1)$ karena kernel menyimpan pointer cache langsung ke leftmost node (`rb_leftmost`).
*   **Kompleksitas Update:** Menghapus atau memasukkan kembali task setelah kuantum waktunya habis memakan waktu $O(\log N)$, di mana $N$ adalah jumlah task yang runnable di runqueue core tersebut.

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

### Lifecycle & State Transitions

```
                    +--------------------------------+
                    |           fork()               |
                    +--------------------------------+
                                   |
                                   v
+-------------------> [ TASK_RUNNING (R) ] <-----------------+
|                       |            ^                      |
|            Scheduler  |            | Event/Data           |
|            Preempts   |            | Arrives              |
|                       v            |                      |
|       +-------------------+        |                      |
|       | TASK_INTERRUPTIBLE|--------+                      |
|       |       (S)         |                               |
|       +-------------------+                               |
|                 ^                                         |
|                 | System Call (Blocking I/O)              |
|                 |                                         |
|       +---------------------+                             |
|       |TASK_UNINTERRUPTIBLE |                             |
|       |       (D)           |                             |
|       +---------------------+                             |
|                 |                                         |
|                 | Hardware Device Ready                   |
|                 +-----------------------------------------+
|
| Sinyal SIGCONT      Sinyal SIGSTOP / SIGTSTP
|                 +-----------------------+
+-----------------|   TASK_STOPPED (T)    |
                  +-----------------------+
                              |
                              | do_exit()
                              v
                  +-----------------------+
                  |    EXIT_ZOMBIE (Z)    |
                  +-----------------------+
                              |
                              | Parent calls wait4()
                              v
                      [ TASK TERMINATED ]
                     (task_struct freed)
```

### CFS Runqueue (Red-Black Tree) Representation

```
                         [ CFS Runqueue (Per Core) ]
                                      |
                                  Node B
                            (vruntime = 450ms)
                                 /      \
                                /        \
                           Node A        Node C
                     (vruntime = 320ms) (vruntime = 600ms)
                           /
                          /
                 * [ Node Target: Leftmost ] *
                     (vruntime = 150ms)
                              |
                              v
               [ CPU Context Switches to Target ]
                              |
         Target berjalan selama waktu delta (misal: 10ms)
               vruntime bertambah: 150ms + 10ms = 160ms
                              |
      Target dimasukkan kembali ke RB-Tree pada posisi baru: O(log N)
```

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

Berikut adalah perintah-perintah esensial untuk memeriksa status proses, melacak pohon proses, dan memanipulasi eksekusi secara real-time.

### 1. Memeriksa Struktur Pohon Proses
Melihat bagaimana `systemd` (PID 1) mengontrol seluruh sub-proses:

```bash
# Menampilkan pohon proses beserta PID dan user
pstree -p -u
```

### 2. Memfilter dan Membaca Kolom Status Proses Standar POSIX
Melihat task beserta statenya:

```bash
# Opsi -eo menentukan format output kustom
ps -eo pid,ppid,stat,ni,comm | grep -E 'STAT|apache2|nginx|bash'
```

*Contoh Output:*
```text
    PID    PPID STAT NI COMMAND
   1204       1 Ss    0 nginx
   1205    1204 S     0 nginx
   1450       1 S    10 mysqld
   2040    1020 R+    0 ps
```
*Interpretasi Stat Flags:*
*   `S`: Interruptible Sleep
*   `s`: Session Leader
*   `+`: Berada di Foreground Process Group
*   `R`: Sedang berjalan (Running)
*   `NI`: Nilai nice (0 = default, 10 = low priority)

### 3. Mengirimkan Kontrol Sinyal secara Manual
Menghentikan sementara dan melanjutkan eksekusi proses:

```bash
# 1. Jalankan proses dummy di background
sleep 1000 &
TARGET_PID=$!
echo "Process started with PID: ${TARGET_PID}"

# 2. Kirim sinyal STOP (state berubah menjadi T)
kill -STOP ${TARGET_PID}
ps -o pid,stat,comm -p ${TARGET_PID}

# 3. Lanjutkan kembali proses (state kembali ke S / R)
kill -CONT ${TARGET_PID}
ps -o pid,stat,comm -p ${TARGET_PID}

# 4. Bersihkan proses
kill -TERM ${TARGET_PID}
```

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

### Skenario: Investigasi "High Load Average" dengan Zero CPU Utilization (D-State Lockup)

#### 1. Konteks Masalah
Sebuah server database melaporkan `load average: 15.00, 14.80, 12.10`, namun utilitas CPU secara agregat via `mpstat` atau `top` hanya berkisar di `3%`. Kueri database mengalami timeout total.

#### 2. Investigasi Root-Cause Menggunakan `/proc` dan Tooling Sistem

Langkah A: Identifikasi task yang berada di status `D` (*Uninterruptible Sleep*):
```bash
# Mencari semua proses berstatus D
ps -eo pid,ppid,user,stat,wchan:30,comm | awk '$4 ~ /D/ {print $0}'
```

*Output yang diperoleh:*
```text
  PID  PPID USER     STAT WCHAN                          COMMAND
 8492  1200 postgres D    nfs_wait_bit_uninterruptible  postgres
 8493  1200 postgres D    nfs_wait_bit_uninterruptible  postgres
 8494  1200 postgres D    nfs_wait_bit_uninterruptible  postgres
```
*Analisis:* Kolom `WCHAN` (Wait Channel) menunjukkan fungsi kernel tempat task tersebut tidur: `nfs_wait_bit_uninterruptible`. Task terkunci di layer filesystem NFS.

Langkah B: Melacak Call Stack Kernel dari task tersebut secara non-destruktif:
```bash
# Memeriksa stack kernel PID 8492
cat /proc/8492/stack
```

*Output Stack Trace:*
```text
[<0>] nfs_wait_bit_uninterruptible+0x33/0x50 [nfs]
[<0>] __rpc_execute+0x85/0x3f0 [sunrpc]
[<0>] rpc_execute+0x59/0xc0 [sunrpc]
[<0>] nfs4_call_sync_sequence+0x68/0xa0 [nfsv4]
[<0>] _nfs4_proc_getattr+0x6a/0x90 [nfsv4]
[<0>] nfs4_proc_getattr+0x54/0x80 [nfsv4]
[<0>] nfs_getattr+0x13c/0x270 [nfs]
[<0>] vfs_statx+0x99/0x100
[<0>] __do_sys_newstat+0x39/0x70
[<0>] do_syscall_64+0x5b/0x1b0
[<0>] entry_SYSCALL_64_after_hwframe+0x44/0xa9
```
*Akar Masalah Terbukti:* Proses `postgres` mengeksekusi syscall `newstat` menuju share NFS yang sedang *stale* / unreachable network-nya. Karena berada di `TASK_UNINTERRUPTIBLE`, sinyal `kill -9 8492` tidak akan pernah diproses oleh kernel untuk task ini.

#### 3. Prosedur Remediasi
Karena task di D-state tidak merespons interupsi software, intervensi harus dilakukan pada subsistem I/O penyebab:
```bash
# 1. Identifikasi mount point NFS yang macet
df -hT | grep nfs || mount | grep nfs

# 2. Paksa pemutusan mount NFS secara lazy/unmount paksa
umount -f -l /mnt/nfs_share

# 3. Jika mount terlepas, thread NFS akan return error (EIO) ke sistem,
# mengembalikan task ke TASK_RUNNING dan melepaskan lock Load Average.
```

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

Ketika merekayasa atau men-tuning alokasi CPU untuk task di Linux, engineer dihadapkan pada sejumlah trade-off mekanis:

### 1. Scheduler Policy: `SCHED_OTHER` (CFS) vs `SCHED_FIFO` / `SCHED_RR` (Real-Time)

| Kriteria | `SCHED_OTHER` (CFS) | `SCHED_FIFO` (Real-Time) | `SCHED_RR` (Real-Time) |
| :--- | :--- | :--- | :--- |
| **Prinsip Dasar** | Keadilan alokasi bandwidth CPU via `vruntime`. | Prioritas statis absolut (1–99). Tidak ada keadilan. | Prioritas statis absolut dengan kuantum waktu per-task. |
| **Preemption** | Preempt jika task lain punya `vruntime` jauh lebih kecil. | **Tidak pernah** di-preempt oleh CFS. Berjalan sampai selesai atau yield. | Di-preempt hanya oleh task RT lain dengan prioritas sama setelah time slice habis. |
| **Latency Determinis** | Rendah, namun ada jitter (variasi latency). | Ekstrem deterministik (sangat rendah). Cocok untuk sinyal audio/robotik. | Sangat deterministik. |
| **Risiko Kegagalan** | Rendah. Sistem aman dari starvation total. | **Tinggi.** Bug infinite loop pada task RT akan mematikan akses OS (kernel freeze). | **Tinggi.** Memerlukan pembatasan kuota CPU via sysctl. |

### 2. CFS Tuning: Latency Target vs Throughput (Context Switching Cost)
Kernel CFS menyediakan knob tuning di direktori `/proc/sys/kernel/`:

*   `sched_latency_ns`: Target periode di mana semua task runnable harus mendapat giliran minimal 1 kali.
*   `sched_min_granularity_ns`: Durasi minimum CPU time slice yang dijamin bagi task sebelum task tersebut dapat di-preempt oleh CFS.

*Trade-Off Analysis:*
*   **Mengurangi `sched_min_granularity_ns`:** Latency respons task meningkat secara responsif (sangat baik untuk UI desktop atau microservices API dengan SLA latensi < 1ms). **Kelemahan:** Frekuensi context-switch melonjak drastis, memicu cache invalidation di L1/L2/L3 CPU, dan mengorbankan *overall throughput*.
*   **Meningkatkan `sched_min_granularity_ns`:** Throughput sistem maksimal karena CPU fokus mengeksekusi instruksi tanpa banyak overhead context switching (ideal untuk HPC / batch processing / data encoding). **Kelemahan:** Latensi tail (P99) aplikasi web interaktif akan memburuk.

---

## SEKSI 11 — BEST PRACTICES

1.  **Gunakan Sinyal POSIX secara Bertahap (Graceful Termination):**
    *   Jangan membiasakan langsung menggunakan `kill -9` (`SIGKILL`).
    *   Kirimkan sinyal `kill -15` (`SIGTERM`) terlebih dahulu. Biarkan aplikasi melepaskan koneksi TCP, mem-flush I/O buffer ke disk, dan menghapus socket/lock file. Gunakan `SIGKILL` hanya jika proses gagal terminasi setelah grace period (misal: timeout 10-30 detik).
2.  **Mitigasi Zombie Process pada Container:**
    *   Container engine memetakan proses entrypoint container ke PID 1 di dalam namespace tersebut. Jika entrypoint bukan init process (seperti `tini` atau `dumb-init`) dan aplikasi gagal memanggil `wait4()` pada sub-proses yang telah mati, sistem namespace akan dipenuhi oleh *zombie processes*. Selalu gunakan init handler ringkas pada kontainer yang men-spawn proses shell (`exec dumb-init -- /app/run`).
3.  **Terapkan Isolasi Thread Kritis via `chrt` dan Core Affinity (`taskset`):**
    *   Untuk aplikasi low-latency (seperti payment gateway engine atau financial matching engine), kombinasikan kebijakan real-time dengan CPU pinning untuk mengeliminasi cache thrashing:
    ```bash
    # Mengikat proses PID 5432 ke CPU Core 2 dan 3 dengan prioritas Real-Time FIFO 50
    taskset -cp 2,3 5432
    chrt -f -p 50 5432
    ```
4.  **Audit Context Switch Sistem secara Periodik:**
    *   Pantau metrik `cs` (*context switches*) dan `in` (*interrupts*) pada `vmstat 1`. Jika angka *involuntary context switches* (`pidstat -w`) sangat tinggi pada task tertentu, itu menandakan over-subscription CPU atau pertarungan resource yang parah.

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

1.  **Mengasumsikan Zombie Process Mengonsumsi Memori dan CPU:**
    *   *Kekeliruan:* Banyak sysadmin panik saat melihat kolom `Z` di `top` dan menduga ada memory leak.
    *   *Fakta Teknis:* Zombie process **tidak mengonsumsi CPU ataupun alokasi memori fisik (RAM)**. Memori sudah dikembalikan ke kernel saat `exit()`. Zombie hanya mengonsumsi 1 slot pada Process Table kernel (berupa entri `task_struct`). Bahaya sesungguhnya dari zombie adalah exhaustion alokasi PID kernel (ditentukan di `/proc/sys/kernel/pid_max`).
2.  **Mencoba Me-`SIGKILL` Task di Status `D` (Uninterruptible Sleep):**
    *   *Kekeliruan:* Menjalankan `kill -9 <PID>` pada task berstatus `D` dan merasa heran mengapa proses tidak pernah hilang.
    *   *Fakta Teknis:* Kode kernel task di status `D` secara eksplisit mengabaikan sinyal pending (bitmask signal tidak diproses) sampai task terbangun dari blokade hardware. Satu-satunya cara menghilangkan proses D-state adalah dengan mengembalikan resource I/O yang ditunggu, atau me-reboot mesin jika terjadi deadlock hardware kernel driver.
3.  **Salah Membaca Nilai Nice:**
    *   *Kekeliruan:* Mengira bahwa nilai nice `+19` berarti prioritas paling tinggi.
    *   *Fakta Teknis:* Skala nice adalah -20 hingga +19. Semakin **tinggi** angka nice-nya, semakin **ramah (nice)** task tersebut terhadap proses lain, yang berarti prioritas eksekusinya **paling rendah**. Nilai -20 adalah prioritas CFS tertinggi.

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Lab 1: Guided — Eksplorasi Struktur Proses di `/proc` dan Dynamic Renicing
*Tujuan:* Mempelajari korelasi antara representasi kernel di `/proc` dan manipulasi CFS.

1.  Jalankan kalkulasi background CPU-intensive:
    ```bash
    # Menggunakan pipeline sha256 terus-menerus
    sha256sum /dev/zero &
    LAB_PID=$!
    echo "Lab Process running with PID: ${LAB_PID}"
    ```
2.  Inspeksi pemetaan memori virtual dan atribut penjadwalan via `/proc`:
    ```bash
    cat /proc/${LAB_PID}/sched | head -n 15
    cat /proc/${LAB_PID}/status | grep -E 'State|Threads|voluntary'
    ```
3.  Ubah nilai prioritas nice proses tersebut dari 0 ke 15:
    ```bash
    renice -n 15 -p ${LAB_PID}
    ```
4.  Verifikasi perubahan nilai nice dan pembobotan di `/proc`:
    ```bash
    cat /proc/${LAB_PID}/stat | awk '{print "PID: "$1, "Nice: "$19, "Priority: "$18}'
    ```
5.  Terminasi proses lab:
    ```bash
    kill -TERM ${LAB_PID}
    ```

### Lab 2: Semi-Guided — Simulasi dan Penanganan Zombie Process
*Tujuan:* Mensimulasikan pembiaran proses child oleh parent dan melakukan mitigasi via PPID targeting.

1.  Buat script Python sederhana `zombie_maker.py`:
    ```python
    import os
    import time
    import sys

    pid = os.fork()

    if pid > 0:
        print(f"[Parent] PID: {os.getpid()} spawned child PID: {pid}")
        print("[Parent] Sleeping for 60 seconds without calling wait()...")
        time.sleep(60)
        print("[Parent] Exiting.")
    else:
        print(f"[Child] PID: {os.getpid()} exiting immediately.")
        sys.exit(0)
    ```
2.  Jalankan script di background:
    ```bash
    python3 zombie_maker.py &
    ```
3.  Amati status child process menggunakan `ps`:
    ```bash
    ps -eo pid,ppid,stat,comm | grep -E 'zombie_maker|defunct'
    ```
    *(Identifikasi tanda `Z` atau `<defunct>` pada child).*
4.  *Tugas Praktik:* Coba jalankan `kill -9` pada PID child. Amati apakah child hilang? Mengapa tidak?
5.  *Tugas Eksekusi:* Lakukan terminasi terhadap PID parent. Amati siapa yang mereap child process setelah parent-nya mati. (Gunakan `pstree` atau periksa kembali tabel proses).

### Lab 3: Challenge — Menemukan Process Resource Hogger Menggunakan CLI Native
*Skenario:* Sebuah load simulator liar berjalan di sistem Anda dan menghabiskan resource CPU melalui context switching. Anda tidak memiliki akses ke tool GUI atau dashboard cloud.

*Spesifikasi Tantangan:*
1.  Jalankan skrip reproduksi berikut untuk memicu thrashing:
    ```bash
    for i in $(seq 1 4); do while true; do :; done & done
    ```
2.  Identifikasi daftar PID loop tersebut secara tepat hanya dengan menggunakan `/proc` dan tool baris perintah dasar (`ps`, `pidstat`, atau `top -b -n 1`).
3.  Simpan PID-PID tersebut secara dinamis ke dalam sebuah environment variable bash.
4.  Ubah semua PID tersebut sekaligus agar memiliki nice priority minimum (+19) tanpa menghentikan layanannya.
5.  Lakukan terminasi terkontrol (`SIGTERM`) secara serentak pada semua proses tersebut dan validasi bahwa seluruh child background job telah bersih dari core CPU.

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

#### Soal 1:
Ketika syscall `fork()` dieksekusi oleh sebuah aplikasi C, apa yang dialokasikan oleh kernel secara instan untuk proses anak (*child process*) sebelum terjadi modifikasi memori?
*   A. Salinan fisik identik dari seluruh page RAM milik parent.
*   B. Struktur data `task_struct`, alokasi PID baru, dan duplikasi page tables yang mengarah ke physical page yang sama dengan atribut Read-Only.
*   C. Swap space sementara berukuran sama dengan Virtual Memory Size (VSZ) dari parent.
*   D. Ruang heap terpisah yang langsung dialokasikan pada memory zone HIGHMEM.

#### Soal 2:
Jika sebuah task di kernel Linux mengalami pergeseran nilai *nice* dari `0` menjadi `-5`, apa implikasi matematisnya terhadap nilai `vruntime` task tersebut di mata Completely Fair Scheduler (CFS)?
*   A. `vruntime` akan langsung direset menjadi nol untuk menjamin task dieksekusi seketika.
*   B. `vruntime` akan meningkat dengan laju yang jauh lebih cepat dibanding task bernilai nice 0 untuk durasi run-time yang sama.
*   C. Bobot task ($W_p$) membesar, sehingga untuk durasi run-time fisik CPU yang sama, `vruntime` task tersebut bertambah dengan laju yang lebih lambat.
*   D. Node task pada RB-tree CFS akan dipindahkan ke node paling kanan (*rightmost*).

#### Soal 3:
Server web menunjukkan penurunan performa drastis. Saat perintah `ps -eo state` dijalankan, terdapat 45 proses berstatus `D`. Langkah diagnostik pertama apa yang paling tepat untuk mengisolasi penyebab tanpa memicu kernel crash?
*   A. Menjalankan perintah `killall -9` pada seluruh proses berstatus D.
*   B. Membaca pseudo-file `/proc/<PID>/stack` dari beberapa PID yang bermasalah untuk mengidentifikasi fungsi kernel yang memblokir I/O execution path.
*   C. Melakukan *echo 3 > /proc/sys/vm/drop_caches* untuk memaksa pelepasan buffer I/O disk.
*   D. Menjalankan `renice -20` pada proses status D tersebut agar penjadwal memprioritaskannya.

#### Soal 4:
Apa perbedaan mendasar antara implementasi context switch *voluntary* dan *involuntary* yang dilaporkan oleh perintah `pidstat -w`?
*   A. Voluntary terjadi saat task menunggu resource I/O atau memanggil `sched_yield()`, sedangkan involuntary terjadi saat kuantum waktu CFS habis atau task di-preempt oleh task berprioritas lebih tinggi.
*   B. Voluntary terjadi karena sinyal `SIGKILL`, involuntary karena alokasi memori gagal (*OOM*).
*   C. Voluntary hanya terjadi pada thread kernel, sedangkan involuntary hanya terjadi pada user process.
*   D. Voluntary terjadi akibat instruksi CPU invalid, sedangkan involuntary terjadi akibat kegagalan page fault.

#### Soal 5:
Mengapa Zombie Process (`EXIT_ZOMBIE`) tidak dapat dieliminasi secara langsung menggunakan perintah `kill -9 <ZOMBIE_PID>`?
*   A. Karena sinyal `SIGKILL` membutuhkan akses root privilege khusus via *sudo*.
*   B. Karena proses tersebut memiliki status proteksi SELinux yang mengisolasi namespace sinyal.
*   C. Karena proses tersebut sebenarnya sudah mati; tidak ada context eksekusi atau thread loop yang tersisa untuk menangani sinyal POSIX.
*   D. Karena zombie process berada dalam pengelolaan subsistem memory swap kernel.

---

### Kunci Jawaban & Rasional Penilaian:

1.  **Jawaban: B**
    *   *Rasional:* Linux mengimplementasikan mekanisme Copy-On-Write (COW). Kernel tidak menyalin physical frame secara naif, melainkan menyalin *page tables* dan menandai referensi page sebagai Read-Only. Alokasi memori fisik baru hanya terjadi saat ada operasi penulisan (*write fault*).
2.  **Jawaban: C**
    *   *Rasional:* Formula CFS adalah $\Delta vruntime = \Delta exec\_time \times (1024 / W_p)$. Nilai nice yang lebih rendah (-5) menaikkan nilai bobot $W_p$. Akibatnya, nilai pembagi membesar, kenaikan `vruntime` melambat, dan proses bertahan lebih lama di sisi kiri RB-tree (mendapatkan alokasi CPU lebih banyak).
3.  **Jawaban: B**
    *   *Rasional:* Status D (*TASK_UNINTERRUPTIBLE*) berarti proses sedang menunggu di kernel-space (biasanya driver I/O, storage, atau network socket). Membaca `/proc/<PID>/stack` akan langsung membuka call stack kernel fungsi blocking tersebut secara non-destruktif. Opsi A keliru karena proses berstatus D kebal terhadap `SIGKILL`.
4.  **Jawaban: A**
    *   *Rasional:* *Voluntary switch* diprakarsai oleh task itu sendiri (misal: memanggil `read()` pada socket kosong), sedangkan *involuntary switch* dipaksakan oleh kernel CFS karena time slice berakhir atau ada task berprioritas lebih tinggi yang siap jalan.
5.  **Jawaban: C**
    *   *Rasional:* Proses zombie hanyalah sisa entri di Process Table. Kode program dan resource-nya sudah dihapus oleh `do_exit()`. Anda tidak bisa "membunuh" sesuatu yang sudah mati. Zombie hanya hilang jika parent-nya membaca status keluaran via `wait4()` atau jika parent-nya dibunuh sehingga diadopsi oleh init process (PID 1).

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

1.  **Buku Standard Industri:**
    *   *Linux Kernel Development (3rd Edition)* oleh Robert Love — Bab 3: "Process Management" dan Bab 4: "Process Scheduling".
    *   *Understanding the Linux Kernel (3rd Edition)* oleh Daniel P. Bovet & Marco Cesati — Bab 3: "Processes".
    *   *Systems Performance: Enterprise and the Cloud (2nd Edition)* oleh Brendan Gregg — Bab 6: "CPUs".
2.  **Dokumentasi Resmi Linux Kernel:**
    *   `Documentation/scheduler/sched-design-CFS.rst` (Kernel Source Code Documentation).
    *   `Documentation/filesystems/proc.rst` (Spesifikasi file-file di `/proc`).
3.  **Linux Man Pages:**
    *   `man 2 fork`, `man 2 clone`, `man 2 execve` (System Calls Interface).
    *   `man 2 waitpid`, `man 7 sched` (Scheduling APIs).
    *   `man 5 proc` (Format struktur data `/proc`).

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

*   Di kernel Linux, tidak ada perbedaan representasi biner fundamental antara proses dan thread; keduanya direpresentasikan sebagai entitas `task_struct`.
*   Pembuatan proses melalui `fork()` mengandalkan mekanisme **Copy-On-Write (COW)** untuk efisiensi instansiasi memori, di mana pemisahan physical page hanya terjadi ketika ada aksi penulisan data.
*   Siklus hidup proses mencakup state: `TASK_RUNNING` (R), `TASK_INTERRUPTIBLE` (S), `TASK_UNINTERRUPTIBLE` (D), `TASK_STOPPED` (T), dan `EXIT_ZOMBIE` (Z).
*   **Completely Fair Scheduler (CFS)** mendistribusikan waktu komputasi menggunakan metrik `vruntime` yang diindeks dalam struktur data **Red-Black Tree**. Task dengan `vruntime` terendah di sisi leftmost tree selalu dipilih untuk dieksekusi berikutnya.
*   Nilai prioritas *nice* (-20 hingga +19) memodifikasi pembobotan matematis pada penambahan `vruntime`, di mana nilai negatif memperlambat kenaikan `vruntime` sehingga task mendapatkan porsi CPU lebih besar.
*   Task dalam status `TASK_UNINTERRUPTIBLE` (D-state) berkontribusi langsung pada perhitungan metrik **Load Average** sistem operasi, meskipun utilitas CPU berada di angka 0%.
*   Zombie process tidak memakan memori fisik atau siklus CPU, melainkan menahan entri pada Process Table kernel yang berisiko menyebabkan *PID exhaustion*.

---

## SEKSI 17 — GLOSARIUM

1.  **`task_struct`:** Struktur data C di kernel Linux yang bertindak sebagai Process Control Block (PCB), menyimpan seluruh metadata yang berkaitan dengan proses atau thread.
2.  **Copy-On-Write (COW):** Pola optimasi memori di mana alokasi duplikasi data aktual ditunda sampai saat terjadinya modifikasi/penulisan pertama pada memori tersebut.
3.  **CFS (Completely Fair Scheduler):** Algoritma penjadwal CPU bawaan (default) kernel Linux untuk task non-real-time yang meniru ideal pipeline "perfect multitasking hardware".
4.  **`vruntime` (Virtual Runtime):** Metrik penghitungan CFS dalam satuan nanodetik yang merefleksikan seberapa banyak eksekusi CPU yang telah dinikmati oleh task, dinormalisasi dengan bobot nilai prioritasnya.
5.  **Red-Black Tree:** Pohon biner pencarian seimbang (*self-balancing binary search tree*) yang digunakan oleh CFS untuk mengurutkan runnable tasks berdasarkan `vruntime` dengan kompleksitas mutasi $O(\log N)$.
6.  **Load Average:** Rata-rata jumlah task yang berada dalam status `TASK_RUNNING` (R) ditambah task dalam status `TASK_UNINTERRUPTIBLE` (D) selama rentang waktu 1, 5, dan 15 menit.
7.  **D-State (`TASK_UNINTERRUPTIBLE`):** Status tidur proses yang tidak merespons sinyal perangkat lunak karena sedang menunggu event perangkat keras/driver subsistem kernel yang sifatnya sinkron.
8.  **Zombie Process (`EXIT_ZOMBIE`):** Status transisi task yang telah berhenti beroperasi namun entri `task_struct`-nya belum dibersihkan dari Process Table oleh sistem karena proses parent belum memanggil fungsi `wait()`.
9.  **Context Switching:** Prosedur kernel dalam menyimpan status CPU register suatu task yang sedang berjalan dan me-restore register task lain ke dalam CPU core untuk dieksekusi.
10. **Reaping:** Tindakan proses parent membaca status keluar (*exit code*) proses anak melalui syscall `waitpid()`/`wait4()`, yang memicu kernel untuk membersihkan entri `task_struct` child tersebut.
11. **TGID (Thread Group ID):** Identifier kernel yang merepresentasikan ID proses utama yang menaungi sekelompok thread (identik dengan PID di level user space).
12. **Nice Value:** Parameter ruang pengguna (-20 sampai +19) yang digunakan untuk memetakan bobot prioritas task di dalam kalkulasi CFS.

---

## SEKSI 18 — CATATAN INSTRUKTUR

*   **Poin Penekanan Materi:**
    *   Sangat penting untuk meluruskan miskonsepsi peserta didik terkait *Load Average*. Banyak engineer pemula mengira Load Average tinggi otomatis CPU overload. Gunakan Lab 1 & Skenario D-State di Seksi 09 untuk mendemonstrasikan bahwa storage yang rusak/macet dapat menaikkan Load Average hingga ratusan tanpa adanya beban CPU.
    *   Tekankan bahwa `kill -9` adalah tindakan kasar yang merusak integritas state aplikasi (bypass file cache flush, bypass exit handlers). Ajarkan selalu alur: `SIGTERM` $\to$ tunggu $\to$ `SIGKILL`.
*   **Jebakan Umum Peserta Saat Lab:**
    *   Saat lab simulasi zombie, banyak peserta mencoba mematikan proses zombie berulang kali dengan `kill -9 <child_pid>` dan berasumsi sistem mereka rusak karena PID tidak hilang. Arahkan mereka untuk melihat PPID-nya dan mematikan parent process-nya.
    *   Peserta sering bingung membedakan antara field PID dan TID saat menggunakan `ps -eLf` atau `top -H`. Jelaskan kembali konsep TGID vs PID di kernel level.
*   **Setup Lingkungan:**
    *   Pastikan lab environment menggunakan Linux native (Ubuntu 22.04 LTS / Rocky Linux 9 / Debian 12).
    *   Hindari menjalankan lab penjadwalan CPU di atas WSL1 (Windows Subsystem for Linux 1) karena arsitektur kernel emulasinya tidak memiliki CFS dan `/proc` yang representatif. WSL2 diperbolehkan karena berjalan di atas virtual machine Linux kernel utuh.

---

## SEKSI 19 — CHANGELOG & VERSI

*   **Versi 1.0.0 (Tanggal Pembuatan):**
    *   Rilis awal materi kurikulum sesuai standar panduan GEMINI.md.
    *   Cakupan komprehensif lifecycle proses, struktur `task_struct`, algoritma penjadwal CFS, bedah kasus D-state, serta set hands-on laboratory tingkat lanjut.

---

## SEKSI 20 — NAVIGASI KURIKULUM

*   **Modul Sebelumnya:** `LIN-01-03-02` (Arsitektur Filesystem Linux: VFS, Inodes, dan Mounting)
*   **Modul Saat Ini:** `LIN-01-04-01` (Arsitektur Proses Linux: Lifecycle, Struktur Kernel (`task_struct`), dan Penjadwalan CFS)
*   **Modul Berikutnya:** `LIN-01-04-02` (Manajemen Thread, Inter-Process Communication (IPC), Signals, dan POSIX Semaphores)
*   **Relasi Jalur Belajar:** Fondasi utama untuk melangkah ke modul *02-Systems-Engineering* (Cgroups, Namespaces, Containerization Internals) dan *03-Performance-Tuning* (eBPF, Perf profiling, Kernel Latency Tracing).