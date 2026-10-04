## SEKSI 01 — IDENTITAS MODUL

* **Kurikulum:** Computer Science
* **Kategori:** 01-Core-Foundations
* **Bab:** 06 — Jaringan Komputer & Protokol Internet
* **Modul:** 01 — Arsitektur Jaringan, Protokol Layering (OSI & TCP/IP), dan Socket Programming
* **Kode Modul:** CS-CF-NET-0601
* **Tingkat Kesulitan:** Intermediate
* **Estimasi Waktu Penyelesaian:** 8–10 Jam Belajar Mandiri / Praktikum Terpandu
* **Prasyarat:** Pemrograman Sistem Dasar (C/C++ atau Python), Representasi Data Komputer (Biner, Heksadesimal, Endianness), Konsep Dasar Sistem Operasi (Proses, Thread, File Descriptor, I/O Interrupts).

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

1. **Menganalisis Arsitektur Layering:** Membedakan model 7-Layer OSI dan 4/5-Layer TCP/IP, serta melacak alur enkapsulasi/dekapsulasi data dari *Application Layer* hingga *Physical Layer*.
2. **Membedah Mekanisme Transport Layer:** Menjelaskan secara matematis dan logis cara kerja *TCP 3-Way Handshake*, *Connection Teardown*, *Flow Control* (Sliding Window), dan *Congestion Control* (Reno, Cubic, BBR) dibandingkan dengan sifat koneksi nir-status *UDP*.
3. **Mengidentifikasi Masalah Framing:** Mengimplementasikan teknik pemisahan pesan (*message framing*) pada stream berorientasi byte (TCP) untuk mencegah anomali *packet coalescing* dan *fragmentation*.
4. **Membangun Aplikasi Jaringan Berskala Rendah:** Mengembangkan program client-server fungsional berbasis *POSIX Sockets API* dengan penanganan *concurrency* (multi-threading/event-loop), *non-blocking I/O*, dan penanganan galat jaringan riil.
5. **Mendiagnosis Anomali Jaringan:** Memeriksa dan menganalisis transmisi paket mentah menggunakan utilitas standar industri seperti `tcpdump`, `wireshark`, dan `netstat`/`ss`.

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```text
[Arsitektur Jaringan Komputer]
          │
          ├──> [Model Komunikasi Berlapis]
          │         ├── Model OSI (7 Layer: Application down to Physical)
          │         └── Model TCP/IP (Application, Transport, Network, Data Link, Physical)
          │
          ├──> [Siklus Hidup Data: Enkapsulasi & Dekapsulasi]
          │         ├── Data -> Segment (L4) -> Packet (L3) -> Frame (L2) -> Bits (L1)
          │         └── Address Resolution: DNS (Domain -> IP), ARP (IP -> MAC)
          │
          ├──> [Transport Layer Dynamics]
          │         ├── TCP (Transmission Control Protocol)
          │         │     ├── 3-Way Handshake & 4-Way Teardown (State Machine)
          │         │     ├── Reliability: Sequence Numbers, ACKs, Retransmission (RTO)
          │         │     ├── Flow Control: Sliding Window Buffer
          │         │     └── Congestion Control: Slow Start, Congestion Avoidance, Fast Retransmit
          │         └── UDP (User Datagram Protocol)
          │               └── Connectionless, Unreliable, Low Overhead, Datagram Boundaries
          │
          └──> [Network Programming (Socket API)]
                    ├── POSIX Socket Lifecycle: socket() -> bind() -> listen() -> accept() -> read()/write()
                    ├── TCP Byte-Stream Framing (Length-prefix vs Delimiter)
                    └── Socket I/O Multiplexing: select(), poll(), epoll()/kqueue
```

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

Semua sistem komputasi modern—mulai dari arsitektur *microservices*, komputasi awan (*cloud*), sistem terdistribusi, hingga perangkat *Edge/IoT*—bergantung pada komunikasi data antar-mesin yang terhubung melalui jaringan. Kegagalan memahami mekanika fundamental jaringan komputer sering kali menyebabkan arsitektur perangkat lunak yang rapuh, latensi tinggi yang tidak terjelaskan, *cascading failures*, serta celah keamanan kritis.

Bagi seorang *Software Engineer* atau *Systems Architect*, jaringan bukan sekadar kotak hitam (*black box*) yang menjamin data tiba secara instan. Mengetahui batasan fisik seperti *Maximum Transmission Unit* (MTU), latensi propagasi (*speed of light in fiber*), dan *packet loss* sangat krusial. 

Tanpa pemahaman tentang bagaimana protokol transport mengelola *buffer* dan *flow control*, pengembang rentan membuat kesalahan fatal, seperti berasumsi bahwa satu panggilan `write()` pada TCP socket akan selalu diterima oleh tepat satu panggilan `read()` pada sisi penerima (*framing bug*), atau mengalami kehabisan port (*ephemeral port exhaustion*) akibat status `TIME_WAIT` yang tidak dikelola. Penguasaan lapisan ini adalah pembeda antara pengembang yang hanya bisa menggunakan API dengan teknisi yang mampu mengoptimalkan performa sistem hingga ke batas kemampuan perangkat keras dan protokolnya.

---

## SEKSI 05 — APA ITU (WHAT)

### 1. Model OSI vs Model TCP/IP

Model referensi jaringan membagi tugas komunikasi yang kompleks menjadi beberapa modul lapisan independen (*layering abstraction*). Masing-masing lapisan hanya berkomunikasi dengan lapisan di atasnya, di bawahnya, dan lapisan yang setara (*peer layer*) di mesin lawan.

| Layer OSI | Layer TCP/IP | Unit Data Protokol (PDU) | Protokol & Contoh Identifikasi | Tanggung Jawab Utama |
| :--- | :--- | :--- | :--- | :--- |
| **Application (L7)** | Application | Data | HTTP/HTTPS, DNS, SSH, gRPC | Interaksi dengan aplikasi end-user. |
| **Presentation (L6)**| Application | Data | TLS/SSL, JSON, Protobuf | Translasi, enkripsi, dan kompresi data. |
| **Session (L5)**     | Application | Data | RPC, NetBIOS, Sockets (konseptual) | Pengelolaan sesi dan checkpointing. |
| **Transport (L4)**   | Transport | Segment (TCP) / Datagram (UDP) | TCP, UDP, QUIC, Port (0–65535) | Komunikasi end-to-end proses-ke-proses. |
| **Network (L3)**     | Internet / Network | Packet | IPv4, IPv6, ICMP, IP Address | *Routing* dan *logical addressing* lintas jaringan. |
| **Data Link (L2)**   | Network Access | Frame | Ethernet, Wi-Fi (802.11), MAC Address | Transmisi node-to-node fisik di segmen lokal. |
| **Physical (L1)**    | Network Access | Bits | Kabel Tembaga, Fiber Optik, Gelombang RF | Modulasi sinyal fisik pembawa bit 0 dan 1. |

### 2. Transport Layer: TCP vs UDP

Lapisan Transport bertanggung jawab mengantarkan data antar-aplikasi menggunakan abstraksi **Port Number**.

* **TCP (Transmission Control Protocol - RFC 793):**
  * *Connection-oriented:* Wajib membentuk koneksi sebelum data dikirim.
  * *Reliable:* Menjamin data sampai tanpa korupsi, secara berurutan (*in-order*), dan tanpa duplikasi menggunakan mekanisme *Sequence Number* dan *Acknowledgment (ACK)*.
  * *Byte-stream oriented:* Tidak ada batasan pesan bawaan. TCP menganggap data sebagai aliran byte tunggal berkelanjutan.
  * *Mechanisms:* Flow control (mencegah *receiver buffer overflow*) dan Congestion control (mencegah kemacetan jaringan global).

* **UDP (User Datagram Protocol - RFC 768):**
  * *Connectionless:* Data dikirim langsung ke target tanpa negosiasi awal.
  * *Unreliable:* Tidak ada jaminan data sampai, tidak ada retransmisi bila paket hilang, tidak ada jaminan urutan (*out-of-order delivery*).
  * *Message-oriented (Datagram):* Mempertahankan batas pesan. Satu operasi pengiriman sama dengan satu operasi penerimaan.
  * *Overhead Rendah:* Header TCP berukuran minimal 20 byte (bisa bertambah hingga 60 byte dengan *options*), sedangkan header UDP berukuran konstan 8 byte.

---

## SEKSI 06 — BAGAIMANA CARA KERJA (HOW)

### 1. Enkapsulasi dan Dekapsulasi

Ketika aplikasi mengirim data (misalnya payload HTTP), data tersebut bergerak turun melewati stack jaringan:

1. **L7 Application:** Menghasilkan payload data (contoh: `GET / HTTP/1.1\r\n\r\n`).
2. **L4 Transport:** Payload dibungkus dengan Header TCP (berisi *Source Port*, *Destination Port*, *Sequence Number*, dll.). Hasilnya disebut **Segment**.
3. **L3 Network:** Segment dibungkus dengan Header IP (berisi *Source IP*, *Destination IP*, TTL, dll.). Hasilnya disebut **Packet**.
4. **L2 Data Link:** Paket dibungkus dengan Header Ethernet (berisi *Source MAC*, *Destination MAC*) dan Frame Check Sequence (FCS) di akhir. Hasilnya disebut **Frame**.
5. **L1 Physical:** Frame dikonversi menjadi representasi voltase, pulsa cahaya, atau gelombang radio untuk dikirimkan melalui media fisik.

Pada sisi penerima, proses dibalik (**Dekapsulasi**): L1 membaca bit -> L2 memvalidasi MAC dan FCS -> L3 membaca IP -> L4 membaca Port dan memvalidasi integritas segmen -> L7 memproses payload aplikasi.

### 2. Siklus Koneksi TCP (State Machine)

#### A. Pembentukan Koneksi: TCP 3-Way Handshake
1. **SYN:** Klien memilih *Initial Sequence Number* acak ($ISN_c$) dan mengirim paket dengan flag `SYN=1`, `Seq=ISN_c`. Klien masuk ke state `SYN-SENT`.
2. **SYN-ACK:** Server merespons dengan memilih $ISN_s$ miliknya, menyetel flag `SYN=1`, `ACK=1`, `Seq=ISN_s`, dan `Ack=ISN_c + 1`. Server masuk ke state `SYN-RECEIVED`.
3. **ACK:** Klien merespons dengan flag `ACK=1`, `Seq=ISN_c + 1`, `Ack=ISN_s + 1`. Koneksi resmi terbentuk. Klien dan server masuk ke state `ESTABLISHED`.

#### B. Terminasi Koneksi: 4-Way Teardown
1. **FIN (Klien -> Server):** Klien mengirim flag `FIN=1`. Klien masuk ke state `FIN-WAIT-1`.
2. **ACK (Server -> Klien):** Server mengakui FIN dengan `ACK`. Server masuk ke `CLOSE-WAIT`, klien masuk ke `FIN-WAIT-2`. (Koneksi *half-closed*; server masih bisa mengirim sisa data).
3. **FIN (Server -> Klien):** Setelah selesai memproses, server mengirim `FIN=1`. Server masuk ke `LAST-ACK`.
4. **ACK (Klien -> Server):** Klien mengirim `ACK`, lalu masuk ke state `TIME_WAIT` selama durasi $2 \times MSL$ (*Maximum Segment Lifetime*, umumnya 60–120 detik) sebelum benar-benar ditutup (`CLOSED`). Tujuannya adalah memastikan ACK terakhir sampai ke server dan mencegah paket usang dari koneksi lama mengontaminasi koneksi baru dengan kombinasi socket 4-tuple yang sama.

### 3. Kontrol Kemacetan TCP (Congestion Control)

TCP menggunakan jendela kemacetan (*Congestion Window* / `cwnd`) dan *Receiver Advertised Window* (`rwnd`) untuk menentukan berapa banyak byte yang boleh dikirim tanpa menunggu ACK:

$$\text{Effective Window} = \min(\text{cwnd}, \text{rwnd})$$

Algoritma standar melibatkan 4 fase utama:
1. **Slow Start:** Dimulai dengan `cwnd` kecil (contoh: 10 MSS). Setiap menerima ACK, `cwnd` bertambah secara eksponensial (dua kali lipat setiap *Round Trip Time* / RTT) hingga mencapai *Slow Start Threshold* (`ssthresh`).
2. **Congestion Avoidance:** Setelah `cwnd >= ssthresh`, pertumbuhan diubah menjadi linear (bertambah 1 MSS per RTT) untuk mencari batas kapasitas pipa jaringan secara hati-hati.
3. **Loss Detection:** 
   * Jika terjadi **Timeout**: Jaringan dinilai mengalami kemacetan parah. `ssthresh` dipotong menjadi $\text{cwnd} / 2$, `cwnd` direset ke 1 MSS, dan masuk kembali ke Slow Start.
   * Jika menerima **3 Duplicate ACKs**: Terjadi kehilangan paket terisolasi. Algoritma melakukan *Fast Retransmit* (mengirim ulang segmen yang hilang tanpa menunggu timer habis) dan *Fast Recovery* (menyetel `cwnd = ssthresh + 3*MSS` tanpa kembali ke 1 MSS).

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

### 1. Enkapsulasi PDU Lintas Lapisan

```text
+-----------------------------------------------------------------------------------+
| Lapisan Aplikasi (L7/L6/L5)                                                       |
| [ Application Payload: "GET /index.html HTTP/1.1\r\nHost: example.com\r\n\r\n" ] |
+-----------------------------------------------------------------------------------+
                                         │
                                         ▼ (Enkapsulasi Transport)
+------------------------------------+----------------------------------------------+
| TCP Header                         | Data (Payload Aplikasi)                      |
| [SrcPort: 54321, DstPort: 80,      |                                              |
|  Seq: 1001, Ack: 0, Flags: PSH|ACK]|                                              |
+------------------------------------+----------------------------------------------+
 <-------------------------------- Segment (L4) ----------------------------------->
                                         │
                                         ▼ (Enkapsulasi Network)
+-------------------+---------------------------------------------------------------+
| IPv4 Header       | Data (TCP Segment)                                            |
| [SrcIP: 10.0.0.2, |                                                               |
|  DstIP: 93.184...]|                                                               |
+-------------------+---------------------------------------------------------------+
 <-------------------------------- Packet (L3) ------------------------------------>
                                         │
                                         ▼ (Enkapsulasi Data Link)
+-------------------+-------------------------------------------+-------------------+
| Ethernet Header   | Data (IP Packet)                          | Frame Check (FCS) |
| [SrcMAC: aa:bb.., |                                           | [ CRC32 Checksum ]|
|  DstMAC: cc:dd..] |                                           |                   |
+-------------------+-------------------------------------------+-------------------+
 <-------------------------------- Frame (L2) ------------------------------------->
                                         │
                                         ▼ (Modulasi Fisik)
 [ 01010100 01100101 01110011 01110100 00100000 01100010 01101001 01110100 01110011 ] -> L1
```

### 2. State Transition: TCP 3-Way Handshake & 4-Way Teardown

```text
      CLIENT (State)                                       SERVER (State)
         [CLOSED]                                             [LISTEN]
            │                                                    │
            │ ─── 1. SYN (Seq=ISN_c) ──────────────────────────> │ (Menerima SYN)
      [SYN-SENT]                                            [SYN-RECEIVED]
            │                                                    │
            │ <── 2. SYN-ACK (Seq=ISN_s, Ack=ISN_c+1) ────────── │
    (Menerima SYN-ACK)                                           │
    [ESTABLISHED]                                                │
            │                                                    │
            │ ─── 3. ACK (Seq=ISN_c+1, Ack=ISN_s+1) ───────────> │ (Menerima ACK)
            │                                              [ESTABLISHED]
            │                                                    │
            │ <══════════ DATA TRANSFER PHASE ═════════════════> │
            │                                                    │
            │ ─── 4. FIN (Seq=U) ──────────────────────────────> │ (Menerima FIN)
     [FIN-WAIT-1]                                            [CLOSE-WAIT]
            │                                                    │
            │ <── 5. ACK (Ack=U+1) ───────────────────────────── │
     [FIN-WAIT-2]                                                │
            │                                                    │ (Aplikasi selesai kirim)
            │ <── 6. FIN (Seq=V, Ack=U+1) ────────────────────── │
            │                                                 [LAST-ACK]
    (Menerima FIN)                                               │
            │ ─── 7. ACK (Ack=V+1) ────────────────────────────> │
      [TIME-WAIT]                                             [CLOSED]
            │
      (Wait 2 * MSL)
            │
         [CLOSED]
```

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

Berikut adalah implementasi mendasar TCP Echo Server dan TCP Client menggunakan POSIX Sockets API standar di Python 3, yang mendemonstrasikan antarmuka soket primitif.

### `server_sederhana.py`
```python
import socket

def run_simple_server(host: str = '127.0.0.1', port: int = 8080):
    # 1. Inisialisasi Socket (AF_INET = IPv4, SOCK_STREAM = TCP)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_sock:
        # Mengatur socket option untuk menghindari error "Address already in use" saat restart cepat
        server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        # 2. Binding ke Alamat & Port
        server_sock.bind((host, port))
        
        # 3. Mendengarkan koneksi masuk (backlog = 5 antrean)
        server_sock.listen(5)
        print(f"[*] Server mendengarkan di {host}:{port}")
        
        # 4. Menerima koneksi masuk (Blocking call)
        conn, client_addr = server_sock.accept()
        with conn:
            print(f"[+] Terkoneksi dengan klien: {client_addr}")
            
            # 5. Membaca data mentah dari socket buffer
            data = conn.recv(1024)
            if data:
                print(f"[<] Menerima: {data.decode('utf-8')}")
                # 6. Mengirim balasan (Echo)
                conn.sendall(data)
                print("[>] Respon echo berhasil dikirim.")

if __name__ == '__main__':
    run_simple_server()
```

### `client_sederhana.py`
```python
import socket

def run_simple_client(host: str = '127.0.0.1', port: int = 8080):
    # 1. Inisialisasi Socket TCP IPv4
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_sock:
        # 2. Melakukan koneksi ke server (Memicu TCP 3-Way Handshake)
        client_sock.connect((host, port))
        print(f"[*] Berhasil terhubung ke {host}:{port}")
        
        # 3. Mengirim payload
        pesan = "Halo Jaringan Komputer!"
        client_sock.sendall(pesan.encode('utf-8'))
        print(f"[>] Terkirim: {pesan}")
        
        # 4. Menerima balasan
        response = client_sock.recv(1024)
        print(f"[<] Diterima dari server: {response.decode('utf-8')}")

if __name__ == '__main__':
    run_simple_client()
```

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

Masalah terbesar pada aplikasi tingkat pemula adalah **TCP Streaming Problem**. TCP memperlakukan data sebagai *unstructured stream of bytes*. Dua pemanggilan `send()` berturut-turut oleh pengirim dapat diterima sebagai satu potongan besar oleh penerima (*packet coalescing/clumping*), atau satu pemanggilan `send()` besar dapat dipecah menjadi beberapa potongan `recv()` kecil (*packet segmentation*).

Berikut adalah implementasi sistem produksi menggunakan **Length-Prefixed Framing Protocol (TLV Pattern - Type-Length-Value)** yang berjalan di atas server konkurensi berbasis `asyncio`. Setiap frame diawali oleh 4-byte *Network Byte Order (Big-Endian)* unsigned integer yang mendefinisikan panjang payload.

### `robust_protocol_server.py`
```python
import asyncio
import struct
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class RobustFramingProtocol:
    HEADER_SIZE = 4  # 4 bytes unsigned int (format: !I)

    @classmethod
    async def read_frame(cls, reader: asyncio.StreamReader) -> bytes:
        """
        Membaca tepat 1 frame utuh dari TCP stream menggunakan length-prefix.
        Mengatasi chunking dan partial-reads.
        """
        try:
            # 1. Baca ukuran frame (persis 4 byte)
            header_bytes = await reader.readexactly(cls.HEADER_SIZE)
            payload_len = struct.unpack('!I', header_bytes)[0]
            
            # Batasan keamanan (misal: proteksi buffer exhaustion max 10MB)
            if payload_len > 10 * 1024 * 1024:
                raise ValueError(f"Payload terlalu besar: {payload_len} bytes")

            # 2. Baca payload persis sepanjang payload_len
            payload = await reader.readexactly(payload_len)
            return payload

        except asyncio.IncompleteReadError:
            # Terjadi jika koneksi terputus saat membaca
            return None

    @classmethod
    def create_frame(cls, data: bytes) -> bytes:
        """Membungkus data mentah dengan 4-byte header length-prefix."""
        header = struct.pack('!I', len(data))
        return header + data

async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    peer = writer.get_extra_info('peername')
    logging.info(f"Koneksi baru dari: {peer}")

    try:
        while True:
            # Baca frame dengan aman tanpa risiko boundary issue
            payload = await RobustFramingProtocol.read_frame(reader)
            if payload is None:
                logging.info(f"Klien {peer} menutup koneksi secara normal.")
                break

            pesan = payload.decode('utf-8', errors='replace')
            logging.info(f"Frame diterima dari {peer} ({len(payload)} bytes): {pesan}")

            # Kirim balasan dengan frame baru
            balasan = f"ACK: {pesan}".encode('utf-8')
            frame_balasan = RobustFramingProtocol.create_frame(balasan)
            
            writer.write(frame_balasan)
            await writer.drain() # Pastikan buffer kernel dikosongkan ke jaringan

    except Exception as e:
        logging.error(f"Error saat memproses klien {peer}: {e}")
    finally:
        writer.close()
        await writer.wait_closed()
        logging.info(f"Socket untuk {peer} dibersihkan.")

async def main():
    host, port = '127.0.0.1', 9999
    server = await asyncio.start_server(handle_client, host, port)
    logging.info(f"Server Framed-TCP berjalan pada {host}:{port}")

    async with server:
        await server.serve_forever()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Server dihentikan oleh user.")
```

### `robust_protocol_client.py`
```python
import asyncio
import struct
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class RobustFramingClient:
    HEADER_SIZE = 4

    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.reader = None
        self.writer = None

    async def connect(self):
        self.reader, self.writer = await asyncio.open_connection(self.host, self.port)
        logging.info(f"Terhubung ke server {self.host}:{self.port}")

    async def send_message(self, message: str):
        payload = message.encode('utf-8')
        frame = struct.pack('!I', len(payload)) + payload
        
        self.writer.write(frame)
        await self.writer.drain()
        logging.info(f"[>] Frame terkirim ({len(payload)} bytes): {message}")

    async def read_response(self) -> str:
        header_data = await self.reader.readexactly(self.HEADER_SIZE)
        payload_len = struct.unpack('!I', header_data)[0]
        payload = await self.reader.readexactly(payload_len)
        return payload.decode('utf-8')

    async def close(self):
        if self.writer:
            self.writer.close()
            await self.writer.wait_closed()
            logging.info("Koneksi ditutup.")

async def main():
    client = RobustFramingClient('127.0.0.1', 9999)
    await client.connect()

    # Menguji pengiriman beruntun (pipeline/back-to-back)
    # Tanpa framing, pesan-pesan ini bisa bergabung menjadi 1 packet stream
    pesan_list = [
        "Pesan ke-1: Ping",
        "Pesan ke-2: Konfigurasi Parameter X",
        "Pesan ke-3: Data Sensor Multibyte ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    ]

    for p in pesan_list:
        await client.send_message(p)
        respon = await client.read_response()
        logging.info(f"[<] Menerima balasan: {respon}")

    await client.close()

if __name__ == '__main__':
    asyncio.run(main())
```

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

| Dimensi | Opsi A: TCP | Opsi B: UDP | Opsi C: QUIC (HTTP/3) |
| :--- | :--- | :--- | :--- |
| **Keandalan Transmisi** | Tinggi (Retransmission, ACK, checksum). | Rendah (Best effort, tidak ada ACK). | Tinggi (Sama seperti TCP, berbasis ACK). |
| **Head-of-Line (HoL) Blocking** | Ada. Kehilangan 1 paket memblokir seluruh stream byte. | Tidak ada. Datagram independen. | Tidak ada di level stream; dibangun di atas UDP dengan enkapsulasi independen. |
| **Connection Overhead** | 3-way handshake (1 RTT) + TLS (1-2 RTT). | Nol RTT (langsung kirim datagram). | 0-RTT atau 1-RTT connection setup terintegrasi TLS 1.3. |
| **Konsumsi Resource Kernel** | Tinggi (Stateful: buffer send/recv, timers, PCB). | Rendah (Stateless, buffer minimal). | Menengah (Dikelola di User-Space memory stack). |
| **Kompatibilitas Middlebox** | Sangat tinggi (Didukung semua NAT/firewall). | Cukup tinggi (Sering dibatasi/di-rate-limit pada NAT/firewall publik). | Menengah (Port UDP 443 terkadang diblokir oleh admin korporat konservatif). |
| **Kasus Penggunaan Ideal** | Web (HTTP/1.1, HTTP/2), Transfer File, Database queries, Email. | Game realtime (posisi pemain), Voice/Video call (RTP), DNS. | Web Performa Tinggi (HTTP/3), Jaringan Seluler dengan fluktuasi sinyal tinggi. |

---

## SEKSI 11 — BEST PRACTICES

1. **Gunakan Network Byte Order (Big-Endian):**
   Arsitektur CPU modern (seperti x86_64) umumnya *Little-Endian*, sedangkan jaringan mengadopsi representasi *Big-Endian*. Selalu gunakan konversi eksplisit seperti fungsi `htons()`, `htonl()`, `ntohs()`, `ntohl()` di C/C++ atau format modifier `!` di pustaka `struct` Python saat memanipulasi nilai biner header.
2. **Atur Opsi `SO_REUSEADDR`:**
   Pada server daemon, selalu atur `setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)` sebelum memanggil `bind()`. Ini mencegah crash `EADDRINUSE` saat server di-*restart* mendadak sementara soket sebelumnya masih tertahan di status kernel `TIME_WAIT`.
3. **Pahami dan Kendalikan Algoritma Nagle (`TCP_NODELAY`):**
   Algoritma Nagle menahan paket-paket kecil untuk digabungkan menjadi satu segmen utuh hingga ACK sebelumnya diterima. Ini menghemat bandwidth namun menyebabkan latensi tambahan (hingga ratusan milidetik) jika dikombinasikan dengan *TCP Delayed ACK*. Nonaktifkan Nagle (`TCP_NODELAY = 1`) untuk aplikasi interaktif atau RPC berlatensi rendah.
4. **Validasi Batas Payload (Prevent DoS):**
   Saat mengimplementasikan framing berbasis panjang (*length-prefixed framing*), validasi nilai panjang yang dibaca dari header *sebelum* mengalokasikan memori penyangga. Menerima nilai kotor seperti `uint32_max` (4 GB) dapat memicu *Out-Of-Memory (OOM) Panic*.
5. **Gunakan Heartbeat / Keepalive Application-Level:**
   Mekanisme `SO_KEEPALIVE` bawaan kernel sering kali memiliki interval default yang terlalu lambat (default 2 jam pada Linux). Buat ping/pong tingkat aplikasi secara berkala untuk mendeteksi *dead peers* atau putusnya jalur kabel fisik (*half-open connection*) secara cepat.

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

1. **Asumsi "Satu Send = Satu Recv":**
   *Gejala:* Kode berjalan normal saat diuji pada `localhost`, tetapi pecah atau data korup ketika diuji di jaringan nyata (*production*).
   *Penyebab:* TCP adalah aliran byte (*byte stream*), bukan pembawa pesan (*message stream*). Satu pemanggilan `recv(4096)` tidak menjamin 4096 byte langsung masuk, dan tidak menjamin satu baris kalimat utuh diterima sekaligus.
   *Solusi:* Wajib menggunakan protokol framing (delimiter seperti `\r\n` atau panjang terprefix).

2. **Mengabaikan Nilai Kembali (*Return Value*) dari `recv()` atau `send()`:**
   *Gejala:* Kehilangan data acak saat mengirim payload besar.
   *Penyebab:* Fungsi `send(buf)` di level POSIX tidak menjamin *seluruh* buffer terkirim ke antrean kernel; fungsi tersebut mengembalikan jumlah byte yang *benar-benar* berhasil masuk antrean.
   *Solusi:* Lakukan loop sampai total byte terkirim (`sendall()` pada Python secara otomatis menangani loop ini, tetapi pada C/C++ Anda harus mengimplementasikannya secara manual).

3. **Kehabisan File Descriptor (FD Leak):**
   *Gejala:* Server melempar galat `OSError: [Errno 24] Too many open files` setelah beberapa jam beroperasi.
   *Penyebab:* Lupa memanggil `.close()` pada soket klien setelah terjadi *exception* atau pemutusan koneksi oleh pihak remote.
   *Solusi:* Manfaatkan blok *context manager* (`with` statement) atau blok `try ... finally` yang menjamin pemanggilan fungsi penutupan soket.

4. **Socket Exhaustion Akibat Penutupan Sisi Klien:**
   *Gejala:* Klien HTTP/Microservice tidak bisa lagi membuat koneksi keluar dan memicu galat `Cannot assign requested address`.
   *Penyebab:* Pihak yang pertama kali memicu pemutusan koneksi (mengirimkan `FIN`) akan mengalihkan soket lokal ke state `TIME_WAIT` selama 1–2 menit. Jika klien terus menerus membuka dan menutup koneksi secara singkat tanpa *connection pooling*, rentang port dinamis (*ephemeral ports*) lokal akan habis.
   *Solusi:* Implementasikan *HTTP Connection Pooling* / *Persistent Connections* (Keep-Alive).

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Latihan 1: Analisis Paket Menggunakan `tcpdump` dan `wireshark` (Beginner)
* **Deskripsi:** Analisis alur pertukaran paket TCP 3-Way Handshake dan 4-Way Teardown secara nyata.
* **Tugas:**
  1. Jalankan perekaman paket pada antarmuka lokal menggunakan terminal:
     ```bash
     sudo tcpdump -i lo -nn -S "tcp port 8080" -w handshake.pcap
     ```
  2. Jalankan `server_sederhana.py` dan `client_sederhana.py` dari Seksi 08.
  3. Buka file `handshake.pcap` menggunakan Wireshark.
* **Pertanyaan Verifikasi:**
  * Berapa nilai *Sequence Number* absolut pada paket SYN pertama?
  * Bagaimana nilai *Acknowledgment Number* dihitung pada paket SYN-ACK balasan server? Tunjukkan korelasinya dengan nilai ISN milik klien.

### Latihan 2: Implementasi Protocol Delimiter-Based / Line-Based Reader (Intermediate)
* **Deskripsi:** Selain *length-prefixed*, protokol populer seperti HTTP/1.1, Redis (RESP), dan SMTP menggunakan format pembatas teks (*delimiter-based*).
* **Tugas:** Tulis fungsi Python berbasis soket standar `recv_line(sock, delimiter=b'\r\n')` yang mengumpulkan byte demi byte (atau menggunakan internal buffer) hingga pembatas ditemukan, dan mengembalikan byte utuh tanpa pembatas tersebut. Tangani kondisi ketika koneksi diputus oleh remote sebelum delimiter ditemukan (*EOF anomaly*).

### Latihan 3: Mini DNS Resolver Berbasis UDP Socket Mentah (Advanced)
* **Deskripsi:** Buat program Python yang membuat paket kueri DNS mentah (*DNS Query Packet*) format RFC 1035, mengirimkannya langsung melalui UDP Socket ke server DNS publik Google (`8.8.8.8` port 53), dan membedah (*parse*) jawaban biner untuk mendapatkan alamat IPv4 target.
* **Ketentuan:**
  * Dilarang menggunakan pustaka eksternal pihak ketiga (hanya boleh modul bawaan: `socket`, `struct`).
  * Harus mampu memetakan nama domain arbitrer (misal: `example.com`) menjadi Record Type A (IPv4).

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

1. **Pertanyaan:** Apa alasan status `TIME_WAIT` harus bertahan selama $2 \times MSL$ pada pihak yang menginisiasi pemutusan koneksi TCP?
   * A) Menunggu server memproses seluruh antrean thread.
   * B) Memastikan segmen ACK terakhir sampai ke server dan mencegah paket usang dari koneksi sebelumnya mengontaminasi koneksi baru yang memiliki 4-tuple identik.
   * C) Menghitung ulang throughput jaringan untuk dilaporkan ke sistem operasi.
   * D) Menghindari pemakaian CPU 100% pada proses socket.
   * *Kunci Jawaban:* **B**
   * *Penjelasan:* Jika ACK terakhir hilang, server akan mengirim ulang FIN. Klien harus tetap dalam keadaan aktif untuk merespons ACK lagi. Rentang $2 \times MSL$ menjamin seluruh paket yang beredar di jaringan (*in-flight*) telah mati/kedaluwarsa sebelum kombinasi IP dan port yang sama dialokasikan kembali.

2. **Pertanyaan:** Jika sebuah segmen TCP memiliki MSS (Maximum Segment Size) sebesar 1460 byte, berapa ukuran total frame Ethernet standar lapisan L2 (tanpa opsi tambahan)?
   * A) 1460 Byte
   * B) 1500 Byte
   * C) 1514 Byte (atau 1518 Byte jika menyertakan FCS)
   * D) 1522 Byte
   * *Kunci Jawaban:* **C**
   * *Penjelasan:* MSS (1460) + Header TCP (20) + Header IP (20) = MTU (1500 Byte). Frame Ethernet L2 menambahkan Header Ethernet (14 Byte MAC Src/Dst/Type) + FCS (4 Byte CRC), sehingga totalnya menjadi 1514 (tanpa FCS) atau 1518 Byte.

3. **Pertanyaan:** Apakah perbedaan mendasar perilaku antara algoritma kontrol kemacetan (*Congestion Control*) dan kendali aliran (*Flow Control*)?
   * A) Flow control melindungi kapasitas penerima dari banjir data; Congestion control melindungi kapasitas infrastruktur jaringan dari kelebihan beban.
   * B) Flow control diatur oleh router L3; Congestion control diatur oleh host L4.
   * C) Flow control hanya ada di UDP; Congestion control hanya ada di TCP.
   * D) Flow control menggunakan byte; Congestion control menggunakan bit.
   * *Kunci Jawaban:* **A**
   * *Penjelasan:* Flow control menggunakan parameter `rwnd` (Receive Window) yang dikirim oleh penerima agar pengirim tidak melebihi kapasitas buffer lokal penerima. Sebaliknya, Congestion control menggunakan parameter internal `cwnd` yang dihitung oleh pengirim untuk mencegah terjadinya degradasi atau macet total pada intermediate switches/routers di internet.

4. **Pertanyaan:** Mengapa protokol UDP lebih diutamakan daripada TCP dalam transmisi metrik koordinat pemain secara *real-time* pada game kompetitif multiplayer online?
   * A) Karena header UDP lebih aman terhadap mitigasi serangan spoofing IP.
   * B) Retransmisi paket yang hilang pada TCP menyebabkan *Head-of-Line Blocking*; dalam game waktu nyata, data posisi yang tertunda sudah basi dan lebih baik dibuang daripada menghentikan alur data baru.
   * C) Karena ukuran buffer TCP di sistem operasi dibatasi maksimal 64KB.
   * D) Karena UDP menjamin *Zero Packet Loss* pada jaringan nirkabel.
   * *Kunci Jawaban:* **B**
   * *Penjelasan:* TCP menjamin urutan data. Jika sebuah paket hilang, TCP menahan data selanjutnya di antrean sampai paket yang hilang berhasil dikirim ulang. Pada game aksi, informasi posisi musuh 100ms yang lalu sudah tidak berguna; aplikasi membutuhkan posisi paling mutakhir secepat mungkin.

5. **Pertanyaan:** Apa implikasi dari mengabaikan sinyal pengembalian (return value) 0 saat membaca soket menggunakan pemanggilan `recv()` di POSIX?
   * A) Program akan memicu *Segmentation Fault* seketika.
   * B) Server akan terjebak dalam *infinite loop* (busy-waiting) yang mengonsumsi CPU 100%, karena return value 0 menandakan remote host telah menutup koneksi (*End Of File / Graceful Shutdown*).
   * C) Paket secara otomatis akan dibaca ulang dari awal buffer.
   * D) Socket berubah status secara otomatis menjadi non-blocking.
   * *Kunci Jawaban:* **B**
   * *Penjelasan:* Pada POSIX Socket API, nilai kembali `0` dari pembacaan soket yang bersifat *blocking* secara definitif menyatakan bahwa peer remote telah menutup sisi pengirimannya (mengirimkan segmen FIN). Jika program tidak memeriksa kondisi `len == 0` dan tidak menutup soket, fungsi pembacaan berikutnya akan terus menerus langsung mengembalikan 0 tanpa henti.

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

* **RFC Fundamental (Internet Engineering Task Force):**
  * [RFC 791](https://datatracker.ietf.org/doc/html/rfc791) — *Internet Protocol (IPv4 Specification)*.
  * [RFC 793](https://datatracker.ietf.org/doc/html/rfc793) — *Transmission Control Protocol (TCP Specification)*.
  * [RFC 768](https://datatracker.ietf.org/doc/html/rfc768) — *User Datagram Protocol (UDP Specification)*.
  * [RFC 9000](https://datatracker.ietf.org/doc/html/rfc9000) — *QUIC: A UDP-Based Multiplexed and Secure Transport*.
* **Buku Teks Utama:**
  * Kurose, J. F., & Ross, K. W. (2021). *Computer Networking: A Top-Down Approach* (8th Edition). Pearson.
  * Stevens, W. R., Fenner, B., & Rudoff, A. M. (2004). *UNIX Network Programming, Volume 1: The Sockets Networking API* (3rd Edition). Addison-Wesley.
  * Fall, K. R., & Stevens, W. R. (2011). *TCP/IP Illustrated, Volume 1: The Protocols* (2nd Edition). Addison-Wesley Professional.
* **Dokumentasi & Standar Industri:**
  * Linux Kernel Documentation: [IP Sysctl tuning (`/proc/sys/net/ipv4/*`)](https://www.kernel.org/doc/Documentation/networking/ip-sysctl.txt).
  * Beej's Guide: [Beej's Guide to Network Programming (Using Internet Sockets)](https://beej.us/guide/bgnet/).

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

* Abstraksi jaringan modern dipisahkan ke dalam lapisan struktural (OSI & TCP/IP) di mana setiap lapisan menambahkan metadatanaya sendiri melalui proses **Enkapsulasi** dan melepaskannya kembali melalui **Dekapsulasi**.
* **TCP** mengorbankan latensi dan menambahkan *overhead* demi menyajikan abstraksi aliran byte (*byte-stream*) yang reliabel, terurut, dan bebas error melalui *Three-Way Handshake*, *Sequence/ACK Numbers*, serta *Congestion Control*.
* **UDP** menawarkan mekanisme transmisi datagram nir-status (*stateless*) tanpa garansi dan overhead minimal, ideal untuk sistem waktu nyata (*low-latency*) atau protokol berbasis kueri sederhana.
* TCP tidak mengelola batas-batas data aplikasi. Merancang protokol tingkat aplikasi wajib menyertakan mekanisme pemisahan pesan (**Message Framing**), seperti prefiks ukuran (*Length-prefixed*) atau pembatas biner/karakter (*Delimiter-based*).
* Status koneksi TCP seperti `TIME_WAIT` adalah fitur proteksi sistem operasi, bukan anomali, namun memerlukan pemahaman mendalam terkait alokasi *ephemeral port* dan arsitektur *connection pool*.

---

## SEKSI 17 — GLOSARIUM

* **Backlog:** Ukuran antrean kernel untuk menyimpan permintaan koneksi yang belum sempat diproses oleh pemanggilan `accept()` aplikasi.
* **Byte-Order (Endianness):** Urutan penyimpanan byte representasi nilai multi-byte di memori. Jaringan menggunakan format *Big-Endian* (Most Significant Byte diletakkan paling awal).
* **FCS (Frame Check Sequence):** Kode redundansi siklik (CRC-32) di akhir frame L2 untuk mendeteksi distorsi atau korupsi bit saat melewati media fisik.
* **Head-of-Line (HoL) Blocking:** Fenomena di mana sebuah antrean transmisi terhenti total karena paket paling depan rusak/hilang dan harus ditransmisikan ulang.
* **MSS (Maximum Segment Size):** Ukuran muatan (*payload*) data murni terbesar yang dapat ditampung oleh satu segmen TCP tunggal tanpa menyertakan header TCP/IP (umumnya 1460 byte pada MTU 1500).
* **MTU (Maximum Transmission Unit):** Batas ukuran paket lapisan jaringan terbesar (termasuk header IP) yang dapat dilewatkan oleh antarmuka jaringan fisik tanpa mengalami fragmentasi (default Ethernet: 1500 byte).
* **Nagle's Algorithm:** Mekanisme pengoptimalan jaringan yang menghentikan pengiriman paket-paket kecil sebelum paket sebelumnya terkonfirmasi, demi meminimalkan *overhead* transmisi header.
* **RTT (Round Trip Time):** Durasi waktu total yang dibutuhkan suatu sinyal/paket untuk berpindah dari sumber ke target dan kembali lagi ke sumber.
* **Socket:** Titik akhir abstraksi antarmuka perangkat lunak (*software endpoint*) yang disediakan oleh OS untuk komunikasi antar-proses lintas jaringan, diidentifikasi oleh 5-tuple (Protokol, IP Sumber, Port Sumber, IP Target, Port Target).
* **TIME_WAIT:** Status akhir TCP di mana sisi penutup menunggu durasi $2 \times MSL$ untuk memastikan ACK penutup telah diterima dan paket lama di jaringan telah dibuang secara alami.

---

## SEKSI 18 — CATATAN INSTRUKTUR

* **Poin Rawan Miskonsepsi:** Mahasiswa sering berasumsi bahwa perintah `socket.send(data)` mengirim data seketika itu juga ke komputer lawan. Tekankan berulang kali bahwa fungsi socket API hanya memindahkan data antara *Memory Buffer Ruang Pengguna (User-Space)* dan *Buffer Antrean Kernel (Kernel-Space Socket Buffer)*. Waktu transmisi fisik sesungguhnya dikontrol sepenuhnya oleh *TCP Congestion Engine* dan kartu jaringan (NIC).
* **Saran Demonstrasi Kelas:**
  * Jangan hanya menunjukkan slide konseptual. Jalankan demonstrasi langsung menggunakan Wireshark. Minta salah satu mahasiswa mengirim pesan raw TCP menggunakan perintah `nc -l 8080` (netcat) dan tangkap proses 3-way handshake secara nyata di layar proyektor.
  * Tunjukkan kondisi *race condition* atau *framing error* dengan mengirim payload JSON 100 kali berturut-turut tanpa pembatas; biarkan mahasiswa melihat respons error `JSONDecodeError: Extra data` karena beberapa paket tergabung dalam satu panggilan `recv()`.
* **Diferensiasi Pembelajaran:**
  * Bagi mahasiswa tingkat lanjut, tantang mereka untuk mengimplementasikan *custom binary packing protocol* dengan kompresi bit-level atau mengonfigurasi *Linux Network Namespaces* (`ip netns`) untuk menyimulasikan topologi jaringan terisolasi dalam satu mesin kerja lokal.

---

## SEKSI 19 — CHANGELOG & VERSI

* **Versi 1.0.0 (Januari 2025):**
  * Rilis modul awal standar arsitektur kurikulum CS Core Foundations.
  * Penambahan diagram ASCII mendalam terkait enkapsulasi stack protokol dan alur siklus hidup TCP state machine.
  * Integrasi contoh kode Python Socket fungsional tingkat dasar dan tingkat produksi (Length-Prefixed Framing Asyncio).
  * Penyesuaian materi *modern transport layer* (referensi QUIC/HTTP-3 dan Algoritma BBR).

---

## SEKSI 20 — NAVIGASI KURIKULUM

* **Modul Sebelumnya:** [CS-CF-OS-0504 — Sistem Operasi: Penyimpanan Sekunder, File System, dan Perangkat Masukan/Keluaran (I/O)](../05-Operating-Systems/module-04.md)
* **Modul Saat Ini:** **CS-CF-NET-0601 — Jaringan Komputer: Arsitektur Jaringan, Protokol Layering (OSI & TCP/IP), dan Socket Programming**
* **Modul Berikutnya:** [CS-CF-NET-0602 — Jaringan Komputer: Protokol Routing, Subnetting IPv4/IPv6, dan Keamanan Lapisan Transport (TLS/SSL)](./module-02.md)