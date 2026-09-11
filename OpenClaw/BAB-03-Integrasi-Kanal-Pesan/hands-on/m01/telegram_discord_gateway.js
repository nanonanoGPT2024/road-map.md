/**
 * LAB SIMULATION: Multi-Channel Messaging Gateway (Telegram & Discord Ingress)
 * 
 * Mensimulasikan:
 * 1. Telegram Adapter (HTTP polling message structure).
 * 2. Discord Adapter (WebSocket event message structure).
 * 3. Channel Normalizer Engine.
 * 4. Whitelist Verification per kanal.
 * 5. Formatting balasan khusus per platform (Telegram Markdown vs Discord Embeds).
 */

class MultiChannelGateway {
  constructor(config) {
    this.telegramOwnerId = config.telegramOwnerId;
    this.discordOwnerId = config.discordOwnerId;
  }

  // CHANNEL NORMALIZER
  processInboundMessage(rawPacket) {
    let normalized = null;

    if (rawPacket.platform === "telegram") {
      // Struktur pesan Telegram API
      normalized = {
        platform: "Telegram",
        senderId: String(rawPacket.data.from.id),
        senderName: rawPacket.data.from.first_name,
        chatId: rawPacket.data.chat.id,
        text: rawPacket.data.text || "",
        isVoice: Boolean(rawPacket.data.voice),
        isOwner: String(rawPacket.data.from.id) === String(this.telegramOwnerId)
      };
    } else if (rawPacket.platform === "discord") {
      // Struktur pesan Discord Gateway (MESSAGE_CREATE)
      normalized = {
        platform: "Discord",
        senderId: String(rawPacket.data.author.id),
        senderName: rawPacket.data.author.username,
        channelId: rawPacket.data.channel_id,
        text: rawPacket.data.content || "",
        isVoice: false,
        isOwner: String(rawPacket.data.author.id) === String(this.discordOwnerId)
      };
    }

    return this.dispatchAgent(normalized);
  }

  dispatchAgent(msg) {
    console.log(`\n📥 [${msg.platform.toUpperCase()} INGRESS] Dari "${msg.senderName}" (ID: ${msg.senderId})`);
    console.log(`   Konten: "${msg.isVoice ? "[Voice Note 12 detik]" : msg.text}"`);

    // 1. SECURITY WHITELIST CHECK
    if (!msg.isOwner) {
      console.warn(`🚨 [ACCESS DENIED] Sender ${msg.senderId} tidak ada di whitelist ${msg.platform}!`);
      return {
        target: msg.platform,
        response: "⛔ Akses Ditolak: Anda bukan pemilik bot ini."
      };
    }

    console.log(`🛡️  [Security Passed] Pemilik sah terverifikasi di ${msg.platform}.`);
    console.log(`⏳ [Agent Status] Menampilkan status "Typing..." di aplikasi ${msg.platform}...`);

    // 2. AGENT REASONING SIMULATION
    let replyText = "";
    if (msg.isVoice) {
      replyText = "Transkripsi Audio: 'Tolong restart service nginx'. Hasil: Nginx berhasil di-reload dengan PID baru (2041).";
    } else if (msg.text.toLowerCase().includes("jadwal")) {
      replyText = "Jadwal Anda hari ini: 1) Daily Standup jam 10:00, 2) Review PR OpenClaw jam 14:00.";
    } else {
      replyText = `Instruksi '${msg.text}' telah selesai dieksekusi secara sukses.`;
    }

    // 3. CHANNEL SPECIFIC FORMATTING
    let formattedPayload = null;
    if (msg.platform === "Telegram") {
      formattedPayload = `🤖 *OpenClaw Assistant*\n\n${replyText}\n\n_Waktu: ${new Date().toLocaleTimeString()}_`;
    } else {
      formattedPayload = {
        embed: {
          title: "🤖 OpenClaw Discord Notification",
          description: replyText,
          color: 0x5865F2, // Discord Blurple
          timestamp: new Date().toISOString()
        }
      };
    }

    return {
      target: msg.platform,
      payload: formattedPayload
    };
  }
}

// ======================= PENGUJIAN SKENARIO =======================
const gateway = new MultiChannelGateway({
  telegramOwnerId: "99881122",
  discordOwnerId: "334455667788990011"
});

console.log("===================================================================");
console.log("🛠️  PENGUJIAN MULTI-CHANNEL INGRESS: TELEGRAM & DISCORD");
console.log("===================================================================");

// Skenario 1: Pesan Voice Note dari Pemilik via Telegram
const telegramVoicePacket = {
  platform: "telegram",
  data: {
    message_id: 101,
    from: { id: 99881122, first_name: "Budi" },
    chat: { id: 99881122, type: "private" },
    voice: { file_id: "voice_file_abc123", duration: 12 }
  }
};
const res1 = gateway.processInboundMessage(telegramVoicePacket);
console.log(`📤 [Telegram Response Output]:\n${res1.payload}\n`);

// Skenario 2: Pesan Teks dari Pemilik via Discord
const discordTextPacket = {
  platform: "discord",
  data: {
    id: "msg_9900",
    channel_id: "channel_ops_general",
    author: { id: "334455667788990011", username: "budi_developer" },
    content: "OpenClaw, tolong tampilkan jadwal meeting hari ini"
  }
};
const res2 = gateway.processInboundMessage(discordTextPacket);
console.log(`📤 [Discord Response Embed]:\n`, JSON.stringify(res2.payload, null, 2), "\n");

// Skenario 3: Pesan dari Orang Asing di Discord
const unauthorizedDiscordPacket = {
  platform: "discord",
  data: {
    id: "msg_9901",
    channel_id: "channel_ops_general",
    author: { id: "666666666666666666", username: "unknown_user" },
    content: "Tampilkan password server!"
  }
};
const res3 = gateway.processInboundMessage(unauthorizedDiscordPacket);
console.log(`📤 [Unauthorized Output]: ${res3.response}`);

console.log("\n===================================================================");
console.log(" Kesimpulan:");
console.log("1. Normalizer menyatukan struktur payload Telegram dan Discord ke format standar.");
console.log("2. Whitelisting bekerja konsisten lintas kedua platform perpesanan.");
console.log("3. Balasan otomatis disesuaikan dengan format native masing-masing klien.");
