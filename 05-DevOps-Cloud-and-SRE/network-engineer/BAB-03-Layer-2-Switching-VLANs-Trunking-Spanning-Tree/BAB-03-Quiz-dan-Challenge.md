# Evaluasi Bab 03: Layer 2 Switching, Enterprise VLANs, Trunking, dan Spanning Tree

---

## Bagian 1: Basic Questions (5 Soal)

### Soal 1
Berapa panjang field VLAN ID (VID) pada header tag IEEE 802.1Q, dan berapa jumlah total VLAN teoritis yang dapat direpresentasikan oleh field tersebut?
- A. 8-bit, 256 VLAN
- B. 10-bit, 1024 VLAN
- C. 12-bit, 4096 VLAN
- D. 16-bit, 65536 VLAN

### Soal 2
Ketika sebuah switch menerima Ethernet frame dan menemukan bahwa Destination MAC Address tidak terdapat di dalam CAM Table, tindakan apa yang dilakukan switch?
- A. Menolak frame dan mengirimkan paket ICMP Destination Unreachable ke pengirim.
- B. Melakukan Unknown Unicast Flooding ke seluruh port dalam VLAN yang sama kecuali port penerima.
- C. Menyimpan frame ke dalam memory buffer hingga MAC address tujuan dipelajari.
- D. Mengirimkan frame hanya ke port Trunk atau port default gateway.

### Soal 3
Berapakah nilai default Aging Time untuk entri MAC address dinamis pada CAM table switch enterprise standar jika tidak terjadi perubahan topologi STP?
- A. 30 detik
- B. 60 detik
- C. 300 detik
- D. 3600 detik

### Soal 4
Fitur STP manakah yang secara instan menonaktifkan port (menempatkannya ke dalam status `err-disable`) apabila menerima paket BPDU pada port yang dikonfigurasi untuk edge/end-host?
- A. Root Guard
- B. Loop Guard
- C. BPDU Filter
- D. BPDU Guard

### Soal 5
Pada negosiasi LACP (IEEE 802.3ad), apa kombinasi mode port antar dua switch yang **TIDAK AKAN** berhasil membentuk ikatan Port-Channel?
- A. Active - Active
- B. Active - Passive
- C. Passive - Passive
- D. Active - Auto

---

## Bagian 2: Intermediate Questions (5 Soal)

### Soal 6
Sebuah Ethernet frame dikirimkan dengan konfigurasi 802.1Q tag. Berapakah nilai heksadesimal standar dari field EtherType / TPID (Tag Protocol Identifier) yang disisipkan untuk menandai bahwa frame tersebut bertag 802.1Q?
- A. `0x0800`
- B. `0x8100`
- C. `0x8847`
- D. `0x86DD`

### Soal 7
Pada algoritma Rapid Spanning Tree Protocol (RSTP IEEE 802.1w), port yang berfungsi sebagai jalur cadangan (backup) langsung untuk **Root Port** jika Root Port utama putus disebut:
- A. Designated Port
- B. Backup Port
- C. Alternate Port
- D. Disabled Port

### Soal 8
Dalam topologi link trunk antar dua switch enterprise, Native VLAN di Switch-A diset ke VLAN 10, sedangkan di Switch-B diset ke VLAN 20. Dampak teknis langsung dari miskonfigurasi ini adalah:
- A. Seluruh interface trunk akan otomatis masuk ke status `err-disable` oleh hardware ASIC.
- B. Paket broadcast/untagged dari VLAN 10 pada Switch-A akan diterima langsung oleh host di VLAN 20 pada Switch-B tanpa perantara router.
- C. Protokol STP akan otomatis memblokir seluruh VLAN di trunk tersebut secara permanen.
- D. Frame ber-tag akan kehilangan data payload akibat korupsi header FCS.

### Soal 9
Manakah pernyataan yang paling akurat mengenai perbedaan mendasar antara BPDU Guard dan BPDU Filter saat dikonfigurasi pada level interface access?
- A. BPDU Guard memblokir loop pada port trunk, sedangkan BPDU Filter hanya bekerja pada access port.
- B. BPDU Guard mematikan port (`err-disable`) jika menerima BPDU, sedangkan BPDU Filter mengabaikan/menolak transmisi dan penerimaan BPDU sehingga berisiko menciptakan loop.
- C. BPDU Guard menurunkan priority switch, sedangkan BPDU Filter menaikkan priority switch.
- D. BPDU Guard memvalidasi kesamaan native VLAN, sedangkan BPDU Filter menyaring frame broadcast.

### Soal 10
Mengapa algoritma load balancing LACP berbasis default `src-mac` sangat tidak efisien untuk switch access yang mengalirkan traffic dari 100 workstation lokal menuju server eksternal di cloud melalui router default gateway tunggal?
- A. Karena switch akan kehabisan memory CAM table saat menghitung hash source MAC.
- B. Karena Destination MAC seluruh workstation akan selalu sama, yaitu MAC address interface router gateway, tetapi Source MAC berbeda.
- C. Karena ketika traffic kembali dari cloud melalui router gateway, seluruh paket memiliki Source MAC yang sama (MAC gateway), sehingga traffic balik hanya terkonsentrasi pada satu link fisik tunggal.
- D. LACP tidak mendukung agregasi frame jika melewati layer 3 router.

---

## Bagian 3: Scenario-Based Questions (3 Kasus Nyata)

### Skenario 1: The Midnight Silent Outage
Sebuah data center e-commerce mengalami lonjakan utilisasi bandwidth inter-switch hingga 100% pada pukul 00:00 saat cron backup database berjalan. Tim NOC menemukan jutaan packet drop dan MAC address flapping di syslog switch distribution:
`%SW_MATM-4-MACFLAP_ADDR: Host 0050.56a1.2234 in vlan 100 is flapping between port Po1 and port Po2`
Analisis membuktikan bahwa tidak ada kabel baru yang dicolokkan. Namun, seorang insinyur jaringan sebelumnya baru saja mengaktifkan fitur `spanning-tree bpdufilter enable` pada uplink antar-switch yang mengalami flap, dengan tujuan "menghilangkan log STP yang mengganggu".

**Pertanyaan Analisis:**
1. Mengapa tindakan mengaktifkan BPDU Filter pada uplink antar-switch memicu terjadinya bencana broadcast storm dan MAC flapping saat backup berjalan?
2. Bagaimana mekanisme interaksi CAM table ketika loop tersebut terjadi?

### Skenario 2: The Rogue Switch Infiltration
Seorang kontraktor magang membawa switch managed lama dari rumah dan mencolokkannya ke wall-jack cubicle kantor yang terhubung ke port Switch Access Lantai 2. Switch port kantor tersebut belum dikonfigurasi dengan port protection. Switch milik kontraktor memiliki Bridge Priority `0` (default pabrikan model lama tertentu). 

Dalam hitungan 3 detik, jalur transmisi seluruh kantor pusat teralihkan melintasi switch kontraktor tersebut, memicu packet drops masif dan kebocoran keamanan data.

**Pertanyaan Analisis:**
1. Mengapa switch kontraktor dapat merebut peran Root Bridge dari Core Switch pusat yang memiliki spesifikasi jauh lebih tinggi?
2. Fitur proteksi spesifik apa (sebutkan 2 fitur) yang seharusnya dipasang di switch access perusahaan untuk mencegah insiden ini secara otomatis?

### Skenario 3: Asymmetric LACP Black Hole
Dua switch Core Data Center dihubungkan menggunakan 4 link 10Gbps yang dibundel menggunakan EtherChannel. Teknisi lapangan mengganti salah satu modul SFP+ yang rusak di Port 4. Namun, teknisi salah mengonfigurasi Port 4 di Switch A dengan mode `channel-group 1 mode on` (Static), sedangkan di Switch B dibiarkan dengan konfigurasi `channel-group 1 mode active` (LACP).

**Pertanyaan Analisis:**
1. Jelaskan bagaimana status operasional Port-Channel di kedua sisi switch.
2. Apa dampak yang dialami oleh paket data yang didistribusikan ke Port 4 oleh hash scheduler Switch A?

---

## Bagian 4: Practical Chapter Challenge

### Judul Tantangan:
**Arsitektur Zero-Downtime, Resilient Layer 2 Fabric untuk Platform FinTech Banking**

### Deskripsi Masalah:
Anda ditunjuk sebagai Principal Network Architect untuk mendesain ulang fondasi Layer 2 dari infrastruktur transaksi FinTech core-banking. Topologi fisik terdiri dari:
- 2x Spine/Distribution Switches: `CORE-SW-01` dan `CORE-SW-02`
- 2x Leaf/Access Switches: `RACK-SW-01` dan `RACK-SW-02`
- Setiap Leaf Switch memiliki Dual-Uplink 10Gbps ke masing-masing Core Switch (Total 4 uplink per leaf switch).
- Terdapat 3 VLAN utama:
  - VLAN 100: Transaksi Online (Latensi rendah, mission critical)
  - VLAN 200: Core Database Replication (Throughput tinggi)
  - VLAN 300: Out-of-Band Management

### Instruksi Tugas Teknis:
1. **Desain STP & Determinisme Topologi**:
   - Rancang konfigurasi Spanning Tree Rapid-PVST+ (atau MSTP) di mana `CORE-SW-01` menjadi Primary Root Bridge untuk VLAN 100 & 300, tetapi menjadi Secondary Root Bridge untuk VLAN 200.
   - Sebaliknya, `CORE-SW-02` menjadi Primary Root Bridge untuk VLAN 200, dan Secondary Root Bridge untuk VLAN 100 & 300 (Active-Active Load Sharing per-VLAN).
2. **Link Aggregation**:
   - Buat konfigurasi LACP Port-Channel uplink antara `RACK-SW-01` ke `CORE-SW-01` dan `CORE-SW-02`.
   - Konfigurasikan algoritma hashing load balancing yang paling optimal untuk throughput database dan web traffic (Layer 4 hash).
3. **Hardening Perimeter Layer 2**:
   - Terapkan konfigurasi lengkap mitigasi VLAN Hopping, STP Hijacking, dan Unauthorized DHCP/Switch Injection pada port edge yang mengarah ke server Kubernetes worker nodes.
   - Sediakan konfigurasi siap pakai (syntactically correct) untuk Cisco IOS/NX-OS.

---

## Kunci Jawaban & Pembahasan Evaluasi

### Bagian 1: Basic
1. **C** (12-bit, memberikan rentang $2^{12} = 4096$ kemungkinan ID, yaitu 0 hingga 4095).
2. **B** (Unknown Unicast Flooding; switch membanjiri frame ke seluruh port pada VLAN yang sama untuk memicu respon dari host pemilik IP/MAC tersebut).
3. **C** (Default aging time CAM table switch enterprise umumnya adalah 300 detik atau 5 menit).
4. **D** (BPDU Guard menempatkan port ke `err-disable` jika mendeteksi BPDU pada port PortFast/Edge).
5. **C** (Passive - Passive; kedua belah pihak hanya menunggu paket LACPDU tanpa ada yang memulai inisiasi handshake secara aktif).

### Bagian 2: Intermediate
6. **B** (`0x8100` adalah nilai standar IEEE untuk TPID 802.1Q).
7. **C** (Alternate Port; menyediakan jalur cadangan instan menuju Root Bridge jika Root Port mengalami kegagalan link fisik).
8. **B** (Frame dari native VLAN dikirimkan tanpa tag 802.1Q melintasi trunk. Switch penerima akan menganggap frame tanpa tag tersebut adalah milik native VLAN lokalnya, sehingga terjadi kebocoran traffic antar-VLAN).
9. **B** (BPDU Guard bertindak defensif dengan mematikan port, sedangkan BPDU Filter secara membabi buta membisukan BPDU, yang membuka celah pembentukan loop fisik jika terjadi sambungan redundan).
10. **C** (Ketika traffic berasal dari cloud/internet masuk ke gateway dan diteruskan ke workstation, seluruh traffic tersebut memiliki Source MAC yang identik [MAC router gateway]. Jika switch gateway menggunakan hashing berbasis `src-mac`, semua flow tersebut akan menghasilkan nilai hash yang sama dan dialirkan ke satu port fisik yang sama, membuat link lainnya sia-sia).

### Bagian 3: Solusi Skenario

#### Solusi Skenario 1
1. Mengaktifkan BPDU Filter pada uplink antar-switch menyebabkan switch berhenti mengirim dan memproses BPDU di link tersebut. Akibatnya, STP menganggap link tersebut sebagai jalur bebas loop independen dan membuka semua port ke state Forwarding. Ketika backup database berjalan dengan volume traffic tinggi, frame broadcast/multicast (atau unknown unicast) berputar dalam loop fisik tanpa henti, memicu broadcast storm.
2. CAM table mengalami kekacauan (*thrashing/flapping*): Switch menerima frame dari MAC address server database secara bergantian dari Port-Channel 1 dan Port-Channel 2 dalam hitungan milidetik. Switch terus menerus menimpa entri CAM table-nya, membuang resource komputasi ASIC, dan akhirnya mengalami lock-up pada control plane.

#### Solusi Skenario 2
1. Pemilihan Root Bridge dalam STP didasarkan pada nilai Bridge ID terkecil: Priority + MAC Address. Switch kontraktor memiliki Priority `0` (lebih kecil daripada switch core perusahaan yang mungkin berada pada default 32768 atau 4096). Switch core kalah dalam pemilihan numerik dan secara otomatis melepaskan perannya sebagai root.
2. Dua fitur proteksi mitigasi:
   - **BPDU Guard** pada semua port access end-user: Port otomatis shutdown saat switch kontraktor dicolokkan.
   - **Root Guard** pada port distribution/access yang menuju workstation: Mencegah switch manapun di hilir untuk menjadi Root Bridge meskipun mengirimkan priority 0.

#### Solusi Skenario 3
1. Switch A (Mode ON) berasumsi bahwa agregasi link aktif tanpa perlu negosiasi LACP; Port 4 langsung dimasukkan ke bundle bundle forwarding. Switch B (Mode Active) menunggu paket negosiasi LACPDU dari Switch A di Port 4. Karena Switch A di set Mode ON, Switch A tidak mengirimkan LACPDU. Akibatnya, Switch B menempatkan Port 4 dalam status `Suspended` atau `Individual` (tidak tergabung ke Port-Channel).
2. Terjadi **Traffic Black-Holing**: Scheduler Switch A akan mendistribusikan $\approx 25\%$ frame data keluar melalui Port 4. Namun, karena Switch B tidak mengaktifkan Port 4 sebagai member bundle, Switch B akan membuang (drop) seluruh frame data yang masuk ke Port 4 tersebut.