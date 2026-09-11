/**
 * LAB SIMULATION: WhatsApp Session Pairing & Cross-Channel Identity Sync
 * 
 * Mensimulasikan:
 * 1. WhatsApp Multi-Device Auth Lifecycle (QR Code pairing & session restore).
 * 2. Unified Identity Registry (Telegram + WhatsApp + Slack -> Single User).
 * 3. Cross-Channel Memory Continuity (Konteks WhatsApp dilanjutkan di Slack).
 */

class UnifiedIdentityManager {
  constructor() {
    this.userMap = new Map(); // unifiedId -> UserProfile
    this.channelIndex = new Map(); // "channel:senderId" -> unifiedId
    this.unifiedMemory = new Map(); // unifiedId -> Array of conversation messages
  }

  registerUser(unifiedId, name, accounts = {}) {
    const profile = { unifiedId, name, accounts };
    this.userMap.set(unifiedId, profile);

    if (accounts.telegram) this.channelIndex.set(`telegram:${accounts.telegram}`, unifiedId);
    if (accounts.whatsapp) this.channelIndex.set(`whatsapp:${accounts.whatsapp}`, unifiedId);
    if (accounts.slack) this.channelIndex.set(`slack:${accounts.slack}`, unifiedId);
  }

  resolveUser(channel, senderId) {
    const key = `${channel}:${senderId}`;
    const unifiedId = this.channelIndex.get(key);
    if (!unifiedId) return null;
    return this.userMap.get(unifiedId);
  }

  appendMemory(unifiedId, message) {
    if (!this.unifiedMemory.has(unifiedId)) {
      this.unifiedMemory.set(unifiedId, []);
    }
    this.unifiedMemory.get(unifiedId).push(message);
  }

  getRecentContext(unifiedId, limit = 5) {
    const history = this.unifiedMemory.get(unifiedId) || [];
    return history.slice(-limit);
  }
}

// SIMULASI WHATSAPP MULTI-DEVICE SESSION (BAILEYS)
class WhatsAppSessionSimulator {
  constructor() {
    this.hasCredentials = false;
  }

  login() {
    console.log("\n===================================================================");
    console.log("📱 INISIALISASI KONEKSI WHATSAPP MULTI-DEVICE (BAILEYS SIMULASI)");
    console.log("===================================================================");

    if (this.hasCredentials) {
      console.log("🔑 Kredensial sesi ditemukan di state/wa_auth/creds.json!");
      console.log("⚡ Auto-reconnect berhasil tanpa perlu scan barcode ulang.");
      return { status: "CONNECTED", qrRequired: false };
    } else {
      console.log("⚠️  Tidak ada sesi tersimpan. Menghasilkan QR Code untuk pairing...");
      console.log("┌──────────────────────────┐");
      console.log("│  ██████  ██  ██  ██████  │  <-- [SCAN QR DENGAN APLIKASI WHATSAPP]");
      console.log("│  ██  ██  ██████  ██  ██  │  Buka WhatsApp -> Linked Devices -> Scan");
      console.log("│  ██████  ██  ██  ██████  │");
      console.log("└──────────────────────────┘");
      console.log("📲 Smartphone mendeteksi QR code... Melakukan handshaking kriptografis.");
      this.hasCredentials = true;
      console.log("✅ Device Paired! Sesi tersimpan permanen di state/wa_auth/creds.json.\n");
      return { status: "CONNECTED", qrRequired: true };
    }
  }
}

// ======================= PENGUJIAN SKENARIO =======================
const identityManager = new UnifiedIdentityManager();
const waSimulator = new WhatsAppSessionSimulator();

// 1. Daftarkan Identitas Pengguna Terpadu
identityManager.registerUser("usr_budi", "Budi Santoso", {
  telegram: "99881122",
  whatsapp: "6281299887766",
  slack: "U04_BUDI_DEV"
});

// 2. Jalankan Login WhatsApp Pertama Kali (Butuh QR)
waSimulator.login();

// 3. Uji Simulasi Restart Daemon (Auto-Reconnect tanpa QR)
console.log("🔄 Mensimulasikan server restart...");
waSimulator.login();

console.log("===================================================================");
console.log("🛠️  PENGUJIAN KESINAMBUNGAN MEMORI LINTAS KANAL (WHATSAPP -> SLACK)");
console.log("===================================================================\n");

// Skenario A: Budi mengirim chat di WhatsApp jam 14:00
const waSender = "6281299887766";
const userFromWA = identityManager.resolveUser("whatsapp", waSender);

console.log(`1. [WhatsApp] Pesan masuk dari ${waSender}:`);
const msg1 = "Bro, saya lagi persiapan peluncuran fitur OpenClaw versi 2.0 nih.";
console.log(`   "${msg1}"`);
console.log(`   -> Resolusi Identitas: Dikenali sebagai "${userFromWA.name}" (${userFromWA.unifiedId})`);
identityManager.appendMemory(userFromWA.unifiedId, { channel: "whatsapp", text: msg1, time: "14:00" });

console.log("\n-------------------------------------------------------------------");

// Skenario B: Budi berpindah ke Slack kantor jam 16:00
const slackSender = "U04_BUDI_DEV";
const userFromSlack = identityManager.resolveUser("slack", slackSender);

console.log(`2. [Slack] Pesan masuk dari ${slackSender}:`);
const msg2 = "Bisa bantu buatkan 3 poin pengumuman rilis dari topik yang saya bicarakan tadi?";
console.log(`   "${msg2}"`);
console.log(`   -> Resolusi Identitas: Dikenali sebagai "${userFromSlack.name}" (${userFromSlack.unifiedId})`);

// Ambil Konteks Memori Lintas Kanal
const context = identityManager.getRecentContext(userFromSlack.unifiedId);
console.log(`\n🧠 [Memori Agen] Mengambil konteks obrolan sebelumnya:`);
context.forEach(c => console.log(`   - [${c.channel.toUpperCase()} @ ${c.time}]: "${c.text}"`));

console.log(`\n💬 [Jawaban Agen di Slack]:`);
console.log(`"Halo ${userFromSlack.name}! Berdasarkan obrolan kita via WhatsApp jam 14:00 tadi mengenai 'Fitur OpenClaw v2.0', berikut 3 poin pengumuman rilis untuk tim:\n` +
  ` 1. Dukungan multi-channel terpadu (Telegram, Discord, WhatsApp, Slack).\n` +
  ` 2. Otomasi proaktif dengan heartbeat dan cron.\n` +
  ` 3. Arsitektur zero-trust sandboxing yang lebih aman."`);

console.log("\n===================================================================");
console.log(" Kesimpulan:");
console.log("1. Baileys multi-device menyimpan kunci sesi sehingga tidak perlu scan QR berulang kali.");
console.log("2. Unified Identity Registry berhasil menyatukan ID WhatsApp dan Slack ke satu profil pengguna.");
console.log("3. Agen mempertahankan kesinambungan memori konteks meskipun pengguna berpindah-pindah aplikasi obrolan!");
