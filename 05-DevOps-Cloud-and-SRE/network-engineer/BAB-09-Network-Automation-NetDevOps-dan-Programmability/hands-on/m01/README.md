# Panduan Hands-On: Network Automation, NetDevOps, dan Programmability (m01)

Panduan ini mendemonstrasikan implementasi otomasi jaringan hybrid (*Jinja2 template rendering*, *NAPALM configuration auditing & diffing*, serta *Netmiko CLI command execution*) menggunakan arsitektur Python modern.

---

## 1. Topologi & Kebutuhan Lab

### Prasyarat Perangkat Lunak
- Python 3.9+ 
- Virtualenv (`python3 -m venv`)
- Target Router (Pilih salah satu):
  - **Opsi A (Emulasi Nyata)**: Cisco CSR1000v / Cisco IOSv / Cisco C8000v berjalan di Containerlab / EVE-NG / GNS3.
  - **Opsi B (Docker SSH Mock Terminal)**: Container SSH sederhana yang menerima perintah Cisco dasar untuk pengujian lokal.

---

## 2. Struktur Direktori Lab
```
hands-on/m01/
├── README.md
├── netmiko_napalm_config_audit.py
└── requirements.txt (opsional dibuat lokal)
```

---

## 3. Langkah Instalasi Lingkungan Virtual

Jalankan perintah berikut pada terminal Linux / macOS Anda:

```bash
# 1. Navigasi ke direktori lab
cd hands-on/m01

# 2. Buat virtual environment lokal
python3 -m venv venv

# 3. Aktifkan virtual environment
source venv/bin/activate

# 4. Install dependensi otomasi jaringan
pip install --upgrade pip
pip install netmiko napalm jinja2 requests ncclient
```

---

## 4. Konfigurasi Variabel Lingkungan (*Environment Variables*)

Skrip `netmiko_napalm_config_audit.py` dirancang untuk membaca variabel lingkungan secara dinamis untuk menghindari *hardcoded credentials*:

| Variabel | Deskripsi | Default |
| :--- | :--- | :--- |
| `TARGET_DEVICE_IP` | Alamat IP perangkat jaringan / router target | `127.0.0.1` |
| `TARGET_DEVICE_PORT` | Port SSH perangkat target | `2222` |
| `TARGET_DEVICE_USER` | Username login administrative | `admin` |
| `TARGET_DEVICE_PASS` | Password login administrative | `cisco123` |
| `TARGET_DEVICE_SECRET` | Password privilese enable (`enable secret`) | `cisco123` |
| `NETDEVOPS_EXECUTE_LIVE`| Mode eksekusi (`0` = Dry-run / Diff only, `1` = Live Commit) | `0` |
| `FORCE_NETMIKO_INSPECT` | Memaksa fallback audit Netmiko dijalankan | `1` |

---

## 5. Menjalankan Skrip Otomasi

### Skenario 1: Menjalankan Audit Kepatuhan & Unified Diff (*Dry-Run Mode*)
Mode default bersifat aman (*read-only/dry-run*). Skrip akan merender konfigurasi, menghubungkan NAPALM ke target, dan menampilkan diff jika ada konfigurasi yang belum sesuai:

```bash
export TARGET_DEVICE_IP="192.168.122.100"
export TARGET_DEVICE_PORT="22"
export TARGET_DEVICE_USER="cisco"
export TARGET_DEVICE_PASS="cisco123"
export TARGET_DEVICE_SECRET="cisco123"
export NETDEVOPS_EXECUTE_LIVE="0"

python netmiko_napalm_config_audit.py
```

### Skenario 2: Menerapkan Perubahan Konfigurasi Secara Permanen (*Live Commit Mode*)
Jika diff yang ditampilkan pada Skenario 1 telah diverifikasi dan siap dideploy:

```bash
export NETDEVOPS_EXECUTE_LIVE="1"

python netmiko_napalm_config_audit.py
```

---

## 6. Verifikasi & Analisis Hasil Output
1. **Rendering Template**: Skrip akan mencetak hasil kompilasi *Jinja2* yang memvalidasi bahwa IP DNS, server NTP, dan konfigurasi antarmuka telah digabungkan dengan benar.
2. **Unified Diff Output**:
   ```diff
   --- 
   +++ 
   @@ -15,3 +15,5 @@
   +ip name-server 10.10.10.10
   +ip name-server 10.10.20.10
   +ntp server 172.16.0.1 prefer
   ```
3. **Idempotensi**: Jalankan skrip kedua kali dalam mode live commit (`NETDEVOPS_EXECUTE_LIVE="1"`). Amati bahwa skrip melaporkan: `Perangkat sudah sesuai status desired state. Tidak ada perubahan yang diperlukan (Idempotent)`.

---

## 7. Troubleshooting Umum
- **Error `NetmikoAuthenticationException`**: Periksa kembali kecocokan password dan pastikan user memiliki privilege level 15 pada router Cisco (`username admin privilege 15 secret cisco123`).
- **Connection Refused / Port Timeout**: Pastikan service SSH pada router target sudah aktif:
  ```text
  Router(config)# crypto key generate rsa modulus 2048
  Router(config)# ip ssh version 2
  Router(config)# line vty 0 4
  Router(config-line)# transport input ssh
  Router(config-line)# login local
  ```
- **Error NAPALM Driver Not Implemented**: Pastikan parameter driver sesuai dengan sistem operasi target (`ios`, `eos`, `junos`, atau `nxos_ssh`).