# Module 02: Deep Dive, Implementasi Lanjutan & Arsitektur Produksi (MEV, PBS & Operasional Validator)

---

## 1. Learning Objective

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
1. **Merancang & Mengonfigurasi Arsitektur MEV-Boost Tingkat Lanjut:** Mengimplementasikan topologi validator multi-relay dengan failover otomatis, latensi sub-detik, dan mekanisme perlindungan terhadap *missed slots*.
2. **Menganalisis Siklus Hidup Engine API & Blinded Block:** Membedah interaksi RPC antara Consensus Client (CL), Execution Client (EL), MEV-Boost middleware, dan Relayer pada level payload byte-level.
3. **Mengembangkan Kontrak Pintar Arbitrase MEV Atomik:** Membangun *execution contract* berbasis Yul/Solidity yang tahan terhadap eksploitasi *sandwiching*, mengoptimalkan konsumsi gas, serta menyalurkan *bribe* secara deterministik via `block.coinbase`.
4. **Menerapkan Pipeline Searcher-to-Builder:** Membangun klien Rust asinkron untuk simulasi bundel transaksi privat, estimasi profitabilitas, dan transmisi bundel ke jaringan *builder* via endpoint JSON-RPC terautentikasi (Flashbots bundle format).
5. **Mitigasi Risiko Operasional Validator:** Menjalankan strategi deteksi latensi jaringan, validasi integritas *relay*, dan penanganan *payload delivery failure* untuk mengeliminasi penalti konsensus (*slashing* dan *inactivity leaks*).

---

## 2. Prerequisite

Sebelum mempelajari modul ini, peserta wajib memahami:
* **Konsensus Ethereum Proof-of-Stake:** Mekanisme *slots*, *epochs*, *attestations*, komite validator, dan siklus 12 detik block proposal.
* **Arsitektur Node Ethereum:** Pemisahan Execution Engine (Geth, Reth, Nethermind) dan Consensus Engine (Lighthouse, Prysm, Teku) serta komunikasi via Engine API (`engine_forkchoiceUpdated`, `engine_getPayload`).
* **Sistem Smart Contract Tingkat Lanjut:** Solidity (>= 0.8.20), inline assembly (Yul), pemahaman mendalam tentang *EVM storage layout*, *transient storage* (EIP-1153), dan transfer native token.
* **Pemrograman Sistem & Jaringan:** Rust tingkat menengah (asynchronous runtime dengan `tokio`, parsing data biner dengan `ethers-rs` / `alloy`), HTTP/JSON-RPC, serta Server-Sent Events (SSE).
* **Linux Networking & Systems Administration:** Analisis latensi kernel, konfigurasi NTP/PTP synchronization, serta profiling TCP/IP stack.

---

## 3. Concept & Internal Architecture (Mendalam)

### Proposer-Builder Separation (PBS) & Ekosistem MEV-Boost

Secara historis, validator (atau miner pada era PoW) memegang kendali penuh atas:
1. Pemilihan transaksi dari *public mempool*.
2. Pengurutan transaksi (*ordering*).
3. Penyusunan blok (*block execution*).
4. Usulan blok ke jaringan (*block proposal*).

Konsentrasi kekuatan ini menciptakan insentif sentralisasi ekstrem: entitas dengan kapasitas analitik MEV (*Maximal Extractable Value*) tinggi akan mendominasi *yield* konsensus, menyingkirkan validator independen (*solo stakers*). 

Arsitektur **Proposer-Builder Separation (PBS)** membagi tanggung jawab ini menjadi dua peran terpisah:
* **Block Builder:** Entitas terspesialisasi yang mengagregasikan transaksi dari mempool publik dan bundel privat dari *searcher*, menyimulasikan eksekusi, mengoptimalkan ekstraksi MEV, serta menyusun blok penuh (*execution payload*).
* **Block Proposer (Validator):** Entitas konsensus yang ditunjuk secara pseudorandom oleh algoritma RANDAO pada slot tertentu untuk mengusulkan blok. Validator tidak menyusun blok dari nol; mereka menerima *blinded block header* dari builder via *relay* dan memilih tawaran (*bid*) tertinggi.

Karena enkapsulasi PBS secara native di tingkat protokol (Enshrined PBS / ePBS) masih dalam tahap standarisasi konsensus, ekosistem Ethereum saat ini mengadopsi **MEV-Boost**: implementasi PBS *out-of-protocol* berbasis middleware terbuka yang diinisiasi oleh Flashbots.

```
+---------------------------------------------------------------------------------------+
|                                    SEARCHER DOMAIN                                    |
|  - DEX Arbitrageur      - Liquidator       - Sandwich Bot     - CEX-DEX Hedger        |
+---------------------------------------------------------------------------------------+
                                           |  (Bundles via RPC / Private Mempool)
                                           v
+---------------------------------------------------------------------------------------+
|                                     BUILDER DOMAIN                                    |
|  - Mengagregasi bundles + public txs                                                  |
|  - Mensimulasi eksekusi penuh (State transitions)                                     |
|  - Menentukan reward tertinggi untuk validator (Coinbase Transfer)                   |
|  - Mengirim ExecutionPayload + Bid ke Relay                                           |
+---------------------------------------------------------------------------------------+
                                           |  (Full Block Payload + Bid Value)
                                           v
+---------------------------------------------------------------------------------------+
|                                      RELAY DOMAIN                                     |
|  - Memverifikasi validitas eksekusi payload (Stateless/Stateful validation)           |
|  - Memverifikasi nilai bid pembayaran ke Proposer                                     |
|  - Mengirim ExecutionPayloadHeader (Blinded) ke MEV-Boost                             |
|  - Menahan (Escrow) data payload penuh hingga Proposer menandatangani header           |
+---------------------------------------------------------------------------------------+
                                           |  (Blinded Header via REST API)
                                           v
+---------------------------------------------------------------------------------------+
|                                    VALIDATOR DOMAIN                                   |
|                                                                                       |
|   +--------------------+       Engine API       +---------------------+               |
|   |  Execution Client  | <--------------------> |  Consensus Client   |               |
|   |  (Geth/Reth)       |                        |  (Lighthouse/Prysm) |               |
|   +--------------------+                        +----------+----------+               |
|                                                            |                          |
|                                                   Builder API (REST)                  |
|                                                            |                          |
|                                                 +----------v----------+               |
|                                                 |      MEV-Boost      |               |
|                                                 |     (Middleware)    |               |
|                                                 +---------------------+               |
+---------------------------------------------------------------------------------------+
```

### Mekanisme Komunikasi Engine API & Blind Auction

Alur kerja teknis pertukaran payload pada MEV-Boost berlangsung melalui siklus interaksi ketat:

1. **Inisialisasi Slot:** Consensus Client (CL) mendeteksi gilirannya untuk mengusulkan blok pada slot $N$.
2. **Panggilan Header:** CL mengirim permintaan HTTP `getHeader` ke MEV-Boost. MEV-Boost mem-fanning out permintaan ini ke seluruh relay yang terdaftar secara paralel.
3. **Penyaringan Bid:** Setiap relay mengembalikan `ExecutionPayloadHeader` beserta nilai bid (dalam Wei). MEV-Boost memvalidasi signature relay, memilih header dengan nilai bid tertinggi, dan mengembalikannya ke CL.
4. **Penandatanganan Konsensus (Blinded Block):** CL membungkus `ExecutionPayloadHeader` tersebut ke dalam `SignedBeaconBlock` (sehingga isinya tetap "buta" bagi validator), menandatanganinya dengan *validator private key*, dan mengirimkannya kembali ke MEV-Boost via `submitBlindedBlock`.
5. **Payload Unblinding:** MEV-Boost meneruskan blok yang telah ditandatangani ke relay yang memenangkan lelang. Relay memverifikasi integritas signature proposer.
6. **Rilis Payload:** Relay merilis `ExecutionPayload` penuh ke MEV-Boost, yang langsung meneruskannya ke CL.
7. **Injeksi Engine API:** CL mengirimkan payload lengkap tersebut ke Execution Client (EL) lokal via `engine_newPayloadV3`, memicu eksekusi state transition lokal, diikuti oleh `engine_forkchoiceUpdatedV3` untuk finalisasi fork-choice.

---

## 4. Why & What

### Mengapa PBS Dibutuhkan?

1. **Pencegahan Sentralisasi Validator:** Mengoperasikan algoritma pencarian MEV membutuhkan kluster server berkecepatan tinggi, konektivitas peering mempool privat, dan algoritma matematika yang kompleks. Jika validasi dipaketkan dengan ekstraksi MEV, validator individual tereliminasi oleh institusi besar yang memiliki kapabilitas *quant trading*.
2. **Eliminasi Negatif Eksternalitas Mempool (Priority Gas Auctions):** Sebelum adanya Flashbots dan PBS, bot MEV berkompetisi di mempool publik melalui *Priority Gas Auctions* (PGA). Hal ini memicu lonjakan gas fee bagi pengguna reguler dan membanjiri ruang blok (*blockspace bloat*) dengan transaksi yang gagal dieksekusi (*reverted transactions*).
3. **Pemisahan Risiko Operasional:** Validator tidak perlu mengeksekusi kode berbahaya atau menanggung risiko latensi komputasi dari simulasi ribuan kombinasi transaksi; validator cukup memverifikasi dan menandatangani komitmen lelang.

### Apa itu Bundel MEV (MEV Bundle)?

Bundel adalah struktur data yang berisi satu atau lebih transaksi yang harus dieksekusi secara:
* **Sekuensial:** Urutan transaksi di dalam bundel bersifat deterministik persis sesuai instruksi searcher.
* **Atomik:** Jika ada satu transaksi dalam bundel yang gagal (*revert*), seluruh bundel harus dibatalkan dan tidak boleh dimasukkan ke dalam blok.
* **Privat:** Bundel dikirimkan langsung ke builder melalui RPC privat, melewati mempool publik sehingga terhindar dari *front-running* oleh bot kompetitor.

---

## 5. How (Workflow Detail)

Siklus slot 12 detik pada Ethereum memiliki batas waktu (*deadlines*) yang sangat ketat untuk memastikan konsensus tidak terpecah:

```
T = 0s               T = 4s                         T = 8s                     T = 12s
|----------------------|------------------------------|--------------------------|
| Block Proposal Phase | Attestation Aggregation Phase| Finalization & Next Prep |
|                      |                              |                          |
|<--- MEV Auction ---->|                              |                          |
|     Deadline         |                              |                          |
```

### Rincian Eksekusi Sub-Detik

* **T = -1000ms s/d T = 0ms:** 
  * Searcher mengevaluasi perubahan state dari slot sebelumnya, membuat bundel transaksi, dan mengirimkannya ke builder.
  * Builder terus menyusun kombinasi blok paling optimal (*block bin-packing*).
* **T = +0ms (Awal Slot):**
  * CL validator memulai permintaan `getHeader` ke MEV-Boost.
* **T = +0ms s/d T = +300ms:**
  * MEV-Boost mengumpulkan respons bid dari semua relayer terdaftar.
  * Timeout default MEV-Boost diatur antara 400ms hingga 950ms untuk mengantisipasi relay yang lambat.
* **T = +300ms s/d T = +500ms:**
  * MEV-Boost memilih bid bernilai tertinggi.
  * Jika MEV-Boost gagal merespons dalam window timeout atau jika nilai bid eksternal lebih rendah dari blok lokal yang dibangun oleh EL lokal, CL beralih (*fallback*) ke EL lokal via `engine_getPayload`.
* **T = +500ms s/d T = +1000ms:**
  * CL menandatangani blinded header.
  * Panggilan `submitBlindedBlock` dikirimkan ke relay pemenang.
  * Relay memvalidasi signature, memublikasikan payload ke jaringan p2p eksekusi, dan mengembalikan payload penuh ke CL validator.
* **T = +1000ms s/d T = +2000ms:**
  * CL memublikasikan `SignedBeaconBlock` ke jaringan libp2p Consensus Layer.
* **T = +4000ms (Attestation Cutoff):**
  * Komite validator pengesah (*attestation committee*) untuk slot tersebut harus sudah menerima blok. Jika blok tiba setelah T = 4s, validator attestation akan memilih *voting for parent block*, menyebabkan blok ter-reorganisasi (*orphaned/reorged*).

---

## 6. Analogy & Diagram ASCII

### Analogi Sistem PBS: Lelang Kontrak Konstruksi Tertutup

Bayangkan sebuah kota metropolitan yang memerlukan pembangunan gedung pencakar langit (Satu Blok Data):
* **Proposer (Walikota):** Memiliki hak legal tunggal untuk menyetujui cetak biru mana yang akan dibangun pada jam ini. Namun, sang walikota tidak memiliki keahlian arsitektur maupun alat berat (komputasi eksekusi).
* **Searcher (Sub-kontraktor Spesialis):** Para tukang pipa, teknisi listrik, dan desainer interior yang menemukan celah efisiensi material (arbitrase harga semen di pasar A vs pasar B). Mereka menyusun modul instalasi mereka sendiri dalam kontainer tertutup (Bundel).
* **Builder (Kontraktor Utama):** Mengumpulkan modul-modul dari berbagai sub-kontraktor, mengintegrasikannya dengan proyek umum masyarakat (mempool), dan merancang cetak biru gedung utuh yang menghasilkan laba paling optimal.
* **Relay (Notaris Independen Terakreditasi):** Kontraktor menyerahkan cetak biru utuh ke notaris. Notaris mengunci cetak biru tersebut, lalu hanya memperlihatkan amplop bersegel berisi nilai dividen tunai (Bid Header) kepada Walikota. Notaris menjamin: jika Walikota menandatangani amplop, kontraktor wajib membayar tunai, dan cetak biru dipastikan aman dari pelanggaran hukum konstruksi.
* **MEV-Boost (Asisten Pribadi Walikota):** Mengumpulkan amplop dari belasan notaris di seluruh dunia dalam waktu 500 milidetik, memilih amplop dengan isi uang tertinggi, dan meletakkannya di meja kerja walikota.

### Diagram Arsitektur Jaringan Produksi

```
[ Searchers Pool ]
   |         |
   | (JSON-RPC Bundles)
   v         v
+-----------------------+          +-----------------------+
|  Block Builder Alpha  |          |   Block Builder Beta  |
+-----------------------+          +-----------------------+
            \                                 /
             \ (Full Payloads + Bids)        /
              v                             v
     +-----------------------------------------------+
     |              MEV RELAYS TIER                  |
     |  +----------------+      +-----------------+  |
     |  | Flashbots Relay|      |  BloXroute Max  |  |
     |  +----------------+      +-----------------+  |
     |  | Ultra Sound    |      |  Agnostic Relay |  |
     |  +----------------+      +-----------------+  |
     +-----------------------------------------------+
                            |
                            | (HTTP REST: Bid Headers / Blind Payloads)
                            v
     +-----------------------------------------------+
     |               VALIDATOR HOST                  |
     |                                               |
     |              +-----------------+              |
     |              |    MEV-Boost    |              |
     |              |  (Reverse Proxy)|              |
     |              +--------+--------+              |
     |                       ^                       |
     |                       | Engine API            |
     |                       v                       |
     |              +-----------------+              |
     |              | Consensus Client|              |
     |              |  (Lighthouse)   |              |
     |              +--------+--------+              |
     |                       ^                       |
     |                       | Auth Engine API:8551  |
     |                       | (JWT Secret Protected)|
     |                       v                       |
     |              +-----------------+              |
     |              | Execution Client|              |
     |              |  (Reth Engine)  |              |
     |              +-----------------+              |
     +-----------------------------------------------+
```

---

## 7. Simple Example & Practical Example

### Simple Example: Kontrak Arbitrase Flash Loan Atomik (Solidity)

Kontrak ini menerima dana dari flash swap, mengeksekusi arbitrase antar-DEX (Uniswap v2 vs Sushiswap), memvalidasi net-profit, dan mentransfer sebagian profit langsung ke validator penambang (`block.coinbase`) sebagai insentif inklusi blok prioritas.

```solidity
// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

interface IERC20 {
    function transfer(address recipient, uint256 amount) external returns (bool);
    function balanceOf(address account) external view returns (uint256);
}

interface IUniswapV2Pair {
    function swap(uint amount0Out, uint amount1Out, address to, bytes calldata data) external;
}

/**
 * @title AtomicMEVExecutor
 * @notice Menjalankan arbitrase atomik dan membayar suap langsung ke penambang/validator
 */
contract AtomicMEVExecutor {
    address public immutable owner;

    error Unauthorized();
    error UnprofitableExecution(uint256 balanceAfter, uint256 requiredBalance);
    error BribeFailed();

    modifier onlyOwner() {
        if (msg.sender != owner) revert Unauthorized();
        _;
    }

    constructor() {
        owner = msg.sender;
    }

    receive() external payable {}

    /**
     * @notice Menjalankan siklus eksekusi arbitrase
     * @param targetPoolA Pool sumber likuiditas murah
     * @param targetPoolB Pool tujuan likuiditas mahal
     * @param amount0Out Nilai token 0 yang dipinjam dari pool A
     * @param amount1Out Nilai token 1 yang dipinjam dari pool A
     * @param bribeAmount Nilai suap (Wei) yang akan dikirim ke block.coinbase
     */
    function executeArbitrage(
        address targetPoolA,
        address targetPoolB,
        uint256 amount0Out,
        uint256 amount1Out,
        uint256 bribeAmount
    ) external payable onlyOwner {
        uint256 balanceBefore = address(this).balance;

        // 1. Eksekusi swap pada Pool A
        IUniswapV2Pair(targetPoolA).swap(
            amount0Out,
            amount1Out,
            targetPoolB,
            new bytes(0)
        );

        // 2. Logika validasi profitabilitas internal (disederhanakan untuk demonstrasi)
        // Memastikan balance pasca arbitrase mencukupi untuk membayar bribe + net profit
        if (address(this).balance < balanceBefore + bribeAmount) {
            revert UnprofitableExecution(address(this).balance, balanceBefore + bribeAmount);
        }

        // 3. Mentransfer bribe ke coinbase (Validator yang mengusulkan blok)
        if (bribeAmount > 0) {
            (bool success, ) = block.coinbase.call{value: bribeAmount}("");
            if (!success) revert BribeFailed();
        }
    }

    function withdrawAsset(address token) external onlyOwner {
        if (token == address(0)) {
            payable(owner).transfer(address(this).balance);
        } else {
            uint256 bal = IERC20(token).balanceOf(address(this));
            IERC20(token).transfer(owner, bal);
        }
    }
}
```

### Practical Example: Rust MEV Searcher Bundle Submitter

Aplikasi Rust berikut membaca pool mempool internal, membangun bundel berformat Flashbots v2, menandatangani payload dengan *Searcher Identity Key*, dan mengirimkannya ke endpoint Builder Relay.

```rust
use reqwest::header::{HeaderMap, HeaderValue, CONTENT_TYPE};
use serde::{Deserialize, Serialize};
use serde_json::json;
use std::error::Error;
use std::time::{SystemTime, UNIX_EPOCH};

#[derive(Serialize, Deserialize, Debug)]
pub struct FlashbotsBundleRequest {
    pub jsonrpc: String,
    pub id: u64,
    pub method: String,
    pub params: Vec<BundleParam>,
}

#[derive(Serialize, Deserialize, Debug)]
pub struct BundleParam {
    #[serde(rename = "txs")]
    pub txs: Vec<String>, // Hex-encoded raw signed transactions
    #[serde(rename = "blockNumber")]
    pub block_number: String, // Target block in hex: e.g. "0x1174ef"
    #[serde(rename = "minTimestamp", skip_serializing_if = "Option::is_none")]
    pub min_timestamp: Option<u64>,
    #[serde(rename = "maxTimestamp", skip_serializing_if = "Option::is_none")]
    pub max_timestamp: Option<u64>,
}

pub struct FlashbotsClient {
    client: reqwest::Client,
    relay_endpoint: String,
    searcher_private_key: String, // Digunakan untuk header X-Flashbots-Signature
}

impl FlashbotsClient {
    pub fn new(relay_endpoint: String, searcher_private_key: String) -> Self {
        Self {
            client: reqwest::Client::new(),
            relay_endpoint,
            searcher_private_key,
        }
    }

    /// Menghitung tanda tangan X-Flashbots-Signature untuk autentikasi reputasi searcher
    fn sign_payload(&self, payload: &str) -> Result<String, Box<dyn Error>> {
        use ethers::core::k256::ecdsa::SigningKey;
        use ethers::prelude::*;
        
        let wallet = self.searcher_private_key.parse::<LocalWallet>()?;
        let message_hash = ethers::utils::hash_message(ethers::utils::keccak256(payload.as_bytes()));
        let signature = wallet.sign_hash(message_hash)?;
        
        Ok(format!("{:?}:0x{}", wallet.address(), signature))
    }

    pub async fn send_bundle(
        &self,
        signed_txs: Vec<String>,
        target_block: u64,
    ) -> Result<String, Box<dyn Error>> {
        let bundle_param = BundleParam {
            txs: signed_txs,
            block_number: format!("0x{:x}", target_block),
            min_timestamp: None,
            max_timestamp: None,
        };

        let rpc_payload = json!({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "eth_sendBundle",
            "params": [bundle_param]
        });

        let body_str = serde_json::to_string(&rpc_payload)?;
        let signature = self.sign_payload(&body_str)?;

        let mut headers = HeaderMap::new();
        headers.insert(CONTENT_TYPE, HeaderValue::from_static("application/json"));
        headers.insert(
            "X-Flashbots-Signature",
            HeaderValue::from_str(&signature)?,
        );

        let response = self
            .client
            .post(&self.relay_endpoint)
            .headers(headers)
            .body(body_str)
            .send()
            .await?;

        let response_text = response.text().await?;
        Ok(response_text)
    }
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn Error>> {
    let relay_url = "https://relay.flashbots.net".to_string();
    // Ganti dengan private key pengenal searcher (bukan penampung aset finansial)
    let searcher_reputation_key = 
        "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80".to_string();

    let client = FlashbotsClient::new(relay_url, searcher_reputation_key);

    // Contoh payload raw transaksi yang telah ditandatangani
    let raw_signed_tx = vec![
        "0x02f873018202d0843b9aca008504a817c800825208940000000000000000000000000000000000000000880de0b6b3a764000080c0".to_string()
    ];

    let target_block_number = 19850123;
    println!("Mengirimkan bundel ke Flashbots Relay untuk target blok {}", target_block_number);

    match client.send_bundle(raw_signed_tx, target_block_number).await {
        Ok(res) => println!("Response dari Builder: {}", res),
        Err(e) => eprintln!("Gagal mengirimkan bundel: {}", e),
    }

    Ok(())
}
```

---

## 8. Real World Case Study (Enterprise Scale)

### Infrastruktur Validator Skala Enterprise: 50.000 Validator Tanpa Missed Proposals

Sebuah penyedia layanan *Liquid Staking* institusional mengelola lebih dari 50.000 validator Ethereum yang tersebar di region AWS eu-central-1, us-east-1, dan ap-southeast-1. 

#### Tantangan Produksi:
1. **Missed Slots Akibat Timeout MEV-Boost:** Relay eksternal mengalami *spike* latensi jaringan (RTT > 1200ms) di region Eropa, mengakibatkan validator telat menerima unblinded payload sehingga blok di-reorg oleh jaringan konsensus. Kerugian: Hilangnya nilai proposal blok (~2.5 ETH per insiden).
2. **Risiko Sensor & Kepatuhan:** Regulasi OFAC mengharuskan sebagian cluster mematuhi pemfilteran transaksi, namun institusi ingin memaksimalkan imbal hasil secara non-diskriminatif tanpa melanggar yurisdiksi.
3. **Equivocation / Slashing:** Jika MEV-Boost mengalami *split-brain* dan menandatangani dua header dari dua relay berbeda untuk satu slot yang sama, validator akan di-slash dan di-eject dari jaringan konsensus.

#### Arsitektur Solusi Terapan:
1. **Relay Multiplexing Berjenjang:**
   * Node MEV-Boost dikonfigurasi menghubungkan validator ke 7 relayer independen (Flashbots, Ultra Sound, BloXroute Max Profit, BloXroute Regulated, Agnostic, Eden, dan Aestus).
2. **Circuit Breaker & Fallback Deterministic:**
   * Parameter `-request-timeout 800ms` diterapkan secara ketat.
   * Parameter `-min-bid 0.05 ether` diberlakukan. Jika seluruh relay memberikan bid di bawah 0.05 ETH, validator secara instan menolak eksternal builder dan beralih ke pembuatan blok lokal pada Execution Client (Reth) sendiri via local Engine API. Ini menjamin inklusi transaksi mempool internal dan meniadakan latensi lelang pihak ketiga jika margin tipis.
3. **Penyebaran Geografis dengan Reverse Proxy Anycast:**
   * Di setiap datacenter fisik, instans MEV-Boost dideploy sebagai *daemon* lokal pada loopback interface (`127.0.0.1:18550`) yang sama dengan Consensus Client, memangkas latensi overhead network TCP socket lokal ke tingkat < 1 milidetik.
4. **Hasil Operasional:**
   * Nilai *Missed Slot Rate* terpangkas dari 1.8% menjadi 0.02%.
   * Tambahan *Staking APR* meningkat sebesar +1.42% secara agregat berkat ekstraksi lelang multi-relay yang kompetitif.

---

## 9. Trade-offs

Perancangan infrastruktur MEV dan pemilihan dependensi melibatkan kompromi fundamental:

| Parameter Arsitektural | Opsi A: Agresif (Full External Multi-Relay) | Opsi B: Konservatif (Local Block Construction Only) | Opsi C: Hybrid (MEV-Boost dengan High Min-Bid Fallback) |
| :--- | :--- | :--- | :--- |
| **Potensi Pendapatan (Yield)** | **Maksimal.** Menangkap ekstraksi MEV global dari ribuan searcher. | **Minimal.** Hanya mengandalkan tip prioritas dari mempool publik lokal. | **Optimal.** Menangkap lonjakan MEV besar sembari membatasi risiko latensi pada blok bernilai rendah. |
| **Latensi Block Proposal** | **Tinggi (300ms - 900ms).** Tergantung RTT round-trip relay escrow. | **Sangat Rendah (< 50ms).** Payload langsung ditarik dari IPC/RPC socket engine lokal. | **Terkendali.** Jika relay tidak merespons dalam 600ms, langsung potong ke mesin lokal. |
| **Resiko Reorg / Missed Slot** | **Signifikan.** Ketergantungan penuh pada availability dan integritas relay pihak ketiga. | **Nol / Sangat Rendah.** Dependensi zero-third-party. | **Rendah.** Diproteksi oleh parameter *failover timeout*. |
| **Kompleksitas Infrastruktur** | **Tinggi.** Manajemen relay monitoring, pembaruan sertifikat, filter OFAC. | **Sangat Sederhana.** Hanya EL + CL. | **Menengah-Tinggi.** Memerlukan tuning metrik observabilitas secara berkelanjutan. |
| **Asumsi Kepercayaan (Trust)** | Membutuhkan kepercayaan bahwa Relay tidak menyembunyikan payload (*griefing*). | *Trustless* sepenuhnya. | Membutuhkan kurasi ketat terhadap daftar relay tepercaya. |

---

## 10. Common Mistakes & Troubleshooting

### Kesalahan Konfigurasi Umum

1. **Konfigurasi Timeout MEV-Boost Terlalu Longgar:**
   * *Problem:* Mengatur timeout relay hingga `> 2500ms`.
   * *Impact:* Proposer terlambat menyiarkan blok ke jaringan p2p. Pada T = 4s, komite attestation belum menerima blok, menyebabkan blok di-vote off (reorged), kehilangan reward konsensus dan reward MEV sekaligus.
2. **Ketiadaan Local Fallback Engine:**
   * *Problem:* Mematikan opsi fallback pada CL saat MEV-Boost tidak dapat dihubungi.
   * *Impact:* Jika service MEV-boost crash, validator melewatkan proposal blok (*0 proposed blocks*), membuang jatah slot sepenuhnya.
3. **Penggunaan Single Relay Berstatus Tersentralisasi:**
   * *Problem:* Hanya mendaftarkan 1 relay tanpa redundansi.
   * *Impact:* Titik kegagalan tunggal (*single point of failure*). Jika relay mengalami downtime atau filtering, validator terdampak secara langsung.

### Matriks Troubleshooting Lapangan

| Gejala Kerusakan | Root Cause (Akar Masalah) | Prosedur Investigasi | Langkah Remediasi |
| :--- | :--- | :--- | :--- |
| Log CL: `Could not get header from builder: 504 Gateway Timeout` | Koneksi antara MEV-Boost dan Relayer mengalami degradasi TCP atau relay kelebihan beban komputasi. | Jalankan `curl -I -m 1 https://<relay-url>/eth/v1/builder/status` dari terminal node validator. Analisis latensi respons via `traceroute`. | Sesuaikan flag `-request-timeout` pada MEV-Boost ke `900ms`. Hapus relay yang tidak responsif dari konfigurasi active. |
| Log EL: `engine_newPayloadV3: Payload contains invalid transactions` | Relay meloloskan blok yang tidak valid secara state execution (cacat builder). | Periksa log relay bersangkutan. Cek apakah ada insiden konsensus atau fork minor. | Nonaktifkan relay tersebut segera. Laporkan pelanggaran ke registry komunitas; beralih ke builder yang memverifikasi blok secara stateless (misal: via Reth/Geth tracer). |
| Profit MEV yang masuk ke `feeRecipient` bernilai 0 padahal lelang berhasil | Builder membayar suap langsung via transaksi internal transfer ke `block.coinbase`, bukan via gas tip standar. | Analisis transaksi terakhir pada blok tersebut menggunakan internal call tracer (Tenderly / Phalcon). | Verifikasi address `feeRecipient` pada CL sudah sesuai. Builder legitimate membayar via coinbase transfer langsung di akhir blok. |

---

## 11. Best Practices (Production Checklist)

### Security & Operational Checklist

- [ ] **MEV-Boost Localhost Binding:** Pastikan MEV-Boost hanya mendengarkan loopback interface (`127.0.0.1:18550` atau unix socket), jangan pernah mengekspos port MEV-Boost ke public internet tanpa mTLS.
- [ ] **Diversifikasi Relay (Minimal 4 Relay):** Konfigurasikan kombinasi relay non-censoring dan high-reliability:
  - Ultra Sound Relay
  - Agnostic Relay
  - Flashbots Relay
  - BloXroute Max Profit
- [ ] **Tuning Parameter Timeout Konsensus:**
  - Tetapkan flag MEV-Boost: `-request-timeout 800` (milidetik).
  - Tetapkan flag CL: `--builder-fallback-limit 3` (maksimal 3 percobaan fallback).
- [ ] **Circuit Breaker Minimum Bid (`-min-bid`):**
  - Pasang ambang batas rasional (contoh: `0.02 ETH` s/d `0.05 ETH`). Transaksi di bawah nilai ini lebih aman diproses via local block execution engine demi mereduksi latensi.
- [ ] **Sinkronisasi Waktu Ultra-Presisi (Chrony/PTP):**
  - Pastikan drift clock mesin validator di bawah 10 milidetik menggunakan Network Time Protocol (NTP) tersinkronisasi via AWS Time Sync Service atau Cloudflare NTP (`time.cloudflare.com`).
- [ ] **Monitoring & Alerting Aktif:**
  - Setup Prometheus alerts untuk metrik:
    - `mev_boost_relay_response_time_ms{quantile="0.95"} > 700`
    - `validator_missed_proposals_total > 0`
    - `mev_boost_status{code!="200"}`

---

## 12. Hands-on Practice

Dalam latihan ini, Anda akan menyiapkan lingkungan simulasi PBS lokal yang terdiri dari mock MEV-Boost relay, mengeksekusi kontrak arbitrase dengan verifikasi *coinbase transfer*, dan menyimulasikan transaksi bundel.

Simpan seluruh file pada path: `hands-on/m02/`

### File Setup 1: Kontrak Arbitrase (`hands-on/m02/FlashArb.sol`)

```solidity
// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

contract FlashArb {
    address payable public immutable owner;

    event ArbitrageExecuted(uint256 profit, uint256 bribe);

    modifier onlyOwner() {
        require(msg.sender == owner, "NOT_OWNER");
        _;
    }

    constructor() payable {
        owner = payable(msg.sender);
    }

    receive() external payable {}

    function triggerArb(uint256 minExpectedBalance, uint256 bribeAmount) external onlyOwner {
        // Simulasi kalkulasi keuntungan transaksi arbitrase
        uint256 currentBalance = address(this).balance;
        require(currentBalance >= minExpectedBalance, "INSUFFICIENT_PROFIT");

        if (bribeAmount > 0) {
            require(currentBalance >= bribeAmount, "CANT_COVER_BRIBE");
            (bool sent, ) = block.coinbase.call{value: bribeAmount}("");
            require(sent, "BRIBE_PAYMENT_FAILED");
        }

        emit ArbitrageExecuted(currentBalance - bribeAmount, bribeAmount);
    }
}
```

### File Setup 2: Test Suite Eksekusi Arbitrase via Foundry (`hands-on/m02/FlashArb.t.sol`)

```solidity
// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import "forge-std/Test.sol";
import "./FlashArb.sol";

contract FlashArbTest is Test {
    FlashArb public arb;
    address payable public mockCoinbase = payable(address(0x1337));

    function setUp() public {
        arb = new FlashArb{value: 10 ether}();
        vm.deal(mockCoinbase, 0);
    }

    function testExecutionWithCoinbaseBribe() public {
        uint256 initialArbBalance = address(arb).balance;
        uint256 bribe = 1 ether;

        // Set simulated block.coinbase
        vm.coinbase(mockCoinbase);

        // Eksekusi transaksi arbitrase oleh owner
        arb.triggerArb(5 ether, bribe);

        // Assert: Pastikan balance validator (coinbase) bertambah sesuai bribe
        assertEq(mockCoinbase.balance, bribe);
        // Assert: Pastikan balance kontrak berkurang sebesar nilai bribe
        assertEq(address(arb).balance, initialArbBalance - bribe);
    }

    function testRevertOnFailedProfit() public {
        vm.coinbase(mockCoinbase);
        // Ekspektasi revert karena minimum balance melebihi ketersediaan dana
        vm.expectRevert("INSUFFICIENT_PROFIT");
        arb.triggerArb(20 ether, 1 ether);
    }
}
```

### File Setup 3: Skrip Pengujian Simulasi Bundel (`hands-on/m02/simulate_bundle.sh`)

```bash
#!/usr/bin/env bash
set -euo pipefail

echo "=== Menjalankan Verifikasi Kompilasi & Simulasi MEV ==="

# 1. Pastikan foundry terpasang
if ! command -v forge &> /dev/null; then
    echo "Foundry tidak terdeteksi. Silakan install via https://getfoundry.sh"
    exit 1
fi

# 2. Inisialisasi testing
forge test --match-contract FlashArbTest -vvvv

echo "=== Simulasi Bundel Berhasil Memenuhi Kondisi Konsensus ==="
```

---

## 13. Exercise

### Level Easy
Tuliskan skrip Node.js/TypeScript sederhana menggunakan `@flashbots/ethers-provider-bundle` untuk membaca nomor blok Ethereum terkini, menambahkan 1 blok ke depan sebagai target proposal, dan melakukan ping *status endpoint* pada Flashbots Relay (`https://relay.flashbots.net/`).

### Level Medium
Kembangkan modul middleware Python atau Go yang memonitor endpoint Server-Sent Events (SSE) dari dua MEV Relay berbeda secara simultan. Hitung delta waktu kedatangan (*timestamp differential*) dari blinded payload header yang sama antara kedua relay tersebut, dan simpan log perbedaannya dalam format JSON ke disk.

### Level Hard
Implementasikan kontrak pintar dalam Yul (inline assembly murni) yang melakukan dekode parameter calldata transaksi multi-hop swap, memeriksa apakah eksekusi menghasilkan transfer token WETH dengan profit bersih di atas limit toleransi tertentu, serta mengeksekusi transfer `selfdestruct` atau `CALL` native balance ke `block.coinbase` hanya jika kondisi profit tercapai. Kontrak harus mengonsumsi gas sesedikit mungkin (< 30.000 gas overhead).

---

## 14. Challenge: CEX-DEX High-Frequency Hedging Engine

### Skenario Lapangan:
Anda adalah Lead MEV Infrastructure Engineer pada institusi arbitrase kuantitatif. Tim strategi menemukan dislokasi harga konstan antara Orderbook Binance (CEX) dan Pool Uniswap v3 (DEX). Masalah utamanya: transaksi di CEX bersifat off-chain instan, sedangkan transaksi di Ethereum bergantung pada kepastian inklusi blok dalam rentang waktu sub-detik melalui PBS.

### Persyaratan Arsitektur:
1. Bangun spesifikasi arsitektur mesin searcher yang mengeksekusi transaksi swap di Ethereum hanya jika ada jaminan mutlak bahwa transaksi tersebut menempati urutan posisi **Top-of-Block (Index 0)** pada slot berikutnya.
2. Jika transaksi terdorong ke posisi non-Top-of-Block (misal: Index 1 atau lebih rendah), transaksi harus otomatis dibatalkan (*revert*) secara internal tanpa membakar biaya gas yang signifikan, dan mesin harus membatalkan *hedging order* di CEX secara bersamaan via WebSocket FIX API.
3. Rancang mekanisme mitigasi kegagalan: Apa yang terjadi jika Relay builder menahan bundel Anda (*bundle unbundling/theft*) dan builder internal mereka mencuri rute arbitrase Anda?
4. Formulasikan formula penawaran suap (*optimal bribe bidding function*) dinamis berbasis persentase keuntungan marjinal terhadap pergerakan *gas base fee* (EIP-1559) dan volatilitas harga aset pada CEX secara real-time.

---

## 15. Quiz Evaluasi Pemahaman

### 5 Pertanyaan Basic

1. **Apa perbedaan fungsional mendasar antara Block Builder dan Block Proposer dalam arsitektur PBS?**
   * *Jawaban:* Block Builder bertanggung jawab atas pengumpulan transaksi, pengurutan, simulasi state execution, dan optimasi nilai ekstraksi MEV; sedangkan Block Proposer (Validator yang terpilih) hanya bertugas memilih tawaran header blok terbaik, menandatanganinya, dan mengajukannya ke jaringan konsensus tanpa menyusun isi blok secara mandiri.

2. **Mengapa transaksi bundel MEV yang dikirimkan via Flashbots RPC tidak terlihat di mempool publik?**
   * *Jawaban:* Karena bundel dikirim melalui koneksi point-to-point terenkripsi langsung ke server builder yang bekerja sama secara privat, tanpa pernah di-broadcast ke layer p2p gossip transaksi publik (*public mempool*).

3. **Apa peran variabel global `block.coinbase` pada Solidity dalam konteks ekstraksi MEV?**
   * *Jawaban:* `block.coinbase` menunjuk ke alamat Ethereum dari validator/miner pembuat blok saat ini. Variabel ini digunakan oleh searcher untuk menyalurkan pembayaran langsung (*direct bribe/transfer*) secara bersyarat kepada validator agar transaksi searcher diprioritaskan.

4. **Apa yang dimaksud dengan "Blinded Block" yang ditandatangani oleh Consensus Client?**
   * *Jawaban:* Blok yang hanya berisi header transaksi (akar merkle root eksekusi, hash parent, dan nilai bid) tanpa mengekspos daftar transaksi lengkap di dalamnya, guna mencegah validator mencuri peluang MEV dari builder sebelum blok resmi ditandatangani.

5. **Berapa batas waktu (cutoff deadline) kritis bagi pengusulan blok pada slot PoS Ethereum sebelum validator attestation mulai menolak/mengabaikan blok tersebut?**
   * *Jawaban:* 4 detik sejak slot dimulai ($T = 4s$).

---

### 5 Pertanyaan Intermediate

1. **Bagaimana mekanisme fallback MEV-Boost bekerja jika seluruh relayer yang terdaftar mengalami down time?**
   * *Jawaban:* Consensus Client akan mendeteksi *timeout* atau error dari MEV-Boost. Setelah batas waktu tercapai (`-request-timeout`), CL secara otomatis memanggil Execution Client lokal via Engine API (`engine_getPayload`) untuk memproduksi blok dari transaksi mempool lokal biasa, sehingga slot proposal tetap terlaksana.

2. **Mengapa relayer MEV-Boost tetap memerlukan "trust" (asumsi kepercayaan) dari sisi Searcher/Builder dan Validator?**
   * *Jawaban:* Searcher/Builder harus percaya bahwa Relay tidak membocorkan atau mencuri bundel transaksi mereka sebelum blok dipublikasikan. Validator harus percaya bahwa Relay menyediakan blok yang valid secara eksekusi, tidak menyembunyikan payload penuh (*data withholding*), dan nilai bid yang dijanjikan benar-benar dapat dicairkan.

3. **Apa risiko keamanan jika validator menggunakan nilai `-request-timeout` yang terlalu tinggi (misal: 2500ms) pada MEV-Boost?**
   * *Jawaban:* Risiko *missed proposal* atau blok terkena *reorganisasi* (reorg). Keterlambatan respons relay membuat validator menandatangani dan menyebarkan blok melewati batas 4 detik pertama slot, sehingga komite attester tidak menerima blok tepat waktu dan memvalidasi blok kosong/parent.

4. **Bagaimana searcher melindungi transaksinya agar tidak di-sandwich oleh bot pencari lain di dalam bundel yang sama?**
   * *Jawaban:* Searcher menggunakan RPC privat builder terpercaya, menetapkan slippage tolerance 0% pada kontrak swap, dan menerapkan proteksi otorisasi eksekusi kontrak (`onlyOwner`) sehingga pihak ketiga tidak dapat mengeksekusi fungsi arbitrase kontrak tersebut.

5. **Apa fungsi dari header HTTP `X-Flashbots-Signature` pada payload bundle submission?**
   * *Jawaban:* Mengotentikasi identitas publik searcher berbasis kriptografi public-key tanpa mengekspos kepemilikan aset finansial, yang digunakan oleh builder untuk menghitung skor reputasi searcher guna mencegah serangan spam/DoS simulasi gratis.

---

### 3 Skenario Kasus Produksi

#### Skenario 1: Node Validator Mengalami Missed Proposals Berulang
* **Konteks:** Cluster validator Anda di Frankfurt (AWS) kehilangan reward proposal pada 3 slot berturut-turut saat terpilih via RANDAO. MEV-Boost log menampilkan: `http: request reset by peer: relay.example.org: timeout waiting for header`.
* **Tindakan Diagnostik & Mitigasi:**
  1. Analisis performa latency koneksi dengan membandingkan respons RTT relay via HTTP status probe.
  2. Periksa setting `-request-timeout` pada daemon MEV-Boost. Turunkan nilai batas ke rentang aman `800ms`.
  3. Konfigurasikan minimal 3 relay alternatif independen secara berimbang.
  4. Aktifkan fitur *local payload build comparison* di level Consensus Client (`--builder-selection=max` atau sejenisnya) agar node langsung memotong proses lelang eksternal jika builder eksternal lambat.

#### Skenario 2: Kontrak Arbitrase Dieksekusi Namun Mengalami Revert Massal Saat Volatilitas Ekstrem
* **Konteks:** Bot searcher mendeteksi profit 4 ETH. Transaksi dikirim dalam bundel, namun pada log builder tercatat: `simulation failed: execution reverted: INSUFFICIENT_PROFIT`.
* **Tindakan Diagnostik & Mitigasi:**
  1. Periksa pembaruan state pada *pool reserves* antara waktu simulasi lokal searcher dengan waktu eksekusi builder. Builder kemungkinan memasukkan transaksi bernilai lebih tinggi tepat di depan bundel Anda.
  2. Lakukan simulasi lokal terhadap *pending state* terkini menggunakan tracing node (misal: `debug_traceCall`).
  3. Perbaiki toleransi batas profit dinamis dan gunakan kalkulasi bribe bertahap: jika eksekusi gagal menghasilkan target minimal, fungsi arbitrase harus dirancang untuk revert secara dini dengan biaya gas seminimal mungkin (< 25.000 gas) agar builder tidak membuang reputasi akun searcher Anda.

#### Skenario 3: Transaksi Bundel Searcher Diambil oleh Builder Nakal (Frontrunning by Builder)
* **Konteks:** Searcher memublikasikan bundel yang mengeksekusi liquidasi peminjaman DeFi ke sebuah builder regional baru. Transaksi searcher dipecah (*unbundled*): transaksi target tetap dieksekusi, namun transaksi searcher digantikan oleh alamat transaksi builder itu sendiri.
* **Tindakan Diagnostik & Mitigasi:**
  1. Validasi integritas builder: Segera putuskan koneksi bundle submission ke builder tersebut dan hapus endpoint builder dari routing gateway searcher.
  2. Laporkan jejak transaksi (*transaction receipt* dan bukti prapublikasi) ke komunitas terbuka (seperti Flashbots Forum/Discord) untuk *public accountability*.
  3. Terapkan enkripsi transaksi atau gunakan skema *Searcher-to-Builder Commit-Reveal* / SUAVE bila tersedia, atau batasi routing bundel eksklusif hanya ke builder yang memiliki komitmen reputasi finansial teruji (*bonded builders*).

---

## 16. Summary

Modul 02 telah menyajikan dekonstruksi arsitektur produksi sistem MEV dan Proposer-Builder Separation (PBS) pada Ethereum:

* **Separasi Peran:** MEV-Boost memisahkan beban komputasi perakitan blok (*Block Building*) dari hak konsensus pengesahan (*Block Proposing*), melindungi solo validator dari keharusan bersaing dalam kapabilitas komputasi kuantitatif berlatensi rendah.
* **Protokol Lelang Buta (Blind Auction):** Interaksi relay menggunakan payload header bertanda tangan menjamin integritas insentif finansial: Proposer dijamin menerima kompensasi tertinggi tanpa risiko mencuri strategi arbitrase builder, sementara builder terlindungi dari pembajakan rute nilai transaksi sebelum payload divalidasi.
* **Kritikalitas Timeline Slot:** Seluruh proses lelang, penandatanganan blinded block, dan unblinding payload wajib diselesaikan sebelum cutoff pengesahan attestation $T = 4$ detik demi menghindari kerugian reorganization (*missed block*).
* **Robustness Produksi:** Arsitektur validator enterprise harus mengadopsi prinsip *fail-safe*: penggunaan multi-relay terpercaya, binding koneksi lokal tertutup, implementasi circuit-breaker dengan nilai `-min-bid`, dan kesiapan mesin lokal untuk fallback seketika saat terjadi degradasi jaringan pihak ketiga.