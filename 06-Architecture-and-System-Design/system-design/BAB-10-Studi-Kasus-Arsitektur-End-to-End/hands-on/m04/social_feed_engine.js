/**
 * LAB SIMULATION: Hybrid Fan-Out Social Media Feed Engine (Twitter/Instagram Architecture)
 * 
 * Fitur:
 * 1. Social Graph Engine (Followers & Followings).
 * 2. Deteksi Akun Selebritas (The Celebrity Problem).
 * 3. Fan-out on Write untuk Pengguna Biasa.
 * 4. Fan-out on Read untuk Selebritas.
 * 5. On-the-fly Multi-Way Merge Sort pada Read Path.
 */

class SocialMediaFeedEngine {
  constructor(celebrityThreshold = 3) {
    this.celebrityThreshold = celebrityThreshold; // Ambang batas kecil untuk kemudahan simulasi
    this.followers = new Map(); // userId -> Set of followerIds
    this.postsDatabase = new Map(); // postId -> Post Object
    this.userTimelines = new Map(); // Redis Timeline Cache: userId -> Array of postIds
    this.celebrityPosts = new Map(); // celebrityId -> Array of postIds
  }

  follow(followerId, targetUserId) {
    if (!this.followers.has(targetUserId)) {
      this.followers.set(targetUserId, new Set());
    }
    this.followers.get(targetUserId).add(followerId);
  }

  isCelebrity(userId) {
    const count = this.followers.get(userId) ? this.followers.get(userId).size : 0;
    return count >= this.celebrityThreshold;
  }

  // WRITE PATH: Publish Post
  publishPost(authorId, content) {
    const postId = "POST-" + Math.floor(Math.random() * 9000 + 1000);
    const post = {
      postId,
      authorId,
      content,
      timestamp: Date.now()
    };
    this.postsDatabase.set(postId, post);

    const isCeleb = this.isCelebrity(authorId);
    console.log(`\n📝 [New Post] ${authorId} (${isCeleb ? "⭐ SELEBRITAS" : "👤 REGULER"}): "${content}"`);

    if (isCeleb) {
      // 1. SELEBRITAS: Fan-out on Read (Simpan hanya di Celebrity Post Cache!)
      console.log(`⚡ [Fan-out on Read] Melewati fan-out ke ribuan followers! Disimpan di pool selebritas.`);
      if (!this.celebrityPosts.has(authorId)) this.celebrityPosts.set(authorId, []);
      this.celebrityPosts.get(authorId).unshift(postId);
    } else {
      // 2. REGULER: Fan-out on Write (Push ke Timeline Cache masing-masing follower)
      const followerList = Array.from(this.followers.get(authorId) || []);
      console.log(`🔄 [Fan-out on Write] Mem-push '${postId}' ke ${followerList.length} follower timeline caches.`);
      for (const followerId of followerList) {
        if (!this.userTimelines.has(followerId)) this.userTimelines.set(followerId, []);
        this.userTimelines.get(followerId).unshift(postId);
      }
    }
    return postId;
  }

  // READ PATH: Generate Feed
  getFeed(userId, limit = 10) {
    console.log(`\n📱 [Feed Request] Menghasilkan linimasa untuk '${userId}'...`);

    // 1. Ambil postingan pre-computed dari Redis Timeline Cache user
    const regularPostIds = this.userTimelines.get(userId) || [];

    // 2. Cari selebritas yang di-follow oleh user
    const followedCelebrityPosts = [];
    for (const [targetId, followersSet] of this.followers.entries()) {
      if (followersSet.has(userId) && this.isCelebrity(targetId)) {
        const celebList = this.celebrityPosts.get(targetId) || [];
        followedCelebrityPosts.push(...celebList);
      }
    }

    // 3. Gabungkan dan Hydrate dari Database
    const allCandidateIds = [...regularPostIds, ...followedCelebrityPosts];
    const hydratedPosts = allCandidateIds
      .map(id => this.postsDatabase.get(id))
      .filter(Boolean);

    // 4. On-the-fly Merge Sort berdasarkan Timestamp Terbaru
    hydratedPosts.sort((a, b) => b.timestamp - a.timestamp);

    return hydratedPosts.slice(0, limit);
  }
}

// ======================= PENGUJIAN SKENARIO =======================
const feedEngine = new SocialMediaFeedEngine(3); // Ambang batas 3 followers = Selebritas

console.log("===================================================================");
console.log("🛠️  PENGUJIAN 1: MEMBANGUN SOCIAL GRAPH & MENDETEKSI STATUS");
console.log("===================================================================\n");

// Akun Selebritas: Cristiano (Di-follow oleh User1, User2, User3, User4)
feedEngine.follow("User1", "Cristiano");
feedEngine.follow("User2", "Cristiano");
feedEngine.follow("User3", "Cristiano");
feedEngine.follow("User4", "Cristiano");

// Akun Reguler: Budi (Hanya di-follow oleh User1)
feedEngine.follow("User1", "Budi");

console.log(`Apakah Cristiano Selebritas? -> ${feedEngine.isCelebrity("Cristiano") ? "YA (Followers: 4)" : "TIDAK"}`);
console.log(`Apakah Budi Selebritas?      -> ${feedEngine.isCelebrity("Budi") ? "YA" : "TIDAK (Followers: 1)"}`);

console.log("\n===================================================================");
console.log("🛠️  PENGUJIAN 2: WRITE PATH (FAN-OUT ON WRITE VS ON READ)");
console.log("===================================================================");

// Budi memposting tweet reguler
feedEngine.publishPost("Budi", "Sedang menikmati kopi pagi di Bandung!");

// Cristiano memposting tweet selebritas
feedEngine.publishPost("Cristiano", "Siap bertanding di final malam ini! Hala Madrid!");

console.log("\n===================================================================");
console.log("🛠️  PENGUJIAN 3: READ PATH & HYBRID MERGE TIMELINE UNTUK USER1");
console.log("===================================================================");

const user1Feed = feedEngine.getFeed("User1");

console.log("\n Hasil Linimasa (News Feed) Terakhir di HP User1:");
user1Feed.forEach((p, idx) => {
  console.log(` ${idx + 1}. [${p.authorId}] "${p.content}" (${new Date(p.timestamp).toLocaleTimeString()})`);
});

console.log("\n Kesimpulan:");
console.log("1. Postingan Budi (Reguler) di-fan-out saat menulis (Push Model) langsung ke cache User1.");
console.log("2. Postingan Cristiano (Selebritas) tidak di-fan-out ke semua followers (Mencegah beban jutaan write).");
console.log("3. Saat User1 membuka feed, sistem menggabungkan cache reguler dengan postingan selebritas (Hybrid Architecture).");
