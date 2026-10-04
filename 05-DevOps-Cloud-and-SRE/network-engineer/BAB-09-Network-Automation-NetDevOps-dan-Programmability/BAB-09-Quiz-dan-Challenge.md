# BAB 09: Quiz & Challenge - Network Automation, NetDevOps, dan Programmability

## 1. Basic Questions (5 Soal Pilihan Ganda)

### Soal 1
Perbedaan fundamental antara pendekatan *CLI Scraping* konvensional dengan *Model-Driven Programmability* berbasis RESTCONF/NETCONF adalah:
- A. CLI scraping tidak membutuhkan koneksi jaringan, sedangkan RESTCONF membutuhkan koneksi serial.
- B. CLI scraping bergantung pada parsing teks tidak terstruktur yang rentan terhadap perubahan format output, sedangkan Model-Driven Programmability beroperasi pada skema data terstruktur yang tervalidasi via model YANG.
- C. RESTCONF/NETCONF hanya dapat diterapkan pada sistem operasi Linux server, bukan pada perangkat jaringan enterprise.
- D. CLI scraping mendukung transaksi atomik secara native pada seluruh vendor jaringan, sedangkan NETCONF tidak mendukung rollback.

### Soal 2
Protokol NETCONF beroperasi secara standar pada layer transport SSH menggunakan port default:
- A. TCP 22
- B. TCP 443
- C. TCP 830
- D. TCP 8080

### Soal 3
Dalam pemodelan data YANG (RFC 6020/7950), node data yang digunakan untuk menyimpan nilai skalar tunggal tanpa hierarki anak (child node) disebut:
- A. `container`
- B. `list`
- C. `leaf`
- D. `rpc`

### Soal 4
Ketika melakukan deployment konfigurasi menggunakan pustaka NAPALM, metode yang digunakan untuk membandingkan perbedaan (*diff*) antara konfigurasi yang sedang aktif dengan kandidat konfigurasi baru sebelum diterapkan adalah:
- A. `napalm.merge_config()`
- B. `napalm.compare_config()`
- C. `napalm.get_diff()`
- D. `napalm.validate_candidate()`

### Soal 5
Pada protokol RESTCONF (RFC 8040), HTTP verb yang paling tepat digunakan untuk memperbarui sebagian (*partial update*) dari sebuah resource konfigurasi yang ada tanpa menghapus elemen lain di tingkat hierarki yang sama adalah:
- A. `GET`
- B. `POST`
- C. `PATCH`
- D. `DELETE`

---

## 2. Intermediate Questions (5 Soal Pemahaman Teknis Mendalam)

### Soal 1
Jelaskan perbedaan arsitektur dan siklus hidup antara datastore `<running/>`, `<startup/>`, dan `<candidate/>` pada implementasi protokol NETCONF! Bagaimana mekanisme `<confirmed-commit>` melindungi *network administrator* dari insiden terputusnya akses (*loss of management access*) saat mengonfigurasi perangkat jarak jauh?

### Soal 2
Perhatikan potongan template Jinja2 berikut:
```jinja2
{% for vlan in vlans if vlan.id >= 100 %}
vlan {{ vlan.id }}
 name {{ vlan.name | default('VLAN_' ~ vlan.id) | upper }}
 state active
!
{% endfor %}
```
Jika diberikan input data YAML:
```yaml
vlans:
  - id: 10
    name: mgmt
  - id: 100
  - id: 105
    name: voice_zone
```
Tuliskan teks konfigurasi CLI akhir yang dihasilkan secara presisi!

### Soal 3
Jelaskan secara teknis mengapa pustaka *Scrapli* atau integrasi AsyncIO pada Python memiliki performa throughput eksekusi perintah CLI yang jauh lebih tinggi dibandingkan pendekatan sequential standar menggunakan *Netmiko* tradisional saat berhadapan dengan ratusan perangkat switch!

### Soal 4
Apa perbedaan mendasar antara model data *OpenConfig* dan *Vendor Native YANG Models* (misalnya Cisco Native atau Junos YANG)? Jelaskan implikasi trade-off dari memilih OpenConfig dibandingkan Vendor Native dalam arsitektur otomatisasi jaringan multi-vendor!

### Soal 5
Dalam pipeline CI/CD NetDevOps, apa peran tools analisis data-plane statis seperti **Batfish**? Bagaimana cara kerjanya mendeteksi *forwarding loop* atau kegagalan ACL sebelum konfigurasi di-commit ke perangkat jaringan fisik yang sedang melayani trafik produksi?

---

## 3. Scenario-Based Questions (3 Kasus Nyata Industri)

### Skenario 1: Kegagalan Transaksi Atomik RESTCONF di Datacenter Fabric
Sebuah tim otomasi jaringan menjalankan pipeline Python untuk memperbarui parameter MTU dan BGP peering di seluruh border leaf switch menggunakan RESTCONF PATCH request. Pada switch ke-12, koneksi HTTP RESTCONF mengembalikan kode status `HTTP 400 Bad Request` dengan error payload:
```json
{
  "errors": {
    "error": [
      {
        "error-type": "application",
        "error-tag": "invalid-value",
        "error-path": "/ietf-interfaces:interfaces/interface[name='TenGigabitEthernet0/0/1']/ietf-ip:ipv4/address",
        "error-message": "IP address conflict with existing subnet in VRF: TENANT_PROD"
      }
    ]
  }
}
```
Akibat kegagalan ini, konfigurasi MTU yang dikirimkan pada langkah terpisah sebelumnya tetap terpasang, menyebabkan deviasi status (*partial state mismatch*). 
- **Pertanyaan**: 
  1. Mengapa skenario di atas menunjukkan kelemahan penggunaan request RESTCONF granular yang terpisah-pisah dibandingkan NETCONF edit-config candidate datastore?
  2. Bagaimana Anda merancang ulang arsitektur payload dan pemanggilan RESTCONF/NETCONF agar modifikasi MTU dan subnet IP bersifat atomik (*all-or-nothing*)?

### Skenario 2: BGP Configuration Drift Pasca Insiden Severity-1
Pada tengah malam terjadi gangguan routing BGP antardatacenter. Insinyur on-call melakukan login darurat via CLI manual dan menerapkan *workaround* berupa route-map ad-hoc langsung pada running configuration perangkat switch Core-01. Pagi harinya, pipeline CI/CD Ansible harian yang berjalan secara terjadwal mengeksekusi playbook sinkronisasi dengan status `state: overridden`.
- **Dampak**: Seluruh rute *workaround* terhapus seketika, menyebabkan pemadaman jaringan (*outage*) berulang pada layanan transaksi perbankan.
- **Pertanyaan**:
  1. Identifikasi kegagalan alur kerja operasional (*governance failure*) yang terjadi pada integrasi tim operasi manual dan pipeline GitOps.
  2. Rancang strategi integrasi NetDevOps yang mencakup deteksi *configuration drift* sebelum pipeline commit dijalankan, serta bagaimana mekanisme *drift reconciliation* seharusnya ditangani tanpa merusak stabilitas produksi.

### Skenario 3: Penanganan Timeout dan Semaphore Locking pada NETCONF Concurrency
Sebuah platform manajemen cloud internal memicu 5 microservices berbeda yang mencoba memperbarui konfigurasi Access Control List (ACL) pada satu router core Cisco ASR via NETCONF secara bersamaan (konkuren). Akibatnya, 4 dari 5 microservices mengalami kegagalan dengan error RPC:
`<error-tag>in-use</error-tag><error-message>Lock failed, resource already locked by another session</error-message>`.
- **Pertanyaan**:
  1. Jelaskan arsitektur locking pada candidate datastore NETCONF dan batasan konkurensinya.
  2. Rancang pola arsitektur software (misalnya message queue, distributed locking, retry back-off) pada level orkestrator untuk mengelola transaksi konkuren ke satu target perangkat jaringan secara deterministik!

---

## 4. Practical Chapter Challenge
### Deskripsi Tantangan
Anda ditunjuk sebagai Lead NetDevOps Engineer untuk membangun modul otomasi audit dan provisioning zero-touch compliance untuk edge gateway multi-vendor. 

### Kriteria Keberhasilan Tugas:
1. Bangun skrip Python modular mandiri yang memiliki kapabilitas:
   - Terkoneksi secara terprogram ke perangkat via SSH (Netmiko) dan abstraksi API (NAPALM).
   - Menghasilkan konfigurasi dynamic BGP dan interface menggunakan mesin templat Jinja2 berdasarkan file variabel inventory YAML terpisah.
   - Melakukan parsing status operasional terkini (Interface state, ARP table, BGP summary) dan mengonversinya menjadi dictionary Python terstruktur tanpa ketergantungan pada output CLI teks murni.
   - Menjalankan audit kepatuhan (*compliance check*): Jika NTP server atau DNS server pada perangkat tidak sesuai dengan standar Source of Truth, skrip harus menghasilkan unified diff dan menerbitkan peringatan ke konsol atau log audit tanpa merusak status running perangkat (*dry-run execution*).
2. Kode harus memenuhi kaidah Clean Code: penanganan exception terisolasi, logging terstruktur, tidak ada plain-text password (*environment variable/safe handling*), serta exit code Linux standar (0 untuk sukses, non-zero untuk failure).

---

## Jawaban & Panduan Solusi Quiz

### Kunci Jawaban Basic Questions
1. **B** - CLI scraping bergantung pada regex/string parsing yang mudah rusak saat format CLI berubah, sementara API terstruktur berbasis YANG memiliki validasi skema ketat.
2. **C** - RFC 6241 mengalokasikan TCP port 830 untuk NETCONF over SSH.
3. **C** - Dalam YANG, `leaf` merepresentasikan data skalar tunggal.
4. **B** - `compare_config()` menampilkan unified diff antara active configuration dan candidate.
5. **C** - HTTP `PATCH` digunakan untuk partial update dalam RESTCONF, sedangkan `PUT` menggantikan target resource seutuhnya.

### Panduan Solusi Intermediate Questions (Poin-Poin Kunci)
1. **NETCONF Datastores**: `<running/>` menyimpan konfigurasi aktif data plane. `<startup/>` adalah konfigurasi di NVRAM yang dimuat saat reboot. `<candidate/>` adalah area scratchpad di mana perubahan dapat disusun, di-diff, dan divalidasi sebelum diaplikasikan ke running. `<confirmed-commit>` secara otomatis me-rollback perubahan ke status sebelumnya jika sesi klien terputus sebelum konfirmasi definitif (`<commit/>`) dikirim dalam batas waktu tertentu, melindungi engineer dari kehilangan kontrol akses router.
2. **Output Jinja2**:
```text
vlan 100
 name VLAN_100
 state active
!
vlan 105
 name VOICE_ZONE
 state active
!
```
*(Catatan: VLAN 10 diskip karena kondisi `if vlan.id >= 100`, nama VLAN 100 menggunakan default karena kosong, dan nama VLAN 105 dikonversi ke uppercase).*
3. **Scrapli/AsyncIO vs Netmiko**: Netmiko beroperasi secara synchronous blocking (menunggu I/O per perangkat selesai sebelum beralih ke node berikutnya). Scrapli memanfaatkan non-blocking asynchronous event loops (asyncio), memungkinkan satu thread Python menangani ratusan soket TCP/SSH secara bersamaan (*concurrent multiplexing*) tanpa terhambat oleh latensi respons terminal perangkat.
4. **OpenConfig vs Vendor Native**: OpenConfig menyediakan satu model data konsisten yang dapat diimplementasikan lintas vendor (Cisco, Arista, Juniper), mempermudah otomasi multi-vendor. Namun, OpenConfig adalah subset penyebut umum terendah (*lowest common denominator*); fitur-fitur mutakhir proprietary vendor seringkali tidak terakomodasi dalam model OpenConfig dan hanya dapat diakses melalui Vendor Native YANG.
5. **Batfish Analysis**: Batfish mengurai file konfigurasi vendor menjadi model vendor-independent AST (Abstract Syntax Tree), lalu membangun graph representasi control plane (RIB/FIB simulation). Batfish dapat membuktikan secara matematis jangkauan paket (*reachability query*), mendeteksi cyclic forwarding (*loops*), dan kebocoran rute tanpa membutuhkan booting perangkat virtual atau menyentuh perangkat produksi.