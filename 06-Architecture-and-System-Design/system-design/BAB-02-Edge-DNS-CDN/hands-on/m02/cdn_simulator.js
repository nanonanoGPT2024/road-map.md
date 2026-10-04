// cdn_simulator.js
// Simulator Arsitektur CDN: Cache Hit, Cache Miss, Origin Fetch, dan Surrogate-Key Invalidation

class OriginServer {
  constructor() {
    this.database = {
      "/products/laptop-pro.jpg": {
        data: "<Binary Image Data: Laptop Pro 2026>",
        version: "v1",
        cacheTag: "product-laptop"
      },
      "/api/pricing/laptop": {
        data: JSON.stringify({ price: 1500, currency: "USD" }),
        version: "v1",
        cacheTag: "pricing-laptop"
      }
    };
    this.originRequestCount = 0;
  }

  fetch(path) {
    this.originRequestCount++;
    const asset = this.database[path];
    if (!asset) return { status: 404, body: "Not Found" };

    // Simulasi latensi jaringan jauh ke Origin Data Center (~120ms)
    return new Promise((resolve) => {
      setTimeout(() => {
        resolve({
          status: 200,
          headers: {
            "Content-Type": path.endsWith(".jpg") ? "image/jpeg" : "application/json",
            "Cache-Control": "public, max-age=3600, s-maxage=86400",
            "ETag": `"${asset.version}"`,
            "Surrogate-Key": asset.cacheTag
          },
          body: asset.data,
          version: asset.version
        });
      }, 120);
    });
  }

  updateAsset(path, newData, newVersion) {
    if (this.database[path]) {
      this.database[path].data = newData;
      this.database[path].version = newVersion;
      console.log(`\n📦 [ORIGIN UPDATE]: Konten di origin diperbarui ke versi ${newVersion}.`);
    }
  }
}

class EdgeCDNPouPoint {
  constructor(locationName, originServer) {
    this.location = locationName;
    this.origin = originServer;
    this.cacheStore = new Map(); // path -> cache object
  }

  async handleRequest(path, clientLocation) {
    const startTime = Date.now();

    // 1. Periksa apakah aset ada di cache Edge Server
    if (this.cacheStore.has(path)) {
      const cached = this.cacheStore.get(path);
      const latency = Date.now() - startTime + 4; // ~4ms latensi Edge lokal

      return {
        source: `CDN Edge PoP (${this.location})`,
        status: 200,
        cacheStatus: "HIT",
        latencyMs: latency,
        version: cached.version,
        data: cached.body
      };
    }

    // 2. Jika Cache MISS: Tarik dari Origin Server
    console.log(`   [Edge ${this.location}] Cache MISS untuk "${path}". Mengambil dari Origin Server...`);
    const originResponse = await this.origin.fetch(path);
    const latency = Date.now() - startTime;

    if (originResponse.status === 200) {
      // Simpan di Edge Cache
      this.cacheStore.set(path, {
        body: originResponse.body,
        version: originResponse.version,
        tag: originResponse.headers["Surrogate-Key"]
      });
    }

    return {
      source: `Origin Server via Edge (${this.location})`,
      status: originResponse.status,
      cacheStatus: "MISS",
      latencyMs: latency,
      version: originResponse.version,
      data: originResponse.body
    };
  }

  // Invalidate Cache berbasis Surrogate-Key (Tag)
  purgeByTag(tag) {
    console.log(`\n🧹 [CDN PURGE]: Membersihkan seluruh cache dengan Tag "${tag}" di Edge ${this.location}...`);
    let purgedCount = 0;
    for (const [path, cached] of this.cacheStore.entries()) {
      if (cached.tag === tag) {
        this.cacheStore.delete(path);
        purgedCount++;
        console.log(`   -> Cache untuk "${path}" berhasil dibersihkan.`);
      }
    }
    return purgedCount;
  }
}

async function runCDNDemo() {
  console.log("===================================================================");
  console.log("     SIMULATOR CDN: CACHE HIT/MISS & SURROGATE-KEY INVALIDATION    ");
  console.log("===================================================================");

  const origin = new OriginServer();
  const cdnJakarta = new EdgeCDNPouPoint("Jakarta PoP", origin);

  const targetAsset = "/products/laptop-pro.jpg";

  // Skenario 1: User Pertama di Jakarta meminta gambar (Cold Cache Miss)
  console.log("\n>>> [REQUEST 1]: User Jakarta pertama kali membuka halaman produk:");
  const res1 = await cdnJakarta.handleRequest(targetAsset, "Jakarta");
  console.log(` - Hasil: Status=${res1.status} | Cache=${res1.cacheStatus} | Latensi=${res1.latencyMs}ms | Versi=${res1.version}`);

  // Skenario 2: 3 User berikutnya di Jakarta meminta gambar yang sama (Hot Cache Hit)
  console.log("\n>>> [REQUEST 2, 3, 4]: 3 User lain di Jakarta mengakses gambar yang sama:");
  for (let i = 2; i <= 4; i++) {
    const res = await cdnJakarta.handleRequest(targetAsset, "Jakarta");
    console.log(` - Request #${i}: Status=${res.status} | Cache=${res.cacheStatus} | Latensi=${res.latencyMs}ms | Sumber=${res.source}`);
  }

  // Skenario 3: Admin mengganti gambar produk di Origin Server
  origin.updateAsset(targetAsset, "<Binary Image Data: Laptop Pro 2026 Refresh>", "v2");

  // User mengakses sebelum CDN di-purge (Masih melihat cache v1)
  console.log("\n>>> [REQUEST 5]: User mengakses sebelum dilakukan Purge:");
  const resBeforePurge = await cdnJakarta.handleRequest(targetAsset, "Jakarta");
  console.log(` - Hasil: Cache=${resBeforePurge.cacheStatus} | Versi=${resBeforePurge.version} (Data lama masih tersaji)`);

  // Skenario 4: Pipeline CI/CD / Admin memicu Purge by Tag
  cdnJakarta.purgeByTag("product-laptop");

  // Skenario 5: User mengakses setelah Purge (Otomatis mengambil v2 terbaru dari origin)
  console.log("\n>>> [REQUEST 6]: User mengakses setelah dilakukan Purge:");
  const resAfterPurge = await cdnJakarta.handleRequest(targetAsset, "Jakarta");
  console.log(` - Hasil: Cache=${resAfterPurge.cacheStatus} | Latensi=${resAfterPurge.latencyMs}ms | Versi=${resAfterPurge.version} (Data baru!)`);

  console.log("\n===================================================================");
  console.log("                     STATISTIK PERFORMA AKHIR                      ");
  console.log("===================================================================");
  console.log(` - Total Request Pengguna : 6`);
  console.log(` - Beban ke Origin Server : Hanya ${origin.originRequestCount} request (66.7% offloaded oleh CDN Edge!)`);
  console.log(` - Latensi Rata-rata Hit  : ~4 ms (Bandingkan dengan Origin ~120 ms)`);
  console.log("===================================================================\n");
}

runCDNDemo();
