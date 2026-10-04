/**
 * LAB TOOL: OpenClaw Self-Healing Diagnostic Engine (openclaw doctor --deep)
 * 
 * Mensimulasikan perkakas diagnostik internal OpenClaw:
 * 1. Pengecekan Environment & Runtime (Node.js version).
 * 2. Audit Keamanan Berkas Konfigurasi & Secret Keys.
 * 3. Verifikasi Penyimpanan State Lokal (SQLite Database).
 * 4. Pengujian Handshake Jaringan ke Provider AI & Telegram Gateway.
 * 5. Pelaporan Status: PASS / WARN / FAIL beserta Rekomendasi Solusi.
 */

const fs = require("fs");
const path = require("path");

class OpenClawDoctor {
  constructor(options = {}) {
    this.isDeepCheck = options.deep || false;
    this.results = [];
  }

  recordCheck(category, name, status, detail, recommendation = null) {
    this.results.push({ category, name, status, detail, recommendation });
  }

  async runDiagnostics() {
    console.log("===================================================================");
    console.log(`🩺 OPENCLAW DIAGNOSTIC SUITE ${this.isDeepCheck ? "(--deep mode aktif)" : ""}`);
    console.log("===================================================================\n");

    // 1. RUNTIME & SYSTEM CHECKS
    const nodeVer = process.version;
    const majorVer = parseInt(nodeVer.replace("v", "").split(".")[0], 10);
    if (majorVer >= 18) {
      this.recordCheck("System", "Node.js Runtime", "PASS", `Versi ${nodeVer} (Memenuhi syarat >= v18.0)`);
    } else {
      this.recordCheck("System", "Node.js Runtime", "FAIL", `Versi ${nodeVer} usang!`, "Upgrade Node.js ke versi 18 atau 20 LTS.");
    }

    const memoryUsageMB = Math.round(process.memoryUsage().heapUsed / 1024 / 1024);
    this.recordCheck("System", "Memory Footprint", "PASS", `${memoryUsageMB} MB heap teralokasi`);

    // 2. CONFIGURATION & PERMISSION CHECKS (Simulasi pembacaan file)
    const mockConfig = {
      ownerChatId: "99881122",
      provider: "google-gemini",
      apiKeySet: true,
      filePermission: "0600"
    };

    if (mockConfig.ownerChatId && mockConfig.ownerChatId.length > 5) {
      this.recordCheck("Security", "Owner Whitelist", "PASS", `Owner ID: ${mockConfig.ownerChatId} (Akses privat terproteksi)`);
    } else {
      this.recordCheck("Security", "Owner Whitelist", "WARN", "Owner ID kosong / publik!", "Atur 'ownerChatId' di config.json agar bot tidak disalahgunakan orang asing.");
    }

    if (mockConfig.filePermission === "0600") {
      this.recordCheck("Security", "Config Permissions", "PASS", "Izin berkas 0600 (Hanya pemilik yang dapat membaca token)");
    } else {
      this.recordCheck("Security", "Config Permissions", "WARN", "Izin berkas terlalu longgar (0644)", "Jalankan: chmod 600 ~/.openclaw/config.json");
    }

    // 3. STORAGE & STATE DATABASE
    this.recordCheck("Storage", "SQLite Sessions DB", "PASS", "state/sessions.db dapat ditulis (Read/Write OK)");

    // 4. DEEP NETWORK HANDSHAKES (Jika mode --deep aktif)
    if (this.isDeepCheck) {
      console.log("🌐 Menguji konektivitas endpoint eksternal...");
      
      // Simulasi Test Ping Provider AI
      await new Promise(r => setTimeout(r, 200));
      this.recordCheck("Network", "Gemini 2.0 API Handshake", "PASS", "Latensi 180ms - Status HTTP 200 OK");

      // Simulasi Test Ping Telegram Bot API
      await new Promise(r => setTimeout(r, 150));
      this.recordCheck("Network", "Telegram Bot Gateway", "PASS", "Token valid - Terhubung ke @MyPersonalButlerBot (ID: 7788)");

      // Simulasi Pengecekan Model Lokal Ollama
      await new Promise(r => setTimeout(r, 100));
      this.recordCheck("Network", "Ollama Local Daemon", "WARN", "Port 11434 tidak merespons (Ollama offline)", "Abaikan jika Anda tidak menggunakan model offline lokal.");
    }

    this.renderReport();
  }

  renderReport() {
    console.log("\n-------------------------------------------------------------------");
    console.log("📋 LAPORAN HASIL PEMERIKSAAN KESEHATAN SISTEM");
    console.log("-------------------------------------------------------------------");

    let totalPass = 0;
    let totalWarn = 0;
    let totalFail = 0;

    for (const item of this.results) {
      let icon = "✅";
      if (item.status === "WARN") { icon = "⚠️ "; totalWarn++; }
      else if (item.status === "FAIL") { icon = "❌"; totalFail++; }
      else { totalPass++; }

      console.log(`${icon} [${item.category.padEnd(8)}] ${item.name.padEnd(25)} : ${item.detail}`);
      if (item.recommendation) {
        console.log(`   💡 Saran: ${item.recommendation}`);
      }
    }

    console.log("===================================================================");
    console.log(`📊 Ringkasan: ${totalPass} PASS | ${totalWarn} WARN | ${totalFail} FAIL`);
    
    if (totalFail === 0) {
      console.log("🎉 SISTEM LAYAK JALAN! Gateway Daemon siap diaktifkan 24/7.");
    } else {
      console.log("🚨 PERBAIKAN DIBUTUHKAN sebelum menjalankan daemon.");
    }
    console.log("===================================================================\n");
  }
}

// Jalankan simulasi pemeriksaan deep doctor
const doctor = new OpenClawDoctor({ deep: true });
doctor.runDiagnostics();
