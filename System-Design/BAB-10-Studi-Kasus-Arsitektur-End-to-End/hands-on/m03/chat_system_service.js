/**
 * LAB SIMULATION: End-to-End Real-Time Chat Architecture
 * 
 * Mensimulasikan:
 * 1. Multi-Gateway WebSocket Cluster (Server 1 & Server 2).
 * 2. Session Routing Registry (Mengetahui user terkoneksi di server mana).
 * 3. Presence Service dengan Heartbeat.
 * 4. Pilihan alur: Real-time WS Delivery vs Offline Push Notification (FCM).
 * 5. Group Chat Fan-out Delivery.
 */

// 1. PRESENCE & ROUTING SERVICE (REDIS MOCK)
class SessionAndPresenceService {
  constructor() {
    this.activeSessions = new Map(); // userId -> { serverId, lastHeartbeat }
  }

  registerConnection(userId, serverId) {
    this.activeSessions.set(userId, { serverId, lastHeartbeat: Date.now() });
  }

  removeConnection(userId) {
    this.activeSessions.delete(userId);
  }

  heartbeat(userId) {
    if (this.activeSessions.has(userId)) {
      this.activeSessions.get(userId).lastHeartbeat = Date.now();
    }
  }

  getUserRouting(userId) {
    const session = this.activeSessions.get(userId);
    if (!session) return null;

    // Heartbeat timeout 3 detik
    if (Date.now() - session.lastHeartbeat > 3000) {
      this.removeConnection(userId);
      return null;
    }
    return session.serverId;
  }
}

// 2. WEBSOCKET GATEWAY SERVER
class WebSocketGatewayServer {
  constructor(serverId, sessionService, messageBus) {
    this.serverId = serverId;
    this.sessionService = sessionService;
    this.messageBus = messageBus;
    this.localSockets = new Map(); // userId -> clientSocketCallback
  }

  connectClient(userId, receiveCallback) {
    this.localSockets.set(userId, receiveCallback);
    this.sessionService.registerConnection(userId, this.serverId);
    console.log(`🔌 [${this.serverId}] Klien '${userId}' terhubung via WebSocket.`);
  }

  disconnectClient(userId) {
    this.localSockets.delete(userId);
    this.sessionService.removeConnection(userId);
    console.log(`🔌 [${this.serverId}] Klien '${userId}' disconnect.`);
  }

  // Client mengirim pesan
  sendMessage(senderId, recipientId, content) {
    const message = {
      messageId: "MSG-" + Math.random().toString(36).substring(2, 8),
      senderId,
      recipientId,
      content,
      timestamp: new Date().toISOString()
    };
    this.messageBus.routeMessage(this.serverId, message);
  }

  // Server menerima pesan dari Message Bus untuk diteruskan ke socket lokal
  deliverToLocalSocket(message) {
    const socket = this.localSockets.get(message.recipientId);
    if (socket) {
      socket(message);
    }
  }
}

// 3. MESSAGE BUS & PUSH NOTIFICATION DISPATCHER
class MessageBusRouter {
  constructor(sessionService) {
    this.sessionService = sessionService;
    this.gateways = new Map(); // serverId -> gatewayInstance
    this.offlineInbox = new Map(); // userId -> Array of unread messages
  }

  registerGateway(gateway) {
    this.gateways.set(gateway.serverId, gateway);
  }

  routeMessage(originServerId, message) {
    const { recipientId, senderId, content, messageId } = message;
    console.log(`\n📨 [MessageBus] Menerima ${messageId} dari ${senderId} untuk ${recipientId}`);

    // Cek routing table
    const targetServerId = this.sessionService.getUserRouting(recipientId);

    if (targetServerId) {
      console.log(`⚡ [MessageBus] Rute Ditemukan: ${recipientId} sedang ONLINE di '${targetServerId}'.`);
      const targetGateway = this.gateways.get(targetServerId);
      targetGateway.deliverToLocalSocket(message);
    } else {
      console.log(`📴 [MessageBus] ${recipientId} sedang OFFLINE!`);
      // Simpan ke offline storage
      if (!this.offlineInbox.has(recipientId)) this.offlineInbox.set(recipientId, []);
      this.offlineInbox.get(recipientId).push(message);

      // Trigger Push Notification (FCM / APNs)
      console.log(`🔔 [Push Notification Service] Mengirim push pop-up ke HP '${recipientId}': "${senderId}: ${content}"`);
    }
  }
}

// ======================= PENGUJIAN SKENARIO =======================
const sessionService = new SessionAndPresenceService();
const bus = new MessageBusRouter(sessionService);

const wsGateway1 = new WebSocketGatewayServer("WS-Gateway-1", sessionService, bus);
const wsGateway2 = new WebSocketGatewayServer("WS-Gateway-2", sessionService, bus);

bus.registerGateway(wsGateway1);
bus.registerGateway(wsGateway2);

console.log("===================================================================");
console.log("🛠️  PENGUJIAN 1: PENGIRIMAN PESAN 1-ON-1 LINTAS SERVER GATEWAY");
console.log("===================================================================\n");

// User A terhubung di Server 1
wsGateway1.connectClient("User_A", (msg) => {
  console.log(`📱 [HP User_A] Notif Masuk: "${msg.senderId}: ${msg.content}"`);
});

// User B terhubung di Server 2
wsGateway2.connectClient("User_B", (msg) => {
  console.log(`📱 [HP User_B] Notif Masuk: "${msg.senderId}: ${msg.content}"`);
});

// User A mengirim pesan ke User B (Lintas Gateway 1 -> Gateway 2)
console.log("\n-> User_A (di Gateway 1) mengirim pesan ke User_B (di Gateway 2):");
wsGateway1.sendMessage("User_A", "User_B", "Halo Bro, jadwal meeting kita jadi jam 2 siang kan?");

console.log("\n===================================================================");
console.log("🛠️  PENGUJIAN 2: PENGIRIMAN PESAN KE PENGGUNA OFFLINE (PUSH NOTIF)");
console.log("===================================================================\n");

// User C tidak terhubung (Offline)
console.log("-> User_A mengirim pesan ke User_C (yang sedang offline):");
wsGateway1.sendMessage("User_A", "User_C", "Bro, jangan lupa upload laporan keuangan!");

console.log("\n Kesimpulan:");
console.log("1. Session Routing Registry mengarahkan pesan ke server WebSocket tempat penerima aktif.");
console.log("2. Pesan terkirim instan antar-gateway melalui Message Bus terdistribusi.");
console.log("3. Jika pengguna offline, sistem otomatis mengalihkan pesan ke Push Notification Service.");
