---
[⬅️ Module 01: Frontend Security & CSP](./Module-01-XSS-CSP-Nonces-CSRF-dan-Clickjacking-Defense.md) | [📋 Silabus Induk](../README.md) | [BAB 08 Quiz & Challenge ➡️](./BAB-08-Quiz-dan-Challenge.md)
---

# Module 02: Backend & Supply Chain Defense: SSRF, Server Actions Parameter Tampering, & CORS Isolation

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta didik diharapkan mampu:
- Mengidentifikasi dan memitigasi kerentanan **Server-Side Request Forgery (SSRF)** saat backend melakukan fetch URL eksternal (fitur Webhook, konverter PDF, scraping thumbnail link, atau avatar downloader).
- Mengamankan infrastruktur cloud dari pencurian kredensial instans (AWS IAM Instance Metadata Service `http://169.254.169.254`) dan pemindaian jaringan intranet privat (RFC 1918 IP Ranges & DNS Rebinding Attacks).
- Memahami ancaman **Server Action Parameter Tampering & Mass Assignment**: memperlakukan React Server Actions sebagai endpoint publik yang tidak boleh mempercayai input client secara buta.
- Mengonfigurasi **CORS (Cross-Origin Resource Sharing)** secara aman: memahami perbedaan antara *preflight requests (OPTIONS)*, kredensial (`Access-Control-Allow-Credentials`), dan bahaya penggunaan wildcard (`*`).
- Mengamankan rantai pasok perangkat lunak (*Software Supply Chain Security*): mendeteksi dependensi rentan melalui audit otomatis (npm audit, Snyk, Dependabot) dan mitigasi *Prototype Pollution*.

---

## 2. Prerequisite
- Memahami arsitektur jaringan TCP/IP (IP Public vs Private IP RFC 1918, DNS resolution).
- Memahami konsep React Server Actions dari Bab 03.
- Memahami protokol HTTP dan header CORS.

---

## 3. Concept
Banyak pengembang full-stack pemula menganggap bahwa keamanan hanya tentang "mengunci frontend". Namun bahaya paling mematikan sering kali berakar di sisi **Backend**:

```
[ Pengguna Memasukkan URL Avatar ] ---> "http://169.254.169.254/latest/meta-data/iam/security-credentials/"
                   |
                   v
+--------------------------------------------------------+
| SERVER BACKEND (Node.js / Next.js)                     |
|                                                        |
|  // Kode Ceroboh:                                      |
|  const res = await fetch(userInputUrl);                |
|                                                        |
|  💥 Server melakukan panggilan HTTP ke internal AWS!  |
|  💥 Secret AWS Access Key terbaca & dikirim ke hacker!|
+--------------------------------------------------------+
```

Ketika backend menerima URL dari pengguna dan mengeksekusi `fetch(url)` tanpa validasi alamat IP, server Anda dapat diperdaya untuk menjadi **proksi penyerang (*Server-Side Request Forgery / SSRF*)**. Penyerang dapat membaca database internal perusahaan, memindai port intranet, atau mencuri kunci rahasia cloud serverless tanpa terhalang firewall luar!

---

## 4. Why? (Mengapa Server Actions Perlu Diproteksi seperti REST API?)
Ada kesalahpahaman umum bahwa karena React Server Actions ditulis di file yang sama atau dipanggil seperti fungsi JavaScript biasa (`await updateProfile(data)`), fungsinya dianggap "privat" dan tidak bisa ditembus.

**Kenyataannya**:
- Setiap Server Action yang dideklarasikan dengan `"use server"` dikompilasi oleh Next.js menjadi **endpoint publik HTTP POST** yang memiliki ID unik (hash).
- Penyerang dapat membuka Postman atau `curl`, lalu menembakkan request POST langsung ke Server Action tersebut dengan menyuntikkan payload manipulasi:
  - Mengubah kolom tersembunyi: `{ role: "ADMIN", discountPercent: 100 }` (*Mass Assignment*).
  - Melewati validasi form client-side.
- Oleh karena itu, **setiap Server Action wajib mengulang seluruh otentikasi, otorisasi hak akses, dan validasi Zod** seolah-olah ia adalah REST API publik biasa!

---

## 5. What? (Vektor Serangan & Mekanisme Pertahanan)

### A. SSRF & DNS Rebinding Attacks
- **Rentang IP Terlarang (Private & Loopback)**:
  - `127.0.0.0/8` (Localhost)
  - `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16` (Private Network RFC 1918)
  - `169.254.169.254` (Link-Local Cloud Metadata AWS/GCP/Azure)
  - `::1`, `fc00::/7` (IPv6 Loopback & Local)
- **DNS Rebinding**: Penyerang membuat domain `evil.com`. Saat divalidasi oleh fungsi sanitasi Anda, domain tersebut mengembalikan IP publik `1.2.3.4`. Namun 1 milidetik kemudian saat `fetch()` dijalankan, DNS server penyerang mengubah respon menjadi `127.0.0.1`!
- **Solusi**: Lakukan DNS resolution terlebih dahulu, verifikasi IP hasil resolve, lalu lakukan koneksi langsung ke IP tersebut menggunakan custom HTTP Agent dengan pinning IP.

### B. CORS (Cross-Origin Resource Sharing) Isolation
CORS **bukanlah firewall untuk melindungi server dari hacker** (hacker tidak menggunakan browser). CORS adalah mekanisme browser untuk **melindungi pengguna dari situs jahat**.
- Jika API Anda menerima kredensial cookie (`credentials: 'include'`), header `Access-Control-Allow-Origin: *` **secara tegas dilarang oleh standar web**. Anda wajib menentukan origin yang diizinkan secara eksplisit (whitelist).

---

## 6. How? (Implementasi SSRF Validator & Secure Server Action)

### 1. SSRF Safe Fetcher dengan IP Verification (utils/safeFetch.ts)
```typescript
import dns from "dns/promises";
import ipaddr from "ipaddr.js";

// Daftar CIDR IP yang dilarang keras untuk diakses oleh backend
const BLOCKED_RANGES = [
  "unspecified",
  "broadcast",
  "linkLocal",
  "loopback",
  "private",
  "reserved",
];

export async function validateUrlForSSRF(inputUrl: string): Promise<string> {
  const parsed = new URL(inputUrl);

  // 1. Hanya izinkan protokol HTTP dan HTTPS
  if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
    throw new Error(`Protokol '${parsed.protocol}' ditolak. Hanya HTTP/HTTPS yang diizinkan.`);
  }

  // 2. Resolve DNS hostname menjadi alamat IP fisik
  const addresses = await dns.lookup(parsed.hostname, { all: true });
  if (addresses.length === 0) {
    throw new Error("Hostname tidak dapat diselesaikan via DNS.");
  }

  // 3. Periksa setiap alamat IP hasil resolusi terhadap Blocklist
  for (const addr of addresses) {
    const parsedIp = ipaddr.parse(addr.address);
    const range = parsedIp.range();

    if (BLOCKED_RANGES.includes(range)) {
      throw new Error(`[SSRF DITANGKAL] Alamat IP tujuan '${addr.address}' berada di zona terlarang (${range})!`);
    }

    // Blokir khusus metadata service cloud (169.254.169.254)
    if (addr.address === "169.254.169.254") {
      throw new Error("[SSRF DITANGKAL] Akses ke Cloud Instance Metadata Service dilarang keras!");
    }
  }

  return inputUrl;
}
```

### 2. Secure React Server Action dengan Sanitasi & Autentikasi Penuh
```typescript
// app/actions/update-user.ts
"use server";
import { auth } from "@/auth";
import { db } from "@/db";
import { users } from "@/db/schema";
import { eq } from "drizzle-orm";
import { z } from "zod";

// Skema Zod Ketat: Hanya kolom yang diizinkan yang boleh diubah!
const UpdateProfileSchema = z.object({
  displayName: z.string().min(2).max(50).trim(),
  bio: z.string().max(250).trim().optional(),
  // Kolom sensitif seperti 'role', 'isVerified', 'balance' SENGAJA DITIADAKAN!
});

export async function updateUserProfileAction(rawData: unknown) {
  // 1. Verifikasi Autentikasi Pengguna
  const session = await auth();
  if (!session?.user?.id) {
    throw new Error("Akses ditolak: Anda harus login untuk melakukan aksi ini.");
  }

  // 2. Validasi & Sanitasi Data Input (Mencegah Mass Assignment)
  const parseResult = UpdateProfileSchema.safeParse(rawData);
  if (!parseResult.success) {
    throw new Error(`Data tidak valid: ${parseResult.error.issues.map((i) => i.message).join(", ")}`);
  }

  const { displayName, bio } = parseResult.data;

  // 3. Tulis ke database HANYA untuk record milik user yang sedang aktif
  await db
    .update(users)
    .set({
      name: displayName,
      bio: bio ?? null,
      updatedAt: new Date(),
    })
    .where(eq(users.id, session.user.id));

  return { success: true, message: "Profil berhasil diperbarui!" };
}
```

---

## 7. Analogy
Bayangkan seorang kurir kantor yang Anda suruh keluar untuk mengambil barang:
- **Rentan SSRF**: Anda menyuruh kurir: *"Ambilkan paket di alamat yang tertulis di kertas ini"*. Penyerang menulis alamat: *"Brankas Direktur di Ruang Bawah Tanah Gedung Ini"*. Kurir yang polos berjalan ke brankas rahasia kantor, mengambil dokumen rahasia, lalu menyerahkannya ke penyerang (*SSRF Internal Breach*).
- **SSRF Defense**: Kantor memiliki SOP ketat di pintu pos satpam. Sebelum kurir melangkah, satpam membaca alamat di kertas: *"Alamat ini berada di dalam gedung kantor sendiri (Private IP/Localhost)! Kurir dilarang mengambil barang dari dalam kantor sendiri; kurir hanya boleh pergi ke alamat publik di luar kota!"*.

---

## 8. Diagram Vektor Serangan SSRF ke Cloud Metadata

```
[ Penyerang ] ---> Request: POST /api/generate-pdf { url: "http://169.254.169.254/..." }
                          |
                          v
+--------------------------------------------------------+
| BACKEND APPLICATION SERVER                             |
|                                                        |
| 1. DNS / IP Filter Evaluator                           |
|    - Cek IP Target: `169.254.169.254`                  |
|    - Evaluasi: LINK-LOCAL IP (AWS METADATA ZONE!)      |
|                                                        |
| 2. Keputusan Filter:                                   |
|    ❌ REJECT IMMEDIATELY (Status 400 Bad Request)      |
+--------------------------------------------------------+
                          |
             (Koneksi Dibatalkan di Sini!)
                          x
                          x
+--------------------------------------------------------+
| AWS EC2 / ECS METADATA SERVICE (Port 80)               |
|                                                        |
| (Kredensial IAM Role Aman Terlindungi! 🛡️)             |
+--------------------------------------------------------+
```

---

## 9. Simple Example: CORS Misconfiguration vs Secure Configuration

```typescript
// ❌ SANGAT BERBAHAYA: Mengizinkan Origin Apapun dengan Kredensial!
// (Banyak developer melakukan ini agar cepat selesai saat error CORS)
app.use((req, res, next) => {
  res.header("Access-Control-Allow-Origin", req.headers.origin); // Memantulkan origin sembarangan!
  res.header("Access-Control-Allow-Credentials", "true"); // Cookie dikirimkan ke situs penyerang!
  next();
});

// ✅ KONFIGURASI AMAN: Whitelist Domain Resmi Eksplisit
const ALLOWED_ORIGINS = [
  "https://perusahaan.com",
  "https://admin.perusahaan.com",
];

app.use((req, res, next) => {
  const origin = req.headers.origin;
  if (origin && ALLOWED_ORIGINS.includes(origin)) {
    res.header("Access-Control-Allow-Origin", origin);
    res.header("Access-Control-Allow-Credentials", "true");
    res.header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS");
    res.header("Access-Control-Allow-Headers", "Content-Type, Authorization");
  }
  if (req.method === "OPTIONS") return res.sendStatus(204); // Preflight OK
  next();
});
```

---

## 10. Practical Example: Prototype Pollution Mitigation
Di JavaScript, memodifikasi objek secara rekursif tanpa memeriksa key `__proto__` atau `constructor` dapat merusak prototipe global `Object.prototype`:

```typescript
// Fungsi Deep Merge Aman dari Prototype Pollution
export function safeDeepMerge(target: any, source: any): any {
  for (const key of Object.keys(source)) {
    // Blokir manipulasi prototype chain!
    if (key === "__proto__" || key === "constructor" || key === "prototype") {
      continue;
    }

    if (source[key] instanceof Object && key in target) {
      Object.assign(source[key], safeDeepMerge(target[key], source[key]));
    }
  }
  Object.assign(target || {}, source);
  return target;
}
```

---

## 11. Real-World Example: Webhook Dispatcher E-Commerce
Platform toko online mengizinkan merchant memasukkan URL Webhook untuk menerima event notifikasi pesanan:

1. Merchant mendaftarkan URL: `https://toko-merchant.com/webhook-listener`.
2. Sebelum menyimpan ke database, backend memanggil `validateUrlForSSRF(url)`.
3. Merchant jahat mencoba memasukkan `http://localhost:6379` (Redis server internal backend).
4. Validator melempar error: *"Alamat IP tujuan '127.0.0.1' berada di zona terlarang (loopback)"*.
5. Pendaftaran webhook gagal total dan upaya peretasan dicatat ke audit log keamanan!

---

## 12. Trade-offs: Strict SSRF Filtering vs Fitur Fleksibel

| Pendekatan | Tingkat Keamanan | Dampak terhadap Fitur | Kompleksitas Kode |
| :--- | :--- | :--- | :--- |
| **Strict IP Blocklist + Pinning** | **Tertinggi (Aman dari SSRF & Rebinding)**| Sedikit membatasi URL intranet yang sah | Menengah |
| **Dedicated Isolated Fetcher Proxy** | **Tertinggi (Zero Trust)** | Sangat fleksibel (dijalankan di DMZ sandbox) | Tinggi (Butuh server proxy terpisah) |
| **Bebas Tanpa Validasi** | Nol (Sangat Rentan) | Bebas | Sangat Rendah |

---

## 13. When To Use SSRF Validation
- Setiap kali aplikasi Anda mengunduh konten dari URL yang disediakan pengguna (Avatar downloader, Rich preview scraper, Webhook consumer, PDF generator dari URL).
- Backend Anda berjalan di lingkungan cloud publik (AWS EC2, Google Cloud Compute, Azure VM) yang memiliki layanan *Metadata Service (169.254.169.254)*.

---

## 14. When NOT To Use
- Permintaan HTTP yang tujuannya telah di-hardcode ke domain terpercaya milik perusahaan sendiri (misal: memanggil API Stripe resmi `https://api.stripe.com/v1`).

---

## 15. Common Mistakes
1. **Hanya Menggunakan Regex String untuk Memeriksa URL SSRF**:
   - Mengecek apakah string mengandung `localhost`. Penyerang dapat mengakalinya dengan varian desimal `http://2130706433`, hex `http://0x7f000001`, atau domain kustom seperti `localtest.me` yang mengarah ke `127.0.0.1`. **Wajib gunakan DNS IP resolution!**
2. **Mempercayai `userId` atau `tenantId` dari Parameter Form**:
   - Di Server Action, menerima `userId` dari hidden input form alih-alih membacanya dari `session.user.id`. Penyerang cukup mengubah nilai input tersebut untuk mengedit profil orang lain (*IDOR / Insecure Direct Object Reference*).
3. **Mengabaikan Peringatan `npm audit` di CI/CD**:
   - Membiarkan dependensi pihak ketiga yang sudah usang dan memiliki CVE kritis dieksekusi di lingkungan produksi.

---

## 16. Best Practices

### Must Have
- Selalu ambil identitas pengguna (`userId`, `role`, `orgId`) dari sesi server terverifikasi (`await auth()`), jangan pernah dari input client.
- Gunakan Zod untuk validasi seluruh payload Server Actions guna mencegah Mass Assignment.
- Terapkan validasi rentang IP (RFC 1918 + Cloud Metadata) pada semua fitur pengunduh URL eksternal.

### Recommended
- Jalankan dependabot atau Snyk di repositori GitHub untuk memindai kerentanan rantai pasok secara otomatis pada setiap pull request.
- Gunakan AWS IMDSv2 (yang mewajibkan token header `X-aws-ec2-metadata-token`) untuk memitigasi pencurian metadata via SSRF sederhana.

### Advanced
- Letakkan layanan pengunduh URL pihak ketiga di dalam container terisolasi (*Sandbox Worker*) di Virtual Private Cloud (VPC) terpisah yang sama sekali tidak memiliki akses ke jaringan intranet internal.

### Avoid
- Jangan pernah mengembalikan respon error stack trace mentah (seperti pesan database Postgres atau direktori internal server) ke client browser saat terjadi kegagalan sistem.

---

## 17. Troubleshooting Guide

| Gejala Masalah | Kemungkinan Akar Masalah | Solusi |
| :--- | :--- | :--- |
| Error `CORS header 'Access-Control-Allow-Origin' missing` di browser. | Server backend tidak menyertakan origin client pada whitelist atau request `OPTIONS` preflight gagal dijawab. | Pastikan handler CORS membalas status `204 No Content` pada request ber-metode `OPTIONS`. |
| Merchant legal gagal mendaftarkan webhook karena IP diblokir. | Hostname merchant menunjuk ke IP internal kantor mereka sendiri untuk testing. | Sediakan toggle khusus lingkungan *Staging / Development* untuk mengizinkan testing lokal secara terkontrol. |
| Server Action gagal dijalankan dengan error `Action not found`. | Bundle build client dan server tidak sinkron akibat proses rolling deployment tanpa sticky session. | Konfigurasikan versi deployment tetap (*Deployment ID*) atau gunakan platform modern seperti Vercel yang menangani skew protection otomatis. |

---

## 18. Exercise
- **Easy**: Buat skema Zod untuk Server Action pendaftaran event yang menolak properti `isAdmin: true` secara eksplisit.
- **Medium**: Tulis fungsi validator IP yang memeriksa apakah string IP masuk ke dalam rentang privat `192.168.0.0/16`.
- **Hard**: Rancang custom HTTP Agent di Node.js yang melakukan resolusi DNS sebelum koneksi TCP dibuat, memvalidasi IP terhadap blokir SSRF, dan mengunci koneksi hanya ke IP tersebut untuk mencegah *DNS Rebinding Attack*.

---

## 19. Challenge
Rancang arsitektur microservice *Link Preview & Thumbnail Generator* yang aman: Pengguna dapat menempelkan URL apapun. Service harus memvalidasi URL dari ancaman SSRF (termasuk DNS Rebinding dan HTTP 302 Redirect loop), mengunduh halaman dalam batas waktu 3 detik (*Timeout Guard*), membatasi ukuran unduhan maksimal 2MB (*Payload Bomb Defense*), dan menghasilkan gambar pratinjau aman tanpa mengeksekusi JavaScript berbahaya di server.

---

## 20. Summary
- Keamanan backend dan Server Actions menuntut pendekatan **Zero Trust**: perlakukan setiap Server Action sebagai antarmuka publik yang dapat diserang kapan saja.
- **SSRF** adalah ancaman fatal di era komputasi awan yang dapat membocorkan kredensial rahasia infrastruktur jika URL eksternal tidak divalidasi hingga ke level resolusi IP.
- Menggabungkan validasi Zod ketat, otorisasi berbasis sesi server, whitelist CORS presisi, dan pertahanan SSRF menciptakan data layer dan logika bisnis yang kebal terhadap eksploitasi OWASP Top 10.

---

## Hands-on Practice: Simulasi SSRF Validator & Server Action Parameter Sanitizer
Jalankan simulator pendeteksi serangan SSRF, cloud metadata shield, dan pencegah manipulasi parameter Server Action mandiri:

```bash
node Full-Stack/BAB-08-Keamanan-Full-Stack-Defensif-OWASP/hands-on/m02/server_action_ssrf_sanitizer_sim.js
```

---
[⬅️ Module 01: Frontend Security & CSP](./Module-01-XSS-CSP-Nonces-CSRF-dan-Clickjacking-Defense.md) | [📋 Silabus Induk](../README.md) | [BAB 08 Quiz & Challenge ➡️](./BAB-08-Quiz-dan-Challenge.md)
---
