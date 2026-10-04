# Kurikulum Kurikuler Terstandarisasi: Rekayasa Sistem Blockchain & Protokol Terdesentralisasi

> **Tingkat Kurikulum:** *Production-Grade Enterprise Architecture (L4 - Principal Protocol Engineer)*  
> **Domain Spesialisasi:** *Distributed Systems, Applied Cryptography, Virtual Machine Internals, Zero-Knowledge Scaling, & Smart Contract Security Audit.*

---

## 1. Course Overview & Mindset

### Filosofi Pedagogis
Kurikulum ini dirancang untuk mendidik insinyur perangkat lunak bertransformasi menjadi **Core Protocol Engineer** dan **Smart Contract Security Architect**. Rekayasa blockchain bukan sekadar memanggil API Web3 atau menulis skrip token sederhana; blockchain adalah perpaduan ketat antara **sistem terdistribusi heterogen tanpa kepercayaan (*trustless distributed systems*)**, **primitif kriptografi modern**, **teori permainan (*game theory*)**, dan **verifikasi formal deterministik**.

### Mental Model & Core Primitives
Seorang insinyur protokol harus memandang blockchain sebagai:
$$\text{Blockchain} = f(\text{State}_{t}, \text{Transaction}) \rightarrow \text{State}_{t+1}$$
di mana fungsi transisi status dieksekusi secara deterministik pada ribuan node independen yang terkoordinasi oleh algoritma konsensus toleran terhadap kegagalan Bizantin (*Byzantine Fault Tolerant*), di bawah batasan komputasi terukur (*metered gas economics*).

```
+--------------------------------------------------------------------------+
|                       TUMPUKAN ARSITEKTUR BLOCKCHAIN                     |
+--------------------------------------------------------------------------+
| Layer 4: Aplikasi & Finansial (DeFi, AMM, Lending, Yield Aggregator)     |
+--------------------------------------------------------------------------+
| Layer 3: Penskalaan & Privasi (ZK-Rollups, Optimistic Rollups, Data Avail)|
+--------------------------------------------------------------------------+
| Layer 2: Mesin Eksekusi (EVM Opcodes, Gas Metering, State Storage Trie)  |
+--------------------------------------------------------------------------+
| Layer 1: Konsensus & Jaringan (PoS, PBFT, Nakamoto, libp2p, GossipSub)  |
+--------------------------------------------------------------------------+
| Layer 0: Primitif Kriptografis (ECDSA, BLS, Merkle Trees, ZK-SNARKs)      |
+--------------------------------------------------------------------------+
```

### Prasyarat Teknis (*Prerequisites*)
* **Bahasa Pemrograman Sistem:** Mahir dalam Rust, Go, atau C++ modern (alokasi memori manual, threading, sockets).
* **Matematika Diskrit & Kriptografi Dasar:** Pemahaman tentang aritmatika modular, medan berhingga (*finite fields*), hash resisten-tabrakan, dan tanda tangan digital.
* **Jaringan Komputer & Sistem Terdistribusi:** Pemahaman mendalam tentang TCP/UDP, model RPC, teorema CAP, replikasi status (*state machine replication*), dan konsistensi eventual.

### Tooling Stack Standar Industri
* **Protokol & Framework:** Foundry (`forge`, `cast`, `anvil`), Hardhat, Circom, SnarkJS, Rust (`solana-program`, `alloy`, `ethers-rs`).
* **Analisis & Audit Keamanan:** Slither, Mythril, Echidna, Medusa, Halmos, Certora Prover.
* **Infrastruktur & Klien:** Go-Ethereum (Geth), Reth, Lighthouse, Prysm, Prometheus, Grafana, Docker.

---

## 2. Learning Roadmap

```
Kurikulum Rekayasa Sistem Blockchain
│
├── [Bab 01] Fondasi Kriptografi & Sistem Terdistribusi
│   ├── [M-01] Primitif Kriptografi Asimetris & Struktur Hash Pohon
│   └── [M-02] Model Konsensus Terdistribusi & Toleransi Kerusakan Bizantin
│
├── [Bab 02] Arsitektur Node, Jaringan Peer-to-Peer, & Mempool
│   ├── [M-01] Protokol Jaringan P2P (libp2p, DevP2P, & Kademlia DHT)
│   └── [M-02] Manajemen Mempool, Replikasi Status, & Engine Penyimpanan
│
├── [Bab 03] Rekayasa Mekanisme Konsensus Modern
│   ├── [M-01] Nakamoto Consensus & Dinamika Proof-of-Work
│   └── [M-02] Modern Proof-of-Stake: Finalitas, Slashing, & Desain Insentif
│
├── [Bab 04] Arsitektur Eksekusi: EVM Deep Dive & Bytecode Engineering
│   ├── [M-01] Arsitektur Stack-Based EVM, Gas Mechanics, & Memory Model
│   └── [M-02] Disassembling Bytecode, Yul Intermediate Language, & Huff
│
├── [Bab 05] Rekayasa Smart Contract Enterprise & Optimasi Gas Ekstrem
│   ├── [M-01] Pola Arsitektur Lanjutan: Upgradeable Proxies & Diamond Standard
│   └── [M-02] Rekayasa Optimasi Gas Tingkat Rendah & Manipulasi Bitwise
│
├── [Bab 06] Keamanan Smart Contract, Fuzzing, & Formal Verification
│   ├── [M-01] Taksonomi Eksploitasi: Reentrancy, Oracle Flash Loan, & AMM Drain
│   └── [M-02] Invariant Testing Berbasis Properti (Echidna/Foundry) & Formal Proofs
│
├── [Bab 07] Penskalaan Layer 2 & Modular Data Availability
│   ├── [M-01] Fraud Proofs vs Validity Proofs: Rollup Internals
│   └── [M-02] Arsitektur Modular Data Availability & Danksharding
│
├── [Bab 08] Kriptografi Nol-Pengetahuan (Zero-Knowledge Proofs)
│   ├── [M-01] Fondasi Matematika ZK: Komitmen Polinomial & Protokol Plonk
│   └── [M-02] Implementasi Sirkuit Aritmatika Praktis dengan Circom & SnarkJS
│
├── [Bab 09] Desain Protokol DeFi & Interoperabilitas Cross-Chain
│   ├── [M-01] Matematika AMM Modern (Concentrated Liquidity) & Lending Pools
│   └── [M-02] Protokol Komunikasi Lintas-Rantai & Keamanan Oracle Terdesentralisasi
│
└── [Bab 10] Maximal Extractable Value (MEV), PBS, & Operasional Validator
    ├── [M-01] Anatomi Searcher MEV, Sandwiching, & Proposer-Builder Separation
    └── [M-02] Arsitektur Staking Institusional, HSM Key-Management, & Observabilitas
```

---

## 3. Navigasi Silabus Detail

### [Bab 01: Fondasi Kriptografi & Sistem Terdistribusi](./bab-01-fondasi-kriptografi-dan-sistem-terdistribusi/)
Membedah blok pembangun matematis dan fondasi sistem terdistribusi yang menjamin integritas data tanpa otoritas pusat.
* [Modul 01: Primitif Kriptografi Asimetris & Struktur Hash Pohon](./bab-01-fondasi-kriptografi-dan-sistem-terdistribusi/modul-01-kriptografi-asimetris-dan-merkle-trie.md)
  * *Materi:* SHA-256, Keccak-256, Kurva Eliptik (secp256k1, Ed25519), BLS multi-signatures, Merkle Tree, Sparse Merkle Tree, Patricia-Merkle Trie, dan Verkle Tree berbasis Vector Commitments.
  * *Target Output:* Implementasi mandiri Merkle-Patricia Trie dengan fitur verifikasi bukti inklusi/eksklusi (*inclusion/exclusion proofs*) dalam Go/Rust.
* [Modul 02: Model Konsensus Terdistribusi & Toleransi Kerusakan Bizantin](./bab-01-fondasi-kriptografi-dan-sistem-terdistribusi/modul-02-konsensus-terdistribusi-dan-pbft.md)
  * *Materi:* Teorema CAP, Batasan Impossibility FLP, State Machine Replication (SMR), Crash Fault-Tolerant (Raft/Paxos) vs Byzantine Fault-Tolerant (pBFT, Tendermint Core).
  * *Target Output:* Simulasi kluster konsensus 4-node pBFT lokal yang mampu mempertahankan konsistensi status saat satu node bertindak arbitrer/jahat.

---

### [Bab 02: Arsitektur Node, Jaringan Peer-to-Peer, & Mempool](./bab-02-arsitektur-node-p2p-dan-mempool/)
Menganalisis sistem level-rendah dari klien blockchain: penyebaran pesan p2p, pemrosesan transaksi pending, dan persistensi state lokal.
* [Modul 01: Protokol Jaringan P2P (libp2p, DevP2P, & Kademlia DHT)](./bab-02-arsitektur-node-p2p-dan-mempool/modul-01-protokol-p2p-dan-kademlia-dht.md)
  * *Materi:* Node discovery, Kademlia Distributed Hash Table (DHT), RLPx Wire Protocol, GossipSub messaging pattern, NAT traversal, dan mitigasi serangan Eclipse.
  * *Target Output:* Daemon P2P sederhana berbasis Rust yang melakukan *peer discovery* otomatis dan pertukaran *handshake* data blok terenkripsi.
* [Modul 02: Manajemen Mempool, Replikasi Status, & Engine Penyimpanan](./bab-02-arsitektur-node-p2p-dan-mempool/modul-02-mempool-dan-storage-engine.md)
  * *Materi:* Validasi transaksi non-committed, dynamic fee eviction policies, Log-Structured Merge-trees (LSM), optimasi RocksDB/MDBX pada Geth/Reth, serta mekanisme *state pruning*.
  * *Target Output:* Mempool engine berkinerja tinggi dengan kemampuan deteksi dependensi nonce transaksi secara asinkron.

---

### [Bab 03: Rekayasa Mekanisme Konsensus Modern](./bab-03-rekayasa-mekanisme-konsensus-modern/)
Memahami teori permainan insentif ekonomi dan arsitektur pengamanan jaringan terdistribusi melawan vektor serangan Sybil.
* [Modul 01: Nakamoto Consensus & Dinamika Proof-of-Work](./bab-03-rekayasa-mekanisme-konsensus-modern/modul-01-nakamoto-consensus-dan-pow.md)
  * *Materi:* Difficulty adjustment algorithms, longest-chain rule, self-correcting target retargeting, 51% attack dynamics, Selfish Mining vectors, dan analisis probabilitas reorg.
  * *Target Output:* Script simulator monte-carlo untuk memvalidasi batas profitabilitas *Selfish Mining* di bawah skenario latensi jaringan berbeda.
* [Modul 02: Modern Proof-of-Stake: Finalitas, Slashing, & Desain Insentif](./bab-03-rekayasa-mekanisme-konsensus-modern/modul-02-proof-of-stake-dan-slashing.md)
  * *Materi:* Casper FFG, LMD-GHOST fork-choice rule, attestation mechanisms, dynamic validators churn, inaktivitas penalti (*inactivity leak*), dan kondisi *slashing* matematis.
  * *Target Output:* Smart contract validator registrar yang mengkalkulasi reward, slashing proof validator untuk double-signing, dan auto-ejection logic.

---

### [Bab 04: Arsitektur Eksekusi: EVM Deep Dive & Bytecode Engineering](./bab-04-arsitektur-eksekusi-evm-deep-dive/)
Mendekonstruksi Ethereum Virtual Machine pada level byte: eksekusi instruksi, konsumsi gas per opcode, dan manajemen memori.
* [Modul 01: Arsitektur Stack-Based EVM, Gas Mechanics, & Memory Model](./bab-04-arsitektur-eksekusi-evm-deep-dive/modul-01-evm-internals-dan-memory-layout.md)
  * *Materi:* 256-bit word stack, memory expansion quadratic cost, storage slots slotting algorithm (SSTORE/SLOAD cold vs warm access via EIP-2929), calldata slicing, dan call frames (DELEGATECALL, STATICCALL).
  * *Target Output:* Visualizer eksekusi EVM manual yang men-trace mutasi stack, memory, dan storage per opcode run.
* [Modul 02: Disassembling Bytecode, Yul Intermediate Language, & Huff](./bab-04-arsitektur-eksekusi-evm-deep-dive/modul-02-yul-assembly-dan-huff.md)
  * *Materi:* Membaca raw bytecode, metadata hash decoding, penulisan algoritma dalam bahasa perantara Yul, serta pemanfaatan bahasa berbasis assembly Huff untuk determinisme absolut.
  * *Target Output:* Kontrak ERC-20 yang ditulis murni menggunakan Huff/Yul dengan efisiensi gas 40% lebih hemat dibanding kompilasi Solidity `solc -O3`.

---

### [Bab 05: Rekayasa Smart Contract Enterprise & Optimasi Gas Ekstrem](./bab-05-smart-contract-enterprise-dan-optimasi-gas/)
Merancang sistem multi-kontrak modular yang dapat di-upgrade (*upgradeable*), modular, serta dioptimalkan hingga batas teoritis EVM.
* [Modul 01: Pola Arsitektur Lanjutan: Upgradeable Proxies & Diamond Standard](./bab-05-smart-contract-enterprise-dan-optimasi-gas/modul-01-proxy-patterns-dan-diamond-standard.md)
  * *Materi:* Transparent Upgradeable Proxy (EIP-1967), UUPS pattern, Beacon proxies, Diamond Multi-Facet Proxy (ERC-2535), dan mitigasi tabrakan storage slot (*storage collision*).
  * *Target Output:* Arsitektur protokol Diamond (ERC-2535) modular lengkap dengan faceted loupe functions, ownership management, dan upgrade governance scripts.
* [Modul 02: Rekayasa Optimasi Gas Tingkat Rendah & Manipulasi Bitwise](./bab-05-smart-contract-enterprise-dan-optimasi-gas/modul-02-optimasi-gas-ekstrem-dan-bitwise.md)
  * *Materi:* Tight variable packing, transient storage (EIP-1153), dynamic memory reuse, bit-shifting techniques untuk boolean flags, custom errors parsing, dan kalkulasi unchecked arithmetic.
  * *Target Output:* Suite smart contract batch-processing multi-asset dengan konsumsi gas mendekati theoretical floor (<25k gas per settlement).

---

### [Bab 06: Keamanan Smart Contract, Fuzzing, & Formal Verification](./bab-06-keamanan-smart-contract-dan-formal-verification/)
Mengidentifikasi kegagalan logika kritis, eksploitasi nilai jutaan dolar, dan teknik jaminan kualitas kode berbasis bukti matematis.
* [Modul 01: Taksonomi Eksploitasi: Reentrancy, Oracle Flash Loan, & AMM Drain](./bab-06-keamanan-smart-contract-dan-formal-verification/modul-01-vektor-eksploitasi-dan-serangan-defi.md)
  * *Materi:* Cross-function reentrancy, read-only reentrancy, AMM spot-price manipulation, flash loan attack pipelines, governance proposals hijacking, dan signature replay (EIP-712).
  * *Target Output:* Repositori *Exploit Proof-of-Concept* (PoC) berbasis Foundry yang mereplikasi serangan riil hack Euler Finance dan Cream Finance.
* [Modul 02: Invariant Testing Berbasis Properti (Echidna/Foundry) & Formal Proofs](./bab-06-keamanan-smart-contract-dan-formal-verification/modul-02-property-based-fuzzing-dan-formal-verification.md)
  * *Materi:* State-machine property invariants, automated fuzz testing (Echidna/Medusa), symbolic execution (Halmos), dan spesifikasi formal berbasis Certora Verification Language (CVL).
  * *Target Output:* Test suite invariant lengkap untuk protokol lending kompleks yang membuktikan kondisi solvency selalu terpenuhi di bawah jutaan mutasi status acak.

---

### [Bab 07: Penskalaan Layer 2 & Modular Data Availability](./bab-07-penskalaan-layer-2-dan-modular-da/)
Membangun infrastruktur skalabilitas throughput tinggi di atas lapisan konsensus utama melalui teknik komputasi off-chain.
* [Modul 01: Fraud Proofs vs Validity Proofs: Rollup Internals](./bab-07-penskalaan-layer-2-dan-modular-da/modul-01-rollup-internals-optimistic-vs-zk.md)
  * *Materi:* Arsitektur Arbitrum Nitro (WASM based interactive fraud proofs), Optimism Bedrock, ZK-EVM type classification (Type-1 hingga Type-4), State derivation pipeline, dan Sequencer decentralization.
  * *Target Output:* Implementasi interactive bisection fraud-proof verification simulator dalam smart contract Solidity.
* [Modul 02: Arsitektur Modular Data Availability & Danksharding](./bab-07-penskalaan-layer-2-dan-modular-da/modul-02-modular-data-availability-dan-danksharding.md)
  * *Materi:* The Data Availability Problem, EIP-4844 Blob Transactions, KZG Polynomial Commitments, Erasure Coding (2D Reed-Solomon), Celestia architecture, dan EigenDA.
  * *Target Output:* Pipeline orkestrasi yang mengunggah payload batch transaksi ke blob space EIP-4844 dan membuktikan *availability commitments* di L1.

---

### [Bab 08: Kriptografi Nol-Pengetahuan (Zero-Knowledge Proofs)](./bab-08-kriptografi-nol-pengetahuan-zkp/)
Menguasai matematika sirkuit aritmatika ZK untuk menjaga privasi mutlak dan kompresi verifikasi status multi-transaksi.
* [Modul 01: Fondasi Matematika ZK: Komitmen Polinomial & Protokol Plonk](./bab-08-kriptografi-nol-pengetahuan-zkp/modul-01-matematika-zkp-dan-plonk.md)
  * *Materi:* QAP (Quadratic Arithmetic Programs), Arithmetization (R1CS), Pairing-friendly elliptic curves (BN254, BLS12-381), KZG Commitments, dan protokol argumentasi Plonk/Halo2.
  * *Target Output:* Komputasi sirkuit R1CS manual dari nol menggunakan aljabar matriks dan pembuktian evaluasi polinomial terenkripsi.
* [Modul 02: Implementasi Sirkuit Aritmatika Praktis dengan Circom & SnarkJS](./bab-08-kriptografi-nol-pengetahuan-zkp/modul-02-sirkuit-circom-dan-verifier-onchain.md)
  * *Materi:* Sintaks bahasa Circom, optimasi constraint limits, witness generation, trusted setup ceremonies (Powers of Tau), dan pembuatan On-chain Verifier contract Solidity.
  * *Target Output:* Sirkuit Circom untuk sistem *Private Whitelist / Nullifier Hash* yang diverifikasi langsung melalui smart contract di EVM dengan gas <250k.

---

### [Bab 09: Desain Protokol DeFi & Interoperabilitas Cross-Chain](./bab-09-desain-protokol-defi-dan-interoperabilitas/)
Arsitektur likuiditas terdesentralisasi, agregasi derivatif finansial tingkat lanjut, dan protokol perutean likuiditas lintas rantai.
* [Modul 01: Matematika AMM Modern (Concentrated Liquidity) & Lending Pools](./bab-09-desain-protokol-defi-dan-interoperabilitas/modul-01-amm-concentrated-liquidity-dan-lending-engine.md)
  * *Materi:* Invarian Uniswap v3 (Tick spacing, Virtual Reserves, Math $L = \frac{\Delta y}{\Delta \sqrt{P}}$), Compound/Aave interest rate models (kink utilization model), Collateralization Ratios, dan Bad Debt Socialization.
  * *Target Output:* Core engine AMM concentrated liquidity lengkap yang mengelola mutasi likuiditas dalam tick berbatas dengan akurasi presisi 128.128 fixed-point math.
* [Modul 02: Protokol Komunikasi Lintas-Rantai & Keamanan Oracle Terdesentralisasi](./bab-09-desain-protokol-defi-dan-interoperabilitas/modul-02-cross-chain-messaging-dan-oracles.md)
  * *Materi:* Wormhole Core Layer, LayerZero Ultra Light Nodes, Chainlink CCIP, Price Oracle Manipulation Defense (TWAP arrays, Chainlink heartbeat & deviation threshold checks).
  * *Target Output:* Sistem bridging multi-token berbasis lock-and-mint dengan mekanisme validasi bukti konsensus *Light Client* lintas jaringan EVM.

---

### [Bab 10: Maximal Extractable Value (MEV), PBS, & Operasional Validator](./bab-10-mev-pbs-dan-operasional-validator/)
Menganalisis ekonomi pasar gelap mempool, ekstraksi arbitrase kuantitatif, dan deployment validator node kelas tier-1 berstandar institusi.
* [Modul 01: Anatomi Searcher MEV, Sandwiching, & Proposer-Builder Separation](./bab-10-mev-pbs-dan-operasional-validator/modul-01-mev-searcher-dan-pbs.md)
  * *Materi:* Frontrunning, Backrunning, Sandwich Attacks, Flashbots relay architecture, MEV-Boost, Proposer-Builder Separation (PBS), dan SUAVE.
  * *Target Output:* Searcher bot backend dalam Rust yang mendeteksi peluang arbitrase deterministik via dynamic routing graphs pada pending mempool memori.
* [Modul 02: Arsitektur Staking Institusional, HSM Key-Management, & Observabilitas](./bab-10-mev-pbs-dan-operasional-validator/modul-02-infrastruktur-node-dan-observabilitas.md)
  * *Materi:* Deployment high-availability multi-client nodes (Geth + Reth / Lighthouse + Prysm), Distributed Validator Technology (SSV/Obol DVT), Remote Key Manager via Cloud HSM, telemetri Prometheus, dan Grafana incident response dashboards.
  * *Target Output:* Blueprints infrastruktur Terraform & Docker Compose untuk kluster validator bare-metal anti-slashing dengan sistem failover otomatis.

---

## 4. Panduan Implementasi Lab & Standar Teknis

Setiap modul direktori di atas memuat artefak praktikum teknis dengan standar mutu berikut:

```
[bab-XX-slug]/
├── [modul-YY-slug].md            # Teori komprehensif, arsitektur, math, diagram
└── labs/
    ├── src/                      # Source code (Solidity, Rust, Circom, Go)
    ├── test/                     # Unit test, invariant test, security fuzzing
    └── Makefile / Foundry.toml   # Script build deterministik
```

* **Standar Keamanan:** Seluruh smart contract wajib mengimplementasikan interface OpenZeppelin v5.x atau Solady, bebas dari kerentanan SWC (Smart Contract Weakness Classification), dan lolos linting `slither . --checklist`.
* **Standar Pengujian:** Cakupan pengujian unit test dan branch minimal **98%** berbasis Foundry, dilengkapi pengujian invarian (*fuzz runs* minimal 20,000 iterasi per skenario).
* **Standar Format:** Penulisan clean code, dokumentasi NatSpec lengkap (@notice, @dev, @param, @return), serta gas snapshots profil komparatif.

---

## 5. Enterprise Capstone Project Specification

### Judul Sistem
**"AegisCore: Institutional-Grade Hybrid Layer-2 Lending Protocol with ZK-Proof Solvency & MEV-Resistant Auction Settlement"**

### Ikhtisar Proyek
Membangun protokol finansial terdesentralisasi skala enterprise yang menggabungkan mesin peminjaman (*cross-margin lending engine*), rollup validitas berbasis zero-knowledge untuk penyelesaian likuidasi (*ZK-settlement*), perlindungan *MEV sandwich* via lelang batch order-book, dan integrasi modular data availability.

### Arsitektur Sistem

```
                                  [ INSTITUTIONAL CLIENT / TRADER ]
                                                 │
                                 (EIP-712 Meta-Transactions)
                                                 │
                                                 ▼
                             +───────────────────────────────────────+
                             |     OFF-CHAIN SEQUENCER / MATCHING    |
                             |       ENGINE (RUST / SUB-SECOND)      |
                             +───────────────────────────────────────+
                                   │                           │
                   (Batch Orders)  │                           │  (Liquidation Events)
                                   ▼                           ▼
                        +────────────────────+       +────────────────────+
                        |  CIRCOM / HALO2    |       | MODULAR DATA AVAIL |
                        | PROVER (ZK-STARK)  |       | (CELESTIA / BLOB)  |
                        +────────────────────+       +────────────────────+
                                   │                           │
                         (Validity Proof: ZK)          (DA Pointer)
                                   │                           │
                                   ▼                           ▼
            +─────────────────────────────────────────────────────────────────+
            |                  ETHEREUM MAINNET CORE ENGINE                   |
            |                                                                 |
            |  [ Diamond Proxy ERC-2535: Storage, Governance, Accounting ]   |
            |  [ ZK-Verifier Contract: Verify State Transition & Collateral ] |
            |  [ Liquidation Vault: Instant Repayment via Flash-Mint Proof ]  |
            +─────────────────────────────────────────────────────────────────+
```

### Kebutuhan Teknis Proyek

1. **Smart Contract Architecture (Foundry & Yul):**
   * Mengimplementasikan pola arsitektur **Diamond Standard (ERC-2535)** untuk memisahkan logika: *LendingFacet*, *CollateralFacet*, *LiquidationFacet*, dan *AccountFacet*.
   * Menggunakan representasi memori bit-packed untuk efisiensi data akun dan posisi margin peminjam.
   * Kompatibilitas EIP-1153 (Transient Storage) untuk perlindungan reentrancy mutlak dengan nol biaya gas pembersihan storage.

2. **Off-Chain Sequencer & Matching Engine (Rust):**
   * Mesin pencocokan batch order off-chain yang memproses pesanan terenkripsi pengguna untuk mencegah serangan frontrunning/sandwich MEV.
   * Ekspor jejak eksekusi (*execution trace*) ke format sirkuit aritmatika.

3. **Zero-Knowledge Solvency & Transition Verifier (Circom & SnarkJS / Halo2):**
   * Sirkuit ZK yang membuktikan:
     * Seluruh pengguna yang dilikuidasi memang berada di bawah rasio *Health Factor* $< 1.0$ tanpa membuka identitas pemegang posisi.
     * Neraca sistem secara keseluruhan (*Global Protocol Solvency*) memiliki cadangan lebih besar dibanding liabilitas token yang ditarik ($\sum Assets \ge \sum Liabilities$).
   * Kontrak verifier di-generate dan diverifikasi di dalam *Diamond Facet* on-chain L1.

4. **Integrasi Data Availability & Oracles:**
   * Publikasi ringkasan batch transaksi terkompresi ke Ethereum Blobs (EIP-4844) atau Celestia testnet.
   * Integrasi Oracle multi-feed gabungan (Chainlink Aggregator V3 + Uniswap v3 TWAP) dengan logika circuit breaker otomatis saat terjadi deviasi harga $>2\%$.

5. **Security, Audit, & Testing Suite:**
   * 100% Invariant test coverage menggunakan Foundry dan Echidna: membuktikan properti solvency invariant $\forall \text{ state } S, \text{ Collateral}(S) \ge \text{ Debt}(S) \times \text{MCR}$.
   * Analisis statis nir-warning via Slither (`--severity high,medium`).
   * Skrip eksploitasi serangan simulasi (Flash loan price attack) dan bukti bahwa sistem sukses bertahan (*fail-safe mitigation*).

### Rubrik Penilaian Capstone

| Parameter Evaluasi | Bobot | Kriteria Kelulusan Mutlak |
| :--- | :--- | :--- |
| **Kebenaran Arsitektur & Keamanan** | 35% | Nol kerentanan berstatus High/Critical dari audit tools; pass 100% invariant tests (>50,000 runs Foundry). |
| **Efisiensi EVM & Desain Gas** | 20% | Optimalisasi gas tingkat lanjut; tidak ada pemborosan slot SLOAD/SSTORE; memanfaatkan Transient Storage & bitwise ops. |
| **Implementasi Kriptografi ZK** | 20% | Sirkuit Circom bebas dari *unconstrained variable bugs*; verifier contract sukses tereksekusi deterministik di EVM. |
| **Kematangan Sistem Off-chain (Rust)** | 15% | Sequencer mampu menangani antrean transaksi mempool, concurrency race-condition handling, dan pembentukan batch aman. |
| **Kualitas Dokumentasi & CI/CD** | 10% | NatSpec 100%, diagram Mermaid arsitektur lengkap, automated GitHub Actions workflow untuk security linting & fuzzing. |

---

*Kurikulum ini dirawat secara aktif untuk mencerminkan dinamika standar protokol desentralisasi terkini. Mahasiswa diharapkan melakukan riset EIP (*Ethereum Improvement Proposals*) terbaru secara kontinu.*