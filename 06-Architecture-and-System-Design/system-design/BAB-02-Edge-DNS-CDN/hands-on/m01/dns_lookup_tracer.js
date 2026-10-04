// dns_lookup_tracer.js
// Simulator Hierarki Resolusi DNS, Latensi Lapis Cache, dan Efek TTL

class DNSResolverSimulator {
  constructor() {
    this.authoritativeZone = {
      "api.tokopedia.com": { ip: "103.24.56.78", ttl: 3 }, // TTL 3 detik untuk simulasi
      "checkout.shopee.co.id": { ip: "143.92.120.45", ttl: 5 }
    };

    this.browserCache = new Map();
    this.osCache = new Map();
    this.resolverCache = new Map();
  }

  // Mengembalikan record jika belum kadaluwarsa (TTL valid)
  checkCache(cacheStore, domain) {
    if (!cacheStore.has(domain)) return null;
    const entry = cacheStore.get(domain);
    const now = Date.now();
    if (now > entry.expiresAt) {
      cacheStore.delete(domain);
      return null; // Expired
    }
    return entry;
  }

  async resolveDomain(domain) {
    console.log(`\n===============================================================`);
    console.log(` 🔍 MEMULAI PENCARIAN DNS: "${domain}"`);
    console.log(`===============================================================`);

    let totalLatencyMs = 0;

    // 1. Cek Browser Cache
    const browserHit = this.checkCache(this.browserCache, domain);
    if (browserHit) {
      console.log(` [1. Browser Cache]      HIT! IP: ${browserHit.ip} (Sisa TTL: ${((browserHit.expiresAt - Date.now())/1000).toFixed(1)}s) [Latensi: +0ms]`);
      return { ip: browserHit.ip, latency: totalLatencyMs, source: 'Browser Cache' };
    }
    console.log(` [1. Browser Cache]      MISS! (Meneruskan ke OS Cache) [Latensi: +0ms]`);

    // 2. Cek OS Cache
    const osHit = this.checkCache(this.osCache, domain);
    if (osHit) {
      totalLatencyMs += 1;
      console.log(` [2. OS Cache]           HIT! IP: ${osHit.ip} (Sisa TTL: ${((osHit.expiresAt - Date.now())/1000).toFixed(1)}s) [Latensi: +1ms]`);
      // Update browser cache
      this.browserCache.set(domain, osHit);
      return { ip: osHit.ip, latency: totalLatencyMs, source: 'OS Cache' };
    }
    console.log(` [2. OS Cache]           MISS! (Meneruskan ke ISP Recursive Resolver) [Latensi: +1ms]`);
    totalLatencyMs += 1;

    // 3. Cek ISP Resolver Cache
    const resolverHit = this.checkCache(this.resolverCache, domain);
    if (resolverHit) {
      totalLatencyMs += 15; // Latensi jaringan ke ISP terdekat
      console.log(` [3. ISP Resolver Cache] HIT! IP: ${resolverHit.ip} [Latensi: +15ms]`);
      this.osCache.set(domain, resolverHit);
      this.browserCache.set(domain, resolverHit);
      return { ip: resolverHit.ip, latency: totalLatencyMs, source: 'ISP Resolver' };
    }
    console.log(` [3. ISP Resolver Cache] MISS! (Memulai Rekursi Global) [Latensi: +15ms]`);
    totalLatencyMs += 15;

    // 4. Kunjungan Rekursif Global (Root Server -> TLD Server -> Authoritative Server)
    console.log(`   -> [Root Nameserver]        Query TLD ".com"               [Latensi: +35ms]`);
    totalLatencyMs += 35;
    console.log(`   -> [TLD Nameserver]         Query Otoritatif "tokopedia"   [Latensi: +40ms]`);
    totalLatencyMs += 40;
    console.log(`   -> [Authoritative Server]   Ditemukan IP Asli & TTL        [Latensi: +45ms]`);
    totalLatencyMs += 45;

    const record = this.authoritativeZone[domain];
    if (!record) {
      throw new Error(`NXDOMAIN: Domain ${domain} tidak terdaftar!`);
    }

    const cacheEntry = {
      ip: record.ip,
      expiresAt: Date.now() + (record.ttl * 1000),
      ttl: record.ttl
    };

    // Simpan ke seluruh layer cache
    this.resolverCache.set(domain, cacheEntry);
    this.osCache.set(domain, cacheEntry);
    this.browserCache.set(domain, cacheEntry);

    console.log(`\n ✅ RESOLUSI SELESAI:`);
    console.log(`    IP Address Target : ${record.ip}`);
    console.log(`    Total Latensi DNS : ${totalLatencyMs} ms`);
    console.log(`    Cache TTL Ditetapkan: ${record.ttl} detik`);

    return { ip: record.ip, latency: totalLatencyMs, source: 'Authoritative Nameserver (Cold Miss)' };
  }
}

async function sleep(ms) {
  return new Promise(r => setTimeout(r, ms));
}

async function runDemo() {
  const sim = new DNSResolverSimulator();

  // Query 1: Cold Cache Miss (Harus mencari dari Root hingga Authoritative)
  await sim.resolveDomain("api.tokopedia.com");

  // Query 2: Immediate Repeated Query (Hit di Browser Cache)
  console.log("\n>>> Mengirim request ulang seketika:");
  await sim.resolveDomain("api.tokopedia.com");

  // Query 3: Menunggu TTL kadaluwarsa (TTL = 3 detik)
  console.log("\n>>> Menunggu 3.5 detik hingga TTL kadaluwarsa...");
  await sleep(3500);

  // Query 4: Query setelah TTL habis (Cache Miss kembali)
  console.log(">>> Mengirim request setelah TTL expired:");
  await sim.resolveDomain("api.tokopedia.com");

  console.log(`\n===============================================================`);
  console.log(` [KESIMPULAN ANALISIS DNS]:`);
  console.log(` 1. Cold Query memakan ~136 ms (Network RTT ke 4 server berbeda).`);
  console.log(` 2. Hot Cache Hit memangkas latensi menjadi 0 ms.`);
  console.log(` 3. Setelah TTL kadaluwarsa, rekursi penuh wajib diulang kembali.`);
  console.log(`===============================================================\n`);
}

runDemo();
