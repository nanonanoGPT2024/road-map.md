# BAB 06: Quiz, Challenge, & Knowledge Check
**Configuration Management & Server Provisioning (Ansible)**

---

## 1. Basic Questions (5 Soal)
1. Apa arti arsitektur *Agentless* pada Ansible, dan protokol jaringan apa yang digunakan untuk mengelola server Linux target?
2. Jelaskan konsep **Idempotency** dalam konteks eksekusi otomatisasi task Ansible!
3. Apa fungsi dari file **Inventory** (`hosts.ini` atau `hosts.yaml`) pada project Ansible?
4. Mengapa kita disarankan menggunakan modul resmi (seperti `ansible.builtin.apt`) daripada menjalankan modul `shell` atau `command`?
5. Apa peran dari direktori `defaults/` dan `vars/` di dalam struktur sebuah **Ansible Role**? Manakah yang memiliki prioritas lebih tinggi?

---

## 2. Intermediate Questions (5 Soal)
6. Bagaimana cara kerja mekanisme **Handlers** dan `notify` pada Ansible Playbook? Kapan sebuah handler akan dieksekusi?
7. Apa itu **Jinja2 Templating**, dan bagaimana sintaks loop `{% for host in groups['web'] %}` digunakan untuk membentuk konfigurasi upstream Nginx dinamis?
8. Bagaimana **Ansible Vault** mengamankan password database dan private key di dalam Git repository menggunakan enkripsi AES-256?
9. Apa fungsi dari perintah `ansible-playbook --check` (Dry Run Mode) sebelum menjalankan deployment ke server produksi?
10. Bagaimana cara mempercepat waktu eksekusi playbook saat mengelola 200 server sekaligus menggunakan parameter `forks`?

---

## 3. Scenario-Based Questions (3 Soal)

### Skenario A: The Non-Idempotent Shell Task Outage
Seorang SysAdmin menulis task Ansible:
```yaml
- name: Append config
  ansible.builtin.shell: echo "export ENV=production" >> /etc/environment
```
Setiap kali playbook dijalankan harian, baris tersebut bertambah terus hingga ada 50 baris duplikat di `/etc/environment`, menyebabkan aplikasi gagal membaca variabel environment.
- *Pertanyaan:* Modul bawaan apa yang seharusnya digunakan (misal `ansible.builtin.lineinfile`), dan parameter apa yang menjamin baris tersebut hanya ada tepat 1 kali?

### Skenario B: The Master Vault Password Disaster
Sebuah perusahaan menggunakan Ansible Vault untuk mengenkripsi 30 file rahasia di Git. Suatu hari, developer yang membuat password master tersebut resign tanpa mendokumentasikan kata sandinya.
- *Pertanyaan:* Apakah isi file Ansible Vault dapat didekripsi tanpa password master, dan prosedur manajemen *Vault Password Key Escrow* apa yang harus diterapkan di masa depan?

### Skenario C: Handlers Skipped on Mid-Playbook Crash
Playbook Anda memiliki task menyalin file konfigurasi database dengan `notify: Restart Database`. Namun, task berikutnya (task instalasi plugin) gagal melempar error sehingga playbook terhenti. Database tidak pernah di-restart dengan konfigurasi baru.
- *Pertanyaan:* Bagaimana parameter `--force-handlers` atau blok `rescue` pada Ansible dapat memastikan handler penting tetap dieksekusi saat terjadi kegagalan parsial?

---

## 4. Chapter Challenge
**Tantangan Praktis: The Modular Production Hardening Role**
Rancang sebuah struktur Ansible Role lengkap (`roles/security_baseline`):
1. **`defaults/main.yml`**: Mendefinisikan port SSH standar (`ssh_port: 2222`) dan paket wajib (`common_packages: [curl, htop, ufw, fail2ban]`).
2. **`tasks/main.yml`**:
   - Memastikan paket wajib terinstal secara idempotent.
   - Merender template Jinja2 `/etc/ssh/sshd_config.j2`.
   - Mengaktifkan firewall UFW dan mengizinkan hanya port `{{ ssh_port }}` dan port `80, 443`.
   - Memicu handler jika file sshd_config berubah.
3. **`handlers/main.yml`**: Me-restart service `ssh` atau `sshd`.
4. **Ansible Vault**: Mengenkripsi password user sudoer di `vars/vault.yml`.

---

## 5. Knowledge Check & Checklist

### Saya harus memahami:
- [ ] Arsitektur Agentless berbasis SSH dan Python interpreter.
- [ ] Prinsip Idempotency (membedakan status `ok`, `changed`, `failed`).
- [ ] Standar konvensi direktori Ansible Roles.
- [ ] Sintaks dynamic templating Jinja2 (loops, filters, conditionals).
- [ ] Enkripsi simetris file rahasia menggunakan Ansible Vault.

### Saya tidak perlu menghafal:
- [ ] Ratusan modul spesifik vendor jaringan Cisco/Juniper (cukup pahami modul standar Linux OS).
- [ ] Format internal enkripsi cipher block chaining.

### Saya harus bisa melakukan:
- [ ] Menulis playbook yang idempotent dan bebas dari penggunaan shell kotor.
- [ ] Merender template konfigurasi dinamis berbasis host facts.
- [ ] Mengenkripsi, mengedit, dan mendekripsi file kredensial via `ansible-vault`.

---
*Ketik **LANJUT** untuk berpindah ke BAB 07: Continuous Integration & Continuous Delivery (CI/CD).*
