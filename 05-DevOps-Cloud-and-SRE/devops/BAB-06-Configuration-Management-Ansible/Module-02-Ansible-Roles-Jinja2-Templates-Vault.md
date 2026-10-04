# Module 02: Ansible Roles, Jinja2 Templating, & Ansible Vault

## 1. Learning Objective
Setelah menyelesaikan modul ini, pembelajar akan mampu:
1. Menata struktur playbook skala besar menggunakan **Ansible Roles** (`tasks`, `handlers`, `vars`, `defaults`, `templates`, `meta`).
2. Menghasilkan file konfigurasi server yang dinamis menggunakan engine **Jinja2 Templating** (`{{ variables }}`, conditional `{% if %}`, dan loop `{% for %}`).
3. Mengamankan kredensial rahasia (password, SSL private key, API tokens) di dalam Git menggunakan **Ansible Vault** (Enkripsi simetris AES-256).
4. Memanfaatkan ekosistem komunitas terverifikasi melalui **Ansible Galaxy**.

---

## 2. Prerequisite
- Memahami konsep dasar Playbook, Inventory, dan Idempotensi dari [BAB 06 Module 01](file:///d:/explore/roadmap.sh%20materi/DevOps/BAB-06-Configuration-Management-Ansible/Module-01-Idempotency-Playbooks-Inventory-SSH.md).
- Mengetahui dasar logika percabangan (if/else) dan perulangan (looping).

---

## 3. Concept
Saat infrastruktur berkembang dari 2 server menjadi ratusan server dengan berbagai peran (Web Server, Database, Cache, Logging Agent), menyimpan semua task di dalam satu file `playbook.yaml` akan menjadi mimpi buruk:
- File menjadi ribuan baris dan sulit dipelihara.
- Variabel bercampur baur antara environment dev dan prod.
- Password database terpampang jelas dalam bentuk plaintext di Git.

Ansible menyediakan 3 pilar arsitektur tingkat lanjut:
1. **Ansible Roles**: Standar konvensi direktori modular yang memisahkan logika task, handler, file statis, dan template ke dalam paket mandiri yang dapat digunakan kembali (*reusable*).
2. **Jinja2 Templating**: Mengubah file statis menjadi file dinamis. Satu file `nginx.conf.j2` dapat otomatis menyesuaikan jumlah `worker_processes` berdasarkan jumlah core CPU server (`{{ ansible_processor_vcpus }}`) dan mendaftarkan upstream backend secara dinamis via loop.
3. **Ansible Vault**: Alat enkripsi berbasis AES-256 yang mengenkripsi seluruh file YAML atau variabel tertentu (*vault-encrypted strings*), memungkinkan Anda menyimpan password sensitif di dalam Git dengan aman.

---

## 4. Why?
Mengapa Roles, Jinja2, dan Vault mutlak digunakan?
1. **Modularitas & Kerapian Kode**: Role `nginx` atau role `security_hardening` dapat dipanggil di puluhan playbook berbeda tanpa perlu menulis ulang task.
2. **Fleksibilitas Lintas Lingkungan**: Konfigurasi memori database atau nama domain disesuaikan otomatis dari file variabel tanpa perlu mengubah logika task.
3. **Keamanan DevSecOps**: Menghilangkan risiko kebocoran password di version control Git tanpa membutuhkan server secrets manager eksternal yang rumit di awal.

---

## 5. What?
Komponen arsitektur:
- **Struktur Standar Direktori Ansible Role**:
  ```text
  roles/common_web/
  ├── defaults/main.yml    # Variabel default (prioritas terendah, mudah di-override)
  ├── vars/main.yml        # Variabel konstan peran
  ├── tasks/main.yml       # Daftar task eksekusi utama
  ├── handlers/main.yml    # Handlers (misal: restart service)
  ├── templates/*.j2       # Template Jinja2 dinamis
  ├── files/*              # File statis murni yang langsung disalin
  └── meta/main.yml        # Metadata peran dan dependency ke role lain
  ```
- **Sintaks Jinja2**:
  - `{{ variable_name }}`: Substitusi nilai variabel.
  - `{% if condition %} ... {% endif %}`: Percabangan logika.
  - `{% for item in list %} ... {% endfor %}`: Looping iterasi data.
- **Ansible Vault CLI**:
  - `ansible-vault create secret.yml`: Membuat file terenkripsi.
  - `ansible-vault encrypt / decrypt`: Mengenkripsi atau mendekripsi file eksisting.
  - `ansible-vault edit secret.yml`: Mengedit file terenkripsi secara in-place.

---

## 6. How?
Alur kerja rendering Jinja2 dan Ansible Vault saat Playbook dijalankan:

```text
[ File playbook.yml ] + [ File vault-secrets.yml (Terenkripsi AES-256) ]
                               │
                               │ Eksekusi: ansible-playbook site.yml --vault-password-file .vault_pass
                               ▼
            [ Ansible Mendekripsi Secret di Memori RAM ]
                               │
                               ▼
        [ Membaca Template: templates/nginx.conf.j2 ]
        "worker_processes {{ ansible_processor_vcpus }};"
        "listen {{ http_port }};"
        "proxy_pass {{ vault_database_password }};"
                               │
                               ▼
            [ Jinja2 Engine Melakukan Substitusi Nilai ]
                               │
                               ▼
[ File Hasil Render /etc/nginx/nginx.conf Disalin ke Managed Node ]
```

---

## 7. Analogy
Bayangkan **Roles & Jinja2 Templates** seperti **Formulir Surat Perjanjian Notaris**:
- Anda memiliki draf baku (*Template Jinja2*):
  *"Pada hari ini {{ hari }}, pihak pertama {{ nama_1 }} menyepakati kontrak senilai {{ nominal }} rupiah..."*
- Anda tidak menulis ulang seluruh pasal dari nol untuk setiap klien; Anda hanya mengganti data isian variabel.
- Brankas kunci (*Ansible Vault*): Data nomor rekening dan PIN klien disimpan di dalam buku catatan bersandi rahasia yang hanya bisa dibaca jika Anda memegang kata sandi master.

---

## 8. Diagram
```text
+-------------------------------------------------------------+
|                     ANSIBLE PLAYBOOK                        |
|  - hosts: all                                               |
|    roles:                                                   |
|      - role: security_baseline                              |
|      - role: postgresql_cluster                             |
|      - role: nodejs_backend                                 |
+-------------------------------------------------------------+
                               │
            ┌──────────────────┴──────────────────┐
            ▼                                     ▼
+-----------------------+             +-----------------------+
|  ROLE: POSTGRESQL     |             |  ANSIBLE VAULT        |
|  ├── tasks/main.yml   | <=========> |  db_password:         |
|  ├── templates/*.j2   |  (Injects)  |  $ANSIBLE_VAULT;1.1;  |
|  └── handlers/        |             |  AES256;...           |
+-----------------------+             +-----------------------+
```

---

## 9. Simple Example
Contoh template Jinja2 `/roles/web/templates/app.conf.j2`:

```nginx
# Konfigurasi di-generate otomatis oleh Ansible
worker_processes {{ ansible_processor_vcpus | default(2) }};

events {
    worker_connections 1024;
}

http {
    upstream api_backend {
        {% for server in backend_servers %}
        server {{ server.ip }}:{{ server.port }};
        {% endfor %}
    }

    server {
        listen {{ http_port }};
        server_name {{ server_domain }};

        location / {
            proxy_pass http://api_backend;
        }
    }
}
```

---

## 10. Practical Example
Penggunaan Ansible Vault untuk mengamankan kredensial:

```bash
# 1. Enkripsi file variabel sensitif dengan password
ansible-vault encrypt group_vars/all/vault.yml

# Tampilan file vault.yml setelah dienkripsi (Aman di-commit ke Git):
# $ANSIBLE_VAULT;1.1;AES256
# 63313264626233306535313938643232386134373461623861343238616234383161393839353934

# 2. Menjalankan playbook dengan menyertakan file password vault
ansible-playbook -i inventory.ini site.yml --vault-password-file ~/.vault_pass.txt
```

---

## 11. Real World Example
### Kasus: Konfigurasi Nginx Upstream Dinamis Berdasarkan Hasil Discovery Server
1. Jumlah backend worker berubah-ubah (bisa 2, 5, atau 10 server tergantung load).
2. Engineer mengelompokkan server di inventory:
   ```ini
   [api_nodes]
   api1.corp ansible_host=10.0.1.10 port=3000
   api2.corp ansible_host=10.0.1.11 port=3000
   api3.corp ansible_host=10.0.1.12 port=3000
   ```
3. Template Jinja2 di proxy Nginx:
   ```jinja2
   upstream backend {
   {% for host in groups['api_nodes'] %}
       server {{ hostvars[host]['ansible_host'] }}:{{ hostvars[host]['port'] }};
   {% endfor %}
   }
   ```
4. Saat ada server baru ditambahkan di inventory, Ansible otomatis merekonstruksi blok upstream dan me-reload Nginx tanpa ada satu baris kode manual yang diedit!

---

## 12. Trade-offs
| Solusi Manajemen Secret | Ansible Vault | HashiCorp Vault / AWS Secrets Manager |
|---|---|---|
| **Infrastruktur Pendukung** | Nol (Enkripsi file statis di Git) | Memerlukan dedicated server/cluster terpisah |
| **Pembaruan Dinamis** | Statik (Harus re-run playbook) | Dinamis (Aplikasi fetch langsung via API/SDK) |
| **Kemudahan Kolaborasi** | Tim harus berbagi password vault master | Berbasis Role-Based Access Control (RBAC) granular |
| **Kesesuaian** | Provisioning VM & server bootstrapping | Microservices cloud-native skala enterprise |

---

## 13. When To Use
- Gunakan **Ansible Roles**: Untuk semua project otomatisasi yang memiliki lebih dari 3 peran server atau lebih dari 10 tasks.
- Gunakan **Jinja2**: Untuk semua file konfigurasi yang nilainya bergantung pada IP host, jumlah core CPU, atau environment dev/prod.
- Gunakan **Ansible Vault**: Untuk menyimpan password database, private key SSH, dan token API di dalam repository Ansible.

---

## 14. When NOT To Use
- Jangan gunakan Ansible Vault untuk secret aplikasi yang harus di-rotate setiap 5 menit secara otomatis (gunakan HashiCorp Vault).

---

## 15. Common Mistakes
1. **Mengabaikan `defaults/main.yml`**: Menaruh seluruh variabel di `vars/main.yml`. Variabel di `vars/` memiliki prioritas sangat tinggi sehingga sulit di-override dari luar role. Selalu taruh variabel konfigurasi fleksibel di `defaults/main.yml`.
2. **Menyimpan Password Vault di Git**: Lupa menambahkan file `.vault_pass.txt` ke dalam `.gitignore`!
3. **Menggunakan Sintaks Variabel di Dalam Conditional**: Menulis `when: "{{ is_production }} == true"` alih-alih `when: is_production`. Direktif `when` sudah mengevaluasi ekspresi Python secara alami tanpa kurung kurawal ganda.

---

## 16. Best Practices
### Must Have
- Sertakan `.vault_pass*` di file `.gitignore`.
- Berikan nama yang deskriptif pada setiap task dan role (`nginx_reverse_proxy`, bukan sekadar `web`).
- Gunakan filter Jinja2 default untuk mencegah error jika variabel kosong (`{{ my_var | default('8080') }}`).

### Recommended
- Gunakan `ansible-lint` untuk memeriksa kepatuhan best practices pada setiap commit Git.
- Manfaatkan role komunitas dari **Ansible Galaxy** (`ansible-galaxy install geerlingguy.docker`) daripada menulis ulang role umum dari nol.

### Avoid / Overengineering
- Jangan membuat logika Jinja2 yang terlalu rumit dengan ekspresi regex berlapis di dalam template; siapkan data bersih di variabel Python/YAML terlebih dahulu.

---

## 17. Troubleshooting
| Gejala | Kemungkinan Penyebab | Solusi |
|---|---|---|
| `fatal: [host]: FAILED! => {"msg": "Decryption failed (no vault secrets found)"}` | File password vault salah atau file belum terenkripsi | Pastikan passphrase yang digunakan saat enkripsi sama dengan yang di `.vault_pass` |
| `undefined variable: 'item'` | Kesalahan penulisan nama variabel di Jinja2 template atau variabel belum didefinisikan | Periksa spelling variabel di `defaults/` atau `vars/` |
| Role tidak ditemukan (*role not found*) | Folder role tidak berada di direktori `roles/` atau path `roles_path` di `ansible.cfg` belum diatur | Pindahkan folder ke direktori `roles/` lokal atau atur path di `ansible.cfg` |

---

## 18. Exercise
1. Buat template Jinja2 untuk file `/etc/motd` (Message of the Day) yang menyertakan hostname dan tanggal rilis sistem.
2. Buat file variabel rahasia `secret.yml` menggunakan perintah `ansible-vault create` dan uji coba membacanya dengan flag `--ask-vault-pass`.

---

## 19. Challenge
Rancang arsitektur simulasi **Ansible Role & Jinja2 Template Renderer Engine**:
- Simulasikan engine yang memuat struktur folder Role (`defaults/`, `vars/`, `templates/`).
- Render file template Jinja2 dinamis dengan loop iterasi host upstream.
- Implementasikan simulasi enkripsi & dekripsi file secret ala Ansible Vault menggunakan cipher AES-256.

---

## 20. Summary
- Ansible Roles menghadirkan modularitas, keterbacaan, dan standarisasi konfigurasi skala enterprise.
- Jinja2 mengotomatiskan pembentukan file konfigurasi dinamis berdasarkan fakta sistem nyata dan variabel inventory.
- Ansible Vault memungkinkan penyimpanan kredensial rahasia secara aman di version control Git melalui enkripsi simetris yang kuat.
- Modul praktikum lab dapat dijalankan langsung di [hands-on/m02/ansible_roles_vault_sim.js](file:///d:/explore/roadmap.sh%20materi/DevOps/BAB-06-Configuration-Management-Ansible/hands-on/m02/ansible_roles_vault_sim.js).
