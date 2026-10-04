# Kurikulum Keamanan Siber Enterprise: Identitas, Akses & Pengerasan Host

---

## 1. Identitas Modul

*   **Track:** Cyber Security Engineering & Infrastructure Defense
*   **Kategori:** 07-Quality-and-Security
*   **Bab:** 03 - Identity, Access & Host Hardening
*   **Modul:** 01 - Arsitektur Active Directory, Kerberos Internals, Privileged Access Management (PAM), dan CIS Baseline Hardening
*   **Tingkat Kerumitan:** Lanjutan (Advanced) / Spesialis Keamanan Tingkat Atas
*   **Prasyarat:** Pemahaman mendalam tentang TCP/IP, OSI Stack, Kriptografi Simetris/Asimetris (AES, RSA, HMAC), Arsitektur Sistem Operasi Linux (Kernel, SUID, POSIX Capabilities, PAM subsystem), serta Arsitektur Windows Server (NTFS, SAM, LSASS, RPC, Registry).
*   **Estimasi Waktu Penyelesaian:** 16 Jam (Materi Teori, Analisis Kode, Lab Implementasi, dan Bedah Insiden)

---

## 2. Learning Objectives (LO)

Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:

*   **LO-01:** Menganalisis topologi enterprise Active Directory Domain Services (AD DS) dan relasi trust lintas-forest untuk memetakan jalur transmisi identitas terotentikasi.
*   **LO-02:** Menguraikan secara kriptografis protokol autentikasi Kerberos v5 (AS-REQ/REP, TGS-REQ/REP, AP-REQ/REP), struktur Privilege Attribute Certificate (PAC), dan fungsi KDC (Key Distribution Center).
*   **LO-03:** Merekonstruksi mekanisme serangan pemalsuan tiket identitas (*Golden Ticket* dan *Silver Ticket*), membedakan vektor injeksi PAC, serta menerapkan validasi PAC berbasis RPC (*PAC Validation*).
*   **LO-04:** Merancang arsitektur Privileged Access Management (PAM) enterprise berbasis prinsip *Just-In-Time* (JIT), *Just-Enough-Administration* (JEA), dan Enterprise Access Model (Tier 0, Tier 1, Tier 2).
*   **LO-05:** Mendeteksi dan memitigasi vektor ekskalasi hak akses (*Privilege Escalation*) pada Windows (Unquoted Service Paths, SeImpersonatePrivilege, DLL Hijacking) dan Linux (SUID abuse, Capabilities, Sudoers misconfigurations).
*   **LO-06:** Mengembangkan dan mengotomatisasi skrip audit konfigurasi sesuai Center for Internet Security (CIS) Benchmarks Level 1 dan Level 2 pada sistem operasi Windows Server dan Linux Enterprise (RHEL/Debian).
*   **LO-07:** Mengoperasikan investigasi forensik terhadap artefak LSASS (*Local Security Authority Subsystem Service*) memory dump dan Windows Security Event Logs terkait indikasi anomali tiket Kerberos.
*   **LO-08:** Merancang tata kelola siklus hidup kredensial krusial enterprise, termasuk prosedur *Dual-Rotation* akun `krbtgt`, gMSA (*Group Managed Service Accounts*), dan integrasi LAPS (*Local Administrator Password Solution*).

---

## 3. Concept Map & Architecture Diagram

Berikut adalah arsitektur aliran autentikasi Active Directory Kerberos v5, interaksi KDC, divergensi serangan tiket, dan perimeter pemisahan host hardening:

```
[ IDENTITAS & INFRASTRUKTUR ACTIVE DIRECTORY ]
  +-----------------------------------------------------------------------------------+
  |                                Domain Controller (DC)                             |
  |  +-----------------------------------------------------------------------------+  |
  |  |                     Key Distribution Center (KDC)                           |  |
  |  |  +--------------------------------+     +--------------------------------+  |  |
  |  |  |  Authentication Service (AS)  |     | Ticket Granting Service (TGS)  |  |  |
  |  |  +--------------------------------+     +--------------------------------+  |  |
  |  +-----------------------------------------------------------------------------+  |
  |  | NTDS.dit Database: KRBTGT Hash, Machine Hashes, User Credentials            |  |
  |  +-----------------------------------------------------------------------------+  |
  +-----------------------------------------------------------------------------------+
              ^ (1) AS-REQ        | (2) AS-REP          ^ (3) TGS-REQ     | (4) TGS-REP
              | [Pre-Auth Enc]   | [TGT + SessKey]     | [TGT + Auth]    | [Service Ticket]
              v                  v                     v                 v
  +----------------------------------------+       +----------------------------------+
  |             Klien Peminta              |       |         Target Service Host      |
  |        (Workstation / Endpoint)        |       |        (e.g., CIFS, MSSQL, IIS)  |
  |  +----------------------------------+  |       |  +----------------------------+  |
  |  | LSASS.exe Cache: TGT & SessionKey|  |       |  | Service Principal Name(SPN)|  |
  |  +----------------------------------+  | (5)   |  +----------------------------+  |
  |                                        | AP-REQ|  | CIS Hardened Baseline:    |  |
  |  * VEKTOR ANCAMAN:                     |------>|  | - SMB Signing Mandatory    |  |
  |    - Golden Ticket -> Bypass KDC       |       |  | - Kerberos Armoring (FAST) |  |
  |      (Membutuhkan KRBTGT AES/NTLM)     |       |  | - Credential Guard Active  |  |
  |    - Silver Ticket -> Bypass KDC       |       |  +----------------------------+  |
  |      (Membutuhkan Service Account Key) |                                          |
  +----------------------------------------+                                          |
                                                                                      |
  [ PERIMETER PRIVILEGED ACCESS MANAGEMENT (PAM) & TIERING MODEL ]                    |
  +--------------------------------------------------------------------------------+  |
  | Tier 0: Domain Controller, PKI, Identity Providers, PAW (Privileged Workstation)|  |
  | Tier 1: Enterprise Servers, Database Clusters, Storage, Hypervisors            |  |
  | Tier 2: End-User Devices, Workstations, Mobile, Printers                       |  |
  +--------------------------------------------------------------------------------+--+
```

---

## 4. Mengapa Ini Penting (Why & Business / Security Impact)

Identitas adalah perimeter keamanan utama (*identity is the new perimeter*) dalam arsitektur komputasi modern. Kegagalan tata kelola identitas dan perizinan sistem operasi menyebabkan keruntuhan total isolasi keamanan (*defense-in-depth*).

### Dampak Keamanan (Security Impact)
1. **Compromise Total Forest Active Directory:** Apabila kunci simetris akun `krbtgt` bocor, penyerang dapat mengeksekusi serangan *Golden Ticket*. Ini memberikan kapabilitas untuk membuat tiket autentikasi secara independen (*offline*) tanpa menghubungi Domain Controller, menunjuk diri sendiri sebagai anggota grup `Enterprise Admins`, dan mempertahankan persistensi tanpa terikat pada perubahan kata sandi akun individual pengguna.
2. **Penyebaran Lateral Cepat (*Lateral Movement blast radius*):** Penyerang yang memperoleh akses tingkat rendah pada satu workstation (Tier 2) dapat mengeksploitasi *misconfiguration* hak akses lokal (Privilege Escalation), mengekstrak kredensial dari memori `LSASS.exe`, dan melompat ke server produksi (Tier 1) atau Domain Controller (Tier 0) apabila batasan sesi administratif tidak diisolasi.

### Dampak Bisnis (Business & Operational Impact)
1. **Downtime Operasional Skala Enterprise:** Pemulihan (*recovery*) lingkungan Active Directory yang telah terkompromi total memerlukan isolasi jaringan komprehensif, rekonstruksi forest (*forest recovery*), dan rotasi ganda kunci KRBTGT. Prosedur ini memakan waktu rata-rata 3 hingga 14 hari kerja dengan kerugian finansial langsung bernilai jutaan dolar akibat berhentinya rantai pasok dan operasional transaksi.
2. **Kegagalan Kepatuhan Regulasi Formal:** Standar global seperti ISO/IEC 27001 (Kontrol A.9), PCI-DSS v4.0 (Persyaratan 7 dan 8), serta SOC 2 Tipe II mewajibkan prinsip *Least Privilege*, pemisahan tugas (*Segregation of Duties*), pengawasan akses istimewa (PAM), dan audit kepatuhan konfigurasi sistem (CIS Benchmarks). Kegagalan mitigasi tiket palsu dan hak akses berlebih secara langsung mengakibatkan pencabutan lisensi operasional atau denda kepatuhan bernilai tinggi.

---

## 5. Apa Itu Konsep (What & Definisi Formal Mendalam)

### Active Directory Domain Services (AD DS)
Direktori tersentralisasi berbasis protokol X.500 dan LDAP (*Lightweight Directory Access Protocol*), menggunakan Kerberos sebagai mekanisme autentikasi utama dan DNS untuk resolusi lokasi layanan. AD DS mengelola objek hierarkis (Domains, Trees, Forests, Organizational Units) dan menerapkan kebijakan keamanan global menggunakan Group Policy Objects (GPO).

### Kerberos v5 (RFC 4120)
Protokol autentikasi pihak ketiga tepercaya (*trusted third-party*) yang berbasis kriptografi kunci simetris (*symmetric key cryptography*). Mengandalkan Key Distribution Center (KDC) yang terdiri dari dua sub-komponen: *Authentication Server* (AS) dan *Ticket Granting Server* (TGS). Kerberos menghilangkan kebutuhan pengiriman kata sandi mentah melalui jaringan dengan menggunakan *ticket* berwaktu (*timestamped tickets*).

### Privilege Attribute Certificate (PAC)
Struktur data ekstensi spesifik Microsoft (MS-PAC) yang disematkan di dalam bagian otorisasi pada tiket Kerberos. PAC memuat Security Identifier (SID) dari akun pengguna, SID dari seluruh grup keamanan yang diikutinya (*group memberships*), hak istimewa (*user rights*), serta dua tanda tangan digital kriptografis: *Server Signature* dan *KDC Signature*. PAC inilah yang menentukan hak akses nyata pada host tujuan.

### Golden Ticket vs Silver Ticket
*   **Golden Ticket:** Tiket Pemberian Tiket (*Ticket Granting Ticket* / TGT) yang dipalsukan secara kriptografis menggunakan hash NTLM atau kunci AES-256 dari akun sistem internal domain `krbtgt`. Karena KDC memvalidasi TGT hanya dengan mendekripsi data menggunakan kunci `krbtgt`, pemegang kunci ini dapat membuat TGT valid dengan masa aktif puluhan tahun dan PAC yang berisi identitas sembarang (misalnya Administrator dengan SID-500).
*   **Silver Ticket:** Tiket Layanan (*Ticket Granting Service* / TGS) yang dipalsukan menggunakan hash NTLM atau kunci AES milik akun layanan target (*service account* yang memiliki SPN terkait). Serangan ini tidak melibatkan interaksi dengan Domain Controller sama sekali, hanya berlaku untuk layanan spesifik target (misal: SMB/CIFS, MSSQL), dan jauh lebih sulit dideteksi pada log tersentralisasi KDC.

### Privileged Access Management (PAM)
Kerangka kerja tata kelola yang menggabungkan kontrol kebijakan, alur kerja operasional, dan arsitektur perangkat lunak untuk mengontrol, memantau, dan mengamankan akun yang memiliki hak administratif tingkat tinggi (seperti Domain Admins, Enterprise Admins, Root, dan Administrator Lokal). Menerapkan metode *Just-In-Time* (JIT) provisioning dan *Ephemeral Credentials*.

### CIS (Center for Internet Security) Benchmarks
Panduan standar konsensus global yang mendefinisikan konfigurasi sistem berbasis *baseline* keamanan preskriptif. Terbagi menjadi dua profil utama:
*   **CIS Level 1 Baseline:** Aturan pengerasan konfigurasi dasar yang dapat diimplementasikan secara luas dengan dampak performa minimal dan risiko degradasi fungsionalitas sistem yang sangat rendah.
*   **CIS Level 2 (Defense-in-Depth):** Aturan pengerasan tingkat lanjut untuk lingkungan dengan persyaratan keamanan kritis, mematikan subsistem warisan (*legacy*), mengisolasi port komunikasi, dan membatasi kapabilitas administratif secara ketat, yang berpotensi menurunkan kompatibilitas aplikasi non-modern.

---

## 6. Bagaimana Cara Kerjanya (How & Mekanika Internal Arsitektur)

### Mekanisme Autentikasi Kerberos v5 Langkah-demi-Langkah

```
[ Klien ]              [ KDC: AS ]             [ KDC: TGS ]          [ Target Service ]
    |                      |                        |                        |
    |----(1) AS-REQ------->|                        |                        |
    |<---(2) AS-REP--------|                        |                        |
    |                                               |                        |
    |----(3) TGS-REQ------------------------------->|                        |
    |<---(4) TGS-REP--------------------------------|                        |
    |                                                                        |
    |----(5) AP-REQ--------------------------------------------------------->|
    |<---(6) AP-REP (Opsional: Autentikasi Mutual)---------------------------|
```

1. **AS-REQ (Authentication Service Request):**
   * Pengguna menginput kredensial. Workstation menghitung kunci rahasia pengguna ($K_{user}$) menggunakan fungsi derivasi kunci (PBKDF2 atau MD4 untuk NTLM).
   * Workstation mengenkripsi stempel waktu (*timestamp*) saat ini menggunakan $K_{user}$ sebagai bukti kepemilikan kredensial tanpa mengirim kata sandi (*Pre-Authentication*, `PA-ENC-TIMESTAMP`).
   * Paket AS-REQ berisi nama prinsipal pengguna, realm, nama target KDC SPN (`krbtgt`), dan blok pre-autentikasi dikirim ke KDC melalui UDP/TCP port 88.

2. **AS-REP (Authentication Service Response):**
   * KDC mencari akun pengguna di `NTDS.dit`, mengambil $K_{user}$, dan mendekripsi `PA-ENC-TIMESTAMP`.
   * Jika selisih waktu antara mesin klien dan KDC berada di dalam batas toleransi *Clock Skew* (standar default $\le 5$ menit), pre-autentikasi dinyatakan valid.
   * KDC membuat *Logon Session Key* acak ($K_{AS-Client}$).
   * KDC menyusun Ticket Granting Ticket (TGT). TGT berisi: Identitas Klien, Masa Berlaku Tiket, $K_{AS-Client}$, dan struktur PAC yang memuat daftar SID grup pengguna. Seluruh muatan TGT dienkripsi menggunakan kunci rahasia KDC ($K_{krbtgt}$).
   * KDC menyusun paket AS-REP: Bagian pertama berisi TGT (terenkripsi $K_{krbtgt}$), dan bagian kedua berisi salinan $K_{AS-Client}$ yang dienkripsi menggunakan $K_{user}$.

3. **TGS-REQ (Ticket Granting Service Request):**
   * Workstation mendekripsi respons AS-REP menggunakan $K_{user}$, mengekstrak $K_{AS-Client}$, dan menyimpannya di memori aman LSASS.
   * Saat ingin mengakses layanan (misalnya SMB share pada server target `FS01.corp.local`), klien membentuk paket TGS-REQ.
   * Paket TGS-REQ berisi: TGT (terenkripsi $K_{krbtgt}$), Service Principal Name target (misal: `cifs/FS01.corp.local`), dan *Authenticator* baru yang berisi nama klien dan timestamp yang dienkripsi menggunakan $K_{AS-Client}$.

4. **TGS-REP (Ticket Granting Service Response):**
   * KDC menerima TGS-REQ, mendekripsi TGT menggunakan $K_{krbtgt}$, mengekstrak $K_{AS-Client}$ dan PAC internal.
   * KDC menggunakan $K_{AS-Client}$ untuk mendekripsi *Authenticator*, memverifikasi kesesuaian identitas klien dan kebaruan timestamp.
   * KDC membuat *Service Session Key* baru ($K_{Client-Service}$).
   * KDC mengambil kunci rahasia akun layanan target dari database ($K_{service}$), yang diturunkan dari kata sandi akun layanan pemilik SPN.
   * KDC menyusun *Service Ticket* (TGS Ticket). Service Ticket memuat: Identitas Klien, $K_{Client-Service}$, masa berlaku tiket, dan salinan PAC yang diperbarui. Service Ticket dienkripsi penuh menggunakan $K_{service}$.
   * KDC merespons klien dengan TGS-REP yang berisi: Service Ticket (terenkripsi $K_{service}$) dan salinan $K_{Client-Service}$ yang dienkripsi dengan $K_{AS-Client}$.

5. **AP-REQ (Application Request):**
   * Klien mendekripsi respons menggunakan $K_{AS-Client}$, mengambil $K_{Client-Service}$.
   * Klien menyusun paket AP-REQ berisi: Service Ticket (terenkripsi $K_{service}$) dan Authenticator yang dienkripsi menggunakan $K_{Client-Service}$.
   * Paket AP-REQ dikirim langsung ke port layanan target (misal: TCP port 445 untuk SMB).

6. **AP-REP (Mutual Authentication - Opsional tapi direkomendasikan):**
   * Server target mendekripsi Service Ticket menggunakan kunci rahasianya sendiri ($K_{service}$).
   * Server target mengekstrak $K_{Client-Service}$ dan membaca PAC untuk menetapkan konteks keamanan pengguna (token akses).
   * Server menggunakan $K_{Client-Service}$ untuk membaca Authenticator dan memvalidasi keaslian klien.
   * Jika autentikasi mutual diaktifkan, server merespons dengan AP-REP yang membuktikan kepada klien bahwa server tersebut benar-benar mampu membaca tiket tersebut.

---

## 7. Perbandingan Paradigma / Taksonomi Matriks

### Tabel Komparasi: Mekanisme Serangan Kredensial Tiket

| Karakteristik | Kerberoasting | AS-REP Roasting | Golden Ticket | Silver Ticket | Diamond Ticket |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Kunci Dibutuhkan** | Tidak ada awal (butuh akun domain valid) | Tidak ada (hanya butuh nama user `DoNotRequirePreAuth`) | Kunci Hash/AES Akun `krbtgt` | Kunci Hash/AES Target `Service Account` | Kunci Hash/AES Akun `krbtgt` + Akses KDC API |
| **Tiket yang Dibuat** | TGS Legitim (ekstraksi offline) | AS-REP Legitim (ekstraksi offline) | TGT Palsu (*Forged*) | TGS Palsu (*Forged*) | TGT Modifikasi KDC Legitim |
| **Interaksi Jaringan** | Interaksi langsung ke KDC (Port 88) | Interaksi langsung ke KDC (Port 88) | **Nol interaksi ke KDC** (Hanya ke host target) | **Nol interaksi ke KDC** (Hanya ke host target) | Interaksi normal ke KDC, modifikasi PAC via KDC |
| **Komponen Kriptografi Target** | Hash kata sandi SPN (RC4-HMAC / AES) | Hash kata sandi User (RC4-HMAC / AES) | Kunci Simetris `krbtgt` (AES256) | Kunci Simetris Layanan (AES/RC4) | Kunci Simetris `krbtgt` |
| **Tingkat Akses yang Dihasilkan** | Sesuai hak pemilik SPN | Sesuai hak akun tanpa Pre-Auth | Domain / Enterprise Admin Tak Terbatas | Penuh atas Server Layanan Tunggal | Domain / Enterprise Admin Tak Terbatas |
| **Deteksi Default KDC** | Event ID 4769 (TGS Request tidak wajar) | Event ID 4768 (Pre-auth type 0) | Tidak terlihat di KDC logs | Tidak terlihat di KDC logs | Sangat sulit (Event ID 4768 terbit secara sah) |

---

## 8. Analisis Mendalam Attack Surface & Vector Matrix

### Windows Host Privilege Escalation Vectors

| Vektor Serangan | Mekanisme Eksploitasi Teknis | Indikator Kerentanan | MITRE ATT&CK ID | Mitigasi Kunci |
| :--- | :--- | :--- | :--- | :--- |
| **Unquoted Service Path** | Path binary service memiliki spasi dan tidak diapit tanda kutip (`"`). Windows mengevaluasi binary berurutan (`C:\Program.exe`, `C:\Program Files\Sub.exe`). | Write access pada direktori induk path binary service. | T1574.009 | Enforce quotes pada ImagePath di Registry via GPO / script. |
| **SeImpersonatePrivilege Abuse** | Akun layanan (e.g., `NT AUTHORITY\NETWORK SERVICE`, IIS AppPool) menyalahgunakan hak impersonasi token via Named Pipe Spooler/RPC (*Potato attacks*). | Token hak akses memiliki flag `SeImpersonatePrivilege` aktif. | T1134.001 | Batasi privilege, implementasikan CIS isolation, gunakan gMSA. |
| **AlwaysInstallElevated** | Registry key mengizinkan file Windows Installer (`.msi`) berjalan dengan hak `NT AUTHORITY\SYSTEM` tanpa memandang hak user eksekutor. | Value `AlwaysInstallElevated = 1` pada HKCU dan HKLM. | T1546.016 | Set `AlwaysInstallElevated = 0` via Administrative Templates GPO. |
| **DLL Search Order Hijacking** | Aplikasi memuat modul DLL tanpa absolute path; sistem mengeksekusi pencarian berurutan yang memungkinkan penempatan payload DLL palsu. | Writable directories pada urutan pencarian DLL (Current working dir, system PATH). | T1574.001 | SafeDllSearchMode aktif, path validation, AppLocker / WDAC. |

### Linux Host Privilege Escalation Vectors

| Vektor Serangan | Mekanisme Eksploitasi Teknis | Indikator Kerentanan | MITRE ATT&CK ID | Mitigasi Kunci |
| :--- | :--- | :--- | :--- | :--- |
| **SUID/SGID Binary Abuse** | Binary dengan flag `setuid` mengabaikan batasan pengguna dan mengeksekusi instruksi di bawah konteks UID pemilik (biasanya Root). Menggunakan GTFOBins. | Flag bit `4000` aktif pada binary executable (e.g., `find`, `vim`, `bash`). | T1548.001 | Mount partisi dengan opsi `nosuid`, hilangkan bit SUID non-standar. |
| **Misconfigured Sudoers File** | Perizinan sudo tanpa kata sandi (`NOPASSWD`) untuk binary yang memiliki kapabilitas *shell breakout* atau parameter eksekusi arbitrary script. | Baris `user ALL=(ALL) NOPASSWD: /usr/bin/less` di `/etc/sudoers`. | T1548.003 | Terapkan validasi `visudo`, prinsip least privilege, audit sudo logs. |
| **Linux Capabilities Misuse** | Kapabilitas granular Linux (misal: `CAP_SETUID`, `CAP_DAC_READ_SEARCH`) diberikan langsung ke binary non-privileged. | Output dari utilitas `getcap -r / 2>/dev/null`. | T1548.001 | Minimalisasi assign capability, monitor proses via `auditd`. |
| **Shared Object Inversion (LD_PRELOAD)** | Konfigurasi sudoers mempertahankan environment variable `env_keep += LD_PRELOAD`, memungkinkan injeksi library kustom sebelum binary sistem dijalankan. | `env_keep` mengekspos environment variable dinamis linker. | T1574.006 | Pastikan opsi `always_set_home` dan sanitasi env default aktif di `sudoers`. |

---

## 9. Code Example Sederhana: Audit Unquoted Service Paths (PowerShell)

Skrip PowerShell berikut mengidentifikasi service pada Windows yang rentan terhadap eksploitasi *Unquoted Service Path* dengan memverifikasi ketiadaan tanda kutip dan keberadaan spasi pada ImagePath:

```powershell
# Inisialisasi daftar temuan
$VulnerableServices = @()

# Ambil semua service yang berjalan atau terdaftar di WMI/CIM
$Services = Get-CimInstance -ClassName Win32_Service | 
    Select-Object Name, DisplayName, PathName, StartMode, State

foreach ($Service in $Services) {
    $Path = $Service.PathName
    
    # Abaikan entri kosong atau path yang menunjuk ke system32 default
    if ([string]::IsNullOrWhiteSpace($Path)) { continue }
    
    # Normalisasi path untuk mengabaikan parameter argumen CLI
    $CleanPath = $Path.Trim()
    
    # Cek apakah path mengandung spasi DAN TIDAK diawali dengan tanda kutip ganda
    if ($CleanPath -match '^[a-zA-Z]:\\([^\\]+\\)+[^\.]+\s[^\.]+\.[a-zA-Z0-9]+' -and -not ($CleanPath.StartsWith('"'))) {
        $VulnerableServices += [PSCustomObject]@{
            ServiceName = $Service.Name
            DisplayName = $Service.DisplayName
            RawPath     = $Path
            StartMode   = $Service.StartMode
            State       = $Service.State
        }
    }
}

# Tampilkan representasi data audit
if ($VulnerableServices.Count -gt 0) {
    Write-Warning "Ditemukan $($VulnerableServices.Count) service dengan Unquoted Path:"
    $VulnerableServices | Format-Table -AutoSize
} else {
    Write-Host "[OK] Tidak ditemukan service yang rentan terhadap Unquoted Service Path." -ForegroundColor Green
}
```

---

## 10. Code Example Lanjutan: Forensic PAC Signature & Ticket Anomaly Detector

Skrip automasi analitik tingkat lanjut untuk mendeteksi potensi pemalsuan tiket Kerberos (*Golden/Silver Ticket*) melalui pemantauan Windows Security Event Log. Skrip ini melacak inkonsistensi durasi masa berlaku tiket (misalnya tiket dengan masa aktif $> 10$ jam default domain) serta anomali grup privilise pada Event ID 4672 dan 4768.

```powershell
<#
.SYNOPSIS
    KerberosTicketAnomalyDetector.ps1
    Menganalisis Event Log Keamanan Windows untuk mendeteksi tanda anomali tiket Kerberos.
.DESCRIPTION
    Skrip ini melakukan scanning mendalam pada Security Event Log:
    - Event ID 4768: Kerberos TGT Request (Memeriksa masa berlaku tiket abnormal / Golden Ticket).
    - Event ID 4769: Kerberos Service Ticket Request (Deteksi brute-force enkripsi RC4 / Kerberoasting).
    - Event ID 4624/4672: Log Masuk & Hak Istimewa Khusus (Deteksi anomali SID injection).
#>

[CmdletBinding()]
param (
    [int]$HoursToAnalyze = 24,
    [int]$MaxTicketDurationHours = 10
)

$StartTime = (Get-Date).AddHours(-$HoursToAnalyze)
Write-Host "[*] Memulai audit integritas tiket Kerberos sejak: $StartTime" -ForegroundColor Cyan

# 1. Deteksi Indikasi Golden Ticket (Durasi Masa Aktif Tiket Tidak Wajar pada TGT)
$FilterExplicit = @{
    LogName   = 'Security'
    Id        = 4768
    StartTime = $StartTime
}

try {
    $TgtEvents = Get-WinEvent -FilterHashtable $FilterExplicit -ErrorAction Stop
    Write-Host "[*] Menganalisis $($TgtEvents.Count) event TGT Request (Event 4768)..."
    
    foreach ($Event in $TgtEvents) {
        $Xml = [xml]$Event.ToXml()
        $Data = $Xml.Event.EventData.Data
        
        $TargetUserName = ($Data | Where-Object { $_.Name -eq 'TargetUserName' }).'#text'
        $EndTimeString  = ($Data | Where-Object { $_.Name -eq 'EndTime' }).'#text'
        $TicketOptions  = ($Data | Where-Object { $_.Name -eq 'TicketOptions' }).'#text'
        $IpAddress      = ($Data | Where-Object { $_.Name -eq 'IpAddress' }).'#text'

        if ($EndTimeString) {
            $EndTime = [DateTime]::Parse($EndTimeString)
            $Duration = ($EndTime - $Event.TimeCreated).TotalHours

            # Nilai ambang batas masa aktif TGT domain standar adalah 10 Jam
            if ($Duration -gt $MaxTicketDurationHours) {
                Write-Host "[ALERT] Indikasi Pemalsuan Tiket Kerberos Terdeteksi!" -ForegroundColor Red
                Write-Host "   Target User : $TargetUserName"
                Write-Host "   Masa Aktif  : $Duration Jam (Batas Konfigurasi: $MaxTicketDurationHours Jam)"
                Write-Host "   Alamat IP   : $IpAddress"
                Write-Host "   Event Time  : $($Event.TimeCreated)"
                Write-Host "   Entropy Tag : POTENTIAL_GOLDEN_TICKET_FORGERY"
            }
        }
    }
} catch [System.Exception] {
    Write-Warning "Peringatan: Gagal memproses Event ID 4768: $($_.Message)"
}

# 2. Deteksi Kerberoasting (Penggunaan Cipher Suite Usang RC4-HMAC pada Ekstraksi TGS)
$TgsFilter = @{
    LogName   = 'Security'
    Id        = 4769
    StartTime = $StartTime
}

try {
    $TgsEvents = Get-WinEvent -FilterHashtable $TgsFilter -ErrorAction Stop
    Write-Host "[*] Menganalisis $($TgsEvents.Count) event TGS Request (Event 4769)..."

    $SuspiciousTgs = @()
    foreach ($Event in $TgsEvents) {
        $Xml = [xml]$Event.ToXml()
        $Data = $Xml.Event.EventData.Data
        
        $ServiceName    = ($Data | Where-Object { $_.Name -eq 'ServiceName' }).'#text'
        $TicketEncType  = ($Data | Where-Object { $_.Name -eq 'TicketEncryptionType' }).'#text'
        $TargetUserName = ($Data | Where-Object { $_.Name -eq 'TargetUserName' }).'#text'
        $IpAddress      = ($Data | Where-Object { $_.Name -eq 'IpAddress' }).'#text'

        # Cipher Suite 0x17 = 23 (Decimal) merepresentasikan RC4-HMAC
        if ($TicketEncType -eq '0x17' -and -not ($ServiceName.EndsWith('$'))) {
            $SuspiciousTgs += [PSCustomObject]@{
                TimeCreated    = $Event.TimeCreated
                User           = $TargetUserName
                Service        = $ServiceName
                EncryptionType = "RC4-HMAC (0x17)"
                ClientIP       = $IpAddress
            }
        }
    }

    if ($SuspiciousTgs.Count -gt 0) {
        Write-Host "[ALERT] Potensi Serangan Kerberoasting Teridentifikasi (RC4 Request):" -ForegroundColor Yellow
        $SuspiciousTgs | Format-Table -AutoSize
    } else {
        Write-Host "[OK] Tidak ada anomali cipher suite lama pada TGS requests." -ForegroundColor Green
    }
} catch [System.Exception] {
    Write-Warning "Peringatan: Gagal memproses Event ID 4769: $($_.Message)"
}
```

---

## 11. Diagram Alur Serangan & Mitigasi (Attack vs Defense Flow)

Diagram alur berikut mengilustrasikan vektor eskalasi dari host yang terinfeksi malware hingga mencapai penguasaan menyeluruh (*full compromise*) domain melalui DCSync dan pemalsuan tiket identitas, beserta lapisan kontrol mitigasinya:

```
+-------------------------------------------------------------------------------------------------------------------------+
|                                                   ATTACK FLOW LIFECYCLE                                                 |
+-------------------------------------------------------------------------------------------------------------------------+
       |
       v
[ 1. Host Initial Breach ] (Phishing / Web Shell / Stolen NTLM Hash)
       |
       |  Eksploitasi Vektor: SeImpersonatePrivilege / Unquoted Path / SUID
       v
[ 2. Local Privilege Escalation ] -> Mendapatkan hak akses SYSTEM / Root lokal
       |
       |  Mitigasi: CIS L1/L2 Hardening, AppLocker, UAC Remote Restrictions
       v
[ 3. Kredensial Harvesting ] -> Mimikatz membaca memori LSASS (Mencari Kredensial Domain Admin tersimpan)
       |
       |  Mitigasi: LSA Protection (RunAsPPL), Windows Defender Credential Guard (Virtualization-Based Security)
       v
[ 4. Active Directory Lateral Movement ] -> Melakukan koneksi RPC/DRSUAPI ke Domain Controller
       |
       |  Eksploitasi Vektor: DCSync Attack (Mereplikasi database direktori tanpa kode eksekusi di DC)
       v
[ 5. Eksfiltrasi Kunci Kriptografi `krbtgt` ] -> Mendapatkan AES-256 Key akun krbtgt
       |
       |  Eksploitasi Vektor: Offline Forgery -> Pembuatan TGT palsu (Golden Ticket)
       v
[ 6. Full Domain Impersonation (Domain Controller Compromise) ]
       |
+-------------------------------------------------------------------------------------------------------------------------+
|                                                  DEFENSIVE REMEDIATION LAYER                                            |
+-------------------------------------------------------------------------------------------------------------------------+
       |
       +--> Layer 1: CIS Baseline Hardening (Matikan WDigest, enforce SMB signing, audit priv escalation).
       +--> Layer 2: PAM Tiering Architecture (Kredensial Tier 0 dilarang masuk ke mesin Tier 1/2).
       +--> Layer 3: Network Microsegmentation (Isolasi traffic RPC/SMB workstation-ke-workstation).
       +--> Layer 4: Protected Users Group (Memaksa enkripsi AES, menonaktifkan delegasi dan NTLM cache).
       +--> Layer 5: KRBTGT Dual-Rotation Process (Rotasi kunci terencana 2x berturut-turut untuk invalidasi tiket).
```

---

## 12. Trade-offs & Security vs Usability / Performance

Implementasi kontrol keamanan identitas dan pengerasan sistem host memperkenalkan konsekuensi operasional yang memerlukan kalkulasi presisi:

### 1. PAC Validation Mandatory Enforcement
*   **Keamanan:** Mencegah modifikasi struktur PAC lokal oleh host nakal karena host target memverifikasi tanda tangan PAC kembali ke Netlogon Domain Controller melalui RPC.
*   **Trade-off/Overhead:** Menimbulkan latensi tambahan dan peningkatan beban jaringan yang drastis pada Domain Controller jika ada puluhan ribu klien yang mengautentikasi layanan web/basis data secara simultan (*RPC thread exhaustion*).

### 2. Privileged Access Workstation (PAW) & Model Pemisahan Tier
*   **Keamanan:** Menjamin isolasi mutlak kredensial Tier 0 dari workstation operasional harian yang rentan phishing.
*   **Trade-off/Usability:** Menurunkan fleksibilitas tim administrator sistem secara radikal. Staf TI harus mengoperasikan dua perangkat fisik atau VM terpisah untuk tugas operasional harian (email, internet) versus tugas administrasi server.

### 3. CIS Level 2 Host Hardening (e.g., SMB v1 Disablement & NTLM Elimination)
*   **Keamanan:** Menutup kerentanan eksekusi kode remote warisan (seperti MS17-010/EternalBlue) dan meniadakan vektor serangan *NTLM Relay*.
*   **Trade-off/Kompatibilitas:** Memutus integrasi sistem warisan (*legacy systems*), printer jaringan enterprise generasi lama, perangkat IoT industri, serta perangkat lunak pihak ketiga yang tidak mendukung Kerberos SPN negotiation.

### 4. Credential Guard (Virtualization-Based Security - VBS)
*   **Keamanan:** Memindahkan proses penanganan rahasia LSASS ke lingkungan virtual terisolasi (*Isolated User Mode* / VSM), membuat dumping memori via `mimikatz` atau dump reader menjadi tidak berguna.
*   **Trade-off/Performa:** Membutuhkan CPU dengan kapabilitas virtualisasi tingkat lanjut (SLAT/VT-x), mengonsumsi alokasi RAM konstan, serta dapat menimbulkan inkompatibilitas dengan hypervisor pihak ketiga (misalnya VirtualBox atau emulator tertentu) di host workstation.

---

## 13. Edge Cases & Complex Failure Modes

### 1. Cross-Forest Trust SID History Injection
Pada arsitektur multi-forest yang menggunakan *two-way forest trust*, penyerang yang menguasai forest anak (*child domain*) dapat menyuntikkan SID istimewa dari forest induk (*parent domain*) ke dalam atribut `sIDHistory` pada PAC tiket Kerberos. Jika konfigurasi *SID Filtering* (*Quarantine*) dinonaktifkan pada trust tersebut, penyerang dapat mengeksekusi eskalasi antar-forest ke tingkat `Enterprise Admins`.
*Mitigasi:* Jalankan `netdom trust <TrustingDomain> /domain:<TrustedDomain> /quarantine:yes` untuk memastikan *SID Filtering* selalu aktif.

### 2. Kerberos Clock Skew Synchronization Failure
Protokol Kerberos bergantung mutlak pada timestamp untuk mitigasi serangan *Replay Attack*. Batas default divergensi waktu adalah 300 detik (5 menit). Jika terjadi desinkronisasi NTP skala besar (misalnya kegagalan hierarki PDC Emulator waktu), seluruh autentikasi Kerberos domain akan lumpuh seketika, memaksa sistem jatuh kembali (*fallback*) ke protokol NTLM yang lebih rentan serangan, atau memicu *Denial of Service* total.

### 3. Kegagalan Rotasi Kunci gMSA (Group Managed Service Accounts)
Ketika sebuah host kehilangan koneksi domain selama periode pembaruan kata sandi otomatis gMSA (standar setiap 30 hari), atau jika terjadi inkonsistensi replikasi atribut `msDS-ManagedPassword` antar-DC, akun layanan tersebut akan terkunci dalam status *out-of-sync*. Akibatnya, seluruh daemon layanan aplikasi (misalnya klaster SQL) akan gagal melakukan proses *start up* (Error: `Logon failure: unknown user name or bad password`).

### 4. Linux PAM Namespace Privilege Leakage
Pada lingkungan Linux yang menggunakan container runtime atau bind mounting direktori `/proc` atau `/sys` yang tidak di-sandbox secara sempurna, bit SUID dan Linux POSIX Capabilities dapat bocor dari container ke host OS. Hal ini menciptakan celah pelarian kontainer (*container escape*) yang memberikan hak akses `root` penuh pada host OS yang mendasarinya.

---

## 14. Anti-Patterns & Common Vulnerabilities

Berikut adalah praktik buruk konfigurasi identitas dan sistem yang sering ditemukan dalam arsitektur enterprise:

### 1. Unconstrained Kerberos Delegation
*   **Anti-Pattern:** Mengaktifkan flag `TRUSTED_FOR_DELEGATION` pada atribut komputer/layanan di Active Directory.
*   **Mekanisme Kerentanan:** Ketika pengguna mengautentikasi ke server dengan delegasi tanpa batas ini, KDC menyalin TGT pengguna ke dalam tiket layanan. Server tersebut kemudian menyimpan TGT pengguna di dalam memori LSASS. Jika penyerang mengompromikan server perantara ini, mereka dapat mengekstrak TGT pengguna tersebut dan menirukan identitasnya ke layanan apa pun di seluruh forest.
*   **Praktik Benar:** Terapkan *Constrained Delegation* berbasis protokol S4U2Self/S4U2Proxy atau *Resource-Based Constrained Delegation* (RBCD).

### 2. Layanan Berjalan Menggunakan Hak Domain Admin
*   **Anti-Pattern:** Mengonfigurasi layanan pihak ketiga (backup agent, antivirus central, monitoring tool) untuk berjalan di bawah akun pengguna domain yang merupakan anggota grup `Domain Admins`.
*   **Mekanisme Kerentanan:** Akun ini meninggalkan jejak tiket TGS dan token kredensial pada memori host lokal di mana agen tersebut berjalan. Penyerang yang menguasai satu host acak dapat membuang memori proses dan mengekstrak kredensial tingkat Domain Admin (*Credential Harvest*).
*   **Praktik Benar:** Gunakan akun layanan individual dengan hak seminimal mungkin (*Least Privilege*) atau Group Managed Service Accounts (gMSA).

### 3. Password akun KRBTGT Tidak Pernah Dirotasi
*   **Anti-Pattern:** Mengabaikan siklus rotasi kata sandi akun internal direktori `krbtgt` sejak awal pembentukan forest domain Active Directory.
*   **Mekanisme Kerentanan:** Jika kunci hash `krbtgt` pernah terekspos dalam insiden bertahun-tahun sebelumnya, penyerang masih dapat mencetak Golden Ticket tanpa batasan waktu secara persisten, bahkan jika seluruh kata sandi akun karyawan telah diubah secara berkala.
*   **Praktik Benar:** Lakukan rotasi ganda kata sandi `krbtgt` secara terjadwal (misal: setiap 180 hari) menggunakan skrip tersertifikasi.

### 4. Penulisan Wildcard pada File Crontab Linux
*   **Anti-Pattern:** Membuat skrip cronjob root yang mengeksekusi perintah berbasis wildcard, seperti:
    `cd /opt/app/backup && tar -zcf /tmp/backup.tar.gz *`
*   **Mekanisme Kerentanan:** Pengguna non-privileged yang memiliki hak tulis pada direktori target dapat membuat file dengan nama opsi perintah tar (misal: `--checkpoint=1` dan `--checkpoint-action=exec=sh shell.sh`). Utilitas `tar` mengurai nama file ini sebagai argumen baris perintah, mengeksekusi arbitrary shell script di bawah konteks `root`.
*   **Praktik Benar:** Hindari penggunaan wildcard pada cronjob otomatis root; gunakan argumen eksplisit atau sanitasi direktori target secara ketat.

---

## 15. Best Practices & Enterprise Remediation Guide

Implementasi pengerasan identitas dan host wajib dilakukan secara terstruktur menggunakan metodologi bertahap:

### Active Directory Hardening Blueprint
1. **Penerapan Enterprise Access Model (Tiering):**
   * **Tier 0:** Domain Controller, Active Directory Certificate Services (AD CS), Identity Access Management (IAM), Server PAM, dan Privileged Access Workstations (PAW). Kredensial Tier 0 diisolasi secara mutlak dan tidak boleh digunakan untuk login ke level bawah.
   * **Tier 1:** Server aplikasi enterprise, file server, database, hypervisor.
   * **Tier 2:** Perangkat pengguna akhir (workstations, laptop, printer, smartphone).
2. **Pemanfaatan Protected Users Security Group:**
   * Masukkan seluruh akun administratif berisiko tinggi ke dalam grup `Protected Users`.
   * Akun di dalam grup ini secara otomatis menonaktifkan autentikasi NTLM, melarang cipher suite RC4 pada Kerberos, mencegah delegasi kredensial (Unconstrained/Constrained), dan tidak menyimpan kredensial pada cache LSASS setelah pengguna logout.
3. **Mekanisme Dual-Rotation Akun KRBTGT:**
   * Rotasi kata sandi `krbtgt` sebanyak dua kali dengan interval jeda minimal waktu replikasi domain penuh (misal: jeda 12 hingga 24 jam di antara rotasi pertama dan kedua). Hal ini memastikan tiket TGT lama yang beredar hangus tanpa memicu pemutusan mendadak (*abrupt disconnection*) pada layanan yang sedang berjalan dengan TGT aktif.
4. **Implementasi LAPS (Local Administrator Password Solution):**
   * Hapus keseragaman kata sandi administrator lokal pada seluruh endpoint. LAPS merotasi kata sandi administrator lokal secara dinamis, menggunakan entropi tinggi, dan menyimpannya di atribut terenkripsi AD DS yang hanya dapat dibaca oleh personel terotorisasi.

### Baseline CIS Host Hardening Blueprint

#### Windows Host Baseline:
*   Aktifkan *LSA Protection* (`RunAsPPL=1`).
*   Aktifkan *Virtualization-Based Security* (VBS) dan *Credential Guard*.
*   Wajibkan penandatanganan paket SMB (*SMB Signing Mandatory* - `RequireSecuritySignature=1`).
*   Blokir transmisi hash NTLMv1 (`LmCompatibilityLevel = 5` - Menolak LM & NTLM, hanya kirim respons NTLMv2).
*   Nonaktifkan protokol penamaan lokal berisiko: LLMNR (*Link-Local Multicast Name Resolution*) dan NetBIOS over TCP/IP.

#### Linux Host Baseline:
*   Mounting partisi non-sistem (`/tmp`, `/var/tmp`, `/dev/shm`) dengan parameter: `nosuid,nodev,noexec`.
*   Audit ekstensif file berkas dengan SUID/SGID menggunakan integrasi `auditd`.
*   Konfigurasi `/etc/ssh/sshd_config`:
    *   `PermitRootLogin no`
    *   `PasswordAuthentication no`
    *   `MaxAuthTries 3`
    *   `KexAlgorithms curve25519-sha256@libssh.org,diffie-hellman-group16-sha512`
    *   `Ciphers chacha20-poly1305@openssh.com,aes256-gcm@openssh.com`
*   Konfigurasi `/etc/pam.d/common-auth` atau `/etc/pam.d/system-auth` untuk mengunci akun setelah ambang batas kegagalan sandi (*faillock* / *pam_tally2*).

---

## 16. Hands-on Lab Step-by-Step

### Skenario Lab:
Laboratorium ini merekonstruksi audit pengerasan host Linux (eksploitasi hak SUID dan remediasi CIS), disusul dengan verifikasi forensik tiket Kerberos pada Domain Controller menggunakan CLI.

### Bagian 1: Eksploitasi & Remediasi SUID pada Host Linux

**Langkah 1.1: Pemetaan Sistem Mencari Binary SUID Berisiko**
Masuk ke terminal host Linux dan eksekusi pencarian rekursif untuk menemukan file binary dengan bit setuid:
```bash
find / -perm -4000 -type f -exec ls -la {} 2>/dev/null \;
```
*Hasil Analisis:* Ditemukan binary `/usr/bin/python3` memiliki flag `-rwsr-xr-x` (SUID aktif di bawah kepemilikan user `root`).

**Langkah 1.2: Eksploitasi Hak Akses Lokal (Privilege Escalation Execution)**
Jalankan instruksi shell breakout berikut untuk menaikkan privilege dari user `devuser` ke `root`:
```bash
# Verifikasi identitas awal
id
# Output: uid=1001(devuser) gid=1001(devuser) groups=1001(devuser)

# Eksekusi exploitasi Python SUID via drop-down UID context
/usr/bin/python3 -c 'import os; os.setuid(0); os.system("/bin/bash")'

# Verifikasi eskalasi hak
id
# Output: uid=0(root) gid=1001(devuser) groups=1001(devuser)
```

**Langkah 1.3: Remediasi Sesuai Standar CIS Baseline**
Cabut hak SUID non-standar dari binary interpreter dan lakukan persistensi audit:
```bash
# Menghapus bit SUID dari binary python
chmod u-s /usr/bin/python3

# Verifikasi perbaikan
ls -la /usr/bin/python3
# Output: -rwxr-xr-x 1 root root ...

# Mendaftarkan monitoring SUID baru ke audit system engine
cat << 'EOF' >> /etc/audit/rules.d/cis_hardening.rules
-a always,exit -F arch=b64 -S setuid -F key=priv_escalation
-a always,exit -F arch=b64 -S setresuid -F key=priv_escalation
EOF

# Reload daemon auditd
augenrules --load
```

---

### Bagian 2: Investigasi Tiket Kerberos dan Remediasi Domain Controller

**Langkah 2.1: Pemeriksaan Tiket Kerberos Aktif pada Workstation**
Buka PowerShell Administrator pada workstation Windows untuk melihat memori tiket pengguna:
```powershell
# Menampilkan tiket TGT dan TGS yang tersimpan di sesi LSASS pengguna
klist

# Analisis output:
# Perhatikan Client: Administrator @ CORP.LOCAL
# Perhatikan Server: krbtgt/CORP.LOCAL
# Perhatikan KerbTicket Encryption Type: AES-256-CTS-HMAC-SHA1-96 (Aman)
# Jika tipe enkripsi adalah RSADSI RC4-HMAC-MD5, sistem berada dalam kondisi rentan!
```

**Langkah 2.2: Deteksi dan Investigasi Atribut Unconstrained Delegation**
Lakukan audit pada direktori AD DS untuk mencari objek komputer selain Domain Controller yang memiliki izin delegasi bebas:
```powershell
Import-Module ActiveDirectory

Get-ADComputer -Filter {TrustedForDelegation -eq $True -and PrimaryGroupID -ne 516} `
    -Properties TrustedForDelegation, ServicePrincipalNames, IPv4Address |
    Select-Object Name, IPv4Address, TrustedForDelegation, ServicePrincipalNames |
    Format-List
```

**Langkah 2.3: Remediasi Delegasi Berbahaya Melalui Active Directory PowerShell**
Cabut hak delegasi tanpa batas dari komputer target dan masukkan akun administratif ke Protected Users:
```powershell
# Cabut Unconstrained Delegation dari server target bermasalah
Set-ADComputer -Identity "SRV-FILE-APP01" -TrustedForDelegation $False

# Masukkan identitas pengguna tier tinggi ke Protected Users Security Group
$ProtectedGroup = Get-ADGroup -Identity "Protected Users"
Add-ADGroupMember -Identity $ProtectedGroup -Members "admin-jdoe", "admin-service"

# Verifikasi keanggotaan grup
Get-ADGroupMember -Identity "Protected Users" | Select-Object Name, SamAccountName
```

---

## 17. Real-World Case Study & Incident Analysis Enterprise

### Profil Insiden
*   **Target:** Korporasi Jasa Finansial Multinasional.
*   **Vektor Akses Awal:** Akun VPN kontraktor dieksfiltrasi melalui pencurian sesi kredensial browser. VPN tidak mengonfirmasi postur perangkat (*No Device Compliance Check*).
*   **Waktu Penyusupan hingga Kompromi Total:** 48 Jam.

### Anatomi Pelaksanaan Serangan (Post-Mortem Analysis)

1.  **Fase Masuk & Pengintaian Internal (Hour 0 - 6):**
    Penyerang tersambung ke jaringan internal melalui VPN kontraktor menggunakan kredensial curian. Penyerang mengeksekusi scanning port terarah pada segmen server internal dan menemukan sebuah instance web internal Apache Tomcat usang yang berjalan pada Windows Server 2019 (Tier 1).

2.  **Eskalasi Hak Lokal (Hour 6 - 12):**
    Penyerang mengeksploitasi kerentanan eksekusi perintah jarak jauh (*Remote Code Execution*) pada Apache Tomcat. Proses berjalan di bawah konteks akun layanan lokal `tomcat-svc` dengan hak `SeImpersonatePrivilege`. Penyerang mengeksekusi exploit berbasis *SweetPotato*, memanfaatkan integrasi RPC lokal untuk mengambil token proses `NT AUTHORITY\SYSTEM`.

3.  **Credential Dumping & Pembongkaran Batas Tiering (Hour 12 - 24):**
    Dari konteks `SYSTEM` di Server Tomcat, penyerang mengakses memori proses `LSASS.exe`. Karena *Credential Guard* tidak diaktifkan dan server tersebut tidak mematuhi CIS Level 1, penyerang mengekstrak hash NTLM dari akun `admin-infra`.
    *Kegagalan Arsitektur Fatal:* Akun `admin-infra` ternyata terdaftar sebagai anggota grup lokal `Administrators` di server tersebut, sekaligus anggota grup `Domain Admins` (Pelanggaran Pemisahan Tier: Akun Tier 0 digunakan login ke Server Tier 1).

4.  **DCSync & Pembuatan Golden Ticket (Hour 24 - 30):**
    Menggunakan konteks keamanan `admin-infra`, penyerang tidak perlu melakukan koneksi RDP ke Domain Controller. Dari server Tomcat yang terinfeksi, penyerang mengeksekusi protokol replikasi direktori DRSUAPI (`DCSync`) menggunakan paket *Mimikatz/Impacket* yang diarahkan ke Primary Domain Controller:
    `lsadump::dcsync /domain:corp.fintech /user:krbtgt`
    KDC mengembalikan seluruh metadata rahasia, termasuk Master AES-256 Key untuk akun `krbtgt`.

5.  **Persistensi Melalui Golden Ticket (Hour 30 - 48):**
    Penyerang mencetak Golden Ticket dengan masa aktif 10 tahun, menyematkan SID `Enterprise Admins (519)`, dan menyuntikkan tiket ke sesi memori. Meskipun tim SOC mendeteksi anomali akses RCE pada Tomcat di jam ke-36 dan memutus koneksi server Tomcat dari jaringan, penyerang telah memiliki tiket offline yang valid. Penyerang mengakses Domain Controller secara sah melalui jaringan wireless korporasi menggunakan tiket palsu tersebut.

### Mitigasi dan Restorasi Krisis (*Root Cause Remediation*)

1.  **Eksekusi Pemulihan Darurat KRBTGT:**
    Tim tanggap insiden mengisolasi seluruh Domain Controller dan mengeksekusi skrip pembaruan kata sandi `krbtgt` secara ganda:
    *   Rotasi pertama dilakukan seketika untuk menghasilkan hash baru.
    *   Jeda replikasi 24 jam diberikan agar seluruh TGT layanan yang aktif direfresh secara terkontrol.
    *   Rotasi kedua dilakukan setelah 24 jam untuk sepenuhnya menghapus kunci lama dari riwayat (*password history*), yang secara instan membatalkan (*invalidating*) seluruh Golden Ticket yang telah dibuat penyerang.
2.  **Restrukturisasi Arsitektur Tiering Model:**
    Pemisahan hak akun total diterapkan. Akun Domain Admin dibatasi hanya boleh masuk (*Logon Locally / Network Logon*) ke Domain Controller dan Workstation Khusus (PAW). Pembuatan skema LAPS diberlakukan untuk mengisolasi kredensial administrator lokal di seluruh server Tier 1.
3.  **Aktivasi CIS Baseline Controls:**
    Seluruh sistem host Windows Server dipaksa mengaktifkan *LSA Protection* (`RunAsPPL`) dan *Hypervisor-Enforced Code Integrity* (HVCI) via GPO untuk memblokir teknik pembacaan memori LSASS di masa mendatang.

---

## 18. Quiz Pemahaman & Challenge

### Uji Pemahaman Teori & Logika Keamanan

**Pertanyaan 1:**
Dalam alur autentikasi Kerberos standar, jika sebuah tiket Service Ticket (TGS) dipalsukan melalui teknik serangan *Silver Ticket*, mengapa aktivitas ini tidak menghasilkan Security Event ID 4769 pada log Domain Controller?
*   A. Karena Silver Ticket menggunakan enkripsi asimetris yang otomatis mengabaikan logging KDC.
*   B. Karena pembuatan Silver Ticket dilakukan sepenuhnya secara offline menggunakan kunci rahasia akun layanan tujuan, dan klien langsung menyajikannya ke server target (AP-REQ) tanpa pernah menghubungi KDC.
*   C. Karena Domain Controller secara otomatis menghapus log TGS yang memiliki atribut waktu validitas kurang dari 1 jam.
*   D. Karena Windows Event Log ID 4769 hanya mencatat autentikasi berbasis protokol NTLMv2.

**Pertanyaan 2:**
Mengapa proses rotasi kata sandi akun `krbtgt` untuk mitigasi serangan Golden Ticket diwajibkan dilakukan sebanyak **dua kali**, bukan satu kali?
*   A. Rotasi pertama mengubah password di Active Directory, sedangkan rotasi kedua mengubah password di Azure AD (Entra ID).
*   B. Sistem Active Directory mempertahankan riwayat satu kunci kata sandi sebelumnya (`pwdLastSet` n-1) untuk mencegah kegagalan autentikasi instan pada tiket TGT sah yang masih beredar. Rotasi dua kali menghapus kunci asli yang bocor dari riwayat historis.
*   C. Karena KDC memerlukan siklus ganda untuk membersihkan cache DNS SRV records.
*   D. Sebagai mekanisme verifikasi ganda apabila Domain Controller cadangan berada dalam status offline.

**Pertanyaan 3:**
Manakah pernyataan berikut yang secara akurat menjelaskan mekanisme serangan *Kerberoasting*?
*   A. Penyerang membuang hash NTLM akun komputer Domain Controller menggunakan eksploitasi RPC Zerologon.
*   B. Penyerang meminta tiket TGT palsu dari KDC tanpa pre-autentikasi untuk kemudian diserang secara brute force.
*   C. Pengguna domain terotentikasi meminta tiket layanan (TGS) untuk SPN yang terdaftar pada akun pengguna biasa, kemudian mengekstraksi tiket terenkripsi dari memori untuk di-crack secara offline guna menemukan kata sandi plaintext pemilik akun SPN.
*   D. Penyerang menyuntikkan tiket TGS palsu ke dalam registry SAM lokal workstation.

**Pertanyaan 4:**
Pada pengerasan sistem operasi Linux sesuai CIS Benchmark, mengapa opsi mount `noexec` pada partisi `/dev/shm` dan `/tmp` sangat kritikal dalam memitigasi eskalasi hak akses lokal?
*   A. Mencegah kernel membaca berkas konfigurasi root.
*   B. Direktori tersebut memiliki izin tulis global (*world-writable*); opsi `noexec` memblokir penyerang mengeksekusi payload binary atau skrip eksploitasi yang ditransmisikan dan disimpan di direktori tersebut.
*   C. Menghentikan eksploitasi buffer overflow pada driver VGA kernel.
*   D. Menghalangi sistem mengeksekusi instruksi cronjob terjadwal.

**Pertanyaan 5:**
Hak akses (*Privilege*) manakah pada Windows yang sering disalahgunakan oleh exploit keluarga *Potato* (e.g., JuicyPotato, SweetPotato) untuk mengekskalasi hak akun layanan non-admin menjadi `NT AUTHORITY\SYSTEM`?
*   A. `SeShutdownPrivilege`
*   B. `SeBackupPrivilege`
*   C. `SeImpersonatePrivilege`
*   D. `SeTimeZonePrivilege`

---

### Kunci Jawaban & Rationale Quiz

*   **Jawaban Pertanyaan 1:** **B**. Rationale: Silver Ticket hanya membutuhkan kunci rahasia akun layanan target (SPN). Penyerang membentuk tiket layanan TGS sendiri secara lokal dan mengirimkannya langsung ke server target melalui AP-REQ. Domain Controller sama sekali tidak terlibat dan tidak menerima request apa pun, sehingga tidak ada jejak event 4769 di KDC.
*   **Jawaban Pertanyaan 2:** **B**. Rationale: AD DS menyimpan kata sandi saat ini dan satu kata sandi sebelumnya untuk akun `krbtgt` agar tiket TGT sah yang diterbitkan sesaat sebelum rotasi tidak langsung ditolak oleh KDC. Oleh karena itu, rotasi harus dilakukan dua kali (dengan jeda replikasi) untuk membersihkan kunci lama yang terekspos dari memori KDC.
*   **Jawaban Pertanyaan 3:** **C**. Rationale: Kerberoasting memanfaatkan fitur sah Kerberos di mana pengguna domain mana pun dapat meminta TGS untuk SPN apa pun. Tiket TGS dienkripsi menggunakan kunci akun pemilik SPN. Jika akun tersebut adalah akun pengguna biasa (bukan akun mesin AD yang memiliki kata sandi acak 128-karakter), hash-nya rentan di-crack secara offline menggunakan dictionary attack.
*   **Jawaban Pertanyaan 4:** **B**. Rationale: Direktori `/tmp` dan `/dev/shm` memerlukan hak tulis publik agar aplikasi normal dapat membuat berkas sementara. Penyerang sering menyalin tool eksploitasi mereka ke folder ini. Mengaktifkan `noexec` secara langsung mencegah kernel Linux memanggil API `execve()` pada berkas apa pun di dalam partisi tersebut.
*   **Jawaban Pertanyaan 5:** **C**. Rationale: `SeImpersonatePrivilege` memungkinkan sebuah proses untuk mengimpersonasi konteks keamanan klien yang terhubung dengannya. Penyerang menipu proses berhak istimewa (`SYSTEM`) untuk melakukan autentikasi ke Named Pipe atau RPC endpoint lokal yang dikendalikan penyerang, lalu mencuri token identitas tersebut.

---

### Practical Challenge

**Misi Pertahanan:**
Anda adalah Senior Security Engineer yang ditugaskan mengamankan server aplikasi Linux Ubuntu 22.04 LTS yang baru di-provisioning.
Tuliskan skrip bash otomatisasi (*Bash Hardening Script*) berstandar produksi yang melakukan 4 hal berikut secara terverifikasi:
1. Memastikan seluruh konfigurasi SSH di `/etc/ssh/sshd_config` melarang autentikasi berbasis kata sandi, memblokir akses root langsung, dan menetapkan `MaxAuthTries` menjadi 3.
2. Melakukan audit dan pencabutan bit SUID secara otomatis dari 3 binary GTFOBins berisiko: `/usr/bin/pkexec`, `/usr/bin/nmap` (jika ada), dan `/usr/bin/vim` (jika ada).
3. Menerapkan penguncian akun setelah 5 kegagalan autentikasi berturut-turut menggunakan subsistem `pam_faillock`.
4. Memvalidasi bahwa setiap perubahan berkas didokumentasikan dan service `sshd` di-reload tanpa memutus koneksi sesi administrator saat ini (*syntax validation checking via `sshd -t`*).

---

## 19. Summary & Key Takeaways

1. **Identitas adalah Fondasi Keamanan Enterprise:** Kompromi arsitektur identitas seperti Active Directory meniadakan efektivitas kontrol keamanan layer aplikasi dan data.
2. **Kriptografi Kerberos Menuntut Perlindungan Kunci Simetris:** Mekanisme keamanan Kerberos bergantung penuh pada kerahasiaan kunci simetris KDC (`krbtgt`) dan kunci akun layanan (SPN). Kegagalan menjaga kunci `krbtgt` berujung pada eksploitasi *Golden Ticket*, yang memberikan kekuasaan tak terbatas tanpa interaksi KDC.
3. **Pemberantasan Pemalsuan Tiket:** Deteksi *Silver Ticket* memerlukan monitoring ketat di level host lokal (Event ID 4624/4672 dan konsistensi PAC), sementara mitigasi *Golden Ticket* menuntut penerapan protokol rotasi ganda kunci `krbtgt` secara periodik dan isolasi ketat perimeter Tier 0.
4. **Isolasi Hierarki Akses (Tiering Model):** Jangan pernah membiarkan kredensial dengan level privilege tinggi (Tier 0) menyentuh atau tersimpan di memori sistem dengan level privilege lebih rendah (Tier 1 atau Tier 2).
5. **Host Hardening sebagai Pertahanan Lapis Kedua:** Eksploitasi hak istimewa lokal (SUID abuse, Capabilities, Unquoted Paths, SeImpersonatePrivilege) dapat ditekan secara sistematis melalui kepatuhan terhadap CIS Benchmarks Level 1 dan Level 2.
6. **Credential Protection pada Endpoint:** Mekanisme modern seperti *Credential Guard* (Virtualization-Based Security) dan *LSA Protection* (`RunAsPPL`) pada Windows, serta restriksi direktori temporary (`noexec,nosuid`) pada Linux, wajib diimplementasikan untuk mengamankan memori kredensial runtime dari teknik dumping tools.

---

## 20. Referensi Resmi & Standar Keamanan

1. **RFC 4120:** *The Kerberos Network Authentication Service (V5)* - IETF Official Standard Specification.
2. **Microsoft Open Specifications (MS-PAC):** *Privilege Attribute Certificate Data Structure Specification* - Microsoft Corporation.
3. **CIS Benchmarks Documentation:**
   * *CIS Microsoft Windows Server 2022 Benchmark v2.0.0*
   * *CIS Ubuntu Linux 22.04 LTS Benchmark v1.0.0*
   * Center for Internet Security (cisecurity.org).
4. **MITRE ATT&CK Framework:**
   * T1558.001: *Steal or Forge Kerberos Tickets: Golden Ticket*
   * T1558.002: *Steal or Forge Kerberos Tickets: Silver Ticket*
   * T1558.003: *Steal or Forge Kerberos Tickets: Kerberoasting*
   * T1068: *Exploitation for Privilege Escalation*
   * T1548.001: *Abuse Elevation Control Mechanism: Setuid and Setgid*
5. **NIST Special Publication:** *NIST SP 800-63-3: Digital Identity Guidelines* dan *NIST SP 800-207: Zero Trust Architecture* - National Institute of Standards and Technology.
6. **Microsoft Security Best Practices:** *Securing Privileged Access (SPA) and Enterprise Access Model* - Microsoft Security Technical Documentation.