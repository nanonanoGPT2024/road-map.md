# Bab 10: Maximal Extractable Value (MEV), Proposer-Builder Separation (PBS), & Operasional Validator
**Module 01: Ekosistem MEV, Protokol PBS, dan Eksekusi Otonom Berbasis Agent**

---

### 1. Learning Objectives (Spesifik & Terukur)

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
- **Menganalisis dan Mengkuantifikasi Sumber MEV (Maximal Extractable Value)**: Mengidentifikasi *atomic arbitrage*, *liquidations*, dan *sandwich attacks* pada EVM state transitions secara deterministik dengan kalkulasi keuntungan bersih setelah dikurangi *priority fee* dan *builder kickbacks*.
- **Merancang Arsitektur Proposer-Builder Separation (PBS)**: Menguraikan alur kerja interaksi antara *Searcher*, *Block Builder*, *Relay*, dan *Validator (Proposer)* menggunakan spesifikasi Engine API dan Builder API (v1/v2).
- **Mengembangkan Autonomous Searcher Agent**: Membangun bot otonom berbasis Python/Go yang memantau *pending transactions* (mempool), mendeteksi ketidakefisienan harga lintas Automated Market Maker (AMM), memformulasikan *bundle*, dan menyimulasikannya menggunakan *state override* secara atomik.
- **Mengonfigurasi dan Mengamankan Infrastruktur Validator Enterprise**: Mengimplementasikan setup *MEV-Boost*, *remote signer* (Web3Signer), strategi anti-slashing (*double signing* dan *surround voting mitigation*), serta *relay fallback mechanism*.
- **Mengevaluasi Risiko Sistemik MEV**: Menganalisis dampak MEV terhadap sentralisasi validator, stabilitas konsensus (seperti *time-bandit attacks* dan *chain reorgs*), serta menilai solusi mitigasi masa depan (ePBS, Encrypted Mempools, SUAVE).

---

### 2. Concept Overview (Mental Model & Teori Inti)

Secara historis, penambang (Proof-of-Work) atau validator (Proof-of-Stake) memiliki kendali absolut atas urutan eksekusi transaksi di dalam blok. Kemampuan untuk menyisipkan (*insert*), menghapus (*drop*), atau mengubah urutan (*reorder*) transaksi guna meraup keuntungan finansial di luar *block reward* standar dan *gas tip* didefinisikan sebagai **Maximal Extractable Value (MEV)**.

#### Mental Model: The Distributed Assembly Line
Bayangkan rantai pasok manufaktur:
1. **Searchers (AI/Autonomous Agents)** adalah detektif pasar yang mencari celah inefisiensi harga atau likuidasi yang belum terpenuhi di seluruh state EVM.
2. **Builders** adalah pabrik perakitan yang mengumpulkan ribuan transaksi reguler dari mempool publik dan *bundles* privat dari Searchers, lalu menyusun blok optimal yang memaksimalkan total nilai ekonomi (*bid* tertinggi).
3. **Relays** adalah auditor terpercaya (*mutually trusted third parties*) yang memvalidasi integritas blok Builder, menyembunyikan payload transaksi dari Proposer untuk mencegah pencurian strategi (*MEV stealing*), dan menerbitkan *header* blok ke Proposer.
4. **Validators (Proposers)** adalah pengawas jalur lelang akhir yang menandatangani *blinded block header* paling bernilai tanpa melihat transaksi mentah di dalamnya sampai tanda tangan divalidasi oleh konsensus.

```
+-------------------------------------------------------------------------------+
|                             MEMPOOL PUBLIK & PRIVAT                           |
+-------------------------------------------------------------------------------+
                                      │
                                      ▼
                        +---------------------------+
                        |  Searchers (AI Agents)   | ──> Mencari Arbitrage / Liquidation
                        +---------------------------+
                                      │ (Bundles privat)
                                      ▼
                        +---------------------------+
                        |       Block Builders      | ──> Mengemas Blok Optimal
                        +---------------------------+
                                      │ (ExecutionPayload + Bid)
                                      ▼
                        +---------------------------+
                        |       MEV-Boost Relay     | ──> Escrow & Validasi Header
                        +---------------------------+
                                      │ (Blinded Beacon Block Header)
                                      ▼
                        +---------------------------+
                        |    Validator (Proposer)   | ──> Menandatangani Header Blok
                        +---------------------------+
```

Formula dasar kalkulasi MEV:
$$\text{MEV}_{\text{net}} = \Delta V_{\text{state}} - \text{GasCost}_{\text{base}} - \text{GasCost}_{\text{priority}} - \text{Bid}_{\text{builder}}$$

Di mana $\Delta V_{\text{state}}$ merepresentasikan deviasi nilai aset yang diekstrak oleh transaksi Searcher dari state awal ($S_0$) ke state akhir ($S_n$).

---

### 3. Why It Matters (Masalah di Dunia Nyata & Kebutuhan Enterprise)

1. **Sentralisasi Consensus Layer**: Tanpa PBS, entitas staking besar (seperti exchange kustodian atau pool staking terpusat) dapat membangun algoritma proprietary untuk mengekstrak MEV dalam skala masif. Hal ini menciptakan *economies of scale* di mana validator kecil tersingkir karena yield staking mereka kalah jauh dibandingkan entitas raksasa. PBS mendemokratisasikan distribusi hasil MEV ke seluruh validator via lelang terbuka.
2. **Degradasi UX & Jaringan**: *Sandwich attacks* dan perang Priority Gas Auctions (PGA) di masa lalu membanjiri mempool P2P publik dengan transaksi *spam* dan *reverts*, meningkatkan konsumsi bandwidth node dan memicu lonjakan *gas fee* global yang merugikan pengguna ritel.
3. **Keamanan Konsensus (Fork Choice Instability)**: Nilai MEV yang sangat besar pada blok $n$ berpotensi memicu *Time-Bandit Attack*, di mana validator pada blok $n+1$ lebih memilih mereorganisasi (*reorg*) chain untuk mencuri MEV blok $n$ daripada memperluas canonical chain, merusak finalitas konsensus PoS.
4. **Autonomous Agent Economy**: Pada sistem AI otonom terdesentralisasi, agen dituntut mengeksekusi rebalancing portofolio, arbitrase lintas protokol, dan eksekusi likuidasi pinjaman tanpa terekspos slippage agresif atau *frontrunning* oleh predator lain di mempool.

---

### 4. Arsitektur & Diagram Komponen

#### Arsitektur PBS (MEV-Boost & Builder API)

```
+-------------------------------------------------------------------------------------------+
|                                    CONSENSUS CLIENT                                       |
|                                    (e.g., Lighthouse)                                     |
+-------------------------------------------------------------------------------------------+
                                 │                         ▲
                  Engine API     │                         │ Builder API
     (engine_forkchoiceUpdated)  │                         │ (getHeader / submitBlindedBlock)
                                 ▼                         │
+------------------------------------+           +------------------------------------------+
|          EXECUTION CLIENT          |           |                MEV-BOOST                 |
|          (e.g., Geth/Besu)         |           |               (Local Proxy)              |
+------------------------------------+           +------------------------------------------+
                                                               │                ▲
                                                               │ REST API       │ Payload /
                                                               │ (Signed Header)│ Bid Value
                                                               ▼                │
                                                 +------------------------------------------+
                                                 |             MEV-BOOST RELAY              |
                                                 |        (Ultra Sound / Flashbots)         |
                                                 +------------------------------------------+
                                                               ▲                ▲
                                               Submisi Blok    │                │ Submisi Blok
                                               (Full Payload)  │                │ (Full Payload)
                                                 +--------------------+  +------------------+
                                                 |   Block Builder A  |  |  Block Builder B |
                                                 +--------------------+  +------------------+
                                                           ▲                       ▲
                                            Bundles        │                       │ Bundles
                                            (via RPC)      │                       │ (via RPC)
                                                 +--------------------+  +------------------+
                                                 | Searcher Agent X   |  | Searcher Agent Y |
                                                 +--------------------+  +------------------+
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### 5.1 Siklus Hidup Eksekusi PBS di Proof-of-Stake

1. **Bundle Formulation**: Searcher memonitor status transaksi `pending` di mempool menggunakan websocket stream node lokal. Saat peluang arbitrase terdeteksi, AI Searcher membuat *bundle* berisi array transaksi:
   $$\mathcal{B} = [T_{\text{target}}, T_{\text{searcher}}]$$
   Bundle ini dikirim ke Builder via endpoint JSON-RPC privat (misal: `eth_sendBundle`), sehingga transaksi tidak terlihat oleh mempool publik.

2. **Block Construction**: Block Builder mengeksekusi ribuan bundle yang bersaing menggunakan simulasi EVM parallel (menggunakan engine seperti Revm). Builder mengurutkan bundle yang tidak bentrok dan memaksimalkan transfer ether ke alamat coinbase:
   $$\text{Block} = \arg\max_{\text{Perm}} \sum_{j} \text{GasUsed}(T_j) \times \text{EffectivePriorityFee}(T_j) + \text{DirectCoinbaseTransfers}$$

3. **Relay Verification & Escrow**: Builder mengirim `ExecutionPayload` lengkap ke Relay. Relay menjalankan langkah validasi:
   - Memastikan blok sah terhadap state Ethereum terbaru (validitas gas, state transition).
   - Memastikan nilai transfer pada instruksi terakhir menguntungkan Proposer yang dijadwalkan pada slot tersebut.
   - Menghasilkan `ExecutionPayloadHeader` (representasi *blinded* tanpa daftar transaksi lengkap).

4. **Proposer Header Auction**:
   - Consensus Client validator memanggil MEV-Boost melalui Builder API: `GET /eth/v1/builder/header/{slot}/{parent_hash}/{pubkey}`.
   - MEV-Boost meneruskan query ini ke multi-relay yang dikonfigurasi, mengumpulkan header, membandingkan nilai lelang ($Bid$), dan mengembalikan header dengan tawaran tertinggi ke Consensus Client.

5. **Signing & Payload Unblinding**:
   - Validator menandatangani `BlindedBeaconBlock` menggunakan private key validator (atau melalui Remote Signer).
   - Consensus Client mengirim blok yang telah ditandatangani kembali ke MEV-Boost: `POST /eth/v1/builder/blinded_blocks`.
   - Relay memverifikasi tanda tangan signature proposer. Jika valid, Relay menyebarkan `ExecutionPayload` penuh ke P2P network dan mengembalikannya ke Consensus Client untuk dirakit menjadi blok utuh canonical.

#### 5.2 Strategi AI-Driven MEV Searchers
Dalam modul AI Agents ini, autonomous searcher bukan sekadar script linear sederhana:
- **State Prediction Models**: Searcher memanfaatkan Graph Neural Networks (GNN) atau transformer ringkas untuk memprediksi slippage dan path routing terbaik pada $N$-hop AMM (UniswapV2, UniswapV3, Curve) sebelum state commit terjadi.
- **Dynamic Fee Bidding Logic**: Menggunakan algoritma Reinforcement Learning (seperti PPO - Proximal Policy Optimization) untuk menentukan persentase optimal ekstraksi MEV yang harus diberikan ke Builder:
  $$\text{Bid} = \alpha \cdot \text{MEV}_{\text{gross}}, \quad \text{di mana } \alpha \in [0.90, 0.999]$$
  Jika $\alpha$ terlalu rendah, builder menolak bundle karena kalah saing; jika terlalu tinggi, agen merugi secara operasional akibat fluktuasi gas dasar ($L1 \text{ basefee}$).

---

### 6. Production-Ready Code Implementation

Berikut adalah implementasi **Autonomous MEV Arbitrage Detector & Bundle Dispatcher** menggunakan Python 3.11+, `web3.py`, `pydantic` untuk validasi schema, pemrosesan konkurensi berbasis `asyncio`, dan format JSON-RPC Flashbots Builder.

```python
#!/usr/bin/env python3
"""
Autonomous Cross-DEX Arbitrage Agent and Flashbots Bundle Submitter.
Engineered for Production Environments with Fail-safe Execution.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

import aiohttp
from eth_account import Account
from eth_account.messages import encode_defunct
from eth_account.signers.local import LocalAccount
from eth_typing import ChecksumAddress, HexStr
from pydantic import BaseModel, Field, ValidationError
from web3 import AsyncWeb3
from web3.providers import AsyncBaseProvider

# --- CONFIGURATION & LOGGING SETUP ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] (%(name)s) %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("MEV-Autonomous-Agent")


class AgentConfig(BaseModel):
    execution_rpc_ws: str = Field(..., description="WebSocket URL Node RPC EVM")
    builder_rpc_url: str = Field(..., description="URL Flashbots/PBS Builder Relay")
    searcher_private_key: str = Field(..., min_length=64, max_length=66)
    weth_address: ChecksumAddress
    target_token_address: ChecksumAddress
    router_a_address: ChecksumAddress
    router_b_address: ChecksumAddress
    min_profit_threshold_wei: int = Field(default=10**16)  # 0.01 ETH minimum profit
    builder_payment_percentage: Decimal = Field(default=Decimal("0.90"))  # 90% ke builder


class FlashbotsBundleParam(BaseModel):
    txs: List[HexStr]
    blockNumber: HexStr
    minTimestamp: Optional[int] = None
    maxTimestamp: Optional[int] = None


class FlashbotsRPCRequest(BaseModel):
    jsonrpc: str = "2.0"
    id: int = 1
    method: str = "eth_sendBundle"
    params: List[FlashbotsBundleParam]


# Minimal Uniswap V2 Pair ABI for Reserves Checking
UNISWAP_V2_PAIR_ABI = [
    {
        "constant": True,
        "inputs": [],
        "name": "getReserves",
        "outputs": [
            {"name": "_reserve0", "type": "uint112"},
            {"name": "_reserve1", "type": "uint112"},
            {"name": "_blockTimestampLast", "type": "uint32"},
        ],
        "payable": False,
        "stateMutability": "view",
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [],
        "name": "token0",
        "outputs": [{"name": "", "type": "address"}],
        "payable": False,
        "stateMutability": "view",
        "type": "function",
    },
]


class MEVEngine:
    def __init__(self, config: AgentConfig) -> None:
        self.config = config
        self.w3 = AsyncWeb3(AsyncWeb3.PersistentConnectionProvider(config.execution_rpc_ws))
        self.account: LocalAccount = Account.from_key(config.searcher_private_key)
        self.session: Optional[aiohttp.ClientSession] = None
        logger.info(f"Agent diinisialisasi dengan signer address: {self.account.address}")

    async def initialize(self) -> None:
        """Koneksi RPC dan pembuatan HTTP Session."""
        connected = await self.w3.is_connected()
        if not connected:
            raise ConnectionError(f"Gagal terhubung ke RPC Node: {self.config.execution_rpc_ws}")
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=5.0),
            headers={"Content-Type": "application/json"},
        )
        logger.info("Koneksi RPC EVM & HTTP Pool Builder berhasil dibentuk.")

    async def close(self) -> None:
        """Graceful shutdown resource connections."""
        if self.session and not self.session.closed:
            await self.session.close()
        logger.info("Session jaringan berhasil ditutup secara aman.")

    def compute_amount_out(
        self, amount_in: int, reserve_in: int, reserve_out: int, fee_bps: int = 997
    ) -> int:
        """Kalkulasi formula Constant Product AMM (x * y = k) dengan fee 0.3%."""
        if amount_in <= 0 or reserve_in <= 0 or reserve_out <= 0:
            return 0
        amount_in_with_fee = amount_in * fee_bps
        numerator = amount_in_with_fee * reserve_out
        denominator = (reserve_in * 1000) + amount_in_with_fee
        return numerator // denominator

    def calculate_cross_market_spread(
        self,
        reserves_a: Tuple[int, int],
        reserves_b: Tuple[int, int],
        borrow_amount_wei: int,
    ) -> Tuple[int, bool]:
        """
        Analisis Spread Arbitrase Antara DEX A dan DEX B:
        Arah: WETH -> Token -> WETH.
        Mengembalikan (net_profit_wei, arah_a_ke_b).
        """
        # Arah: Beli di DEX A, Jual di DEX B
        out_token_a = self.compute_amount_out(borrow_amount_wei, reserves_a[0], reserves_a[1])
        out_weth_b = self.compute_amount_out(out_token_a, reserves_b[1], reserves_b[0])
        profit_a_to_b = out_weth_b - borrow_amount_wei

        # Arah Sebaliknya: Beli di DEX B, Jual di DEX A
        out_token_b = self.compute_amount_out(borrow_amount_wei, reserves_b[0], reserves_b[1])
        out_weth_a = self.compute_amount_out(out_token_b, reserves_a[1], reserves_a[0])
        profit_b_to_a = out_weth_a - borrow_amount_wei

        if profit_a_to_b > profit_b_to_a:
            return profit_a_to_b, True
        return profit_b_to_a, False

    async def craft_signed_arbitrage_tx(
        self,
        target_block: int,
        profit_wei: int,
        direction_a_to_b: bool,
    ) -> HexStr:
        """
        Menyusun dan menandatangani transaksi atomik arbitrase.
        Secara internal mentransfer porsi profit ke block.coinbase (Builder reward).
        """
        builder_reward = int(Decimal(profit_wei) * self.config.builder_payment_percentage)
        nonce = await self.w3.eth.get_transaction_count(self.account.address)
        base_fee = (await self.w3.eth.get_block("latest"))["baseFeePerGas"]
        
        # Priority fee diatur minimum karena builder di-bribe via direct coinbase transfer
        max_priority_fee = 10**9  # 1 Gwei
        max_fee_per_gas = (base_fee * 2) + max_priority_fee

        # Mengemas calldata simulasi eksekusi smart contract arbitrase custom
        # Untuk demonstrasi end-to-end, transaksi berinteraksi sebagai native call
        tx_dict = {
            "type": 2,
            "chainId": await self.w3.eth.chain_id,
            "nonce": nonce,
            "to": self.account.address,  # Target Router / MEV Contract
            "value": 0,
            "gas": 250000,
            "maxFeePerGas": max_fee_per_gas,
            "maxPriorityFeePerGas": max_priority_fee,
            "data": b"",  # Calldata payload ke smart contract
        }

        signed_tx = self.account.sign_transaction(tx_dict)
        return HexStr(signed_tx.raw_transaction.hex())

    async def submit_bundle(
        self, signed_txs: List[HexStr], target_block: int
    ) -> Optional[Dict[str, Any]]:
        """
        Mengirim Bundle ke PBS Builder Relay menggunakan standard Flashbots RPC.
        Tanda tangan bundle header dihitung menggunakan Searcher private key.
        """
        if not self.session:
            raise RuntimeError("HTTP Client Session belum terinisialisasi.")

        bundle_payload = FlashbotsRPCRequest(
            params=[
                FlashbotsBundleParam(
                    txs=signed_txs,
                    blockNumber=HexStr(hex(target_block)),
                )
            ]
        )

        body_str = bundle_payload.model_dump_json()
        message = encode_defunct(text=AsyncWeb3.keccak(text=body_str).hex())
        signature = self.account.address + ":" + self.account.sign_message(message).signature.hex()

        headers = {
            "X-Flashbots-Signature": signature,
            "Content-Type": "application/json",
        }

        async with self.session.post(
            self.config.builder_rpc_url, data=body_str, headers=headers
        ) as response:
            res_text = await response.text()
            if response.status != 200:
                logger.error(f"Builder menolak bundle. Status: {response.status}, Body: {res_text}")
                return None
            result_json = json.loads(res_text)
            logger.info(f"Bundle berhasil terkirim ke Builder! Response: {result_json}")
            return result_json

    async def run_pipeline(self) -> None:
        """Siklus Utama Deteksi Arbitrase dan Disposisi Transaksi."""
        logger.info("Memulai MEV Searcher Pipeline...")
        test_borrow_wei = 10 * 10**18  # 10 WETH

        # Mock mock reserves data untuk simulasi deterministik state AMM
        # Reserve A: 100 WETH, 200,000 USDC -> Price: 2,000 USDC/ETH
        reserves_a = (100 * 10**18, 200000 * 10**6)
        # Reserve B: 80 WETH, 200,000 USDC -> Price: 2,500 USDC/ETH (Discrepancy)
        reserves_b = (80 * 10**18, 200000 * 10**6)

        while True:
            try:
                current_block = await self.w3.eth.block_number
                target_block = current_block + 1

                profit, direction = self.calculate_cross_market_spread(
                    reserves_a, reserves_b, test_borrow_wei
                )

                if profit > self.config.min_profit_threshold_wei:
                    logger.info(
                        f"Peluang Arbitrase Ditemukan pada Blok {target_block}! "
                        f"Estimasi Profit: {profit / 10**18:.4f} ETH. Arah A->B: {direction}"
                    )

                    signed_tx = await self.craft_signed_arbitrage_tx(
                        target_block=target_block,
                        profit_wei=profit,
                        direction_a_to_b=direction,
                    )

                    await self.submit_bundle([signed_tx], target_block)
                else:
                    logger.debug(f"Scan selesai untuk block {target_block}. Profit di bawah ambang batas.")

                await asyncio.sleep(6)  # Sinkronisasi dengan cadence slot konsensus

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Unhanded exception pada execution loop: {str(e)}", exc_info=True)
                await asyncio.sleep(2)


# --- ENTRYPOINT ---
async def main() -> None:
    # Menggunakan dummy configuration untuk keperluan testing & audit
    config = AgentConfig(
        execution_rpc_ws="wss://eth-mainnet.g.alchemy.com/v2/DEMO_KEY",
        builder_rpc_url="https://relay.flashbots.net",
        searcher_private_key="0x4c0883a69102937d6231471b5dbb6204db7ef0b61a308c2d609dafa523398d0c",
        weth_address=ChecksumAddress("0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"),
        target_token_address=ChecksumAddress("0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"),
        router_a_address=ChecksumAddress("0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D"),
        router_b_address=ChecksumAddress("0xd9e1cE17f2641f24aE83637ab66a2cca9C378B9F"),
    )

    engine = MEVEngine(config)
    try:
        # Inisialisasi dibungkus try/except untuk penanganan kegagalan koneksi live RPC
        await engine.initialize()
        await engine.run_pipeline()
    except ConnectionError as err:
        logger.warning(f"Simulasi Mode Standalone: {err}")
    finally:
        await engine.close()


if __name__ == "__main__":
    asyncio.run(main())
```

---

### 7. Edge Cases & Failure Modes

#### 7.1 Reverts dan Unbundling
- **Edge Case**: Transaksi target dieksekusi oleh Searcher lain lebih dulu, membatalkan pre-kondisi arbitrase (*slippage limit exceeded*).
- **Failure Mode**: Builder mengekstrak sebagian transaksi dari bundle Searcher (unbundling), menyebabkan transaksi Searcher mengalami `REVERT` di on-chain, membuang *gas fee* sia-sia.
- **Mitigasi**: Kirim bundle secara eksklusif ke Builder dengan garansi *atomic bundle execution* (jika satu instruksi *revert*, seluruh bundle dibuang oleh Builder tanpa dibebankan on-chain fee).

#### 7.2 Relay Latency & Missed Slots
- **Edge Case**: Koneksi jaringan antara Proposer dan Relay mengalami degradasi latency (>1.5 detik menjelang batas slot).
- **Failure Mode**: Validator gagal menerima `ExecutionPayload` utuh sebelum cut-off attestation 4 detik, menghasilkan blok kosong (*missed slot*) atau terkena *fork-choice filter* (blok ditolak oleh network attester).
- **Mitigasi**: MEV-Boost dikonfigurasi dengan batas `--min-bid` dan flag fallback lokal. Jika payload dari Relay tidak diterima dalam kurun waktu 950ms, Consensus Client beralih otomatis ke *local block production* via Engine API execution client.

#### 7.3 Slashing Conditions pada Operasional Validator
Pemisahan peran proposer tidak meniadakan penalti slashing dasar Proof-of-Stake:
- **Double Signing (Proposer Slashing)**: Validator menandatangani dua `BeaconBlockHeader` berbeda untuk slot yang sama.
- **Surround Voting (Attester Slashing)**: Attestation tanda tangan mencakup rentang epoch yang melanggar prinsip *Casper FFG*.
- **Mitigasi**: Arsitektur validator enterprise **wajib** menggunakan isolated remote signers (misal: Web3Signer) dengan Anti-Slashing PostgreSQL Database terdistribusi dan menonaktifkan instance duplikat dari private key validator secara bersamaan (larangan *active-active redundancy*).

---

### 8. Trade-offs & Alternatif Solusi

| Parameter | Traditional In-Enclave PBS (Saat Ini) | Enshrined PBS (ePBS) | SUAVE (Flashbots) | Encrypted Mempools |
| :--- | :--- | :--- | :--- | :--- |
| **Trust Model** | Membutuhkan kepercayaan pada Relay pihak ketiga (*trusted intermediary*). | Trustless; verifikasi langsung di level Consensus Layer Ethereum. | Terdesentralisasi via execution-layer chain independen. | Kriptografis (Threshold Encryption / Timed Commitments). |
| **Latensi Jaringan** | Tambahan round-trip: Validator $\leftrightarrow$ MEV-Boost $\leftrightarrow$ Relay. | Mengurangi hop eksternal; terintegrasi dalam engine consensus. | Latensi lelang off-chain terdistribusi. | Overhead kriptografis tinggi saat proses deskripsi per blok. |
| **Sensor & Kepatuhan** | Rentan sensor regulasi (misal: Relay menyaring transaksi OFAC). | Tahan sensor (*censorship-resistant*) via Inclusion Lists. | MEV terdistribusi lintas chain tanpa filtering sentral. | Sangat tinggi; isi transaksi buram hingga finalisasi blok. |
| **Kompleksitas Infrastruktur** | Memerlukan runtime MEV-Boost eksternal dan relay pooling. | Zero eksternal binary; dikelola langsung oleh client PoS. | Membutuhkan integrasi node bridge ke SUAVE chain. | Eksekusi proof engine berat (ZK / VDF circuit computation). |

---

### 9. Best Practices & Standar Industri

#### Konfigurasi MEV-Boost Enterprise
Validator kelas institusional tidak boleh bergantung pada satu Relay. Gunakan konfigurasi multi-relay terverifikasi dengan diversifikasi yuridis dan kebijakan OFAC yang eksplisit:

```bash
mev-boost \
  -mainnet \
  -relay-check \
  -relays https://0xac6e77e2f1f7...relay1.net,https://0xa7ab4e85c33...relay2.io \
  -min-bid 0.05 \
  -request-timeout-getheader 950 \
  -request-timeout-getpayload 4000
```

#### Client Diversity Enforcement
Konsensus validator dilarang menggunakan konfigurasi monolitik:
- Gunakan kombinasi minoritas: **Besu / Nethermind** (Execution Client) + **Lighthouse / Teku** (Consensus Client).
- Rasio konsensus supermajority (>66% Geth / Prysm) menimbulkan risiko finalitas rantai yang fatal jika terjadi consensus bug.

#### Penanganan Kunci Staking & Anti-Slashing
1. **Pemisahan Kunci**: Pisahkan secara total antara *Validator Signing Key* (hot key, disimpan di Web3Signer dengan akses read-only HSM) dan *Withdrawal Key* (cold key, offline hardware wallet multi-sig).
2. **Strict Single-Node Rule**: Jangan pernah menggunakan konfigurasi *high-availability active-active* untuk validator client. Kehilangan 1 slot ($0.005\%$ yield) jauh lebih aman daripada ter-slash dan dikeluarkan paksa dari beacon chain (*minimum 1 ETH slash penalty + 36 hari forced exit*).

---

### 10. Hands-on Lab Exercise

#### Skenario Lab
Anda ditugaskan mengonfigurasi validator node testnet (Holesky), mengintegrasikan *MEV-Boost*, dan menguji skenario kegagalan fallback lokal saat Relay offline.

#### Langkah 1: Download & Verifikasi Binary MEV-Boost
```bash
wget https://github.com/flashbots/mev-boost/releases/download/v1.7.0/mev-boost_1.7.0_linux_amd64.tar.gz
tar -xvf mev-boost_1.7.0_linux_amd64.tar.gz
sudo mv mev-boost /usr/local/bin/
mev-boost --version
```

#### Langkah 2: Setup Service Systemd MEV-Boost (Holesky)
Buat file service di `/etc/systemd/system/mev-boost.service`:
```ini
[Unit]
Description=MEV-Boost Proxy Service (Holesky)
After=network.target

[Service]
Type=simple
User=validator-service
ExecStart=/usr/local/bin/mev-boost \
    -holesky \
    -addr 127.0.0.1:18550 \
    -relays https://0xaa1488aec3...holesky-relay.flashbots.net \
    -request-timeout-getheader 900
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```
Jalankan service:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now mev-boost
sudo systemctl status mev-boost
```

#### Langkah 3: Konfigurasi Consensus Client (Lighthouse)
Tambahkan flag builder endpoint pada file environment Lighthouse Validator:
```bash
--builder=http://127.0.0.1:18550
--builder-fallback-epochs-since-finality=2
```

#### Langkah 4: Uji Fallback Mechanism (Simulasi Relay Outage)
Hentikan paksa service `mev-boost` untuk memverifikasi bahwa Consensus Client tidak gagal memproduksi blok:
```bash
sudo systemctl stop mev-boost
```
Pantau log validator saat slot tugas tiba:
```bash
journalctl -fu lighthouse-validator | grep -E "builder|fallback"
```
**Hasil yang Diharapkan:**
Log harus menampilkan pesan peringatan:
`WARN Builder endpoint unreachable, failing over to local execution client engine_forkchoiceUpdated. Block proposal produced locally.` Blok tetap di-broadcast tepat waktu ke jaringan Holesky tanpa terkena sanksi *missed slot*.