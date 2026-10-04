# Evaluasi Bab 10: Monitoring, Observability, High Availability, dan Troubleshooting

---

## I. Basic Questions (Pilihan Ganda & Analisis Singkat)

1. **Mengapa SNMP Polling dengan interval 5 menit tidak memadai untuk mendeteksi degradasi performa pada microservices cloud-native modern?**
   - A. SNMP tidak mendukung enkripsi payload.
   - B. SNMP polling menggunakan protokol TCP yang lambat.
   - C. Fenomena microburst drop terjadi dalam hitungan milidetik sehingga terlewatkan dalam agregasi rata-rata 5 menit.
   - D. SNMP agent hanya dapat dijalankan pada sistem operasi Linux standar.

2. **Perbedaan fundamental arsitektur antara IPFIX dan sFlow adalah:**
   - A. IPFIX menggunakan transport TCP sedangkan sFlow selalu ICMP.
   - B. IPFIX melakukan agregasi stateful flow di cache router, sedangkan sFlow melakukan stateless packet sampling di level ASIC.
   - C. sFlow mengekspor seluruh payload paket aplikasi, sedangkan IPFIX hanya mengekspor TCP flags.
   - D. IPFIX hanya dapat berjalan pada perangkat Cisco proprietary.

3. **Mode subscription gNMI manakah yang paling efisien untuk memonitor perubahan state link status interface (Up/Down) router?**
   - A. `SAMPLE` dengan interval 100ms.
   - B. `POLL` terjadwal setiap 1 detik.
   - C. `ON_CHANGE`.
   - D. `STREAM_ALL`.

4. **Kondisi apa yang ditandai dengan pesan "TCP ZeroWindow" di dalam capture Wireshark?**
   - A. Bandwidth jaringan upstream habis terpakai (link 100% saturated).
   - B. Aplikasi di sisi host penerima tidak mengambil data dari receive buffer socket OS, sehingga window buffer penuh.
   - C. Router di jalur perantara memotong ukuran paket MTU.
   - D. Koneksi TCP ditutup secara paksa oleh firewall perimeter.

5. **Perintah Linux `tc` berikut: `tc qdisc add dev eth0 root netem loss 10%` berfungsi untuk:**
   - A. Menurunkan kecepatan bandwidth kartu jaringan sebesar 10 persen.
   - B. Menginjeksi simulasi packet drop probabilistik sebesar 10% pada egress traffic interface eth0.
   - C. Membatasi alokasi CPU networking kernel sebesar 10%.
   - D. Menolak 10% koneksi TCP handshake yang masuk.

---

## II. Intermediate Questions

1. **Jelaskan siklus hidup (*lifecycle*) sebuah flow di dalam cache NetFlow/IPFIX router: apa yang membedakan trigger `active timeout` dengan `inactive timeout`?**
2. **Mengapa pemblokiran seluruh traffic ICMP pada firewall interface edge dapat menyebabkan kegagalan koneksi TLS handshake aplikasi (MTU Black Hole)? Jelaskan mekanisme Path MTU Discovery (PMTUD) yang terpengaruh.**
3. **Bagaimana protokol BFD (Bidirectional Forwarding Detection) membantu routing dinamis (misal: BGP) mencapai sub-second failover konvergensi saat physical carrier link tidak mengalami down secara mekanikal (*silent failure*)?**
4. **Pada analisis Wireshark, apa interpretasi Anda jika menemukan urutan paket: `TCP Dup ACK` yang berulang diikuti oleh `Fast Retransmission` dari sisi server?**
5. **Sebutkan minimal 3 metrik kuantitatif terpenting yang wajib dipantau pada switch ASIC buffer architecture untuk memprediksi degradasi performa sebelum paket benar-benar di-drop secara fisik.**

---

## III. Scenario-Based Questions

### Kasus 1: Anomali Transaksi FinTech "Misteri Jam Sibuk"
Sebuah bank digital mengalami kegagalan pada 3% transaksi API payment gateway mereka setiap hari kerja antara pukul 11:45 hingga 12:15 WIB. 
- Alerting aplikasi mencatat HTTP `504 Gateway Timeout`.
- Dashboard utilisasi bandwidth interface router (yang ditarik via SNMP 5 menit) hanya menunjukkan utilisasi maksimal 42%.
- Tim network mengklaim link "sehat dan tidak ada masalah bandwidth".
- Pertanyaan:
  1. Buktikan mengapa data utilisasi 42% SNMP tersebut menyesatkan (*misleading*).
  2. Rancang metode investigasi menggunakan command line interface (CLI) Linux / packet capture dan metric telemetry granular apa yang harus diaktifkan pada top-of-rack switch untuk membuktikan akar masalah sesungguhnya.

### Kasus 2: Insiden Failover BGP Cloud Direct-Connect yang Gagal
Sebuah perusahaan e-commerce memiliki koneksi hybrid cloud redundant:
- Link A: Dedicated Cloud Interconnect (10 Gbps, BGP eBGP Primary).
- Link B: Backup IPsec VPN over Internet (1 Gbps, BGP eBGP Secondary).
Ketika serat optik Link A terputus secara fisik 50 km dari data center (di sisi ISP provider), router data center lokal tidak mendeteksi physical link loss (interface tetap `UP/UP` karena terhubung ke intermediate DWDM transponder lokal). 
- Pengalihan traffic ke Link B memakan waktu 175 detik. Selama rentang waktu ini, seluruh transaksi customer terputus total.
- Pertanyaan:
  1. Analisis mengapa failover membutuhkan waktu ~180 detik. Timer spesifik apa pada protokol BGP yang menyebabkan latensi ini?
  2. Berikan rekomendasi konfigurasi arsitektur dan parameter protokol yang presisi agar *failover detection* turun menjadi di bawah 1 detik tanpa membebani CPU router secara berlebihan.

### Kasus 3: Debugging Zero Window dan Connection Stalling
Pada investigasi lambatnya transfer backup database antar-datacenter (kapasitas link 10 Gbps, Round Trip Time = 40ms):
- Analisis capture packet menunjukkan server pengirim berhenti mentransmisikan data selama ratusan milidetik secara periodik.
- Field capture menunjukkan server target berulang kali mengiklankan `TCP Window Size: 0`, kemudian setelah beberapa saat mengirimkan `TCP Window Update`.
- Pertanyaan:
  1. Apa akar masalah pada server penerima (target database)? Apakah masalah ini berada pada Layer 2/3 jaringan atau Layer 4/Host System?
  2. Parameter kernel Linux sysctl apa saja yang harus dianalisis dan dituning pada kedua host untuk mengatasi masalah throughput ini?

---

## IV. Practical Chapter Challenge: Resilient Fabric Automation & Chaos Validation

### Deskripsi Skenario
Anda adalah Lead Network Reliability Engineer untuk sebuah platform Core Banking. Anda diminta membangun testbed validasi ketahanan (*resilience testbed*) dan sistem observabilitas otomatis dengan kriteria berikut:

### Persyaratan Arsitektur
1. **Network Topology & Telemetry**:
   - Konfigurasikan topologi berbasis Linux Network Namespaces yang menyimulasikan 2 Host (`client` dan `server`) dan 2 Intermediate Transit Gateway (`gw-primary` dan `gw-secondary`).
   - Implementasikan skrip Python standalone collector (`hands-on/m01/netflow_collector_analyzer.py`) yang mendengarkan paket UDP flow export, mengagregasikan flow 5-tuple, dan mendeteksi anomali spikes/drop secara real-time.
2. **Chaos Resiliency Injection**:
   - Buat script otomatisasi berbasis `tc` (Linux Traffic Control) yang menyimulasikan:
     - Fase 1: Baseline kondisi ideal (RTT < 2ms, Loss 0%).
     - Fase 2: Degradasi intermiten (Latency 80ms, Jitter 20ms, Loss 3%).
     - Fase 3: Total blackout / link failure pada `gw-primary`.
3. **Automated Triage Runbook Verification**:
   - Dokumentasikan file runbook langkah per langkah yang memvalidasi bahwa sistem pemantau Anda berhasil mendeteksi kegagalan tersebut dalam waktu < 5 detik dan memverifikasi data packet loss menggunakan capture filter `tcpdump`.