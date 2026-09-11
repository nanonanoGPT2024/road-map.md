# Module 01: Idempotency, YAML Playbooks, Inventory Groups, & SSH Remote Exec

## 1. Learning Objective
Setelah menyelesaikan modul ini, pembelajar akan mampu:
1. Memahami perbedaan filosofi antara arsitektur **Agentless** (Ansible via SSH) vs **Agent-based** (Puppet, Chef).
2. Menguasai prinsip fundamental **Idempotency** (dieksekusi 1 kali atau 100 kali menghasilkan kondisi akhir yang persis sama tanpa efek samping).
3. Mengelola pengelompokan server target menggunakan file **Inventory** (INI dan YAML) beserta host variables.
4. Menulis dan mengeksekusi **Ansible Playbooks** terstruktur menggunakan modul standar (`apt`/`dnf`, `systemd`, `copy`, `template`, `file`).

---

## 2. Prerequisite
- Memahami konsep dasar administrasi Linux (SSH key pairs, Systemd service, file permissions) dari [BAB 01](file:///d:/explore/roadmap.sh%20materi/DevOps/BAB-01-Sistem-Operasi-dan-Linux-Automation/Module-02-Otomasi-Shell-Scripting-dan-Diagnostik-Sistem.md).
- Mengetahui struktur format data YAML (indentasi spasi, list, key-value).

---

## 3. Concept
Setelah Terraform selesai membuat 50 Virtual Machine di cloud, server-server tersebut masih kosong melompong (hanya OS Linux mentah). Bagaimana cara menginstal dependensi, mengonfigurasi user Linux, mengatur firewall, dan menyalin konfigurasi Nginx ke 50 server tersebut?
- SSH manual satu per satu? Memakan waktu berjam-jam dan rentan salah ketik.
- Bash script loop? Rentan gagal di tengah jalan dan tidak idempotent.

**Ansible** adalah alat otomatisasi *Configuration Management* yang bekerja secara **Agentless**:
- Anda **tidak perlu menginstal software agen atau daemon tambahan** di server target.
- Ansible cukup berjalan di laptop/bastion host Anda, terhubung ke server target menggunakan protokol standar **OpenSSH**, mengeksekusi modul Python sementara, lalu menghapus jejaknya secara bersih.

Pilar paling agung dalam Ansible adalah **Idempotency**:
Sebuah task Ansible tidak hanya menjalankan perintah, melainkan **memeriksa kondisi saat ini terlebih dahulu**:
> *"Pastikan package nginx terinstal."*
Jika Nginx sudah terinstal, Ansible tidak melakukan apa-apa (`ok`). Jika belum terinstal, Ansible menginstalnya (`changed`). Jika ada error, Ansible berhenti dan melaporkan (`failed`).

---

## 4. Why?
Mengapa Ansible sangat dicintai oleh tim DevOps dan SysAdmin?
1. **Zero Agent Overhead**: Tidak ada proses agent latar belakang yang memakan RAM CPU di server target, dan tidak ada celah keamanan agent port yang harus dibuka.
2. **Keterbacaan Bahasa Manusiawi (YAML)**: Playbook Ansible mudah dibaca oleh siapa saja selayaknya dokumentasi langkah konfigurasi yang hidup.
3. **Idempotensi Bawaan**: Anda dapat menjalankan playbook yang sama setiap hari untuk memastikan tidak ada konfigurasi server yang bergeser (*enforcing desired state*).

---

## 5. What?
Komponen penting dalam Ansible:
- **Control Node**: Mesin tempat Ansible diinstal (Linux/macOS/WSL).
- **Managed Nodes**: Server-server target yang dikelola via SSH.
- **Inventory File (`hosts.ini` / `hosts.yaml`)**: Daftar IP/hostname server yang dikelompokkan ke dalam grup (misal `[webservers]`, `[databases]`).
- **Playbook**: File YAML yang memuat satu atau lebih *Plays*. Setiap Play memetakan grup host ke daftar *Tasks*.
- **Modules**: Satuan kerja diskrit Ansible (contoh: `ansible.builtin.apt`, `ansible.builtin.systemd`, `ansible.builtin.git`).

---

## 6. How?
Alur kerja eksekusi Ansible Playbook:

```text
[ Control Node (Laptop/Runner): ansible-playbook -i hosts site.yaml ]
                                  │
                                  ▼
             [ Baca File Inventory & Kredensial SSH Key ]
                                  │
                                  ▼
[ Terhubung Secara Paralel via OpenSSH ke Managed Nodes ]
  Node 1 (10.0.1.10)       Node 2 (10.0.1.11)       Node 3 (10.0.1.12)
        │                        │                        │
        ▼                        ▼                        ▼
[ Gathering Facts: Kumpulkan OS version, IP, CPU cores, RAM ]
        │                        │                        │
        ▼                        ▼                        ▼
[ Task 1: Pastikan Nginx terinstal (apt state=present) ]
  - Jika belum ada -> apt-get install -> [CHANGED]
  - Jika sudah ada -> Lewati          -> [OK]
        │                        │                        │
        ▼                        ▼                        ▼
[ Task 2: Pastikan Nginx service aktif (systemd state=started) ]
  - Status: [OK]
                                  │
                                  ▼
[ PLAY RECAP: ok=3, changed=1, unreachable=0, failed=0 ]
```

---

## 7. Analogy
Bayangkan **Ansible** seperti **Mandor Inspektur Kualitas Hotel**:
- Sang inspektur (Ansible) membawa daftar checklist standar kamar (*Playbook*):
  - 1. Handuk putih bersih harus ada 2 buah di kamar mandi.
  - 2. Sabun cair harus terisi penuh.
  - 3. AC harus menyala pada suhu 22°C.
- Inspektur masuk ke 50 kamar hotel (Managed Nodes).
- Di Kamar 101, handuk sudah ada 2 buah -> Inspektur tidak mengganti apa-apa (`ok`).
- Di Kamar 102, handuk hanya ada 1 -> Inspektur menambahkan 1 handuk lagi (`changed`).
- Apapun kondisi awal kamar, setelah inspektur selesai, seluruh 50 kamar dijamin berada dalam kondisi standar sempurna yang seragam (*Idempotent*).

---

## 8. Diagram
```text
+-------------------------------------------------------------+
|                     CONTROL NODE (Ansible)                  |
|  ├── hosts.ini (Inventory)                                  |
|  └── deploy-web.yaml (Playbook)                             |
+-------------------------------------------------------------+
           |                                  |
           | SSH:22 (Public Key Auth)         | SSH:22 (Public Key Auth)
           v                                  v
+-----------------------+          +-----------------------+
| MANAGED NODE 01       |          | MANAGED NODE 02       |
| Group: [webservers]   |          | Group: [webservers]   |
| IP: 192.168.1.10      |          | IP: 192.168.1.11      |
| (Python Interpreter)  |          | (Python Interpreter)  |
+-----------------------+          +-----------------------+
```

---

## 9. Simple Example
File Inventory `inventory.ini`:

```ini
[webservers]
web1.prod.acme.com ansible_host=10.0.1.10
web2.prod.acme.com ansible_host=10.0.1.11

[databases]
db1.prod.acme.com ansible_host=10.0.2.10

[all:vars]
ansible_user=ubuntu
ansible_ssh_private_key_file=~/.ssh/id_ed25519
ansible_python_interpreter=/usr/bin/python3
```

Eksekusi ad-hoc command:
```bash
# Ping seluruh server di inventory via SSH
ansible all -i inventory.ini -m ping

# Periksa uptime seluruh server web
ansible webservers -i inventory.ini -a "uptime"
```

---

## 10. Practical Example
Playbook Ansible untuk provisioning web server (`setup-web.yaml`):

```yaml
---
- name: Provisioning Hardened Web Servers
  hosts: webservers
  become: true # Jalankan sebagai sudo root

  tasks:
    - name: Update apt repository cache
      ansible.builtin.apt:
        update_cache: true
        cache_valid_time: 3600

    - name: Pastikan Nginx dan UFW firewall terinstal
      ansible.builtin.apt:
        name:
          - nginx
          - ufw
        state: present

    - name: Salin file konfigurasi kustom Nginx
      ansible.builtin.copy:
        src: files/nginx.conf
        dest: /etc/nginx/nginx.conf
        owner: root
        group: root
        mode: '0644'
      notify: Restart Nginx Service

    - name: Pastikan service Nginx aktif dan enabled saat boot
      ansible.builtin.systemd:
        name: nginx
        state: started
        enabled: true

  handlers:
    - name: Restart Nginx Service
      ansible.builtin.systemd:
        name: nginx
        state: restarted
```

---

## 11. Real World Example
### Kasus: Patching Kerentanan Zero-Day OpenSSL di 200 Server Linux dalam 5 Menit
1. Muncul kerentanan kritis CVE OpenSSL yang memungkinkan remote code execution di seluruh server Ubuntu.
2. Tim keamanan mewajibkan seluruh 200 server di-upgrade ke paket `openssl_3.0.2-0ubuntu1.10` sebelum jam 12:00.
3. Melakukan SSH manual ke 200 server akan memakan waktu minimal 8 jam.
4. SRE menulis playbook 10 baris:
   ```yaml
   - hosts: all
     become: true
     tasks:
       - name: Upgrade openssl package
         ansible.builtin.apt:
           name: openssl
           state: latest
   ```
5. SRE menjalankan perintah dengan konkruensi 20 thread paralel (`forks=20`):
   ```bash
   ansible-playbook -i production_hosts.ini patch-openssl.yaml -f 20
   ```
6. Seluruh 200 server berhasil di-patch secara serentak dalam waktu **4 menit 15 detik**, menghilangkan celah keamanan sebelum peretas sempat mengeksploitasinya.

---

## 12. Trade-offs
| Pendekatan Configuration Mgmt | Agentless (Ansible via SSH) | Agent-Based (Puppet / Chef / Salt) |
|---|---|---|
| **Kebutuhan Server Target** | Nol (Cukup OpenSSH & Python standar) | Memerlukan instalasi agent daemon di setiap server |
| **Kecepatan di Ribuan Server** | Cepat untuk ratusan node; butuh tuning SSH untuk 5.000+ node | Sangat cepat untuk puluhan ribu node (Push event via ZeroMQ) |
| **Penyimpanan State** | Statik (Tidak memerlukan master server terpusat) | Memerlukan dedicated Puppet Master / Chef Server |
| **Kurva Belajar** | Sangat ramah pemula (Bahasa YAML) | Lebih rumit (Ruby DSL / spesifikasi Puppet) |

---

## 13. When To Use
- Mengelola konfigurasi sistem operasi VM (Linux/Windows), user akun, firewall, dan software paket.
- Provisioning server bare-metal atau VM cloud pasca dibuat oleh Terraform.
- Menjalankan patch security massal atau task maintenance audit terjadwal.

---

## 14. When NOT To Use
- Jangan gunakan Ansible untuk me-manage siklus hidup cloud lifecycle (membuat VPC, Subnet, Load Balancer cloud); gunakan **Terraform** untuk provisioning infrastruktur cloud.

---

## 15. Common Mistakes
1. **Menggunakan Modul `shell` atau `command` untuk Hal yang Sudah Ada Modulnya**: Menulis `shell: apt-get install -y nginx` alih-alih modul `ansible.builtin.apt`. Hal ini merusak prinsip idempotency karena task akan selalu berstatus `changed` setiap kali dijalankan.
2. **Hardcoding IP Address di Playbook**: Menulis IP di dalam task alih-alih menggunakan variabel inventory (`{{ inventory_hostname }}`).
3. **Mengabaikan `become: true`**: Menjalankan task instalasi paket software tanpa izin sudo, menyebabkan error *Permission Denied*.

---

## 16. Best Practices
### Must Have
- Selalu gunakan modul resmi bawaan (`ansible.builtin.*`) daripada modul `command` atau `shell`.
- Gunakan `handlers` dengan `notify:` untuk merestart service hanya jika file konfigurasi mengalami perubahan (*changed*).
- Simpan file konfigurasi Ansible di Git repository dengan struktur standar industri.

### Recommended
- Atur parameter `forks = 20` di `ansible.cfg` untuk mempercepat eksekusi paralel pada banyak server.
- Selalu uji playbook dengan flag `--check` (dry-run mode) sebelum dieksekusi secara nyata ke server production.

### Avoid / Overengineering
- Jangan membuat playbook raksasa monolitik 1.000 baris; gunakan pola modular **Ansible Roles**.

---

## 17. Troubleshooting
| Gejala | Kemungkinan Penyebab | Solusi |
|---|---|---|
| `UNREACHABLE! => Failed to connect to the host via ssh` | SSH key tidak cocok, port 22 tertutup, atau user salah | Uji koneksi manual `ssh -i key.pem user@host` dan periksa security group firewall |
| `Missing sudo password` | User membutuhkan input password untuk sudo di server target | Tambahkan flag `-K` (`--ask-become-pass`) atau konfigurasikan `NOPASSWD` di `/etc/sudoers` |
| `Task always reports 'changed'` | Menggunakan modul `shell` yang tidak memiliki status idempotensi | Tambahkan parameter `creates: /path/to/file` pada modul shell untuk mencegah eksekusi berulang |

---

## 18. Exercise
1. Buat file inventory INI yang membagi 3 server dummy ke dalam grup `[web]` dan `[db]`.
2. Tulis playbook sederhana untuk memastikan direktori `/var/www/html` ada dengan permission `0755`.

---

## 19. Challenge
Rancang arsitektur simulasi **Ansible Idempotency & Playbook Runner**:
- Buat engine runner yang menerima deklarasi task (misal: install package, write config, restart service).
- Saat dijalankan pertama kali: eksekusi perubahan dan laporkan status `CHANGED`.
- Saat dijalankan kedua kali tanpa ada modifikasi: evaluasi kondisi eksisting dan laporkan status `OK (SKIPPED)` tanpa menyentuh sistem.

---

## 20. Summary
- Ansible menawarkan otomatisasi konfigurasi server berbasis *agentless* melalui protokol standar SSH.
- Prinsip *Idempotency* menjamin stabilitas sistem dengan hanya menerapkan perubahan saat kondisi nyata belum sesuai dengan deklarasi.
- Kombinasi deklarasi Playbook YAML dan Inventory memungkinkan manajemen ratusan server Linux secara serentak dalam hitungan menit.
- Modul praktikum lab dapat dijalankan langsung di [hands-on/m01/ansible_idempotent_runner.js](file:///d:/explore/roadmap.sh%20materi/DevOps/BAB-06-Configuration-Management-Ansible/hands-on/m01/ansible_idempotent_runner.js).
