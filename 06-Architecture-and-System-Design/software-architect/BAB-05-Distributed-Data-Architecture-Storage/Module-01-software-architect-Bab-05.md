## SEKSI 01 — IDENTITAS MODUL

* **Jalur Kurikulum:** Software Architect
* **Kategori:** 06-Architecture-and-System-Design
* **Kode Modul:** ARC-06-05-01
* **Nama Modul:** Distributed Data Architecture & Storage Strategies: Polyglot Persistence, Event Sourcing, CQRS, Database Sharding, Consensus Protocols (Raft/Paxos), CAP/PACELC
* **Prasyarat:** Database Internals (B-Trees, LSM-Trees, WAL, Isolation Levels), Concurrency Control, Network Protocols (TCP/IP, RPC), Microservices Architecture
* **Target Tingkat Kemahiran:** Advanced / Principal Engineer / Staff Software Architect
* **Estimasi Waktu Belajar:** 18 Jam (Teori Mendalam, Analisis Desain, dan Implementasi Prototipe)

---

## SEKSI 02 — LEARNING OBJECTIVES

Setelah menyelesaikan modul ini, Anda diharapkan mampu:

1. **Menganalisis Trade-Off Teoretis:** Mengevaluasi karakteristik sistem terdistribusi menggunakan teorema CAP dan PACELC, serta memilih model konsistensi data yang presisi berdasarkan batasan latensi dan toleransi kegagalan jaringan.
2. **Merancang State Machine Terdistribusi Menggunakan Konsensus:** Mengoperasionalkan protokol konsensus Raft dan Paxos untuk menjamin *linearizable consistency* pada distributed replicated log, mencegah *split-brain*, dan mengelola *leader election* serta *log compaction*.
3. **Mendesain Pola Partisi Data Skala Masif:** Mengimplementasikan strategi Database Sharding berbasis *Range-based*, *Hash-based*, dan *Consistent Hashing with Virtual Nodes* guna memitigasi *hotspot partitions* dan meminimalkan pergerakan data selama resharding.
4. **Mengkonstruksi Arsitektur CQRS & Event Sourcing:** Membangun *event-driven storage pipeline* yang memisahkan model tulis (*Aggregate Root* + *Immutable Append-Only Event Store*) dari model baca (*Read Projections*), lengkap dengan mitigasi *concurrency conflict* menggunakan *Optimistic Concurrency Control* (OCC).
5. **Menyusun Strategi Polyglot Persistence Terpadu:** Memadukan mesin data relasional, document, key-value, graph, time-series, dan search engine ke dalam satu ekosistem sistem terdistribusi menggunakan *Transactional Outbox Pattern* dan *Change Data Capture* (CDC).

---

## SEKSI 03 — KONSEP UTAMA (CONCEPT MAP)

```
                              ┌────────────────────────────────────────┐
                              │  Distributed Data Architecture Models  │
                              └───────────────────┬────────────────────┘
                                                  │
          ┌───────────────────────────────────────┼────────────────────────────────────────┐
          │                                       │                                        │
┌─────────▼─────────┐                 ┌───────────▼───────────┐                ┌───────────▼───────────┐
│ Theoretical Bounds│                 │ Coordination/Consensus│                │ Structural Partitioning│
├───────────────────┤                 ├───────────────────────┤                ├───────────────────────┤
│ • CAP Theorem     │                 │ • Paxos (Synod, Multi)│                │ • Vertical vs Horiz.  │
│ • PACELC Theorem  │                 │ • Raft (Leader, Log,  │                │ • Consistent Hashing  │
│ • Strong vs       │                 │   Commit Safety)      │                │ • Virtual Nodes       │
│   Eventual Cons.  │                 │ • Quorum (R + W > N)  │                │ • Resharding Hazards  │
└─────────┬─────────┘                 └───────────┬───────────┘                └───────────┬───────────┘
          │                                       │                                        │
          └───────────────────────────────────────┼────────────────────────────────────────┘
                                                  │
          ┌───────────────────────────────────────┴────────────────────────────────────────┐
          │                                                                                │
┌─────────▼──────────┐                                                         ┌───────────▼───────────┐
│ Event-Driven State │                                                         │ Persistence Diversity │
├────────────────────┤                                                         ├───────────────────────┤
│ • Event Sourcing   │                                                         │ • Polyglot Strategy   │
│ • CQRS Separation  │◄──────────────── Change Data Capture (CDC) ────────────►│ • RDBMS + Key-Value   │
│ • Projections      │                  / Transactional Outbox                 │ • Graph + Search Eng. │
│ • Optimistic Lock  │                                                         │ • Time-Series Storage │
└────────────────────┘                                                         └───────────────────────┘
```

---

## SEKSI 04 — MENGAPA INI PENTING (WHY)

Pada sistem monolitik tradisional, arsitek bergantung pada satu basis data relasional terpusat yang menawarkan garansi ACID (*Atomicity, Consistency, Isolation, Durability*). Skalabilitas dicapai secara vertikal (*scale-up*). Namun, ketika volume transaksi mencapai ratusan ribu operasi per detik dan volume data menembus terabyte hingga petabyte, keterbatasan perangkat keras, *lock contention*, dan latensi transmisi lintas-wilayah menuntut transisi ke arsitektur terdistribusi (*scale-out*).

Beralih ke sistem terdistribusi membatalkan asumsi bahwa waktu (*clock*) seragam, memori dapat diakses bersama secara instan, atau jaringan bebas dari kegagalan. Teorema CAP dan perluasannya, PACELC, membuktikan secara matematis bahwa tidak ada sistem penyimpanan terdistribusi yang mampu memberikan konsistensi mutlak sekaligus ketersediaan 100% di hadapan *network partition*, serta latensi rendah di bawah kondisi normal.

Kesalahan memahami prinsip-prinsip ini berakibat fatal:
1. **Inkonsistensi Finansial:** *Split-brain* pada cluster database menyebabkan pembelanjaan ganda (*double spending*).
2. **Kerapuhan Operasional:** Implementasi sharding yang naif mengakibatkan *cascading failures* ketika satu node kelebihan beban (*hotspot*).
3. **Kehilangan Jejak Audit Historis:** Mengubah state database secara *in-place* menghilangkan visibilitas terhadap bagaimana sebuah status akhir terbentuk.

Arsitek perangkat lunak senior wajib menguasai penyimpanan poliglota, partisi data, protokol konsensus, serta pola pemisahan mutasi dan proyeksi data (CQRS/ES) untuk membangun sistem yang tahan banting (*resilient*), berkinerja tinggi, dan dapat diaudit secara matematis.

---

## SEKSI 05 — APA ITU (WHAT)

### 1. Teorema CAP & PACELC
* **CAP (Eric Brewer):** Pada jaringan terdistribusi yang mengalami kegagalan partisi (**P**artition Tolerance), sistem hanya dapat memilih antara Konsistensi (**C**onsistency / *Linearizable*) atau Ketersediaan (**A**vailability / *Setiap node non-failing merespons tanpa error*).
* **PACELC (Daniel Abadi):** Memperluas CAP. **IF** ada Partisi (**P**), bagaimana trade-off antara Ketersediaan (**A**) dan Konsistensi (**C**); **ELSE** (jika sistem berjalan normal tanpa kegagalan), bagaimana trade-off antara Latensi (**L**) dan Konsistensi (**C**)?
  * *Contoh PC/EC:* Google Spanner (mengorbankan ketersediaan saat partisi masif, mengutamakan konsistensi dan latensi rendah via TrueTime API).
  * *Contoh PA/EL:* Amazon DynamoDB / Apache Cassandra (mengutamakan ketersediaan saat partisi dan latensi minimal saat normal, menerima *eventual consistency*).

### 2. Protokol Konsensus Terdistribusi: Paxos vs Raft
Konsensus adalah proses di mana sekumpulan node sepakat terhadap satu nilai atau urutan log eksekusi, bahkan jika sebagian node mati (*crash-recovery*).
* **Paxos:** Protokol konsensus klasik karya Leslie Lamport. Terkenal sangat modular namun sulit dipahami dan diimplementasikan secara praktis (*Multi-Paxos* membutuhkan banyak penyesuaian untuk produksi).
* **Raft:** Didesain oleh Ongaro & Ousterhout untuk keterpahaman (*understandability*). Raft membagi konsensus menjadi sub-problem: *Leader Election*, *Log Replication*, dan *Safety*. Log hanya mengalir searah dari Leader ke Follower.

### 3. Database Sharding & Consistent Hashing
* **Database Sharding:** Memecah dataset monolitik menjadi partisi horizontal yang lebih kecil (*shards*), disebar ke beberapa instance database mandiri.
* **Consistent Hashing:** Algoritma pemetaan data ke node menggunakan cincin hash virtual ($0 \dots 2^{32}-1$). Memanfaatkan *Virtual Nodes* (vnodes) untuk mendistribusikan beban secara homogen dan memastikan saat node ditambah/dihapus, hanya $K/N$ kunci yang direlokasi ($K$ = jumlah kunci, $N$ = jumlah node).

### 4. Event Sourcing & CQRS
* **Event Sourcing (ES):** Status entitas tidak disimpan sebagai snapshot terkini (*state mutation*), melainkan direkonstruksi secara deterministik dari urutan kejadian (*immutable stream of events*) yang dicatat secara *append-only*.
* **Command Query Responsibility Segregation (CQRS):** Pemisahan eksplisit antara jalur komputasi/penulisan (*Command*) yang memvalidasi domain invariants dan jalur pembacaan (*Query*) yang menggunakan model data terdenormalisasi untuk performa tinggi.

### 5. Polyglot Persistence
Konsep penggunaan mesin database yang heterogen dalam satu kesatuan arsitektur, di mana tiap jenis penyimpanan disesuaikan secara presisi dengan karakteristik akses beban kerja (*workload characteristics*):
* RDBMS untuk transaksi ACID ketat dan relasi terstruktur kompleks.
* Key-Value Store (Redis) untuk caching latensi sub-milidetik.
* Document Store (MongoDB) untuk payload skema semi-terstruktur.
* Search Engine (Elasticsearch/OpenSearch) untuk *full-text search* dan agregasi analitik.
* Graph Database (Neo4j) untuk traversal hubungan relasional derajat tinggi.

---

## SEKSI 06 — BAGAIMANA BEKERJA (HOW)

### 1. Mekanisme Protokol Konsensus Raft
Raft mengandalkan konsep waktu logis (*Logical Term*) dan State Machine Replication (SMR).

```
State Node: [Follower] ──(Timeout)──> [Candidate] ──(Majority Votes)──> [Leader]
                 ▲                          │                               │
                 └────────(Discover Leader/─┴───────────────────────────────┘
                           Higher Term)
```

1. **Leader Election:**
   * Node berjalan dengan *randomized election timeout* (misal 150ms - 300ms).
   * Jika Follower tidak menerima *heartbeat* (`AppendEntries` RPC kosong) sebelum timeout, ia menaikkan nilai `currentTerm`, mengubah status menjadi Candidate, memilih dirinya sendiri, dan mengirimkan `RequestVote` RPC ke seluruh node.
   * Node akan memenangkan pemilu jika menerima suara dari mayoritas quorum ($N/2 + 1$).
2. **Log Replication:**
   * Klien mengirim instruksi ke Leader.
   * Leader mencatat instruksi ke WAL (*Write-Ahead Log*) lokalnya, lalu mengirimkan `AppendEntries` RPC ke seluruh Follower.
   * Setelah Follower menyimpan entri tersebut ke disk lokal mereka dan mayoritas mengirimkan respons sukses, entri log dinyatakan **Committed**.
   * Leader mengaplikasikan entri ke state machine lokalnya, merespons ke klien, dan mengabari Follower bahwa entri sudah commit pada RPC berikutnya.
3. **Safety Invariants:**
   * *Election Safety:* Maksimal satu leader terpilih per term.
   * *Leader Append-Only:* Leader tidak pernah menimpa atau memotong lognya sendiri.
   * *Log Matching Property:* Jika dua log memiliki entri dengan index dan term yang sama, maka seluruh log sebelum indeks tersebut identik.

### 2. Mekanisme Consistent Hashing dengan Virtual Nodes
Ketika sebuah key `k` hendak disimpan:
1. Hash key dihitung: $H_k = \text{Murmur3}(k)$.
2. Tiap node fisik direpresentasikan oleh $V$ token acak (*virtual nodes*) pada ruang hash ring $[0, 2^{32} - 1]$.
3. Hash key $H_k$ dipetakan ke token pertama pada ring yang nilainya $\ge H_k$ (bergerak searah jarum jam / *clockwise*).
4. Untuk replikasi (faktor replikasi $R$), data dituliskan ke node pemilik token tersebut dan $R-1$ node fisik unik berikutnya pada ring.

```
       Ring Hash Space [0 -> 2^32-1]
               NodeA_vnode1 (0x1000)
             /                       \
   NodeC_vnode2 (0xD000)          NodeB_vnode1 (0x4000)
         |                              |
         |         Key "usr_99"         |
         |         Hash: 0x5100         |
         |         (Maps to NodeA)      |
   NodeB_vnode2 (0xA000)          NodeA_vnode2 (0x7000)
             \                       /
               NodeC_vnode1 (0x8500)
```

### 3. Pipeline Event Sourcing + CQRS + Asynchronous Projection
1. **Handling Command:**
   * Klien mengeksekusi `Command` (misal: `WithdrawMoney`).
   * Command Handler memuat seluruh *stream events* masa lalu milik Aggregate dari **Event Store**.
   * State Aggregate dihidrasi ulang (*replay* dari snapshot terakhir + sisa event).
   * Aggregate mengevaluasi *business invariant* (misal: `balance >= amount`).
   * Jika valid, Aggregate menghasilkan satu atau lebih *domain events* (misal: `MoneyWithdrawn`).
2. **Persisting Events (Optimistic Concurrency Control):**
   * Event Store mencoba melakukan *append* event baru dengan syarat: `expectedVersion == aggregate.currentVersion`.
   * Jika ada operasi lain yang mendahului, commit gagal (*concurrency conflict*), transaksi dibatalkan, dan klien diminta melakukan *retry*.
3. **Projecting Read Models (Outbox Pattern & CDC):**
   * Event yang sukses di-append dipublikasikan ke message bus (Apache Kafka/RabbitMQ) via Transactional Outbox Worker atau tailing Change Data Capture (Debezium).
   * Berbagai Projector membaca event tersebut secara asinkron, mentransformasikan datanya, dan memperbarui basis data baca terdenormalisasi (Elasticsearch, Redis, Postgres Read Tables).

---

## SEKSI 07 — DIAGRAM ASCII DETAIL

### 1. Raft Consensus Node State Machine & Log Flow

```
+-------------------------------------------------------------------------------+
|                             RAFT CONSENSUS ENGINE                             |
+-------------------------------------------------------------------------------+
  Client Write
       │
       ▼
+─────────────+       AppendEntries(term=1, idx=4)       +─────────────+
|   LEADER    | ────────────────────────────────────────> |  FOLLOWER 1 |
| (Node 1)    |                                          | (Node 2)    |
|             | <──────────────────────────────────────── |             |
| Term: 1     |            Success: true                 +─────────────+
| Log Index: 4|
| Commit: 3   |       AppendEntries(term=1, idx=4)       +─────────────+
|             | ────────────────────────────────────────> |  FOLLOWER 2 |
|             |                                          | (Node 3)    |
|             | <──────────────────────────────────────── | [Unreachable|
+──────┬──────+            Network Drop (Timeout)         +─────────────+
       │
       │ Quorum Reached (2 of 3 nodes acknowledged)
       ▼
+──────────────────────────────────────────+
| Log Entry Committed (Index 4)            |
| Apply to Local State Machine             |
| Return Success to Client                 |
+──────────────────────────────────────────+
```

### 2. End-to-End CQRS & Event Sourcing Architecture

```
   [ CLIENT / API GATEWAY ]
          │              ▲
  Commands│              │ Queries
  (Write) │              │ (Read)
          ▼              │
+──────────────────+   +───────────────────────────────────+
| Command Handler  |   | Query Service                     |
+─────────┬────────+   +─────────────────▲─────────────────+
          │                              │
     Load │ Hydrate                      │ Read Optimized
          ▼                              │
+──────────────────+   +─────────────────┴─────────────────+
|  Aggregate Root  |   | Read Models / Projections         |
| (Domain Logic)   |   | (Elasticsearch / Redis / RDBMS)   |
+─────────┬────────+   +─────────────────▲─────────────────+
          │                              │
     New  │ Events                       │ Project Events
          ▼                              │ (Async Workers)
+──────────────────+   +─────────────────┴─────────────────+
|   Event Store    |──>| Message Broker / Event Bus        |
| (Append-Only WAL)|   | (Kafka / RabbitMQ / Outbox Engine)|
+──────────────────+   +───────────────────────────────────+
```

### 3. Distributed Sharding with Consistent Hash Ring Topology

```
                         Ruang Partisi Hash Cincin [0 -> 2^32]
                                
                                     Token: 0
                                  +------------+
                        ..........|  NODE A_1  |..........
                   .....          +------------+          .....
               ....                                            ....
        +------------+                                      +------------+
        |  NODE C_2  |                                      |  NODE B_1  |
        +------------+                                      +------------+
       .                                                                  .
      .                                                                    .
  Token:                                                                 Token:
  3*10^9                                                                 1*10^9
     .                                                                      .
    .                                                                        .
        +------------+                                      +------------+
        |  NODE B_2  |                                      |  NODE A_2  |
        +------------+                                      +------------+
               ....                                            ....
                   .....          +------------+          .....
                        ..........|  NODE C_1  |..........
                                  +------------+
                                     Token: 2*10^9

 [Klien] ──> Hash("user_uuid_9481") = 1.4*10^9 ──> Rute ke Target: NODE A_2 (Next Clockwise)
```

---

## SEKSI 08 — CONTOH SEDERHANA (SIMPLE EXAMPLE)

Berikut adalah implementasi Python minimal untuk **Consistent Hashing dengan Virtual Nodes** guna memahami bagaimana sharding mendistribusikan beban secara seimbang.

```python
import hashlib
import bisect

class ConsistentHashRing:
    def __init__(self, replicas: int = 3):
        self.replicas = replicas
        self.ring = []          # Berisi sorted list hash tokens
        self.ring_map = {}      # Memetakan token -> identifier node fisik

    def _hash(self, key: str) -> int:
        """Menggunakan MD5 untuk menghasilkan integer 32-bit (untuk demo)."""
        return int(hashlib.md5(key.encode('utf-8')).hexdigest()[:8], 16)

    def add_node(self, node: str) -> None:
        """Menambahkan node fisik beserta virtual nodes (replicas) ke ring."""
        for i in range(self.replicas):
            vnode_key = f"{node}#VN{i}"
            token = self._hash(vnode_key)
            bisect.insort(self.ring, token)
            self.ring_map[token] = node

    def remove_node(self, node: str) -> None:
        """Menghapus seluruh virtual nodes milik node fisik dari ring."""
        for i in range(self.replicas):
            vnode_key = f"{node}#VN{i}"
            token = self._hash(vnode_key)
            idx = bisect.bisect_left(self.ring, token)
            if idx < len(self.ring) and self.ring[idx] == token:
                del self.ring[idx]
                del self.ring_map[token]

    def get_node(self, key: str) -> str:
        """Memetakan routing key ke node fisik searah jarum jam."""
        if not self.ring:
            raise RuntimeError("Hash ring kosong, tidak ada node tersedia.")
        
        token = self._hash(key)
        idx = bisect.bisect_right(self.ring, token)
        
        # Wrap-around ke awal cincin jika melewati nilai token terbesar
        if idx == len(self.ring):
            idx = 0
            
        return self.ring_map[self.ring[idx]]

# Uji Coba Routing Sederhana
if __name__ == "__main__":
    ch = ConsistentHashRing(replicas=3)
    ch.add_node("Database_Node_A")
    ch.add_node("Database_Node_B")
    ch.add_node("Database_Node_C")

    sample_keys = ["user_101", "order_552", "invoice_991", "session_338", "wallet_781"]
    print("--- Pemetaan Awal Kunci ke Node ---")
    for k in sample_keys:
        print(f"Key '{k}' dialokasikan ke -> {ch.get_node(k)}")

    print("\n--- Node 'Database_Node_B' Mengalami Gangguan (Dihapus) ---")
    ch.remove_node("Database_Node_B")
    for k in sample_keys:
        print(f"Key '{k}' dialokasikan ulang ke -> {ch.get_node(k)}")
```

---

## SEKSI 09 — CONTOH PRAKTIS (PRACTICAL EXAMPLE)

Berikut adalah implementasi *production-ready* pola **Event Sourcing Aggregate** dengan **Optimistic Concurrency Control (OCC)** dalam TypeScript/Node.js, merepresentasikan entitas perbankan (`BankAccount`).

```typescript
// ==========================================
// 1. Core Domain Events Definition
// ==========================================
export interface DomainEvent {
  aggregateId: string;
  version: number;
  occurredAt: Date;
  eventType: string;
  data: Record<string, any>;
}

export class AccountOpenedEvent implements DomainEvent {
  readonly eventType = 'AccountOpened';
  constructor(
    public readonly aggregateId: string,
    public readonly version: number,
    public readonly occurredAt: Date,
    public readonly data: { ownerId: string; initialBalance: number }
  ) {}
}

export class MoneyDepositedEvent implements DomainEvent {
  readonly eventType = 'MoneyDeposited';
  constructor(
    public readonly aggregateId: string,
    public readonly version: number,
    public readonly occurredAt: Date,
    public readonly data: { amount: number; referenceId: string }
  ) {}
}

export class MoneyWithdrawnEvent implements DomainEvent {
  readonly eventType = 'MoneyWithdrawn';
  constructor(
    public readonly aggregateId: string,
    public readonly version: number,
    public readonly occurredAt: Date,
    public readonly data: { amount: number; reason: string }
  ) {}
}

// ==========================================
// 2. Aggregate Root (Business Logic & State)
// ==========================================
export class BankAccountAggregate {
  private id!: string;
  private version: number = 0;
  private balance: number = 0;
  private isClosed: boolean = false;
  private uncommittedEvents: DomainEvent[] = [];

  public getAggregateId(): string {
    return this.id;
  }

  public getVersion(): number {
    return this.version;
  }

  public getUncommittedEvents(): DomainEvent[] {
    return [...this.uncommittedEvents];
  }

  public clearUncommittedEvents(): void {
    this.uncommittedEvents = [];
  }

  // Rekonstruksi State dari Log Masa Lalu (Hydration)
  public static replay(history: DomainEvent[]): BankAccountAggregate {
    const aggregate = new BankAccountAggregate();
    for (const event of history) {
      aggregate.apply(event, false);
    }
    return aggregate;
  }

  // --- Command Methods (Invariant Enforcement) ---
  public static open(id: string, ownerId: string, initialBalance: number): BankAccountAggregate {
    if (initialBalance < 0) {
      throw new Error("Initial balance cannot be negative.");
    }
    const aggregate = new BankAccountAggregate();
    const event = new AccountOpenedEvent(id, 1, new Date(), { ownerId, initialBalance });
    aggregate.apply(event, true);
    return aggregate;
  }

  public deposit(amount: number, referenceId: string): void {
    if (this.isClosed) throw new Error("Cannot deposit to closed account.");
    if (amount <= 0) throw new Error("Deposit amount must be positive.");

    const event = new MoneyDepositedEvent(this.id, this.version + 1, new Date(), {
      amount,
      referenceId,
    });
    this.apply(event, true);
  }

  public withdraw(amount: number, reason: string): void {
    if (this.isClosed) throw new Error("Cannot withdraw from closed account.");
    if (amount <= 0) throw new Error("Withdraw amount must be positive.");
    if (this.balance - amount < 0) {
      throw new Error(`Insufficient funds. Current Balance: ${this.balance}, Attempted: ${amount}`);
    }

    const event = new MoneyWithdrawnEvent(this.id, this.version + 1, new Date(), {
      amount,
      reason,
    });
    this.apply(event, true);
  }

  // State Mutation (Internal Deterministic Router)
  private apply(event: DomainEvent, isNew: boolean): void {
    switch (event.eventType) {
      case 'AccountOpened':
        this.id = event.aggregateId;
        this.balance = event.data.initialBalance;
        break;
      case 'MoneyDeposited':
        this.balance += event.data.amount;
        break;
      case 'MoneyWithdrawn':
        this.balance -= event.data.amount;
        break;
      default:
        throw new Error(`Unknown event type: ${event.eventType}`);
    }

    this.version = event.version;
    if (isNew) {
      this.uncommittedEvents.push(event);
    }
  }
}

// ==========================================
// 3. Thread-Safe Event Store with OCC
// ==========================================
export class ConcurrencyError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ConcurrencyError";
  }
}

export class InMemoryEventStore {
  // Simulasi tabel 'events': Map<AggregateId, DomainEvent[]>
  private storage = new Map<string, DomainEvent[]>();

  public async getEvents(aggregateId: string): Promise<DomainEvent[]> {
    return this.storage.get(aggregateId) || [];
  }

  public async appendEvents(
    aggregateId: string,
    expectedVersion: number,
    events: DomainEvent[]
  ): Promise<void> {
    const history = this.storage.get(aggregateId) || [];
    const currentVersion = history.length > 0 ? history[history.length - 1].version : 0;

    // Validasi Optimistic Concurrency Control (OCC)
    if (currentVersion !== expectedVersion) {
      throw new ConcurrencyError(
        `Optimistic lock failed on Aggregate [${aggregateId}]. Expected: ${expectedVersion}, Actual: ${currentVersion}`
      );
    }

    // Atomic Append
    const updatedHistory = [...history, ...events];
    this.storage.set(aggregateId, updatedHistory);
  }
}

// ==========================================
// 4. Execution Pipeline & Concurrency Test
// ==========================================
async function runDemonstration() {
  const eventStore = new InMemoryEventStore();
  const accountId = "acc-corp-001";

  console.log("=== 1. Create Initial Aggregate ===");
  const account = BankAccountAggregate.open(accountId, "client-enterprise-abc", 1000);
  await eventStore.appendEvents(account.getAggregateId(), 0, account.getUncommittedEvents());
  account.clearUncommittedEvents();
  console.log(`Account [${accountId}] created. Version: ${account.getVersion()}`);

  console.log("\n=== 2. Replay & Execute Legitimate Withdrawal ===");
  const history = await eventStore.getEvents(accountId);
  const rehydratedAccount = BankAccountAggregate.replay(history);
  rehydratedAccount.withdraw(300, "Server Maintenance Fee");
  
  await eventStore.appendEvents(
    rehydratedAccount.getAggregateId(),
    rehydratedAccount.getVersion() - rehydratedAccount.getUncommittedEvents().length,
    rehydratedAccount.getUncommittedEvents()
  );
  rehydratedAccount.clearUncommittedEvents();
  console.log(`Withdrawal successful. Current Version: ${rehydratedAccount.getVersion()}`);

  console.log("\n=== 3. Simulating Concurrent Race Condition (Split Writes) ===");
  // Dua proses memuat versi yang sama dari Event Store secara bersamaan (Versi 2)
  const clientAHistory = await eventStore.getEvents(accountId);
  const clientBHistory = await eventStore.getEvents(accountId);

  const instanceA = BankAccountAggregate.replay(clientAHistory);
  const instanceB = BankAccountAggregate.replay(clientBHistory);

  instanceA.deposit(500, "Client A Inbound Remittance");
  instanceB.withdraw(200, "Client B Automated SaaS Debit");

  // Transaksi A berhasil menyimpan data
  await eventStore.appendEvents(
    instanceA.getAggregateId(),
    instanceA.getVersion() - instanceA.getUncommittedEvents().length,
    instanceA.getUncommittedEvents()
  );
  console.log("Process A successfully committed. New Version:", instanceA.getVersion());

  // Transaksi B mencoba menyimpan dengan basis versi lama -> Harus Gagal OCC
  try {
    console.log("Process B attempting commit with stale expected version...");
    await eventStore.appendEvents(
      instanceB.getAggregateId(),
      instanceB.getVersion() - instanceB.getUncommittedEvents().length,
      instanceB.getUncommittedEvents()
    );
  } catch (error) {
    if (error instanceof ConcurrencyError) {
      console.error("SUCCESSFULLY DETECTED OCC CONFLICT:", error.message);
      console.log("Resolution Strategy: Reload aggregate from Event Store, re-evaluate invariants, and retry.");
    } else {
      throw error;
    }
  }
}

runDemonstration();
```

---

## SEKSI 10 — TRADE-OFFS & PERTIMBANGAN

| Dimensi Arsitektural | Opsi A | Opsi B | Trade-off Utama & Dampak Performa |
| :--- | :--- | :--- | :--- |
| **Model Replikasi** | **Synchronous Replication** | **Asynchronous Replication** | Sync: Menjamin *Zero Data Loss* (RPO=0) tapi mengorbankan write latency dan throughput (kematian 1 replica memblokir sistem). Async: Latensi ultra-rendah tapi berisiko *data loss* saat master crash mendadak. |
| **Pola Konsistensi** | **Linearizable / Strong Consistency** | **Eventual Consistency** | Strong: Mencegah *stale reads*, membutuhkan negosiasi konsensus (Raft/Paxos roundtrips). Eventual: Skala pembacaan horizontal tanpa batas, namun klien berisiko membaca data lawas. |
| **Model Penyimpanan** | **CRUD In-Place Mutation** | **Event Sourcing (Append-Only)** | CRUD: Desain simpel, optimasi storage disk efisien, minim latensi baca. ES: Audit trail absolut, fleksibilitas proyeksi temporal, namun membutuhkan strategi snapshotting dan agregasi read model yang kompleks. |
| **Partisi Database** | **Range-Based Partitioning** | **Hash-Based Partitioning** | Range: Efisien untuk query pemindaian rentang (e.g., `WHERE timestamp BETWEEN`), rentan *write hotspot* pada partisi terakhir. Hash: Distribusi merata, namun *range scans* menjadi operasi mahal (*scatter-gather* ke semua shard). |
| **Protokol Konsensus**| **Raft** | **Multi-Paxos** | Raft: Implementasi tegas, *leader-driven*, visualisasi status deterministik. Paxos: Teoretis lebih fleksibel tanpa ketergantungan mutlak pada *strong leader*, namun tingkat kesulitan implementasi dan debugging sangat tinggi. |

---

## SEKSI 11 — BEST PRACTICES

1. **Jamin Idempotensi Consumer Read Model:** Dalam CQRS/ES, mekanisme distribusi pesan bersifat *at-least-once*. Buat seluruh event projector bersifat idempoten dengan menyimpan `last_processed_event_id` atau menggunakan *deduplication keys*.
2. **Terapkan Sharding Key Berkardinalitas Tinggi:** Hindari sharding keys seperti `CountryCode` atau `Status` yang memicu data skew. Gunakan kombinasi UUID terenkripsi atau *composite key* (e.g., `TenantId_EntityId`).
3. **Wajibkan Snapshots untuk Event Streams Panjang:** Jika sebuah aggregate memiliki lebih dari 100-200 event, komputasi hidrasi ulang menjadi *bottleneck* CPU/IO. Simpan snapshot setiap $N$ event, dan muat state dimulai dari `latest_snapshot + subsequent_events`.
4. **Hindari Cross-Shard Transactions:** Jangan merancang sistem yang membutuhkan transaksi ACID lintas shard. Gunakan strategi partisi yang menempatkan data terkait dalam satu shard (e.g., shard by `Customer_ID`).
5. **Konfigurasikan Quorum Secara Simetris:** Pada sistem konsensus, selalu gunakan jumlah node ganjil ($N = 2F + 1$, di mana $N=3$ mentolerir $F=1$ kegagalan; $N=5$ mentolerir $F=2$ kegagalan). Node genap ($N=4$) membutuhkan ukuran kuorum yang sama ($3$) dengan node $N=5$, tanpa meningkatkan toleransi kegagalan.
6. **Terapkan Transactional Outbox:** Jangan pernah menulis ke basis data lalu langsung memanggil API Message Broker secara serial. Gunakan *Transactional Outbox Pattern* dengan Debezium / CDC untuk menjamin integritas publikasi event atomik dengan mutasi data.
7. **Batasi Batasan Aggregate (Bounded Aggregates):** Jangan membuat aggregate raksasa yang menampung terlalu banyak entitas anak. Semakin besar cakupan aggregate, semakin tinggi probabilitas *Optimistic Concurrency Failure* di bawah beban konkurensi tinggi.
8. **Enkapsulasi Upcasting untuk Event Versioning:** Skema event tidak boleh diubah secara destruktif (*events are immutable*). Ketika skema berevolusi, implementasikan pola *Upcaster* untuk mentransformasi event versi 1 ke versi 2 saat dimuat dari disk ke memori.

---

## SEKSI 12 — KESALAHAN UMUM (COMMON MISTAKES)

1. **Dual-Write Anti-Pattern:** Menulis entitas ke PostgreSQL lalu secara manual menulis event ke Apache Kafka dalam satu blok kode aplikasi. Jika aplikasi crash di antara dua baris kode tersebut, sistem akan berada dalam kondisi inkonsistensi data permanen. Solusi: Gunakan CDC atau tabel outbox dalam transaksi DB yang sama.
2. **Menjadikan Event Sourcing Sebagai Generic Storage:** Menerapkan Event Sourcing untuk domain yang murni bersifat CRUD (seperti tabel referensi kota atau konfigurasi sistem). ES menambah kompleksitas struktural secara signifikan dan hanya boleh diterapkan pada inti domain yang memerlukan jejak audit, analisis historis, atau kalkulasi bisnis kompleks.
3. **Mengabaikan PACELC Latency Penalty:** Memilih mode *Strong Consistency* lintas datacenter antar benua untuk aplikasi pengguna akhir. Latensi *round-trip time* (RTT) jaringan optik global (misal Trans-Atlantik 70-100ms) akan langsung menurunkan throughput transaksi secara eksponensial.
4. **Mengubah Shard Key Tanpa Rencana Migrasi:** Mengabaikan kebutuhan resharding di masa depan. Mengubah shard key pada cluster petabyte yang sedang aktif membutuhkan strategi migrasi *dual-write*, replikasi bayangan, dan rekonsiliasi inkonsistensi yang sangat berisiko.
5. **Mengizinkan Read Model Memodifikasi State Domain:** Membiarkan Query Handler atau Read Database melayani logika mutasi state. Ini merusak prinsip dasar CQRS dan menciptakan ketergantungan siklis antarmodel.

---

## SEKSI 13 — LATIHAN HANDS-ON (EXERCISES)

### Latihan 1: Guided Implementation — Event Store Snapshot Engine
* **Tugas:** Tambahkan mekanisme `SnapshotStore` pada implementasi `InMemoryEventStore` di Seksi 09.
* **Instruksi:**
  1. Buat kelas `SnapshotStore` yang menyimpan data: `{ aggregateId, version, state }`.
  2. Modifikasi alur hidrasi `BankAccountAggregate.replay()` agar menerima parameter opsional `latestSnapshot`.
  3. Tulis fungsi simulasi yang menghasilkan 250 event deposit, lalu buat snapshot setiap 50 event.
  4. Buktikan melalui pengukuran waktu eksekusi bahwa hidrasi menggunakan snapshot + 5 event sisa secara signifikan lebih cepat dibanding me-replay keseluruhan 250 event dari index nol.

### Latihan 2: Intermediate Challenge — Resharding Simulation with Consistent Hashing
* **Tugas:** Buat skrip simulasi Consistent Hashing menggunakan modul dari Seksi 08 untuk menganalisis dampak penambahan kapasitas node.
* **Instruksi:**
  1. Masukkan 100.000 generated string keys ke dalam cincin hash dengan 4 node awal (`Node_1`, `Node_2`, `Node_3`, `Node_4`).
  2. Catat distribusi persentase key pada setiap node (analisis standar deviasi keseimbangan).
  3. Tambahkan `Node_5` ke dalam cincin.
  4. Hitung berapa banyak key yang berpindah lokasi dari alokasi awal. Verifikasi secara matematis apakah kunci yang berpindah mendekati nilai teoritis $1/(N+1) \approx 20\%$.

### Latihan 3: Advanced Scenario Architecture Challenge — Flash Sale Inventory Engine
* **Skenario:** Anda adalah Principal Architect di platform e-commerce skala internasional. Tim bisnis meluncurkan *Flash Sale* untuk item eksklusif dengan stok 500 unit, namun diperebutkan oleh 500.000 pengguna secara bersamaan dalam kurun waktu 3 detik.
* **Tugas:**
  1. Rancang arsitektur data lengkap menggunakan kombinasi CQRS, Event Sourcing, Redis Sharding, dan Consensus (Raft-based store).
  2. Tentukan di layer mana *Optimistic Locking* dan validasi stok dilakukan untuk mencegah overselling tanpa memicu *database connection pool exhaustion*.
  3. Gambarkan diagram arsitektur alur data dari penerimaan order hingga commit status kepemilikan barang.
  4. Jelaskan penanganan pembatalan pesanan (*timeout 15 menit*) terhadap inventaris menggunakan event projection.

---

## SEKSI 14 — QUIZ & SELF-ASSESSMENT

1. **Berdasarkan teorema PACELC, apa karakteristik arsitektur sistem MongoDB saat dikonfigurasi dengan `writeConcern: "majority"` dan `readPreference: "primary"`?**
   * A) PA/EL
   * B) PC/EC
   * C) PA/EC
   * D) PC/EL
   * *Jawaban yang Benar:* **B** — Ketika partisi terjadi, sistem membatasi penulisan jika quorum mayoritas tidak tercapai (Consistency over Availability). Ketika normal, membaca dan menulis ke primary menjamin konsistensi data dengan mengorbankan latensi routing langsung (Consistency over Latency).

2. **Dalam protokol konsensus Raft, bagaimana sistem mencegah terpilihnya dua Leader yang berbeda secara bersamaan (*split-brain*) pada partisi jaringan?**
   * A) Leader dipilih berdasarkan timestamp fisik NTP terendah.
   * B) Candidate wajib memperoleh suara dari mayoritas absolut ($N/2 + 1$) node cluster sebelum sah menjadi Leader.
   * C) Node Follower menolak semua Candidate yang memiliki log indeks lebih kecil dari dirinya tanpa mempedulikan term.
   * D) Node Candidate secara acak mematikan node pesaing melalui sinyal pembatalan TCP.
   * *Jawaban yang Benar:* **B** — Mayoritas ($N/2 + 1$) memastikan bahwa dua partisi terpisah tidak mungkin keduanya mencapai kuorum suara, karena irisan dari dua kuorum mayoritas pada himpunan $N$ selalu menghasilkan minimal satu node yang sama.

3. **Mengapa algoritma Consistent Hashing membutuhkan "Virtual Nodes" per instance fisik?**
   * A) Untuk menghindari benturan enkripsi TLS pada level soket.
   * B) Untuk memastikan transaksi terdistribusi ACID dapat dieksekusi secara atomik.
   * C) Untuk memitigasi variansi sebaran data yang tidak homogen (*data skew*) dan mencegah node fisik tertentu menjadi *hotspot*.
   * D) Untuk mereplikasi log Raft langsung ke memori kernel tanpa alokasi buffer pengguna.
   * *Jawaban yang Benar:* **C** — Penempatan node fisik murni dalam jumlah kecil pada ring hash sering kali menghasilkan jarak token yang tidak merata. Virtual nodes mendistribusikan ratusan representasi titik per mesin fisik sehingga probabilitas alokasi beban data merata secara statistik.

4. **Apa bahaya terbesar menggunakan Snapshot yang korup pada sistem Event Sourcing?**
   * A) Semua event historis pada Event Store otomatis terhapus permanen.
   * B) State aggregate yang dihidrasi akan merefleksikan nilai yang salah, dan mutasi data berikutnya akan melanggar *business domain invariants*.
   * C) Optimistic Concurrency Control akan selalu mengizinkan seluruh operasi penulisan tanpa validasi versi.
   * D) Jaringan broker Apache Kafka akan mengalami *infinite rebalancing loop*.
   * *Jawaban yang Benar:* **B** — Snapshot adalah optimasi kinerja yang menggantikan hidrasi event masa lalu. Jika snapshot tidak valid, entitas memulai evaluasi dari state yang salah, memicu keputusan logika bisnis yang keliru (misal: saldo minus diizinkan karena data snapshot saldo salah).

5. **Kapan Database Sharding berbasis Rentang (*Range-Based Sharding*) menjadi pilihan yang BURUK?**
   * A) Ketika aplikasi sering mengeksekusi query agregasi menggunakan rentang tanggal.
   * B) Ketika *shard key* yang digunakan adalah nilai yang naik secara monoton (*monotonically increasing*) seperti Timestamp atau Auto-Increment ID.
   * C) Ketika dataset berukuran lebih dari 100 Terabyte.
   * D) Ketika sistem menggunakan arsitektur Polyglot Persistence.
   * *Jawaban yang Benar:* **B** — Jika shard key bertambah secara monoton, seluruh operasi penulisan baru akan selalu dialokasikan ke satu partisi terakhir yang mencakup rentang nilai tertinggi saat itu, menyebabkan *write hotspot* parah sementara shard lain menganggur.

---

## SEKSI 15 — REFERENSI & SUMBER BELAJAR LANJUTAN

* **Buku Wajib:**
  * *Designing Data-Intensive Applications* oleh Martin Kleppmann (O'Reilly Media) — Bab 5, 6, 7, 8, dan 9.
  * *Patterns, Principles, and Practices of Domain-Driven Design* oleh Scott Millett & Nick Tune (Wrox) — CQRS and Event Sourcing patterns.
  * *Database Internals: A Deep Dive into How Distributed Data Systems Work* oleh Alex Petrov (O'Reilly Media).
* **Makalah Akademis Fundamental (Whitepapers):**
  * Ongaro, D., & Ousterhout, J. (2014). *In Search of an Understandable Consensus Algorithm (Raft)*. USENIX ATC.
  * Lamport, L. (1998). *The Part-Time Parliament (Paxos)*. ACM Transactions on Computer Systems.
  * DeCandia, G., et al. (2007). *Dynamo: Amazon’s Highly Available Key-value Store*. SOSP.
  * Corbett, J. C., et al. (2012). *Spanner: Google’s Globally-Distributed Database*. OSDI.
* **Standar & Spesifikasi Industri:**
  * *The Raft Consensus Algorithm Interactive Visualizer:* https://raft.github.io/
  * *CloudEvents Specification (CNCF):* Standar terbuka pertukaran deskripsi event lintas sistem.

---

## SEKSI 16 — RINGKASAN MODUL (SUMMARY)

1. **Hukum Fisika Sistem Terdistribusi:** Teorema CAP dan PACELC bukanlah opsi konfigurasi perangkat lunak, melainkan batas fundamental sistem komputasi terdistribusi. Latensi jaringan dan partisi fisik mewajibkan arsitek memilih secara sadar kompromi antara konsistensi data instan atau ketersediaan tinggi.
2. **Konsensus Menjamin Kebenaran:** Algoritma konsensus modern seperti Raft mengubah kompleksitas teoritis Paxos menjadi sub-komponen deterministik (*Leader Election*, *Log Replication*, *Safety*), menjadi pondasi mesin terdistribusi seperti etcd, Consul, dan CockroachDB.
3. **Sharding adalah Solusi Skalabilitas Horizontal:** Pembagian partisi data menuntut pemilihan *shard key* yang matang. Algoritma *Consistent Hashing* yang dilengkapi dengan *Virtual Nodes* memitigasi risiko ketimpangan data (*skew*) serta menjaga stabilitas topologi klaster saat node mengalami mutasi skala (*rescaling*).
4. **Event Sourcing Merevolusi State Storage:** Mengganti mutasi state destruktif dengan *append-only log* berbasis fakta domain (*events*) memberikan jejak audit mutlak, rekonstruksi temporal historis (*time-travel debugging*), dan menghilangkan *impedance mismatch* domain bisnis.
5. **CQRS dan Polyglot Persistence:** Memisahkan jalur Command dan Query membebaskan arsitektur dari ketergantungan pada satu jenis database. Komponen penulisan dapat dioptimasi untuk penegakan konsistensi dan integritas logika bisnis, sementara data pembacaan dapat diproyeksikan secara asinkron ke berbagai mesin penyimpanan khusus (pencarian, caching, analitik).

---

## SEKSI 17 — GLOSARIUM

* **Linearizability:** Model konsistensi data terkuat di mana setiap operasi pembacaan dijamin menerima nilai terbaru yang berhasil ditulis, seolah-olah hanya ada satu salinan data tunggal di seluruh alam semesta.
* **Split-Brain:** Anomali kegagalan jaringan di mana cluster terdistribusi terisolasi menjadi dua atau lebih sub-grup yang masing-masing mengira sub-grupnya adalah otoritas tunggal yang valid, berisiko menulis data yang saling bertentangan.
* **Quorum:** Jumlah minimum node anggota cluster terdistribusi yang wajib mencapai kesepakatan voting sebelum sebuah tindakan atau transaksi dinyatakan valid ($Q = \lfloor N/2 \rfloor + 1$).
* **Optimistic Concurrency Control (OCC):** Metode kontrol konkurensi tanpa locking fisik yang mengasumsikan konflik jarang terjadi; transaksi memvalidasi versi entitas sebelum commit dan membatalkan operasi jika versi telah berubah.
* **Idempotence:** Sifat operasi di mana eksekusi berulang kali dengan parameter input yang sama akan selalu menghasilkan output dan state akhir yang identik tanpa efek samping tambahan.
* **Change Data Capture (CDC):** Pola integrasi perangkat lunak yang memonitor, mendeteksi, dan menangkap perubahan level baris (insert, update, delete) pada file transaksi database (*WAL*) dan mengalirkannya sebagai stream pesan *real-time*.
* **Append-Only Log:** Struktur data urut yang hanya mengizinkan operasi penambahan entri baru di bagian akhir (*tail*); entri masa lalu bersifat permanen dan tidak dapat dimodifikasi maupun dihapus.
* **Virtual Nodes (Vnodes):** Titik replikasi logis pada consistent hash ring yang memetakan satu node fisik ke ratusan posisi hash cincin yang berbeda untuk meratakan distribusi alokasi data.

---

## SEKSI 18 — CATATAN INSTRUKTUR

* **Fokus Pedagogis Utama:** Pastikan peserta memahami bahwa Event Sourcing dan CQRS adalah dua pola terpisah yang saling melengkapi, bukan satu kesatuan tunggal. CQRS dapat diimplementasikan tanpa Event Sourcing (misal: RDBMS tables untuk write, ElasticSearch untuk read).
* **Titik Kritis Diskusi Kelas:** Tekankan bahaya *Eventual Consistency* pada antarmuka pengguna (UI/UX). Tantang siswa mencari solusi untuk skenario umum: "Pengguna mengklik Submit Order, halaman dialihkan ke Order Details, namun data pesanan belum muncul di database proyeksi read model." (Solusi: Pola *Read-Your-Own-Writes*, optimistik rendering di frontend, atau polling berbasis version ID).
* **Laboratorium Praktik:** Saat membahas Raft, disarankan membuka simulator visualisasi Raft online (seperti raft.github.io) di depan kelas untuk mendemonstrasikan secara visual apa yang terjadi saat Leader terisolasi di partisi minoritas dan bagaimana reconcilation terjadi saat jaringan tersambung kembali.
* **Mitigasi Miskonsepsi CAP:** Luruskan pemahaman umum yang keliru bahwa "Sistem dapat memilih CA (Consistency + Availability)". Pada sistem terdistribusi riil, kegagalan partisi jaringan (**P**) adalah keniscayaan fisik yang tidak bisa ditolak; oleh karena itu, pilihannya murni adalah **CP** atau **AP**.

---

## SEKSI 19 — CHANGELOG & VERSI

* **Versi:** 1.0.0
* **Tanggal Rilis:** 2025-01-15
* **Author:** Tim Kurikulum Arsitektur Perangkat Lunak
* **Perubahan Terakhir:**
  * Penulisan modul komprehensif 20 seksi arsitektur data terdistribusi.
  * Penambahan kode prototipe TypeScript industri untuk Event Sourcing Aggregate dengan OCC.
  * Penyusunan modul simulasi Consistent Hashing dengan Virtual Nodes dalam Python.
  * Integrasi diagram ASCII untuk mesin konsensus Raft, CQRS pipeline, dan Hash Ring Topology.

---

## SEKSI 20 — NAVIGASI KURIKULUM

* **Modul Sebelumnya:** `ARC-06-04-03` — Enterprise Integration Patterns, Event-Driven Architecture, & Asynchronous Messaging
* **Modul Saat Ini:** `ARC-06-05-01` — Distributed Data Architecture & Storage Strategies: Polyglot Persistence, Event Sourcing, CQRS, Database Sharding, Consensus Protocols (Raft/Paxos), CAP/PACELC
* **Modul Berikutnya:** `ARC-06-05-02` — Distributed Caching Architectures, Cache Coherence Protocols, & Resiliency Engineering Patterns (Circuit Breaker, Bulkhead, Outbox Pattern)