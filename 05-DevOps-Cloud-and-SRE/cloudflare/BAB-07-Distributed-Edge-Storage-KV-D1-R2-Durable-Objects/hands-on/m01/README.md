# Hands-On Lab: Distributed State Management & Durable Objects Coordination

Laboratorium praktis ini memandu Anda dalam melakukan setup, implementasi, deployment, dan stress-testing arsitektur sistem stateful terdistribusi di Cloudflare Edge. Anda akan membuktikan keandalan konsistensi data (*Linearizability*) Durable Objects dalam mencegah race condition di bawah beban penulisan konkuren yang masif.

---

## Prasyarat Lingkungan Kerja
1. **Node.js**: Versi LTS (v18.x atau v20.x ke atas).
2. **NPM / PNPM**: Terinstalasi pada workstation Anda.
3. **Cloudflare Account**: Akun aktif dengan langganan Workers Paid (karena Durable Objects memerlukan paket Workers Paid untuk environment produksi, atau Anda dapat mengujinya secara **100% GRATIS** pada environment lokal via Miniflare/Wrangler local mode).

---

## Langkah 1: Inisialisasi Proyek & Struktur Direktori

Buka terminal workstation Anda dan jalankan perintah berikut:

```bash
mkdir edge-state-lab && cd edge-state-lab
npm init -y
npm install --save-dev wrangler typescript @cloudflare/workers-types
```

Buat struktur folder berikut:
```text
edge-state-lab/
├── src/
│   └── index.js   <-- Salin isi durable_objects_counter_sim.js ke sini
├── wrangler.toml
└── package.json
```

---

## Langkah 2: Konfigurasi `wrangler.toml`

Buat file bernama `wrangler.toml` pada root direktori proyek Anda:

```toml
name = "durable-objects-vote-engine"
main = "src/index.js"
compatibility_date = "2024-04-01"

# Binding KV Namespace untuk Fast-Path Edge Cache
[[kv_namespaces]]
binding = "GLOBAL_CACHE_KV"
id = "mock-kv-id-for-local-dev"

# Binding Durable Objects Coordinator
[[durable_objects.bindings]]
name = "VOTE_COORDINATOR_DO"
class_name = "AtomicVoteCoordinator"

# Deklarasi Migrasi State Durable Object
[[migrations]]
tag = "v1"
new_classes = ["AtomicVoteCoordinator"]
```

Salin file kode `durable_objects_counter_sim.js` dari repositori hands-on ke dalam file `src/index.js`.

---

## Langkah 3: Menjalankan Local Edge Simulator (Miniflare V8 Runtime)

Jalankan server simulator edge lokal Cloudflare menggunakan Wrangler:

```bash
npx wrangler dev --local --port 8787
```

Output terminal akan mengonfirmasi bahwa runtime isolate lokal telah aktif:
```text
[boba] Ready on http://localhost:8787
- Binding VOTE_COORDINATOR_DO (AtomicVoteCoordinator)
- Binding GLOBAL_CACHE_KV
```

---

## Langkah 4: Pengujian Kasus 1 - Pengiriman Suara Normal (Single Vote)

Buka terminal kedua untuk melakukan uji fungsional HTTP API.

Kirim sebuah hak suara untuk kandidat `Alpha` dari pemilih `voter-001`:

```bash
curl -X POST "http://localhost:8787/api/vote/cast?pollId=election-2024" \
  -H "Content-Type: application/json" \
  -d '{"candidate": "Alpha", "voterId": "voter-001"}'
```

**Ekspektasi Respons:**
```json
{
  "status": "SUCCESS",
  "candidate": "Alpha",
  "newVoteCount": 1,
  "totalVotes": 1
}
```

---

## Langkah 5: Pengujian Kasus 2 - Verifikasi Proteksi Idempotency (Anti Double-Vote)

Coba kirimkan kembali vote dengan `voterId` yang sama persis:

```bash
curl -X POST "http://localhost:8787/api/vote/cast?pollId=election-2024" \
  -H "Content-Type: application/json" \
  -d '{"candidate": "Alpha", "voterId": "voter-001"}'
```

**Ekspektasi Respons (HTTP 409 Conflict):**
```json
{
  "error": "Voter has already cast a vote!",
  "voterId": "voter-001"
}
```

Perhatikan bahwa Durable Object menolak request tersebut secara instan tanpa mengorbankan konsistensi counter.

---

## Langkah 6: Pengujian Kasus 3 - Stress Test Konkurensi Tinggi (Zero Discrepancy Verification)

Sekarang kita buktikan keunggulan Actor Model Durable Objects dalam memecahkan race condition jika ratusan vote dikirimkan secara serentak (*concurrent bursts*).

Buat skrip pengujian beban sederhana bernama `load_test.sh`:

```bash
cat << 'EOF' > load_test.sh
#!/bin/bash
echo "Memulai simulasi 100 vote konkuren..."

for i in {1..100}
do
   curl -s -X POST "http://localhost:8787/api/vote/cast?pollId=election-2024" \
     -H "Content-Type: application/json" \
     -d "{\"candidate\": \"Beta\", \"voterId\": \"voter-concurrent-$i\"}" > /dev/null &
done

wait
echo "Seluruh request selesai dieksekusi!"
EOF

chmod +x load_test.sh
./load_test.sh
```

Setelah script selesai dieksekusi, verifikasi metrik agregasi total pada Durable Object:

```bash
curl -s "http://localhost:8787/api/vote/metrics?pollId=election-2024"
```

**Ekspektasi Output Audit:**
```json
{
  "totalVotes": 101,
  "tally": {
    "Alpha": 1,
    "Beta": 100
  },
  "storageEngine": "DurableObjects-Linearizable-SQLite",
  "nodeColo": "LOCAL-DEV"
}
```

**Analisis Hasil Laboratorium:**
Meskipun 100 request HTTP meluncur secara simultan tanpa delay, total vote untuk `Beta` tercatat **tepat 100** dan total akumulasi adalah **101**. 
Tidak ada satupun suara yang hilang (*zero lost updates*). Pada database konvensional tanpa isolasi ketat atau pada Workers KV murni, skenario ini dipastikan akan menghasilkan data korup akibat race condition.

---

## Langkah 7: Pembersihan Lingkungan (*Teardown*)

Hentikan server lokal development dengan menekan kombinasi tombol `Ctrl + C` pada terminal Wrangler Anda. Jika Anda telah melakukan deploy ke Cloudflare live network, hapus deployment menggunakan:

```bash
npx wrangler delete
```