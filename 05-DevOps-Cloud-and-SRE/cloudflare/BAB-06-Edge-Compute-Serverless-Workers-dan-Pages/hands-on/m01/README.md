# Panduan Hands-on Lab: Enterprise Edge Reverse Proxy & Streaming Transformer

## 1. Ringkasan Laboratorium
Dalam lab praktis ini, Anda akan menjalankan dan menguji secara lokal sebuah **Cloudflare Worker** tingkat enterprise yang bertindak sebagai Edge Reverse Proxy, Security Middleware, dan Streaming DOM Manipulator menggunakan Wrangler CLI.

---

## 2. Prasyarat Sistem
Pastikan lingkungan lokal Anda telah terinstal:
- **Node.js**: v18.18.0 atau LTS terbaru (`node -v`)
- **npm** atau **pnpm** (`npm -v`)
- **curl** (untuk pengujian HTTP via CLI)
- Web Browser (Chrome/Firefox/Brave)

---

## 3. Langkah Demi Langkah Setup & Eksekusi

### Langkah 1: Siapkan Struktur Direktori Lab
Buka terminal dan buat direktori kerja baru:
```bash
mkdir -p cloudflare-edge-lab/src
cd cloudflare-edge-lab
```

### Langkah 2: Inisialisasi Project Node.js & Instal Wrangler
Inisialisasi `package.json` dan instalasi runtime Wrangler CLI:
```bash
npm init -y
npm install -D wrangler@latest
```

### Langkah 3: Tempatkan Kode Worker
Salin kode dari file `edge_worker_reverse_proxy.js` ke dalam file `src/index.js`:
```bash
cp /path/to/edge_worker_reverse_proxy.js ./src/index.js
```

### Langkah 4: Buat File Konfigurasi `wrangler.toml`
Buat file `wrangler.toml` pada root direktori:
```toml
name = "enterprise-edge-proxy"
main = "src/index.js"
compatibility_date = "2024-04-01"

[vars]
API_ORIGIN = "https://dummyjson.com"
DOCS_ORIGIN = "https://httpbin.org"
DEBUG_TOKEN = "super-secure-devops-token"
```

### Langkah 5: Jalankan Lingkungan Pengembangan Lokal
Jalankan simulator runtime open-source Cloudflare (`workerd`):
```bash
npx wrangler dev --port 8787
```
Output terminal akan menampilkan:
```text
⎔ Starting local server...
[ready] Ready on http://localhost:8787
```

---

## 4. Pengujian & Verifikasi Kasus Uji

Buka tab terminal baru untuk mengeksekusi skenario uji berikut:

### Uji Skenario 1: Verifikasi HTML Rewriter & Injeksi Header
Akses root path `/` yang me-route ke `https://httpbin.org/html`:
```bash
curl -i http://localhost:8787/
```
**Ekspektasi Verifikasi**:
1. Header response mengandung:
   - `X-Edge-Security: PASSED`
   - `X-Edge-Transform: HTMLRewriter-Stream`
   - `X-Edge-Origin-Time: <angka>ms`
2. Body HTML mengandung:
   - Tag `<title>` bernilai `Enterprise Edge Portal - Managed by Cloudflare Workers