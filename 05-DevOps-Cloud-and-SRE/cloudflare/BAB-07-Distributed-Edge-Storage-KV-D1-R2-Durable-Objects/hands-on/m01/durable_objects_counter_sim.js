/**
 * Hands-on Lab: Durable Objects High-Concurrency Simulation Engine
 * Framework: Cloudflare Workers ES Module Environment (Simulasi & Production Standard)
 * 
 * Modul ini mendemonstrasikan implementasi Actor Model menggunakan Cloudflare Durable Objects
 * untuk memecahkan race condition pada sistem hitung suara / state synchronization global.
 */

// ============================================================================
// 1. DURABLE OBJECT CLASS: AtomicVoteCoordinator
// ============================================================================
export class AtomicVoteCoordinator {
  constructor(state, env) {
    this.state = state;
    this.env = env;
    this.votes = new Map();
    this.totalVotes = 0;
    this.isInitialized = false;

    // Menahan konkurensi request sampai in-memory load selesai secara atomik
    this.state.blockConcurrencyWhile(async () => {
      const storedTotal = await this.state.storage.get("total_votes");
      const storedCandidates = await this.state.storage.get("candidate_records");

      this.totalVotes = storedTotal || 0;
      if (storedCandidates) {
        this.votes = new Map(Object.entries(storedCandidates));
      }
      this.isInitialized = true;
    });
  }

  async fetch(request) {
    const url = new URL(request.url);

    switch (url.pathname) {
      case "/cast-vote": {
        if (request.method !== "POST") {
          return new Response("Method not allowed", { status: 405 });
        }

        const { candidate, voterId } = await request.json();

        if (!candidate || !voterId) {
          return Response.json({ error: "Invalid payload params" }, { status: 400 });
        }

        // 1. Proteksi Idempotency Voter di Persistent Storage DO
        const voterKey = `voter:${voterId}`;
        const hasVoted = await this.state.storage.get(voterKey);
        if (hasVoted) {
          return Response.json(
            { error: "Voter has already cast a vote!", voterId },
            { status: 409 }
          );
        }

        // 2. Atomic In-Memory Mutation
        const currentCandidateVotes = this.votes.get(candidate) || 0;
        this.votes.set(candidate, currentCandidateVotes + 1);
        this.totalVotes += 1;

        // 3. Persist State ke Local Linearizable Engine
        // Menggunakan batch write storage API untuk mengoptimalkan disk IOPS
        await this.state.storage.put({
          [voterKey]: { candidate, timestamp: Date.now() },
          total_votes: this.totalVotes,
          candidate_records: Object.fromEntries(this.votes),
        });

        // 4. Jadwalkan Alarm Otomatis untuk Sync/Snapshot jika belum ada
        const currentAlarm = await this.state.storage.getAlarm();
        if (currentAlarm === null) {
          // Set alarm 30 detik ke depan untuk trigger snapshot persistensi sekunder
          await this.state.storage.setAlarm(Date.now() + 30000);
        }

        return Response.json({
          status: "SUCCESS",
          candidate,
          newVoteCount: this.votes.get(candidate),
          totalVotes: this.totalVotes,
        });
      }

      case "/metrics": {
        return Response.json({
          totalVotes: this.totalVotes,
          tally: Object.fromEntries(this.votes),
          storageEngine: "DurableObjects-Linearizable-SQLite",
          nodeColo: request.cf ? request.cf.colo : "LOCAL-DEV",
        });
      }

      default:
        return new Response("Endpoint Not Found on Actor", { status: 404 });
    }
  }

  // Lifecycle Alarm: Dieksekusi otomatis oleh runtime Cloudflare di background
  async alarm() {
    // Skenario: Lakukan flush data berkala ke external cold-storage atau agregasi
    console.log(`[ALARM RUNNER] Periodic sync trigger for DO. Current Total: ${this.totalVotes}`);
    // Simulasi penulisan checkpoint state ke R2 atau KV dapat dipicu dari sini
  }
}

// ============================================================================
// 2. MAIN WORKER ROUTER (GATEWAY)
// ============================================================================
export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    // Healthcheck endpoint
    if (url.pathname === "/") {
      return new Response("Distributed State Management Coordinator Running.");
    }

    // Routing ke Durable Object: /api/vote?pollId=presidential-2024
    if (url.pathname.startsWith("/api/vote")) {
      const pollId = url.searchParams.get("pollId");
      if (!pollId) {
        return new Response("Missing 'pollId' query parameter", { status: 400 });
      }

      // Mendapatkan Durable Object Stub ID berdasarkan string nama topik
      // Menjamin seluruh pemilih topik yang sama diarahkan ke instance yang sama
      const objectId = env.VOTE_COORDINATOR_DO.idFromName(pollId);
      const doStub = env.VOTE_COORDINATOR_DO.get(objectId);

      if (url.pathname === "/api/vote/cast" && request.method === "POST") {
        // Forward HTTP Request langsung ke Actor Isolate
        return doStub.fetch(
          new Request("http://internal-actor/cast-vote", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: request.body,
          })
        );
      }

      if (url.pathname === "/api/vote/metrics" && request.method === "GET") {
        return doStub.fetch(new Request("http://internal-actor/metrics"));
      }
    }

    // Fast Path Caching Reader via Workers KV: /api/cache-metrics?pollId=presidential-2024
    if (url.pathname === "/api/cache-metrics") {
      const pollId = url.searchParams.get("pollId");
      const cached = await env.GLOBAL_CACHE_KV.get(`metrics:${pollId}`);
      if (cached) {
        return new Response(cached, {
          headers: {
            "Content-Type": "application/json",
            "X-Data-Source": "Workers-KV-Edge-Cache",
          },
        });
      }
      return Response.json({ message: "Cache miss or expired" }, { status: 404 });
    }

    return new Response("Route Not Found", { status: 404 });
  },
};