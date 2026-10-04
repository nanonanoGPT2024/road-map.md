# BAB 03: Identity, Access, dan Host Hardening
## Module 02 - Deep Dive, Implementasi Lanjutan & Arsitektur Produksi

---

### 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
1. **Menganalisis & Mengisolasi Attack Surface Tingkat Kernel**: Memahami cara kerja Linux Security Modules (LSM), eBPF tracing engine, dan mekanisme *kernel space enforcement* untuk memitigasi eskalasi privilese.
2. **Merancang Arsitektur Zero-Trust Workload & Host Identity**: Mengimplementasikan framework identitas workload berbasis SPIFFE/SPIRE dan arsitektur SSH-CA (Certificate Authority) otomatis menggunakan HashiCorp Vault untuk mengeliminasi ketergantungan pada *long-lived static credentials*.
3. **Mengonfigurasi & Menegakkan Linux Host Hardening Skala Enterprise**: Mengotomatisasi baseline keamanan CIS Benchmark Level 2, membatasi *system calls* melalui Seccomp-BPF dan AppArmor/SELinux profiles, serta mengonfigurasi Pluggable Authentication Modules (PAM) dengan Hardware Security Key (FIDO2/WebAuthn).
4. **Mendeteksi & Memblokir Ancaman Runtime secara Real-Time**: Menyusun kebijakan tracing eBPF (menggunakan Cilium Tetragon) untuk mendeteksi *namespace escape*, injeksi memori, dan modifikasi *kernel space* secara deterministik.

---

### 2. Prerequisite

Sebelum mempelajari modul ini, peserta wajib menguasai:
- **Arsitektur Sistem Operasi Linux**: Konsep *User Space* vs *Kernel Space*, VFS (Virtual File System), POSIX Permissions, Syscalls (`execve`, `ptrace`, `clone`, `mprotect`), Namespaces, dan Cgroups.
- **Kriptografi Terapan & PKI**: Prinsip dasar Asymmetric Encryption (RSA, Ed25519), X.509 Certificate Chain of Trust, CRL, OCSP, dan mutual TLS (mTLS).
- **Infrastruktur Jaringan Tingkat Menengah**: TCP/IP stack, socket manipulation, iptables/nftables, dan reverse proxy architecture.
- **Alat & Bahasa Pemrograman**: Kemahiran dasar bahasa Bash, Go, atau Python; familiaritas dengan Git, Docker, Systemd, dan CLI administrasi Linux.

---

### 3. Concept & Internal Architecture

Keamanan host dan identitas modern enterprise bertransisi dari model defensif berbasis perimeter tradisional menuju model **Zero-Trust Ephemeral & Kernel-Enforced Defense-in-Depth**.

```
+-----------------------------------------------------------------------------------+
| USER SPACE                                                                        |
|                                                                                   |
|  +--------------------+   +-----------------------+   +------------------------+  |
|  | User / Bastion SSH |   | Workload (Container)  |   | Security Agent (SPIRE) |  |
|  +---------+----------+   +-----------+-----------+   +-----------+------------+  |
|            |                          |                           |               |
|    SSH Cert (Ephemeral)         mTLS (SVID X.509)        Node Attestation (JWT)   |
|            v                          v                           v               |
|  +--------------------+   +-----------------------+   +------------------------+  |
|  | OpenSSH Server     |   | Workload Socket       |   | HashiCorp Vault / KMS  |  |
|  | (PAM + FIDO2/MFA)  |   | (Envoy / Service Mesh)|   | (CA Root / HSM backed) |  |
|  +---------+----------+   +-----------+-----------+   +------------------------+  |
|            |                          |                                           |
+------------|--------------------------|-------------------------------------------+
| SYSTEM CALL INTERFACE (POSIX API: execve, openat, socket, ptrace, bpf)            |
+------------|--------------------------|-------------------------------------------+
| KERNEL SPACE                          v                                           |
|            |             +-------------------------+                              |
|            +------------>| Linux Security Modules  |                              |
|                          | (SELinux / AppArmor)    |                              |
|                          +------------+------------+                              |
|                                       v                                           |
|                          +-------------------------+                              |
|                          | Seccomp-BPF Filters     |                              |
|                          +------------+------------+                              |
|                                       v                                           |
|                          +-------------------------+                              |
|                          | eBPF Runtime Monitor    |                              |
|                          | (Cilium Tetragon / LSM) |                              |
|                          +------------+------------+                              |
|                                       v                                           |
|    [ CPU / Memory / Storage / Physical NIC Controllers via VFS & Network Core ]   |
+-----------------------------------------------------------------------------------+
```

#### Komponen Arsitektur Utama:

1. **Linux Security Modules (LSM) Engine**:
   LSM menyediakan *hooks* di titik-titik krusial kernel (seperti alokasi *inode*, manipulasi *file descriptors*, eksekusi proses, dan binding *socket*). Ketika sistem memanggil syscall seperti `sys_execve`, kernel tidak langsung mengeksekusinya. Kernel melewati pengecekan DAC (Discretionary Access Control: `rwx` tradisional), lalu mengeksekusi *hook* LSM untuk evaluasi MAC (Mandatory Access Control) via SELinux Type Enforcement atau AppArmor Path-based Profiles.

2. **eBPF (Extended Berkeley Packet Filter) Execution Sandbox**:
   eBPF mengeksekusi bytecode yang diverifikasi secara aman langsung di dalam kernel tanpa perlu mengompilasi ulang kernel atau memuat modul kernel eksternal (LKM). Melalui `tracepoints`, `kprobes`, dan `LSM-BPF hooks`, eBPF menginspeksi argumen register dan payload memori kernel secara asinkron maupun sinkron, memungkinkan *runtime enforcement* berbasis *kill-signal* otomatis seketika saat instruksi terlarang dieksekusi.

3. **Ephemeral Identity Fabric (SPIFFE/SPIRE & Vault SSH-CA)**:
   Menggantikan kunci statis publik/privat (`~/.ssh/authorized_keys`) yang rawan bocor dan sulit dirotasi. Identity Provider bertindak sebagai Certificate Authority (CA) terdistribusi. Node dan workload divalidasi melalui *cryptographic attestation* (platform hardware TPM 2.0, AWS instance identity document, atau Kubernetes Service Account token) sebelum diterbitkan sertifikat X.509 atau SSH Certificate berdurasi sangat pendek (misal: 5 hingga 60 menit).

---

### 4. Why & What

| Dimensi | Pendekatan Konvensional (Legacy) | Pendekatan Enterprise Hardened (Modern) |
| :--- | :--- | :--- |
| **Autentikasi Host** | Kunci privat RSA/Ed25519 statis tersimpan di laptop engineer tanpa masa kedaluwarsa. | SSH Certificate Authority (SSH-CA) dengan sertifikat berdurasi pendek (5 menit) dan autentikasi multi-faktor FIDO2 hardware token. |
| **Identitas Workload** | Database token / API Key statis yang disimpan dalam file konfigurasi atau environment variable. | Identitas dinamis berbasis SPIFFE/SPIRE (SVID) dengan rotasi otomatis mTLS setiap jam tanpa restart aplikasi. |
| **Kontrol Hak Akses** | Discretionary Access Control (DAC: `chmod`, `chown`). Root memiliki kekuasaan mutlak. | Mandatory Access Control (MAC via SELinux/AppArmor) + Seccomp. Sekalipun user `root` terkompromi di container, kernel menolak akses ke host resource. |
| **Runtime Auditing** | Log audit terfragmentasi (`auditd`, syslog) dengan latency pemrosesan tinggi dan risiko log tampered. | eBPF observability (Tetragon/Falco) yang membaca langsung event kernel ring-buffer secara real-time, tamper-proof, dan berperforma tinggi. |

#### Alasan Transisi (The "Why"):
- **Eliminasi Credential Sprawl & Leakage**: 80% insiden peretasan melibatkan kredensial statis yang bocor dari workstation developer atau tersimpan di repositori kode.
- **Blast Radius Containment**: Mencegah lateral movement. Jika sebuah proses compromised di User Space, kernel membatasi hak baca dan eksekusinya ke level paling minimum (*Principle of Least Privilege*).
- **Compliance & Regulatory Standards**: Menjawab mandat standar ketat seperti PCI-DSS v4.0, SOC2 Type II, dan ISO/IEC 27001:2022 klausul kontrol akses dan logging operasional.

---

### 5. How (Workflow Detail)

Alur autentikasi dan penegakan keamanan host modern dibagi menjadi dua alur: Identity Attestation Flow dan Runtime Execution Interception Flow.

#### Workflow 1: Ephemeral SSH Certificate Access via HashiCorp Vault
```
Engineer               Vault (SSH-CA)              Bastion / Target Host
   |                         |                                |
   | 1. OIDC Login (MFA)     |                                |
   |------------------------>|                                |
   | 2. Generate Keypair     |                                |
   |    & Send Pubkey        |                                |
   |------------------------>|                                |
   | 3. Sign SSH Key         |                                |
   |    (Valid for 15 mins)  |                                |
   |<------------------------|                                |
   |                                                          |
   | 4. Connect with Signed Certificate                       |
   |--------------------------------------------------------->|
   |                         |   5. Validate Cert with Host's |
   |                         |      Trusted CA Public Key     |
   |                         |   6. Map Principals & Groups   |
   |                         |   7. Audit PAM Session         |
   |<========================================================>|
   |         Established Secure Shell Session                 |
```

#### Workflow 2: Kernel Space eBPF / LSM Enforcement
1. **Pemicu Sistem**: Penyerang berhasil mengeksekusi remote payload dan mencoba menjalankan *binary* reverse shell `/bin/bash` dari konteks web service `nginx`.
2. **Trap ke Kernel**: CPU beralih dari User Mode (Ring 3) ke Kernel Mode (Ring 0) melalui instruksi `syscall: sys_execve`.
3. **LSM Hook Interception**: Kernel memanggil hook `security_bprm_check`.
4. **AppArmor/SELinux Profile Check**: Kebijakan memeriksa apakah label domain `httpd_t` memiliki hak eksekusi terhadap target bin `shell_exec_t`. Jika tidak cocok, kernel mengembalikan error `EACCES (Permission Denied)`.
5. **eBPF Program Execution**: Program eBPF yang terpasang pada hook `sched_process_exec` mendeteksi adanya pelanggaran namespace process tree (parent process adalah `nginx`, child process adalah `/bin/bash`).
6. **Active Termination**: eBPF mengirimkan sinyal pembatalan syscall atau mengirimkan sinyal `SIGKILL` (via `bpf_send_signal`) langsung ke PID penyerang, mencatat event secara paralel ke Ring Buffer untuk dikirim ke SIEM.

---

### 6. Analogy & Diagram ASCII

#### Analogi: Paspor Diplomatik & Sensor Biometrik Bandara
- **Kunci Statis (Legacy)** ibarat **kunci pintu konvensional**: Jika dicuri atau diduplikasi, siapa pun yang memegangnya bisa masuk kapan saja tanpa jejak hingga silinder kunci diganti secara manual.
- **SSH-CA & SPIFFE (Modern)** ibarat **Paspor Diplomatik Digital dengan Barcode Dinamis**: Paspor ini hanya berlaku 15 menit, mencantumkan dengan tepat ruangan mana yang boleh dikunjungi (principals), diverifikasi oleh petugas gerbang menggunakan stempel resmi kedutaan (CA Public Key), dan hancur dengan sendirinya setelah masa berlakunya habis.
- **LSM & eBPF** ibarat **Sistem Pemindai X-Ray & Penjaga Keamanan Internal Gedung**: Sekalipun seseorang berhasil menyelinap melewati gerbang depan dengan kartu akses curian, setiap kali ia melangkah membuka pintu brankas atau mengambil berkas rahasia, sensor otomatis mendeteksi deviasi perilaku dan menetralkan target seketika di tempat.

#### Diagram Arsitektur Isolasi Host

```
+-------------------------------------------------------------------------+
| HOST BORDER (HARDENED LINUX NODE)                                       |
|                                                                         |
|  [ Ingress Traffic ]                                                    |
|         |                                                               |
|         v                                                               |
|  +--------------------+                                                 |
|  | nftables / eBPF-TC | --> Drop Invalid TCP Flags, Syncookies, Rate Lim|
|  +---------+----------+                                                 |
|            |                                                            |
|            v                                                            |
|  +--------------------+                                                 |
|  | OpenSSH Server     | <-- Uses TrustedUserCAKeys (No local keys)      |
|  +---------+----------+                                                 |
|            |                                                            |
|            v (Fork & Exec User Process)                                 |
|  +--------------------+                                                 |
|  | PAM Stack          | --> pam_faillock, pam_google_authenticator/FIDO2|
|  +---------+----------+                                                 |
|            |                                                            |
|            v                                                            |
|  +-------------------------------------------------------------------+  |
|  | KERNEL EXECUTION BOUNDARY                                         |  |
|  |                                                                   |  |
|  |   Syscall Execution: sys_execve, socket, openat                   |  |
|  |         |                                                         |  |
|  |         v                                                         |  |
|  |   +--------------------------+                                    |  |
|  |   | AppArmor / SELinux (MAC) | --> Reject unauthorized path/label |  |
|  |   +-------------+------------+                                    |  |
|  |                 v                                                 |  |
|  |   +--------------------------+                                    |  |
|  |   | Seccomp Filter Profile   | --> Block unneeded syscalls        |  |
|  |   +-------------+------------+                                    |  |
|  |                 v                                                 |  |
|  |   +--------------------------+                                    |  |
|  |   | Tetragon (eBPF Engine)   | --> Kill process on SIGKILL if bad |  |
|  |   +--------------------------+                                    |  |
|  |                                                                   |  |
|  +-------------------------------------------------------------------+  |
+-------------------------------------------------------------------------+
```

---

### 7. Simple Example & Practical Example

#### A. Simple Example: Linux Sysctl Hardening (`sysctl-hardening.conf`)
Konfigurasi baseline memori dan network stack tingkat kernel untuk mencegah manipulasi memori, redirect routing, dan spoofing.

```ini
# /etc/sysctl.d/99-enterprise-hardening.conf

# 1. Proteksi Memori & Kernel Pointer Restriction
kernel.kptr_restrict = 2
kernel.dmesg_restrict = 1
kernel.printk = 3 3 3 3
kernel.unprivileged_bpf_disabled = 1
net.core.bpf_jit_harden = 2
kernel.yama.ptrace_scope = 2

# 2. Mitigasi Serangan Filesystem Link (Symlink/Hardlink Exploits)
fs.protected_hardlinks = 1
fs.protected_symlinks = 1
fs.protected_fifos = 2
fs.protected_regular = 2

# 3. Penguatan Network Stack (Mencegah Man-in-the-Middle & IP Spoofing)
net.ipv4.conf.all.rp_filter = 1
net.ipv4.conf.default.rp_filter = 1
net.ipv4.conf.all.accept_redirects = 0
net.ipv4.conf.default.accept_redirects = 0
net.ipv4.conf.all.secure_redirects = 0
net.ipv4.conf.default.secure_redirects = 0
net.ipv6.conf.all.accept_redirects = 0
net.ipv6.conf.default.accept_redirects = 0
net.ipv4.conf.all.send_redirects = 0
net.ipv4.conf.default.send_redirects = 0
net.ipv4.icmp_echo_ignore_broadcasts = 1
net.ipv4.tcp_syncookies = 1
net.ipv4.tcp_rfc1337 = 1

# 4. Virtual Memory ASLR & Core Dump Restriction
vm.mmap_rnd_bits = 32
vm.mmap_rnd_compat_bits = 16
fs.suid_dumpable = 0
```

#### B. Practical Example: Production-Grade Infrastructure

##### 1. HashiCorp Vault SSH CA Setup Script (`setup-ssh-ca.sh`)
Mengonfigurasi Vault sebagai Identity-based SSH Certificate Authority.

```bash
#!/usr/bin/env bash
set -euo pipefail

export VAULT_ADDR="https://vault.internal.enterprise:8200"

echo "[+] Mounting SSH Secrets Engine..."
vault secrets enable -path=ssh-client-signer ssh || true

echo "[+] Configuring SSH CA Engine Keypair..."
vault write ssh-client-signer/config/ca \
    generate_signing_key=true

echo "[+] Exporting SSH CA Public Key..."
vault read -field=public_key ssh-client-signer/config/ca > /tmp/trusted-user-ca-keys.pem

echo "[+] Creating Production Engineer Role with TTL = 15m..."
vault write ssh-client-signer/roles/sre-production \
    key_type=ca \
    algorithm_signer=rsa-sha2-512 \
    allow_user_certificates=true \
    allowed_users="ubuntu,admin,deploy" \
    allowed_extensions="permit-pty,permit-port-forwarding" \
    default_extensions='{"permit-pty": ""}' \
    default_user="ubuntu" \
    ttl="15m" \
    max_ttl="30m"

echo "[✓] SSH-CA configured successfully. Public Key saved to /tmp/trusted-user-ca-keys.pem"
```

##### 2. Host SSHD Configuration (`/etc/ssh/sshd_config.d/99-hardened.conf`)
Menghapus penggunaan `authorized_keys` dan mewajibkan autentikasi via Certificate Authority serta konfigurasi cryptographic cipher terkini.

```text
# Enforce Protocol & Network
Port 2222
AddressFamily inet
Protocol 2

# Cryptographic Cipher Suites (Post-Quantum Ready & High Security)
KexAlgorithms curve25519-sha256,curve25519-sha256@libssh.org,diffie-hellman-group16-sha512,diffie-hellman-group18-sha512
Ciphers chacha20-poly1305@openssh.com,aes256-gcm@openssh.com
MACs hmac-sha2-512-etm@openssh.com

# Disable Legacy Authentication
PermitRootLogin no
PasswordAuthentication no
ChallengeResponseAuthentication no
PubkeyAuthentication yes
AuthorizedKeysFile none

# Zero-Trust Certificate Configuration
TrustedUserCAKeys /etc/ssh/trusted-user-ca-keys.pem
RevocationFile /etc/ssh/revoked-keys

# Session & Audit Hardening
ClientAliveInterval 300
ClientAliveCountMax 0
MaxAuthTries 3
MaxSessions 2
TCPKeepAlive no
X11Forwarding no
AllowAgentForwarding no
```

##### 3. Cilium Tetragon eBPF TracingPolicy (`tracing-policy.yaml`)
Mendeteksi dan secara instan membunuh (`SIGKILL`) proses unauthorized yang mencoba membaca file privilese atau mengeksekusi shell dari konteks non-admin.

```yaml
apiVersion: cilium.io/v1alpha1
kind: TracingPolicy
metadata:
  name: block-namespace-and-priv-escalation
  namespace: kube-system
spec:
  kprobes:
    # Trap eksekusi binary
    - call: "sys_execve"
      syscall: true
      args:
        - index: 0
          type: "string" # Binary path
      selectors:
        - matchArgs:
            - index: 0
              operator: "Prefix"
              values:
                - "/bin/nc"
                - "/bin/netcat"
                - "/usr/bin/ncat"
                - "/tmp/"
          matchActions:
            - action: Sigkill
            - action: Post
              rateLimit: "10m"
    # Trap modifikasi kapabilitas kernel
    - call: "commit_creds"
      syscall: false
      args:
        - index: 0
          type: "cred"
      selectors:
        - matchNamespaces:
            - engine: Host
          matchActions:
            - action: Post
```

---

### 8. Real World Case Study

#### Skenario: Bank Digital Multinasional (PT FinTech Global)
* **Konteks**: Infrastruktur FinTech mengelola 1.200 host server bare-metal dan Kubernetes nodes.
* **Insiden**: Sebuah workstation engineer terinfeksi malware infostealer via supply-chain attack plugin VSCode pihak ketiga. Kunci SSH statis pribadi engineer (`id_ed25519`) dicuri. Penyerang menggunakan kunci ini untuk pivot melompati bastion host ke database pembayaran PCI-DSS yang masih mempercayai public key statis tersebut.
* **Akar Masalah**:
  1. *Unrestricted Static Keys*: Tidak ada masa kedaluwarsa pada public keys di `~/.ssh/authorized_keys`.
  2. *Lack of Host Introspection*: Tidak ada deteksi runtime pada host OS saat engineer mengeksekusi *reconnaissance tools* (`nmap`, raw socket binding).

#### Langkah Transformasi:
1. **Adopsi Ephemeral Identity SSH-CA**:
   Menghapus semua file `authorized_keys` di 1.200 host. Setiap akses SSH diwajibkan meminta sertifikat dari Vault yang diintegrasikan ke Identity Provider (Okta) dengan Hardware Token (YubiKey FIDO2). TTL sertifikat dipatok **10 menit**.
2. **Penerapan eBPF Detection & Enforcement**:
   Menginstalasi daemon Cilium Tetragon di setiap node. Setiap eksekusi tool reconnaissance atau manipulasi `/etc/pam.d/` dan `/etc/shadow` langsung memicu sinyal `SIGKILL` dari kernel dan mengirimkan notifikasi prioritas tinggi ke SOC/SIEM via gRPC stream.
3. **Hasil Terukur (Post-Implementation)**:
   - Pengurangan waktu rotasi kredensial dari 30 hari menjadi **0 detik** (otomatis kedaluwarsa).
   - *Lateral movement dwell time* berkurang dari rata-rata **48 jam** menjadi **0 milidetik** (langsung terminated di tingkat kernel).

---

### 9. Trade-offs

| Aspek Implementasi | Keuntungan (Pros) | Biaya / Konsekuensi (Cons) | Strategi Mitigasi |
| :--- | :--- | :--- | :--- |
| **Short-Lived SSH-CA (TTL 10m)** | Kredensial tidak bernilai jika dicuri; audit terpusat; tidak butuh rotasi manual. | Jika kluster Vault down, tidak ada engineer yang bisa login darurat (*break-glass* problem). | Sediakan *Break-glass Emergency CA* fisik offline yang disimpan di brankas fisik dengan skema *Shamir's Secret Sharing*. |
| **LSM Strict Mode (SELinux Enforcing)** | Mengurung proses zero-day exploit; mencegah eksfiltrasi file host. | Konfigurasi rumit; *false positives* tinggi yang dapat merusak aplikasi saat deployment baru. | Bangun pipeline CI/CD yang mengompilasi custom SELinux modules dari environment staging melalui parsing `audit2allow`. |
| **eBPF In-Kernel Kill Signals** | Penindakan sub-milidetik; tidak membebani User Space parsing pipeline. | Potensi *kernel panic* jika tracepoint pointer salah didereferensikan (walaupun telah divalidasi verifier). | Uji eBPF bytecode pada staging kernel target menggunakan kernel CI test harness sebelum rollout produksi. |
| **Kernel Hardening Sysctl** | Menutup celah eksploitasi memori tingkat lanjut (ASLR brute force, ptrace injection). | Berpotensi merusak beberapa software debugging (seperti `gdb`, `strace`, profiling agent). | Aktifkan `ptrace_scope = 2` pada sistem produksi, tetapi longgarkan ke `1` pada server staging khusus development. |

---

### 10. Common Mistakes & Troubleshooting

#### 1. Kesalahan: SSH CA Clock Skew
* **Gejala**: Engineer ditolak saat login SSH dengan error `Certificate invalid: current time is before valid minimum` atau `Certificate expired`.
* **Penyebab**: Perbedaan sinkronisasi waktu (NTP drift) antara Vault Server, Client Machine, dan Host Target.
* **Solusi**: Pastikan seluruh ekosistem disinkronisasikan menggunakan `chrony` dengan pool NTP terpercaya. Di Vault, set opsi `not_before_duration` ke `30s` untuk mengakomodasi clock-skew minor:
  ```bash
  vault write ssh-client-signer/roles/sre-production not_before_duration="30s" ...
  ```

#### 2. Kesalahan: Konfigurasi File Permission PAM/SSH yang Terlalu Permisif
* **Gejala**: SSH daemon secara diam-diam mengabaikan file kunci CA dan kembali menolak koneksi.
* **Penyebab**: SSHD memiliki mekanisme `StrictModes yes`. Jika direktori `/etc/ssh` atau file `trusted-user-ca-keys.pem` memiliki write permission untuk *group* atau *others*, SSHD menolak membacanya demi keamanan.
* **Solusi**:
  ```bash
  sudo chown root:root /etc/ssh/trusted-user-ca-keys.pem
  sudo chmod 0644 /etc/ssh/trusted-user-ca-keys.pem
  ```

#### 3. Kesalahan: SELinux Context Hilang Setelah File Copy
* **Gejala**: Service gagal membaca file konfigurasi baru walaupun izin DAC (`chmod 777`) telah diberikan.
* **Penyebab**: File disalin (`cp`) dari direktori home user sehingga mewarisi label `user_home_t`, bukan `etc_t`.
* **Solusi**: Periksa dan perbaiki label keamanan SELinux menggunakan tool bawaan:
  ```bash
  ls -laZ /etc/ssh/trusted-user-ca-keys.pem
  restorecon -Rv /etc/ssh/
  ```

---

### 11. Best Practices (Production Checklist)

1. [ ] **Nonaktifkan Semua Kunci Statis**: Kosongkan dan matikan `AuthorizedKeysFile` di konfigurasi SSH server.
2. [ ] **Terapkan SSH-CA Ephemeral**: Pastikan sertifikat SSH memiliki validity period $\le 30$ menit.
3. [ ] **Enforce FIDO2 Hardware Token**: Mewajibkan autentikasi hardware token via PAM (`pam_u2f.so`) untuk setiap eskalasi sudo.
4. [ ] **Kunci Sysctl Network Parameter**: Aktifkan `rp_filter = 1`, matikan `accept_redirects` dan `send_redirects`.
5. [ ] **Mandatory Access Control (MAC)**: Pastikan SELinux berada dalam status `Enforcing` atau AppArmor dalam status `enforce`.
6. [ ] **Deploy eBPF Security Observability**: Pasang monitoring runtime kernel (Tetragon atau Falco) dengan export telemetry audit ke remote log store aman.
7. [ ] **Batasi PTRACE**: Set `kernel.yama.ptrace_scope = 2` untuk memblokir proses membaca atau menginjeksi memori proses lain.
8. [ ] **Audit Trail Tamper-Proofing**: Kirim log audit OS langsung melalui remote encrypted syslog (TLS) ke SIEM yang tidak bisa diakses atau dihapus oleh local administrator host.

---

### 12. Hands-on Practice

Simulasikan implementasi arsitektur SSH-CA terenkripsi lokal dan pengujian interkoneksi aman.

#### Struktur Direktori Lab:
```
hands-on/m02/
├── pki/
│   ├── ca-key
│   └── ca-key.pub
├── config/
│   ├── sshd_config.hardened
│   └── sysctl-production.conf
├── scripts/
│   ├── 01-bootstrap-ca.sh
│   ├── 02-issue-certificate.sh
│   └── 03-validate-login.sh
└── Makefile
```

#### Langkah-langkah Implementasi:

##### Langkah 1: Siapkan Environment & Root CA SSH
Buka terminal dan navigasikan ke `hands-on/m02/scripts/01-bootstrap-ca.sh`:

```bash
#!/usr/bin/env bash
set -e

LAB_DIR="$(pwd)/../pki"
mkdir -p "${LAB_DIR}"

echo "[*] Membuat User CA Keypair (Ed25519)..."
ssh-keygen -t ed25519 -f "${LAB_DIR}/ca-key" -C "Lab Enterprise SSH CA" -N ""

chmod 600 "${LAB_DIR}/ca-key"
chmod 644 "${LAB_DIR}/ca-key.pub"

echo "[✓] CA Keypair siap di ${LAB_DIR}"
```

##### Langkah 2: Skrip Penerbitan Sertifikat Ephemeral
Buat skrip `hands-on/m02/scripts/02-issue-certificate.sh`:

```bash
#!/usr/bin/env bash
set -e

USER_ID="sec-engineer"
CA_KEY="../pki/ca-key"
CLIENT_KEY="../pki/id_ed25519_client"

echo "[*] Membuat Keypair Pengguna Sementara..."
rm -f "${CLIENT_KEY}"*
ssh-keygen -t ed25519 -f "${CLIENT_KEY}" -C "${USER_ID}@corp" -N ""

echo "[*] Menandatangani Sertifikat Publik (Validitas: 5 Menit)..."
ssh-keygen -s "${CA_KEY}" \
    -I "${USER_ID}-session" \
    -n "ubuntu,sec-engineer" \
    -V "+5m" \
    "${CLIENT_KEY}.pub"

echo "[*] Memeriksa Detail Sertifikat yang Diterbitkan:"
ssh-keygen -L -f "${CLIENT_KEY}-cert.pub"
```

##### Langkah 3: Eksekusi Validasi Hands-On
Jalankan perintah berikut:
```bash
cd hands-on/m02/scripts
chmod +x *.sh
./01-bootstrap-ca.sh
./02-issue-certificate.sh
```

Amati output detail sertifikat:
- Nilai `Valid: from [timestamp] to [timestamp]` harus mencerminkan durasi tepat 5 menit.
- Nilai `Principals: ubuntu, sec-engineer` membatasi identitas akun mana yang sah untuk dimasuki.

---

### 13. Exercise

#### Level: Easy
Analisis berkas `/etc/sysctl.conf` pada mesin Linux Anda atau mesin lab. Identifikasi setidaknya 3 konfigurasi parameter jaringan yang masih berstatus default dan rentan terhadap serangan IP Spoofing, lalu buat file override `/etc/sysctl.d/98-anti-spoof.conf` untuk menutup celah tersebut.

#### Level: Medium
Tulis sebuah AppArmor Profile (`/etc/apparmor.d/usr.bin.ping`) dari nol. Profil tersebut harus mengizinkan program `ping` menggunakan RAW sockets (`net_raw`), membaca konfigurasi DNS (`/etc/resolv.conf`), tetapi melarang keras pembacaan file direktori sensitif apa pun di dalam `/etc/shadow`, `/root/`, atau `/home/`.

#### Level: Hard
Bangun policy Cilium Tetragon kprobe JSON/YAML yang mendeteksi penggunaan syscall `ptrace` dengan argumen `PTRACE_POKETEXT` atau `PTRACE_ATTACH` yang dilakukan oleh proses yang bukan bagian dari `systemd` atau debugging tool resmi. Terapkan aksi otomatis `Sigkill` seketika proses terdeteksi mencoba melakukan injeksi shellcode ke proses lain.

---

### 14. Challenge

**Studi Kasus**: Anda ditugaskan mengamankan sebuah kluster server *High-Frequency Trading* (HFT) bare-metal yang menjalankan Linux kernel 6.x. Server ini menampung algoritma perdagangan bernilai miliaran rupiah yang berjalan di *in-memory space*.
- **Kendala Teknis**:
  - Penambahan latensi jaringan atau latensi proses di atas 5 mikrodetik ($\mu s$) akan ditolak oleh tim trading (sehingga security agent tradisional berbasis User Space polling seperti OSquery tidak dapat digunakan).
  - Akses developer ke mesin harus tetap tersedia untuk troubleshooting darurat.
- **Tugas Arsitektur**:
  1. Rancang arsitektur akses zero-trust engineer berbasis SSH-CA yang terintegrasi dengan PAM MFA tanpa meninggalkan port SSH terbuka ke internet publik.
  2. Susun rancangan pertahanan kernel menggunakan LSM-BPF (eBPF + LSM) untuk mengunci proses memory binary HFT agar tidak dapat di-*dump* melalui `/proc/[pid]/mem`, Core Dump, maupun di-*attach* via memory-scraping syscall, tanpa menyebabkan latency overhead pada trade processing pipeline. Dokumentasikan trade-off arsitektur ini secara lengkap.

---

### 15. Quiz Evaluasi Pemahaman

#### Basic Level (5 Soal)
1. **Mengapa SSH Certificate Authority (SSH-CA) jauh lebih scalable dibandingkan model pengelolaan `authorized_keys` tradisional?**
   - A. Karena SSH-CA mengenkripsi traffic jaringan dua kali lipat lebih kuat.
   - B. Karena target server tidak perlu menyimpan public key setiap user; server hanya perlu menyimpan satu public key CA untuk memvalidasi ribuan user.
   - C. Karena SSH-CA tidak memerlukan OpenSSH server.
   - D. Karena SSH-CA otomatis mematikan firewall port 22 saat koneksi terjadi.

2. **Sysctl flag `kernel.kptr_restrict = 2` berfungsi untuk...**
   - A. Mengizinkan siapa saja melihat pointer kernel melalui `/proc/kallsyms`.
   - B. Menyembunyikan alamat pointer kernel dari semua user tanpa memandang privilege (bahkan root), guna mencegah eksploitasi memory corruption.
   - C. Mempercepat eksekusi instruksi pointer CPU.
   - D. Menonaktifkan swap memory.

3. **Perbedaan fundamental antara Discretionary Access Control (DAC) dan Mandatory Access Control (MAC) adalah...**
   - A. DAC diatur oleh kernel, sedangkan MAC diatur oleh BIOS.
   - B. Pada DAC, pemilik file (owner) memiliki wewenang penuh membagikan izin akses; pada MAC, kebijakan sistem terpusat membatasi hak akses bahkan jika owner mengizinkannya.
   - C. MAC hanya bekerja pada sistem operasi Windows.
   - D. DAC tidak mendukung permission read dan write.

4. **Apa bahaya keamanan utama jika `net.ipv4.conf.all.accept_redirects` bernilai `1`?**
   - A. Server menolak koneksi HTTP masuk.
   - B. Penyerang di segmen jaringan lokal dapat mengirim paket ICMP redirect palsu untuk membelokkan rute traffic server melalui mesin penyerang (MitM).
   - C. Bandwidth server akan terpakai secara penuh oleh botnet.
   - D. Memory server akan mengalami leak.

5. **Apa fungsi utama dari Seccomp-BPF dalam host hardening?**
   - A. Mengenkripsi partisi hard disk saat rest.
   - B. Membatasi sistem panggilan (system calls) yang diizinkan untuk dieksekusi oleh suatu proses ke kernel.
   - C. Memvalidasi sertifikat SSL/TLS pada layer aplikasi.
   - D. Menggantikan peran iptables dalam filtering paket data.

#### Intermediate Level (5 Soal)
6. **Jika file `/etc/ssh/trusted-user-ca-keys.pem` memiliki mode permissions `0777`, apa yang akan dilakukan oleh OpenSSH Server dengan setting default `StrictModes yes`?**
   - A. Menjalankan autentikasi seperti biasa tanpa peringatan.
   - B. Menolak memvalidasi sertifikat login pengguna dan menolak koneksi karena file CA dinilai tidak aman.
   - C. Mengubah otomatis izin file menjadi `0600`.
   - D. Menghapus file CA tersebut dari sistem operasi.

7. **Pada implementasi eBPF runtime security, mengapa arsitektur pemantauan berbasis eBPF memiliki keunggulan dibanding parsing log auditd secara konvensional?**
   - A. eBPF berjalan di user space sehingga tidak mengonsumsi resource kernel.
   - B. eBPF dapat mencegat dan mengevaluasi data di kernel ring-buffer secara real-time dengan latensi mikrodetik dan dapat membatalkan syscall secara deterministik via LSM-BPF.
   - C. auditd tidak dapat mencatat proses `execve`.
   - D. eBPF tidak membutuhkan compiler atau LLVM.

8. **Saat mengonfigurasi Pluggable Authentication Modules (PAM) di `/etc/pam.d/sshd`, modul manakah yang harus diletakkan pada urutan atas untuk mencegah serangan brute-force dengan mengunci akun setelah $N$ kali kegagalan?**
   - A. `pam_permit.so`
   - B. `pam_faillock.so` (atau `pam_tally2.so` pada distro lawas)
   - C. `pam_motd.so`
   - D. `pam_env.so`

9. **Apa yang terjadi secara internal di kernel ketika parameter `kernel.yama.ptrace_scope` diatur ke nilai `2`?**
   - A. Hanya proses root dengan kemampuan `CAP_SYS_PTRACE` yang dapat memanggil ptrace ke proses lain; user non-root tidak dapat melampirkan debugger bahkan ke proses milik sendiri.
   - B. Semua eksekusi program dihentikan secara permanen.
   - C. Fitur ptrace dimatikan secara fisik di tingkat chip prosesor.
   - D. Seluruh memory heap langsung dienkripsi menggunakan AES-NI.

10. **Bagaimana SPIFFE Workload API mendistribusikan identitas ke kontainer aplikasi tanpa memerlukan kredensial statis jangka panjang?**
    - A. Memasukkan password database melalui file `.env` di dalam Docker image.
    - B. SPIRE Agent mengautentikasi workload menggunakan kernel/container runtime primitives (cgroups, PID) lalu mengirimkan X.509 SVID berumur pendek via Unix Domain Socket lokal.
    - C. Menggunakan public IP host untuk registrasi via internet.
    - D. Menuliskan private key langsung ke registri DNS publik.

#### Production Scenario Analysis (3 Soal)
11. **Skenario 1**: Seorang teknisi junior mengonfigurasi HashiCorp Vault SSH-CA role untuk environment production dengan parameter `allowed_users="*"` dan `ttl="720h"`. Dampak arsitektur keamanan dan kepatuhan (compliance) yang ditimbulkan oleh konfigurasi ini adalah:
    - A. Konfigurasi ini sangat aman karena mengurangi beban CPU Vault dari permintaan sertifikat berulang.
    - B. Konfigurasi ini merusak esensi Zero-Trust dan melanggar prinsip Least Privilege karena memberikan sertifikat berdurasi 30 hari yang dapat login sebagai user mana pun (termasuk root), meningkatkan risiko *credential exposure window* secara drastis.
    - C. SSH daemon pada host target otomatis me-reject sertifikat dengan TTL lebih dari 24 jam secara default.
    - D. Tidak ada dampak keamanan selama private key disimpan menggunakan passphrase.

12. **Skenario 2**: Sistem produksi Anda yang menjalankan microservices di Kubernetes mendadak mengalami insiden di mana sebuah kontainer Node.js berhasil dieksploitasi via RCE (Remote Code Execution). Penyerang berhasil mengunduh binary scanner dan berniat mengeksekusinya. Manakah kombinasi mitigasi host level yang paling efektif untuk memutus rantai serangan ini seketika?
    - A. Read-only Root Filesystem (`readOnlyRootFilesystem: true`) dikombinasikan dengan Seccomp profile default dan eBPF alert pada syscall `execve`.
    - B. Mengaktifkan CloudWatch Logs polling setiap 15 menit.
    - C. Memberikan user `sudo` tanpa password pada container untuk mempermudah monitoring.
    - D. Mengubah port SSH target ke port non-standar (contoh: port 8022).

13. **Skenario 3**: Sebuah institusi finansial memberlakukan aturan bahwa seluruh engineer yang mengakses host produksi harus melalui MFA berbasis Hardware Token FIDO2. Namun, beberapa engineer mengeluhkan koneksi automasi script Ansible mereka terputus dan gagal autentikasi. Solusi arsitektur produksi yang paling tepat dan aman untuk memecahkan masalah ini adalah:
    - A. Mematikan modul MFA di server target untuk seluruh subnet teknisi.
    - B. Memisahkan jalur akses: Mengharuskan engineer manusia menggunakan SSH-CA bertaut FIDO2 via Bastion, sedangkan automasi pipeline (Ansible/CI-CD) menggunakan Workload Identity (seperti SPIRE / OIDC federated machine token) yang memiliki peran restricted dan IP-whitelisted, bukan personal account.
    - C. Memberikan file private key root tanpa passphrase ke server Ansible.
    - D. Memasukkan kredensial Ansible ke dalam source code repositori Git publik.

---

### Kunci Jawaban Quiz

#### Basic Level
1. **B** — SSH-CA mengeliminasi replikasi public key di target server; server cukup memverifikasi stempel digital CA yang ada pada sertifikat client.
2. **B** — Nilai `2` pada `kptr_restrict` menyembunyikan pointer kernel (`%pK`) sepenuhnya dari semua konteks user untuk mencegah attacker menghitung offset exploit memory.
3. **B** — DAC menyerahkan kontrol pada owner file, sedangkan MAC menegakkan regulasi policy security terpusat terlepas dari status ownership.
4. **B** — ICMP redirects dapat dimanipulasi oleh entitas jahat di L2 broadcast domain untuk merusak tabel routing kernel dan melakukan sniffing traffic.
5. **B** — Seccomp-BPF memfilter interface syscall kernel, memblokir akses ke fungsi kernel yang tidak diizinkan untuk proses terkait.

#### Intermediate Level
6. **B** — OpenSSH memiliki sistem proteksi bawaan (`StrictModes`); jika file konfigurasi penting memiliki permission longgar (writeable oleh user lain), SSHD menolak menggunakannya demi integritas sistem.
7. **B** — eBPF beroperasi langsung di kernel space tracepoints/kprobes dengan performa sangat tinggi tanpa overhead context-switch user-kernel auditd, serta mampu bertindak aktif (membatalkan eksekusi/SIGKILL).
8. **B** — `pam_faillock.so` bertindak sebagai rate-limiter dan gatekeeper penghitung kegagalan password pada stack autentikasi PAM.
9. **A** — Scope level `2` mengunci ptrace hanya untuk proses dengan kapabilitas `CAP_SYS_PTRACE`, mencegah proses non-privilese membaca/menulis memory proses lain milik user yang sama.
10. **B** — Workload attestation SPIFFE/SPIRE menggunakan kernel metadata (cgroups, namespaces, PID) untuk mengidentifikasi container dan menerbitkan SVID melalui UDS (Unix Domain Socket) tanpa rahasia statis.

#### Production Scenario Analysis
11. **B** — Parameter `*` dan masa aktif `720h` (1 bulan) melenyapkan sifat ephemeral, mengembalikan kelemahan static credential di mana pencurian cert memberikan kontrol penuh selama 30 hari.
12. **A** — Read-only root filesystem mencegah penulisan binary ke disk, seccomp menolak syscall berisiko, dan eBPF menginterupsi eksekusi binary baru secara real-time.
13. **B** — Manusia dan mesin memiliki karakteristik lifecycle yang berbeda. Manusia wajib melalui hardware token (MFA), sedangkan mesin menggunakan Machine-to-Machine Identity Framework (SPIFFE/Vault Machine Role) terisolasi.

---

### 16. Summary

Implementasi Identity, Access, dan Host Hardening skala enterprise modern bergeser dari mekanisme perimeter terluar ke **Kernel-Enforced Zero-Trust Architecture**. 

1. **Eliminasi Kredensial Statis**: Penggunaan SSH-CA dan workload attestation (SPIFFE/SPIRE) menghapus risiko kebocoran kunci SSH privat statis dan mereduksi attack surface autentikasi secara substansial.
2. **Kernel Defense-in-Depth**: Hardening kernel melalui kombinasi `sysctl` security parameters, pembatasan syscall via **Seccomp-BPF**, dan penegakan Mandatory Access Control (**AppArmor / SELinux**) memastikan penyerang yang berhasil menembus User Space tetap terisolasi di dalam sandbox yang sangat terbatas.
3. **Runtime Protection Berbasis eBPF**: Integrasi tracing engine modern seperti Cilium Tetragon mentransformasi pemantauan keamanan dari model pasif (audit log reaktif) menjadi penegakan aktif (sub-millisecond in-kernel termination), mewujudkan postur pertahanan yang resilient terhadap ancaman zero-day kontemporer.