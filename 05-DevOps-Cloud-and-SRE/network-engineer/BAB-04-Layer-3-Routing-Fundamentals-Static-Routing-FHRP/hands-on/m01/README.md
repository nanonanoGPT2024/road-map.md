# Panduan Hands-on Lab: Modul 01 - Layer 3 Routing & VRRP Failover

Dokumen ini memandu Anda menjalankan simulasi interaktif Finite State Machine (FSM) **Virtual Router Redundancy Protocol (VRRP)** sesuai standar RFC 5798 dan mekanisme Interface Tracking pada modul pembelajaran Bab 04.

---

## 1. Tujuan Lab
- Memahami transisi status internal protokol FHRP (`INITIALIZE`, `BACKUP`, `MASTER`).
- Mengamati bagaimana **Skew Time** dan **Master Down Interval** dihitung berdasarkan formula matematika RFC.
- Memverifikasi mekanisme **Object Tracking Decrement**: bagaimana penurunan status link uplink WAN menurunkan priority router Master dan memicu **Preemption** pada router Backup.
- Menguji mitigasi failback saat node primer pulih.

---

## 2. Struktur Lab
Lab ini menggunakan simulator berbasis threading Python (`vrrp_failover_simulation.py`) murni tanpa ketergantungan library pihak ketiga. Script ini memodelkan:
1. `VirtualRouter`: Mengimplementasikan FSM VRRP, thread scheduler pengiriman paket advertisement, dan timer evaluasi status.
2. `VirtualNetworkBus`: Mengemulasikan media broadcast domain Layer 2 Ethernet lokal yang mendistribusikan frame multicast advertisement antar router.

---

## 3. Langkah Menjalankan Hands-on

### Prasyarat
- Python versi 3.8 atau yang lebih baru.
- Terminal / Bash Console (Linux, macOS, atau Windows WSL / PowerShell).

### Eksekusi Program
1. Buka terminal dan arahkan ke direktori hands-on:
   ```bash
   cd hands-on/m01
   ```

2. Berikan izin eksekusi pada skrip (khusus Linux/macOS):
   ```bash
   chmod +x vrrp_failover_simulation.py
   ```

3. Jalankan simulasi:
   ```bash
   python3 vrrp_failover_simulation.py
   ```

---

## 4. Skenario Pengujian Praktis

Setelah program berjalan, Anda akan disajikan prompt CLI interaktif: `vrrp-sim>`. Lakukan langkah pengujian berikut:

### Skenario A: Baseline State Validation
- Amati log saat inisialisasi:
  - `R1-Primary` (Priority 110) akan segera mempromosikan dirinya menjadi **MASTER** dan membroadcast Gratuitous ARP untuk VIP `192.168.10.1`.
  - `R2-Backup` (Priority 100) menghitung Skew Time dan menetapkan dirinya sebagai **BACKUP**.
- Ketik perintah `s` untuk memeriksa status cluster:
  - Pastikan R1 berstatus `MASTER` dan R2 berstatus `BACKUP`.

### Skenario B: WAN Uplink Failure & Dynamic Preemption Failover
1. Ketik perintah `1` lalu tekan Enter.
2. Amati urutan kejadian pada console log:
   - Interface WAN R1 dimatikan.
   - Tracking engine