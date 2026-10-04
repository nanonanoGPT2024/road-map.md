## SEKSI 01 — IDENTITAS MODUL

* **Kode Modul**: LIN-CORE-0601
* **Nama Modul**: Jaringan Sistem Operasi, Arsitektur Socket, dan TCP/IP Stack
* **Kategori**: 01-Core-Foundations
* **Tingkat Kesulitan**: Tingkat Menengah hingga Lanjutan (Intermediate to Advanced)
* **Prasyarat**:
  * Pemahaman arsitektur kernel Linux dasar (System Calls, Interrupts, VFS).
  * Pemrograman C dasar (Pointer, Memory Management, File Descriptors).
  * Dasar-dasar protokol jaringan (OSI Layer, konsep port, IP addressing, TCP 3-Way Handshake).
* **Estimasi Waktu Penyelesaian**: 8 – 10 Jam Pembelajaran Mandiri / Hands-on Lab
* **Target Audience**: Systems Engineers, DevOps/SRE, Network Software Engineers, Linux Kernel Enthusiasts.

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

1. **Menganalisis Siklus Hidup Paket Jaringan (Packet Ingress/Egress Path)**: Menguraikan alur data secara mendalam dari Network Interface Controller (NIC), Direct Memory Access (DMA), Ring Buffer (RX/TX), Hard IRQ, NAPI subsystem, SoftIRQ (`NET_RX_SOFTIRQ`), routing subsystem, hingga ke transport layer.
2. **Membedah Struktur Data Inti Kernel**: Menjelaskan struktur internal kernel Linux yang merepresentasikan soket dan buffer paket, khususnya `struct sk_buff` (skb), `struct sock`, dan `struct socket`, serta bagaimana abstraksi VFS mengintegrasikan soket sebagai file descriptor.
3. **Mengoperasikan & Mengoptimalkan Socket Lifecycle**: Menjelaskan implementasi level sistem dari rangkaian system call BSD Socket (`socket()`, `bind()`, `listen()`, `accept()`, `connect()`, `send()`, `recv()`) beserta manajemen antrean kernel (`SYN Queue` dan `Accept Queue`).
4. **Mendiagnosis Kemacetan Jaringan (Network Bottlenecks)**: Mengidentifikasi paket drop, buffer overruns, dan TCP state anomalies menggunakan perangkat diagnostik modern (`ss`, `ip`, `ethtool`, `bpftrace`, `/proc/net/`).
5. **Mengimplementasikan I/O Multiplexing Berskala Tinggi**: Membandingkan model eksekusi I/O (`blocking`, `non-blocking`, `select/poll`, `epoll`) dan mengimplementasikan arsitektur socket non-blocking berbasis edge-triggered/level-triggered.

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```text
                     [ Perangkat Keras Jaringan (NIC) ]
                                    │
                                    ▼ (DMA Transfer)
                    [ Ring Buffer Perangkat Keras (RX) ]
                                    │
                           Hard IRQ (MSI-X/Legacy)
                                    │
                                    ▼
                      [ Linux NAPI (Poll Engine) ]
                                    │
                         NET_RX_SOFTIRQ (ksoftirqd)
                                    │
                                    ▼
       [ Alokasi & Konstruksi SKB: struct sk_buff ]
                                    │
                                    ▼
                       [ Layer 2: Driver & Netdevice ]
                        - eth_type_trans()
                                    │
                                    ▼
                        [ Layer 3: IP Processing ]
                        - ip_rcv() -> ip_route_input()
                        - Netfilter / iptables / nftables hooks
                                    │
                                    ▼
                      [ Layer 4: Protocol Demux ]
                        - tcp_v4_rcv() / udp_rcv()
                                    │
              ┌─────────────────────┴─────────────────────┐
              ▼                                           ▼
       [ In-flight TCP Logic ]                    [ Connection Setup ]
       - Sequence validation                      - SYN Queue (半连接)
       - Sliding window / Congestion              - Accept Queue (全连接)
       - sk_receive_queue (rmem)                          │
              │                                           │
              └─────────────────────┬─────────────────────┘
                                    │
                                    ▼
                [ Socket VFS Layer: struct socket / sock ]
                                    │
               System Calls: read(), recv(), epoll_wait()
                                    │
                                    ▼
                         [ Ruang Pengguna (User-Space) ]
```

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

Pada sistem Linux modern berkinerja tinggi, degradasi performa jarang disebabkan oleh keterbatasan CPU murni, melainkan ketidakefisienan I/O subsistem dan miskonfigurasi TCP/IP stack kernel.

1. **Skalabilitas Ekstrem**: Membangun layanan mikro (microservices), gateway proxy, atau basis data terdistribusi yang menangani jutaan koneksi simultan (masalah C10K hingga C10M) menuntut pemahaman konkret tentang konsumsi memori per soket, alokasi `sk_buff`, dan model event multiplexing berbasis kernel.
2. **Diagnostik Tingkat Lanjut**: Saat terjadi latensi tinggi atau packet drop acak, pengembang yang hanya memahami socket API tingkat tinggi akan gagal mengidentifikasi masalah seperti *SYN backlog exhaustion*, *epoll starvation*, *softirq skewing*, atau saturasi *driver ring buffer*.
3. **Optimasi Berbasis Hardware-Software Co-Design**: Konvergensi kartu jaringan berkecepatan 25G/40G/100G menuntut rekayasa tingkat lanjut: pemetaan interupsi multi-queue (RSS), kernel bypass (XDP/DPDK), dan tuning TCP window buffers berbasis BDP (Bandwidth-Delay Product).

---

## SEKSI 05 — APA ITU (WHAT)

### 1. Abstraksi Soket dan VFS
Di Linux, soket jaringan diabstraksikan melalui paradigma Unix: *"Everything is a file"*. Akan tetapi, terdapat lapisan diferensiasi internal yang ketat:
* **`struct file`**: Abstraksi Virtual File System (VFS) standar yang memegang file descriptor (fd) untuk ruang pengguna.
* **`struct socket`**: Titik tumpu VFS untuk antarmuka jaringan (BSD socket abstraction). Struktur ini mengelola status soket tingkat atas dan memiliki pointer langsung ke operasi `proto_ops`.
* **`struct sock` (inet_sock, tcp_sock)**: Struktur data internal kernel networking yang menangani status protokol independen dan dependen (seperti state machine TCP, sliding window buffers, timers, congestion control).

### 2. Struktur `sk_buff` (Socket Buffer)
`sk_buff` adalah struktur data paling mendasar dan kompleks dalam subsistem jaringan Linux. Ia merepresentasikan paket jaringan tunggal di seluruh siklus hidupnya (mulai dari parsing header Ethernet hingga didekode di transport layer).
* Menggunakan pointer manipulasi cerdas (`head`, `data`, `tail`, `end`) untuk mencegah overhead alokasi memori berulang (*zero-copy header prepend/strip*).
* Menangani payload data aktual di memori terpisah, sementara metadata paket dikemas di dalam deskriptor `sk_buff`.

### 3. TCP/IP Stack Kernel
Implementasi modular monolitik di dalam kernel yang bertindak sebagai mesin transisi state teroptimasi secara asinkron. Mengimplementasikan RFC 793, RFC 5681, dan lusinan standar lainnya, mencakup algoritma congestion control terkonfigurasi (CUBIC, BBR, Reno) dan mitigasi serangan otomatis (SYN Cookies).

---

## SEKSI 06 — BAGAIMANA CARA KERJA (HOW)

### 1. Ingress Packet Path (Dari Kabel ke Aplikasi)
Proses penanganan paket dari media fisik hingga ke user-space berlangsung sebagai berikut:

```
[Kabel/Fiber] 
     │
     ▼
[NIC Hardware Layer]
     ├── 1. Menerima sinyal elektrik/optik dan memvalidasi Frame Check Sequence (FCS/CRC).
     └── 2. Mengalirkan frame via DMA (Direct Memory Access) ke Circular Ring Buffer (RX) host memory.
     │
     ▼
[Hard IRQ Phase]
     ├── 3. NIC menembakkan hardware interrupt (MSI-X) ke Core CPU tertentu.
     ├── 4. Kernel menangani interrupt, mematikan interupsi pada antrean tersebut (interrupt mitigation).
     └── 5. Driver menjadwalkan siklus NAPI (New API) via bit flag NET_RX_SOFTIRQ pada CPU lokal.
     │
     ▼
[SoftIRQ Phase (NAPI & ksoftirqd)]
     ├── 6. Scheduler memicu `napi_poll()` dalam konteks perangkat lunak (`ksoftirqd/x`).
     ├── 7. Driver mengalokasikan deskriptor `struct sk_buff` dan mereferensikan memori RX.
     └── 8. Driver mengeksekusi `napi_gro_receive()` (Generic Receive Offload) untuk memaketkan paket.
     │
     ▼
[Layer 2 & Layer 3 Stack]
     ├── 9. Kernel memanggil `__netif_receive_skb()` -> mengidentifikasi protokol Layer 3 via packet type handler.
     ├── 10. `ip_rcv()` dipanggil untuk protokol IPv4:
     │        - Validasi checksum IP header.
     │        - Netfilter PREROUTING hook dieksekusi (iptables/nftables).
     └── 11. `ip_route_input_noref()` menentukan apakah paket ditujukan untuk host lokal (Local Delivery) atau di-forward.
     │
     ▼
[Layer 4 Stack]
     ├── 12. Netfilter LOCAL_IN hook dieksekusi.
     ├── 13. `tcp_v4_rcv()` memvalidasi paket TCP:
     │        - Melakukan pencarian soket (hash lookup 4-tuple: SRC_IP, SRC_PORT, DST_IP, DST_PORT).
     │        - Menjalankan TCP state machine (validasi sequence number, ACK flags, window size).
     └── 14. Data dimasukkan ke dalam `sk_receive_queue` milik target `struct sock`.
     │
     ▼
[User-Space Delivery]
     ├── 15. Kernel membangunkan proses yang tidur di `epoll_wait()`, `select()`, atau thread pemanggil blocking `read()`.
     └── 16. System call `read()` atau `recv()` menyalin data dari kernel-space (`sk_buff`) ke buffer memori user-space.
```

### 2. Antrean TCP: SYN Queue vs Accept Queue
Saat proses server memanggil `listen(sockfd, backlog)`:
* **SYN Queue (Incomplete Connection Queue)**:
  * Menyimpan state koneksi saat klien mengirim `SYN` (state: `SYN_RECV`).
  * Kernel merespons dengan `SYN-ACK`.
  * Ukuran dibatasi oleh `net.ipv4.tcp_max_syn_backlog`.
  * Jika diserang SYN Flood dan antrean penuh, kernel dapat berpindah ke mekanisme stateless `tcp_syncookies`.
* **Accept Queue (Completed Connection Queue)**:
  * Berisi koneksi yang telah menyelesaikan proses 3-Way Handshake (menerima final `ACK`, state: `ESTABLISHED`).
  * Koneksi berada di antrean ini hingga proses memanggil system call `accept()`.
  * Ukurannya dibatasi oleh nilai minimum antara argumen `backlog` pada `listen()` dan sysctl `net.core.somaxconn`.

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

### 1. Struktur Memori `struct sk_buff`

```text
    sk_buff (Header / Metadata)
   ┌───────────────────────────┐
   │ next / prev (Pointers)    │
   │ dev (net_device struct)   │
   │ len / data_len            │
   │ transport_header (offset) │
   │ network_header   (offset) │
   │ mac_header       (offset) │
   │ head ─────────────────────┼────────┐
   │ data ─────────────────────┼──┐     │
   │ tail ─────────────────────┼──┼──┐  │
   │ end  ─────────────────────┼──┼──┼──┼────────┐
   └───────────────────────────┘  │  │  │        │
                                  │  │  │        │
    Linear Packet Memory Data     │  │  │        │
   ┌───────────────────────────┐◄─┘  │  │        │
   │ Headroom (Kosong)         │     │  │        │
   │ (Untuk prepending headers)│     │  │        │
   ├───────────────────────────┤◄────┘  │        │
   │ Layer 2 (Ethernet Header) │        │        │
   ├───────────────────────────┤        │        │
   │ Layer 3 (IP Header)       │        │        │
   ├───────────────────────────┤        │        │
   │ Layer 4 (TCP/UDP Header)  │        │        │
   ├───────────────────────────┤        │        │
   │ Payload (Data Pengguna)   │        │        │
   ├───────────────────────────┤◄───────┘        │
   │ Tailroom (Kosong)         │                 │
   │ (Untuk appending data)    │                 │
   ├───────────────────────────┤◄────────────────┘
   │ struct skb_shared_info    │
   │ (Pointers ke paged frags) │
   └───────────────────────────┘
```

### 2. State Machine TCP Connection Handshake & Queues

```text
       KLIEN (Client)                                    SERVER (Kernel Space)
             │                                                     │
             │                     LISTEN State                    │ listen(fd, backlog)
             │                                                     │
             │               SYN Packet                            │
             ├────────────────────────────────────────────────────►│
             │                                                     │ [Ditaruh ke SYN Queue]
             │                                                     │ (State: SYN_RECV)
             │             SYN-ACK Packet                          │
             │◄────────────────────────────────────────────────────┤
             │                                                     │
             │               ACK Packet                            │
             ├────────────────────────────────────────────────────►│
             │                                                     │ [Dipindah ke Accept Queue]
             │                                                     │ (State: ESTABLISHED)
             │                                                     │
             │                                                     │ accept(fd) dieksekusi
             │                                                     ▼
      ESTABLISHED State                                      ESTABLISHED State
                                                        (Aplikasi menerima Client FD)
```

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

Berikut adalah implementasi TCP Echo Server sederhana di C menggunakan Socket API standar (Blocking I/O) untuk mendemonstrasikan abstraksi fundamental:

```c
/* simple_tcp_server.c */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <arpa/inet.h>
#include <sys/socket.h>

#define PORT 8080
#define BUFFER_SIZE 1024

int main() {
    int server_fd, client_fd;
    struct sockaddr_in address;
    int opt = 1;
    socklen_t addrlen = sizeof(address);
    char buffer[BUFFER_SIZE] = {0};

    // 1. Inisialisasi Socket (Domain: AF_INET, Tipe: SOCK_STREAM/TCP)
    if ((server_fd = socket(AF_INET, SOCK_STREAM, 0)) < 0) {
        perror("Gagal membuat socket()");
        exit(EXIT_FAILURE);
    }

    // 2. Set Sockopt untuk penggunaan ulang alamat/port secara cepat
    if (setsockopt(server_fd, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt))) {
        perror("setsockopt SO_REUSEADDR gagal");
        close(server_fd);
        exit(EXIT_FAILURE);
    }

    address.sin_family = AF_INET;
    address.sin_addr.s_addr = INADDR_ANY; // Bind ke 0.0.0.0
    address.sin_port = htons(PORT);

    // 3. Bind socket ke alamat IP dan Port
    if (bind(server_fd, (struct sockaddr *)&address, sizeof(address)) < 0) {
        perror("bind() gagal");
        close(server_fd);
        exit(EXIT_FAILURE);
    }

    // 4. Masuk ke mode passive listening; alokasikan SYN & Accept Queue
    // 128 adalah backlog hint untuk Accept Queue
    if (listen(server_fd, 128) < 0) {
        perror("listen() gagal");
        close(server_fd);
        exit(EXIT_FAILURE);
    }
    printf("[*] Listening pada port %d...\n", PORT);

    // 5. Blokir eksekusi hingga koneksi baru tiba di Accept Queue
    if ((client_fd = accept(server_fd, (struct sockaddr *)&address, &addrlen)) < 0) {
        perror("accept() gagal");
        close(server_fd);
        exit(EXIT_FAILURE);
    }
    printf("[+] Koneksi diterima dari: %s:%d\n", 
           inet_ntoa(address.sin_addr), ntohs(address.sin_port));

    // 6. Baca data yang masuk ke sk_receive_queue
    ssize_t valread = read(client_fd, buffer, BUFFER_SIZE - 1);
    if (valread > 0) {
        printf("[>] Menerima pesan: %s\n", buffer);
        // Echo balik data ke klien
        write(client_fd, buffer, valread);
    }

    // 7. Terminasi koneksi (mengirimkan FIN segment)
    close(client_fd);
    close(server_fd);
    return 0;
}
```

*Kompilasi dan Jalankan:*
```bash
gcc -Wall -Wextra -O2 simple_tcp_server.c -o simple_tcp_server
./simple_tcp_server
```

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

Dalam skenario produksi dunia nyata, model satu thread per soket (*blocking*) akan gagal total pada konkurensi tinggi. Berikut adalah implementasi server berbasis non-blocking I/O menggunakan Linux kernel-native **`epoll` (Edge-Triggered)**.

```c
/* epoll_server.c */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <errno.h>
#include <sys/epoll.h>
#include <netinet/in.h>
#include <sys/socket.h>

#define MAX_EVENTS 64
#define BUFFER_SIZE 512
#define PORT 9000

// Helper function untuk mengubah socket menjadi non-blocking
static int set_nonblocking(int fd) {
    int flags = fcntl(fd, F_GETFL, 0);
    if (flags == -1) return -1;
    return fcntl(fd, F_SETFL, flags | O_NONBLOCK);
}

int main() {
    int listen_fd, epoll_fd;
    struct sockaddr_in server_addr;
    struct epoll_event ev, events[MAX_EVENTS];

    if ((listen_fd = socket(AF_INET, SOCK_STREAM, 0)) < 0) {
        perror("socket");
        exit(EXIT_FAILURE);
    }

    int opt = 1;
    setsockopt(listen_fd, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt));

    memset(&server_addr, 0, sizeof(server_addr));
    server_addr.sin_family = AF_INET;
    server_addr.sin_addr.s_addr = htonl(INADDR_ANY);
    server_addr.sin_port = htons(PORT);

    if (bind(listen_fd, (struct sockaddr *)&server_addr, sizeof(server_addr)) < 0) {
        perror("bind");
        exit(EXIT_FAILURE);
    }

    if (set_nonblocking(listen_fd) < 0) {
        perror("set_nonblocking listen_fd");
        exit(EXIT_FAILURE);
    }

    if (listen(listen_fd, 1024) < 0) {
        perror("listen");
        exit(EXIT_FAILURE);
    }

    // Inisialisasi instance epoll kernel
    if ((epoll_fd = epoll_create1(0)) < 0) {
        perror("epoll_create1");
        exit(EXIT_FAILURE);
    }

    // Register listen_fd dengan mode Edge-Triggered (EPOLLET)
    ev.events = EPOLLIN | EPOLLET;
    ev.data.fd = listen_fd;
    if (epoll_ctl(epoll_fd, EPOLL_CTL_ADD, listen_fd, &ev) < 0) {
        perror("epoll_ctl listen_fd");
        exit(EXIT_FAILURE);
    }

    printf("[*] Edge-Triggered epoll server running pada port %d...\n", PORT);

    while (1) {
        int nfds = epoll_wait(epoll_fd, events, MAX_EVENTS, -1);
        if (nfds < 0) {
            if (errno == EINTR) continue;
            perror("epoll_wait");
            break;
        }

        for (int i = 0; i < nfds; i++) {
            if (events[i].data.fd == listen_fd) {
                // Ada koneksi masuk baru di Accept Queue
                // Loop accept() sampai habis karena menggunakan Edge-Triggered!
                while (1) {
                    struct sockaddr_in client_addr;
                    socklen_t client_len = sizeof(client_addr);
                    int conn_fd = accept(listen_fd, (struct sockaddr *)&client_addr, &client_len);
                    if (conn_fd < 0) {
                        if ((errno == EAGAIN) || (errno == EWOULDBLOCK)) {
                            // Seluruh koneksi tertunda sudah diproses
                            break;
                        }
                        perror("accept");
                        break;
                    }

                    if (set_nonblocking(conn_fd) < 0) {
                        perror("set_nonblocking conn_fd");
                        close(conn_fd);
                        continue;
                    }

                    ev.events = EPOLLIN | EPOLLET | EPOLLRDHUP;
                    ev.data.fd = conn_fd;
                    if (epoll_ctl(epoll_fd, EPOLL_CTL_ADD, conn_fd, &ev) < 0) {
                        perror("epoll_ctl conn_fd");
                        close(conn_fd);
                    }
                }
            } else {
                // Event IO pada client socket
                int client_fd = events[i].data.fd;

                if (events[i].events & (EPOLLRDHUP | EPOLLHUP | EPOLLERR)) {
                    epoll_ctl(epoll_fd, EPOLL_CTL_DEL, client_fd, NULL);
                    close(client_fd);
                    continue;
                }

                if (events[i].events & EPOLLIN) {
                    char buf[BUFFER_SIZE];
                    // Edge-Triggered mewajibkan kita membaca buffer kernel sampai tuntas (EAGAIN)
                    while (1) {
                        ssize_t bytes_read = read(client_fd, buf, sizeof(buf));
                        if (bytes_read > 0) {
                            // Menulis kembali data ke socket (echo)
                            write(client_fd, buf, bytes_read);
                        } else if (bytes_read == 0) {
                            // Klien menutup koneksi
                            epoll_ctl(epoll_fd, EPOLL_CTL_DEL, client_fd, NULL);
                            close(client_fd);
                            break;
                        } else {
                            if (errno == EAGAIN || errno == EWOULDBLOCK) {
                                // Buffer data selesai dibaca
                                break;
                            }
                            perror("read");
                            epoll_ctl(epoll_fd, EPOLL_CTL_DEL, client_fd, NULL);
                            close(client_fd);
                            break;
                        }
                    }
                }
            }
        }
    }

    close(listen_fd);
    close(epoll_fd);
    return 0;
}
```

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

| Pendekatan / Parameter | Opsi A | Opsi B | Trade-off / Implikasi Teknis |
| :--- | :--- | :--- | :--- |
| **Model Event I/O** | `select()` / `poll()` | `epoll()` (Linux) | `select/poll` memiliki kompleksitas algoritma $O(N)$ linear terhadap total file descriptor. `epoll` beroperasi secara $O(1)$ untuk trigger event karena mengandalkan implementasi kernel callback list dan red-black tree, tetapi tidak portabel di luar Linux (*non-POSIX*). |
| **Epoll Trigger Mode** | Level-Triggered (LT) | Edge-Triggered (ET) | **LT**: Lebih aman, akan terus menembakkan interrupt/wake-up jika data masih ada di kernel buffer. Resiko loop berlebih jika buffer tak segera dikonsumsi.<br>**ET**: Kinerja sangat tinggi, context switch minimal. Namun berisiko tinggi terjadi *deadlock/starvation* bila aplikasi gagal membaca tuntas seluruh paket hingga muncul `EAGAIN`. |
| **TCP Backlog Queue** | Ukuran Backlog Kecil | Ukuran Backlog Besar | Backlog kecil menyebabkan penolakan koneksi (*RST/drop*) di bawah lonjakan traffic (traffic spike). Backlog terlalu besar mengonsumsi memori kernel (`slab allocator`) dan meningkatkan latensi RTT koneksi baru (fenomena *bufferbloat*). |
| **TCP Congestion Control** | CUBIC (Loss-based) | BBR (Model-based) | **CUBIC**: Sangat agresif pada throughput di jaringan throughput-tinggi, tapi rentan salah deteksi loss pada link nirkabel/lossy sebagai tanda saturasi bandwidth.<br>**BBR**: Mengukur bottleneck bandwidth & RTT secara riil; menjaga latensi tetap rendah. Namun dapat memonopoli link terhadap stream yang berbasis loss-based. |

---

## SEKSI 11 — BEST PRACTICES

1. **Gunakan Nilai Somaxconn yang Relevan di Sysctl**:
   Pastikan nilai antrean listen di aplikasi selaras dengan parameter kernel. Ubah via `/etc/sysctl.conf`:
   ```bash
   net.core.somaxconn = 4096
   net.ipv4.tcp_max_syn_backlog = 8192
   ```
2. **Hindari TIME_WAIT Reuse yang Sembrono**:
   Jangan mengaktifkan `net.ipv4.tcp_tw_recycle` (dihapus sejak kernel 4.12 karena melanggar RFC pada NAT traversal). Gunakan `net.ipv4.tcp_tw_reuse = 1` secara spesifik hanya untuk outgoing connections.
3. **Konfigurasi Auto-Tuning TCP Buffer Berbasis BDP**:
   Biarkan Linux melakukan auto-tuning, tetapi naikkan batas maksimum untuk bandwidth gigabit:
   ```bash
   # Format: min default max (dalam bytes)
   net.ipv4.tcp_rmem = 4096 87380 16777216
   net.ipv4.tcp_wmem = 4096 65536 16777216
   ```
4. **Implementasikan CPU Affinity & RSS pada Kartu NIC**:
   Aktifkan *Receive Side Scaling* (RSS) dan pasang IRQ Affinity ke core CPU terisolasi menggunakan `smp_affinity` agar beban parsing `NET_RX_SOFTIRQ` terdistribusi merata, mencegah saturasi 100% pada satu core tunggal (`CPU0 bottleneck`).
5. **Gunakan `TCP_NODELAY` untuk Aplikasi Berlatensi Rendah**:
   Matikan Algoritma Nagle jika mengirimkan pesan-pesan kecil secara beruntun (misalnya format gRPC, JSON payload) untuk memangkas penundaan transfer data hingga 40ms:
   ```c
   int flag = 1;
   setsockopt(sock_fd, IPPROTO_TCP, TCP_NODELAY, (char *)&flag, sizeof(int));
   ```

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

1. **Mengabaikan Drain Loop pada Epoll Edge-Triggered (ET)**:
   *Gejala*: Socket berhenti menerima data setelah membaca batch pertama.
   *Akar Masalah*: Mode ET hanya mengirimkan notifikasi satu kali saat ada transisi state di hardware/buffer. Jika sistem membaca buffer dengan `read()` hanya sekali tanpa looping sampai mendapat nilai `EAGAIN` atau `EWOULDBLOCK`, sisa data tertahan selamanya di kernel buffer.
2. **Kekeliruan Mengartikan Nilai Send Buffer (`SO_SNDBUF`)**:
   *Gejala*: Aplikasi menghitung bahwa `setsockopt(..., SO_SNDBUF, 65536, ...)` berarti ia dapat menyimpan 65536 byte data mentah.
   *Akar Masalah*: Kernel menggandakan nilai ini (`2x`) untuk alokasi internal demi menampung struktur metadata `sk_buff`. Jangan memanipulasi ini secara manual kecuali jika sistem melarang tuning dinamis.
3. **Mengabaikan Status `TIME_WAIT`**:
   *Gejala*: Server crash dengan galat `EADDRINUSE` (Address already in use) saat proses di-restart secara cepat.
   *Akar Masalah*: Socket aktif yang menutup koneksi duluan masuk ke periode penahanan 2MSL (Maximum Segment Lifetime). Solusi: Selalu pasang flag `SO_REUSEADDR` pada listening server socket.
4. **Salah Membaca Output Perintah `ss`**:
   Pada perintah `ss -ltn` (Mode LISTEN):
   * Kolom **Recv-Q** BUKAN berarti jumlah data yang belum dibaca, melainkan **ukuran antrean koneksi di Accept Queue saat ini**.
   * Kolom **Send-Q** BUKAN berarti sisa buffer kirim, melainkan **nilai backlog maksimum yang diperbolehkan** untuk listener tersebut.

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Skenario
Sebuah layanan web API berbasis Nginx melaporkan adanya spike kegagalan koneksi (*connection reset/timeout*) saat peak traffic, meskipun konsumsi memori dan penggunaan agregat CPU host masih di bawah 40%. Anda ditugaskan menganalisis dan membuktikan apakah terjadi packet drops pada kernel queues.

### Langkah Kerja & Panduan Perintah

1. **Inspeksi Antrean Backlog Listen Saat Ini**:
   Jalankan inspeksi socket socket TCP yang sedang listen di sistem:
   ```bash
   ss -lnt '( sport = :80 or sport = :443 )'
   ```
   *Amati*: Apakah nilai `Recv-Q` mendekati atau setara dengan `Send-Q`? Jika ya, Accept Queue telah meluap (*overflow*).

2. **Cek Metrik Kernel Drop Akibat Listen Queue Overflow**:
   Periksa counter statistik TCP sistem dari `/proc/net/netstat`:
   ```bash
   netstat -s | grep -i "listen"
   # atau menggunakan nstat
   nstat -az TcpExtListenOverflows TcpExtListenDrops
   ```
   *Analisis*: Jika angka `TcpExtListenOverflows` bertambah secara real-time, soket gagal memanggil `accept()` secepat koneksi yang masuk.

3. **Verifikasi Ring Buffer Saturation pada Kartu NIC**:
   Periksa kapasitas buffer level hardware dan cek apakah terjadi drop di layer driver:
   ```bash
   # Melihat konfigurasi buffer saat ini vs kapasitas hardware
   ethtool -g eth0

   # Melihat statistik drop frame
   ethtool -S eth0 | grep -E "drop|miss|over|error"
   ```

4. **Tuning Kernel Runtime**:
   Naikkan parameter kernel untuk mengatasi overload tersebut seketika secara dinamis:
   ```bash
   sudo sysctl -w net.core.somaxconn=16384
   sudo sysctl -w net.ipv4.tcp_max_syn_backlog=16384
   sudo sysctl -w net.core.netdev_max_backlog=10000
   ```

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

1. Struktur data kernel apa yang secara langsung merepresentasikan satu frame/paket jaringan yang bergerak melintasi layer-layer TCP/IP di dalam Linux?
   * A. `struct sock`
   * B. `struct sk_buff`
   * C. `struct socket`
   * D. `struct net_device`
   * *Jawaban*: B. `struct sk_buff` (skb) melacak seluruh metadata, pointer data, dan offload properties sebuah paket dari L2 hingga L4.

2. Apa yang terjadi jika client menyelesaikan 3-Way Handshake (mengirim final ACK), tetapi proses server di user-space mengalami deadlock dan tidak pernah memanggil `accept()`?
   * A. Kernel mengirimkan paket RST ke client.
   * B. Koneksi tetap ditaruh di Accept Queue sampai batas backlog tercapai, kemudian paket ACK berikutnya diabaikan/didrop.
   * C. Sistem crash dengan Kernel Panic (*Out of Socket Memory*).
   * D. Koneksi otomatis dipindahkan kembali ke SYN Queue.
   * *Jawaban*: B. Koneksi tetap berstatus `ESTABLISHED` di kernel dan bertengger di Accept Queue. Jika queue penuh, perilaku kernel dikontrol oleh parameter `tcp_abort_on_overflow`.

3. Pada antarmuka `epoll` dengan mode **Edge-Triggered (ET)**, system call `read()` harus dilakukan secara berulang hingga mengembalikan error tertentu untuk mencegah hilangnya data. Error apakah itu?
   * A. `EINTR`
   * B. `EBADF`
   * C. `EAGAIN` atau `EWOULDBLOCK`
   * D. `ECONNRESET`
   * *Jawaban*: C. `EAGAIN` / `EWOULDBLOCK` mengindikasikan bahwa seluruh data yang ada pada antrean buffer socket kernel sudah terkuras habis.

4. Apa peran dari mekanisme **NAPI** (New API) di dalam subsistem penerimaan jaringan Linux?
   * A. Mengganti socket interface POSIX dengan API modern berbasis Rust.
   * B. Beralih dari interrupt-driven model ke polling-driven model saat volume paket tinggi untuk mencegah CPU live-lock.
   * C. Menghubungkan secara otomatis port hardware ke interface loopback.
   * D. Memodifikasi routing table secara asinkron tanpa locking.
   * *Jawaban*: B. NAPI mematikan hardware interrupt saat sistem sibuk dan mengeksekusi fungsi poll melalui ksoftirqd (`NET_RX_SOFTIRQ`), menghemat jutaan siklus interrupt CPU.

5. Jika file descriptor soket ditutup menggunakan `close()`, TCP state apa yang akan dimasuki oleh inisiator penutupan tersebut pertama kali?
   * A. `CLOSE_WAIT`
   * B. `LAST_ACK`
   * C. `FIN_WAIT_1`
   * D. `CLOSING`
   * *Jawaban*: C. Endpoint yang menginisiasi *active close* mengirimkan segment `FIN` dan langsung masuk ke state `FIN_WAIT_1`.

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

* **Dokumentasi Resmi & Kernel Tree**:
  * Linux Kernel Networking Documentation (`Documentation/networking/`)
  * `man 7 socket`, `man 7 tcp`, `man 7 ip`, `man 2 epoll_create1`
* **Buku Fundamental**:
  * *"Understanding Linux Network Internals"* oleh Christian Benvenuti (O'Reilly).
  * *"The Linux Programming Interface"* (Bab 56-61: Sockets) oleh Michael Kerrisk.
  * *"Systems Performance: Enterprise and the Cloud, 2nd Edition"* oleh Brendan Gregg.
* **Makalah & Resource Teknis**:
  * RFC 793 (Transmission Control Protocol Specification).
  * RFC 7323 (TCP Extensions for High Performance).
  * *"Monitoring and Tuning the Linux Networking Stack: Receiving Data"* (Packagecloud Deep Dive Series).

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

1. Paket jaringan masuk via **NIC**, ditransfer ke memori oleh **DMA**, membangkitkan **Hard IRQ**, yang kemudian mengalihkan pekerjaan pemrosesan ke **NAPI SoftIRQ** demi menghindari *interrupt storm*.
2. Seluruh payload dan layer header dipaketkan di kernel dalam struktur data serbaguna berorientasi pointer yang disebut **`struct sk_buff`**.
3. Hubungan antara sistem operasi dan aplikasi dihubungkan oleh VFS: file descriptor merujuk ke **`struct socket`** (lapisan BSD), yang membungkus **`struct sock`** (lapisan implementasi TCP/IP).
4. Penanganan inisiasi koneksi dibagi menjadi dua gerbang: **SYN Queue** (koneksi setengah terbuka / *half-open*) dan **Accept Queue** (koneksi *established* yang siap di-consume aplikasi).
5. Arsitektur I/O modern mengandalkan kernel notification mechanisms seperti **`epoll`** dengan mode Edge-Triggered untuk meminimalisir context-switching pada beban ratusan ribu koneksi konkuren.

---

## SEKSI 17 — GLOSARIUM

* **DMA (Direct Memory Access)**: Mekanisme hardware yang memungkinkan NIC mentransfer data paket langsung ke RAM sistem host tanpa membebani komputasi CPU inti.
* **Hard IRQ (Hardware Interrupt)**: Sinyal hardware dari controller NIC ke CPU fisik untuk mengindikasikan bahwa data telah berada di memory ring buffer.
* **NAPI (New API)**: Sub-framework dalam kernel Linux yang mengombinasikan mekanisme hardware interrupts dengan polling terjadwal untuk pemrosesan throughput paket skala masif.
* **SoftIRQ (`NET_RX_SOFTIRQ`)**: Interrupt level perangkat lunak yang dieksekusi oleh thread kernel `ksoftirqd` untuk melakukan parsing header IP/TCP secara asinkron.
* **`sk_buff` (Socket Buffer)**: Struktur data internal kernel Linux yang menyimpan metadata dan pointer fragment payload paket selama siklus pemrosesan network stack.
* **SYN Queue**: Antrean kernel yang menampung koneksi yang sedang dalam proses jabat tangan (*handshake*) 3 langkah TCP sebelum menerima status final ACK.
* **Accept Queue**: Antrean yang memegang koneksi yang telah berstatus `ESTABLISHED` dan menunggu aplikasi mengeksekusi system call `accept()`.
* **GRO (Generic Receive Offload)**: Optimasi software di level driver jaringan untuk menggabungkan paket-paket kecil yang berurutan menjadi satu deskriptor paket raksasa sebelum dioperasikan ke L3 stack.

---

## SEKSI 18 — CATATAN INSTRUKTUR

* **Poin Penekanan Materi**:
  * Pastikan siswa tidak tertukar antara fungsi **`struct socket`** (abstraksi file POSIX untuk user space) dan **`struct sock`** (state machine jaringan kernel sesungguhnya).
  * Tekankan demonstrasi perbedaan Level-Triggered (LT) vs Edge-Triggered (ET) pada `epoll`. Siswa kerap mengalami bug loop tak berujung (*infinite stall*) karena melupakan penanganan error `EAGAIN`.
* **Panduan Pengujian Lab**:
  * Gunakan tool injeksi beban traffic seperti `wrk` atau `iperf3` untuk mensimulasikan kehabisan Accept Backlog secara visual di metrik `ss -lnt`.
  * Tunjukkan bagaimana SoftIRQ membebani CPU dengan menjalankan `top` lalu menekan tombol `1` untuk melihat konsumsi metric `%si` (Software Interrupt).
* **Tips Troubleshooting Mahasiswa**:
  * Bila saat latihan `epoll_server.c` kompilasi gagal, pastikan kernel Linux yang digunakan mendukung `epoll_create1` (Kernel versi >= 2.6.27).

---

## SEKSI 19 — CHANGELOG & VERSI

* **Versi**: 1.0.0
* **Tanggal Rilis**: 2026-03-30
* **Penulis**: Tim Pengembang Kurikulum Rekayasa Sistem Linux
* **Catatan Perubahan**:
  * `v1.0.0` (2026-03-30): Inisialisasi rilis modul komprehensif 20 seksi: mencakup deep-dive path jaringan kernel, struktur `sk_buff`, arsitektur TCP queues, dan implementasi implementasi epoll Edge-Triggered.

---

## SEKSI 20 — NAVIGASI KURIKULUM

* **Modul Sebelumnya**: `LIN-CORE-0502`: Manajemen Memori Kernel, Virtual Memory, Paging, dan SLAB/SLUB Allocator
* **Modul Saat Ini**: `LIN-CORE-0601`: Jaringan Sistem Operasi, Arsitektur Socket, dan TCP/IP Stack
* **Modul Berikutnya**: `LIN-CORE-0602`: Network Device Drivers, Packet Scheduling (tc), dan Linux Netfilter Subsystem