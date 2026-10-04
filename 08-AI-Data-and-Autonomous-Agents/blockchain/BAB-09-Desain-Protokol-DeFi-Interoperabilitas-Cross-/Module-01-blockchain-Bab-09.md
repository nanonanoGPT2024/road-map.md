# Bab 09: Desain Protokol DeFi & Interoperabilitas Cross-Chain

## Module 01: Autonomous Cross-Chain Liquidity Routing & Intent-Based DeFi Protocol Architecture

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- **Menganalisis & Mengonstruksi** arsitektur *Decentralized Finance* (DeFi) modern berbasis *Automated Market Maker* (AMM) invariants ($x \cdot y = k$ dan *concentrated liquidity*) yang diintegrasikan dengan protokol *General Message Passing* (GMP).
- **Mendesain & Mengimplementasikan** sistem eksekusi *Intent-Based Cross-Chain* (mengacu pada spesifikasi ERC-7683) untuk mengatasi fragmentasi likuiditas antar EVM-compatible rollups.
- **Membangun Autonomous Agent Pipeline** menggunakan TypeScript dan arsitektur *Solver/Filler* yang mampu mendeteksi inefisiensi likuiditas lintas rantai (*cross-chain arbitrage*), menghitung *slippage decay*, dan mengeksekusi *atomic settlement* dengan proteksi *Maximal Extractable Value* (MEV).
- **Mengevaluasi Vektor Kerentanan Kritis** pada *bridge messaging layers* (seperti *replay attacks*, *finality mismatch*, *toxic proof validation*, dan *reentrancy via cross-chain callbacks*).

---

### 2. Concept Overview

Sistem DeFi tradisional beroperasi secara terisolasi pada satu lapisan komputasi (*single execution environment*). Dengan proliferasi Layer-2 (Optimistic & ZK-Rollups) serta Layer-1 alternatif, likuiditas menjadi terfragmentasi secara tajam. Desain protokol modern bertransformasi dari sekadar penyedia *liquidity pool* statis menjadi sistem inter-operabel dinamis yang dikoordinasikan oleh agen otonom (*Autonomous Agents*).

#### Mental Model: The Intent & Filler Engine
Alih-alih pengguna mengeksekusi instruksi deterministik kaku (*imperative transactions*: *Approve -> Bridge -> Swap -> Deposit*), protokol modern menggunakan paradigma **Intent-Based Architecture**:
1. **User Intent**: Pengguna menandatangani deklarasi *state change* yang diinginkan (contoh: "Tukar $10.000$ USDC di Arbitrum menjadi minimal $3.25$ ETH di Optimism").
2. **Autonomous Solvers/Agents**: Agen komputasi off-chain bersaing untuk menyelesaikan intent tersebut secara optimal menggunakan modal mereka sendiri (*private liquidity*).
3. **Optimistic/Proof Settlement**: Protokol menjamin pengembalian dana (*refund*) dan pembayaran reward kepada agen secara atomik setelah validasi kriptografis terpenuhi via GMP layer (Chainlink CCIP, LayerZero V2, atau Hyperlane).

```
[User Interface] 
       │ (Signs EIP-712 Intent)
       ▼
[Decentralized Intent Mempool / Off-Chain P2P Relay]
       │
       ├─────────────────────────┬─────────────────────────┐
       ▼                         ▼                         ▼
[Agent Solver A]          [Agent Solver B]          [Agent Solver C]
(Evaluates Arbitrage,     (Evaluates Route & Fees)  (Calculates Gas Delta)
 Margin & Gas Bounds)
       │ (Wins Right to Settle)
       ▼
[Destination Chain Execution Contract] ──(Unlocks Liquidity to User)
       │
       ▼ (Proves Execution via State Proof / Messaging Protocol)
[Source Chain Settlement Contract] ──────(Reimburses Solver + Spread)
```

---

### 3. Why It Matters

Bagi ekosistem enterprise dan desentralisasi finansial berkapitalisasi tinggi, bridging tradisional berbasis *lock-and-mint* telah terbukti menjadi titik rentan sistemik (contoh kegagalan: Ronin $624M, Wormhole $326M, Nomad $190M). Sebagian besar eksploitasi terjadi akibat celah validasi pada kontrak multisig terpusat atau *deserialization bugs* pada *light client verification*.

Pendekatan *Intent-based Liquidity Routing* yang dieksekusi oleh Agen Otonom mengalihkan risiko *bridge lock-up* dari pengguna akhir ke pasar agen (*filler network*). Jika terjadi kegagalan jaringan atau keterlambatan penyelesaian rantai asal, risiko tertahan ditanggung oleh *solver* profesional yang memiliki sistem hedging terautomasi, bukan pengguna ritel maupun neraca korporat (*treasury*).

---

### 4. Arsitektur & Diagram Komponen

Diagram berikut mengilustrasikan interaksi end-to-end antara Autonomous Agent (Brain), Kontrak On-Chain pada Source Chain dan Destination Chain, serta Layer Validasi Pesan Lintas Rantai.

```
+---------------------------------------------------------------------------------------------------+
|                                  SOURCE CHAIN (e.g., Arbitrum)                                    |
|                                                                                                   |
|  +--------------------+       1. Sign Intent (EIP-712)       +---------------------------------+  |
|  |     User / dApp    | ===================================> |      IntentVault.sol            |  |
|  +--------------------+                                      |  - Escrows User Collateral      |  |
|                                                              |  - Emits IntentCreated Event    |  |
|                                                              +---------------------------------+  |
|                                                                               |                   |
|                                                                               | 5. Release Escrow |
|                                                                               |    to Solver      |
|                                                              +---------------------------------+  |
|                                                              |   CrossChainReceiver.sol        |  |
|                                                              +---------------------------------+  |
+-------------------------------------------------------------------------------▲-------------------+
                                                                                |
                                                                                | Verify Proof &
                                                                                | Release
                                                                                |
+------------------------------------+                         +----------------+------------------+
|      OFF-CHAIN INFRASTRUCTURE      |                         |      CROSS-CHAIN GMP LAYER        |
|                                    |                         |  (Chainlink CCIP / LayerZero V2)  |
|  +------------------------------+  |  2. Read Intent Event   |                                   |
|  | Autonomous Agent Engine      | <--------------------------+  - Decentralized Oracle Network   |
|  | - Market Inefficiency Sensor |  |                         |  - Relayer / Executor Validation  |
|  | - Optimal Path Router        |  |                         +----------------▲------------------+
|  | - Private Liquidity Manager  |  |                                          |
|  +------------------------------+  |                                          |
|                 |                  |                                          | 4. Dispatch State
|                 | 3. Settle Intent |                                          |    Proof / Message
|                 |    with Liquidity|                                          |
+-----------------│------------------+                                          |
                  │                                                             |
+-----------------▼-------------------------------------------------------------│-------------------+
|                                DESTINATION CHAIN (e.g., Optimism)             |                   |
|                                                                               |                   |
|  +-----------------------------------+                       +----------------+----------------+  |
|  | DestinationSettlement.sol         | --------------------> | DestinationGateway.sol          |  |
|  | - Fills User Order (Payout)       |                       | - Encodes Cross-Chain Delivery  |  |
|  | - Enforces Minimum Return Delta   |                       +---------------------------------+  |
|  +-----------------------------------+                                                            |
|                 |                                                                                 |
|                 ▼ Transfer Out Tokens                                                             |
|  +-----------------------------------+                                                            |
|  |         User Address              |                                                            |
|  +-----------------------------------+                                                            |
+---------------------------------------------------------------------------------------------------+
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### A. The AMM Invariant & Concentrated Liquidity Mechanics
AMM modern (Uniswap v3/v4-like) beroperasi pada domain konsentrasi likuiditas berbasis *tick*:
$$L = \sqrt{k} = \frac{\Delta y}{\Delta \sqrt{P}} = \Delta x \cdot \frac{\sqrt{P_b}\sqrt{P_a}}{\sqrt{P_b} - \sqrt{P_a}}$$
Di mana likuiditas ($L$) hanya aktif dalam rentang harga $[P_a, P_b]$. Autonomous Agent yang mengeksekusi routing cross-chain harus mengkalkulasi dampak harga lokal (*local price impact*) versus biaya *gas message passing* lintas rantai. 

#### B. Intent Fulfillment & The Settlement Cycle
1. **Nonce & Replay Safety**: Setiap intent memiliki parameter deterministik yang terikat pada nonce unik:
   $$\text{Hash}_{\text{Intent}} = \text{keccak256}(\text{abi.encode}(\text{user}, \text{sourceChain}, \text{destChain}, \text{tokenIn}, \text{tokenOut}, \text{amountIn}, \text{minAmountOut}, \text{nonce}, \text{deadline}))$$
2. **Atomic Fill**: Agen mengisi pesanan di Destination Chain dengan memanggil kontrak `DestinationSettlement.sol`. Kontrak mentransfer `tokenOut` langsung ke pengguna dari akun Agen.
3. **Asynchronous Attestation**: Agen memicu pesan GMP dari Destination Chain ke Source Chain yang berisi bukti pemenuhan order ($\text{Hash}_{\text{Intent}}$). Source Chain membuka kunci *escrow* dana `tokenIn` beserta reward *solver*.

#### C. Cross-Chain Verification Invariants
Penyelesaian intent bergantung pada integritas lapisan verifikasi:
- **Optimistic Assertion**: Agen menyatakan bahwa intent telah terpenuhi di rantai tujuan. Mekanisme *dispute window* (contoh: 30 menit) terbuka di mana *watcher* lain dapat memangkas (*slash*) deposit agen jika klaim tersebut palsu.
- **Direct Proof Validation**: Validasi langsung melalui GMP di mana relayer independen memvalidasi *receipt execution* rantai asal sebelum melepaskan agunan.

---

### 6. Production-Ready Code Implementation

Arsitektur ini terdiri dari dua komponen inti:
1. **Solidity Contract**: `IntentCrossChainSettler.sol` untuk validasi intent, eksekusi settlement di Destination Chain, dan penguncian escrow.
2. **TypeScript Autonomous Solver Engine**: Modul pemantau, perute, dan eksekutor likuiditas otomatis berbasis Viem.

#### 1. Kontrak Cerdas: `IntentCrossChainSettler.sol`

```solidity
// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

/**
 * @dev Minimal interfaces for ERC20 and Reentrancy Guard
 */
interface IERC20 {
    function transferFrom(address from, address to, uint256 amount) external returns (bool);
    function transfer(address to, uint256 amount) external returns (bool);
    function balanceOf(address account) external view returns (uint256);
}

/**
 * @notice Standardized Cross-Chain Intent struct conforming to generalized intent patterns.
 */
struct OrderIntent {
    address user;
    uint256 originChainId;
    uint256 destinationChainId;
    address inputToken;
    address outputToken;
    uint256 inputAmount;
    uint256 minOutputAmount;
    address recipient;
    uint256 nonce;
    uint256 deadline;
}

abstract contract ReentrancyGuard {
    uint256 private locked = 1;
    modifier nonReentrant() {
        require(locked == 1, "REENTRANCY_DETECTED");
        locked = 2;
        _;
        locked = 1;
    }
}

contract IntentCrossChainSettler is ReentrancyGuard {
    bytes32 public constant INTENT_TYPEHASH = keccak256(
        "OrderIntent(address user,uint256 originChainId,uint256 destinationChainId,address inputToken,address outputToken,uint256 inputAmount,uint256 minOutputAmount,address recipient,uint256 nonce,uint256 deadline)"
    );

    // EIP-712 Domain Separator
    bytes32 public immutable DOMAIN_SEPARATOR;
    
    // Mapping to track filled or cancelled intent hashes
    mapping(bytes32 => bool) public intentExecuted;
    // Mapping to track escrowed assets on Origin Chain: intentHash => escrowed
    mapping(bytes32 => bool) public escrowActive;

    event IntentEscrowed(bytes32 indexed intentHash, address indexed user, uint256 amount);
    event IntentSettled(bytes32 indexed intentHash, address indexed solver, address indexed recipient, uint256 amount);
    event SettlementProven(bytes32 indexed intentHash, address indexed solver);

    error IntentExpired();
    error ChainIdMismatch();
    error IntentAlreadySolved();
    error SlippageExceeded();
    error EscrowNotFound();
    error TransferFailed();

    constructor() {
        DOMAIN_SEPARATOR = keccak256(
            abi.encode(
                keccak256("EIP712Domain(string name,string version,uint256 chainId,address verifyingContract)"),
                keccak256(bytes("CrossChainIntentProtocol")),
                keccak256(bytes("1.0")),
                block.chainid,
                address(this)
            )
        );
    }

    function hashIntent(OrderIntent calldata intent) public pure returns (bytes32) {
        return keccak256(
            abi.encode(
                INTENT_TYPEHASH,
                intent.user,
                intent.originChainId,
                intent.destinationChainId,
                intent.inputToken,
                intent.outputToken,
                intent.inputAmount,
                intent.minOutputAmount,
                intent.recipient,
                intent.nonce,
                intent.deadline
            )
        );
    }

    /**
     * @notice Escrows tokens on the Origin Chain. Executed by the User.
     */
    function openIntentEscrow(OrderIntent calldata intent) external nonReentrant {
        if (block.chainid != intent.originChainId) revert ChainIdMismatch();
        if (block.timestamp > intent.deadline) revert IntentExpired();

        bytes32 intentHash = hashIntent(intent);
        if (escrowActive[intentHash] || intentExecuted[intentHash]) revert IntentAlreadySolved();

        escrowActive[intentHash] = true;

        bool success = IERC20(intent.inputToken).transferFrom(
            intent.user,
            address(this),
            intent.inputAmount
        );
        if (!success) revert TransferFailed();

        emit IntentEscrowed(intentHash, intent.user, intent.inputAmount);
    }

    /**
     * @notice Settles an intent on the Destination Chain. Executed by an Autonomous Solver.
     * @param intent The complete Intent data.
     * @param actualOutputAmount The exact token amount sent to recipient, must be >= minOutputAmount.
     */
    function executeSettlement(
        OrderIntent calldata intent,
        uint256 actualOutputAmount
    ) external nonReentrant {
        if (block.chainid != intent.destinationChainId) revert ChainIdMismatch();
        if (block.timestamp > intent.deadline) revert IntentExpired();
        if (actualOutputAmount < intent.minOutputAmount) revert SlippageExceeded();

        bytes32 intentHash = hashIntent(intent);
        if (intentExecuted[intentHash]) revert IntentAlreadySolved();

        intentExecuted[intentHash] = true;

        // Solver funds the recipient directly using liquidity on this chain
        bool success = IERC20(intent.outputToken).transferFrom(
            msg.sender,
            intent.recipient,
            actualOutputAmount
        );
        if (!success) revert TransferFailed();

        emit IntentSettled(intentHash, msg.sender, intent.recipient, actualOutputAmount);
    }

    /**
     * @notice Releases escrowed funds on the Origin Chain to the Solver upon proof receipt.
     * @dev In production, this call must be gated by a cross-chain verification middleware (e.g., CCIP Receiver).
     */
    function releaseEscrowToSolver(
        OrderIntent calldata intent,
        address solver
    ) external nonReentrant {
        if (block.chainid != intent.originChainId) revert ChainIdMismatch();

        bytes32 intentHash = hashIntent(intent);
        if (!escrowActive[intentHash]) revert EscrowNotFound();

        escrowActive[intentHash] = false;
        intentExecuted[intentHash] = true;

        bool success = IERC20(intent.inputToken).transfer(solver, intent.inputAmount);
        if (!success) revert TransferFailed();

        emit SettlementProven(intentHash, solver);
    }
}
```

#### 2. Solver Engine: `solverAgent.ts`

```typescript
import { 
    createPublicClient, 
    createWalletClient, 
    http, 
    keccak256, 
    encodeAbiParameters, 
    parseAbiParameters,
    Address, 
    Hex, 
    formatUnits
} from "viem";
import { privateKeyToAccount } from "viem/accounts";
import { arbitrum, optimism } from "viem/chains";

// ABI Fragment for Intent Contract
const INTENT_SETTLER_ABI = [
    {
        name: "executeSettlement",
        type: "function",
        stateMutability: "nonpayable",
        inputs: [
            {
                name: "intent",
                type: "tuple",
                components: [
                    { name: "user", type: "address" },
                    { name: "originChainId", type: "uint256" },
                    { name: "destinationChainId", type: "uint256" },
                    { name: "inputToken", type: "address" },
                    { name: "outputToken", type: "address" },
                    { name: "inputAmount", type: "uint256" },
                    { name: "minOutputAmount", type: "uint256" },
                    { name: "recipient", type: "address" },
                    { name: "nonce", type: "uint256" },
                    { name: "deadline", type: "uint256" }
                ]
            },
            { name: "actualOutputAmount", type: "uint256" }
        ],
        outputs: []
    },
    {
        name: "intentExecuted",
        type: "function",
        stateMutability: "view",
        inputs: [{ name: "intentHash", type: "bytes32" }],
        outputs: [{ name: "", type: "bool" }]
    }
] as const;

export interface CrossChainIntent {
    user: Address;
    originChainId: bigint;
    destinationChainId: bigint;
    inputToken: Address;
    outputToken: Address;
    inputAmount: bigint;
    minOutputAmount: bigint;
    recipient: Address;
    nonce: bigint;
    deadline: bigint;
}

export class AutonomousSolverEngine {
    private account;
    private destPublicClient;
    private destWalletClient;
    private contractAddress: Address;
    private isRunning: boolean = false;

    constructor(
        privateKey: Hex, 
        destRpcUrl: string, 
        contractAddress: Address
    ) {
        this.account = privateKeyToAccount(privateKey);
        this.contractAddress = contractAddress;

        this.destPublicClient = createPublicClient({
            chain: optimism,
            transport: http(destRpcUrl)
        });

        this.destWalletClient = createWalletClient({
            account: this.account,
            chain: optimism,
            transport: http(destRpcUrl)
        });
    }

    public calculateIntentHash(intent: CrossChainIntent): Hex {
        const typeHash = keccak256(
            Buffer.from(
                "OrderIntent(address user,uint256 originChainId,uint256 destinationChainId,address inputToken,address outputToken,uint256 inputAmount,uint256 minOutputAmount,address recipient,uint256 nonce,uint256 deadline)"
            )
        );

        return keccak256(
            encodeAbiParameters(
                parseAbiParameters(
                    "bytes32, address, uint256, uint256, address, address, uint256, uint256, address, uint256, uint256"
                ),
                [
                    typeHash,
                    intent.user,
                    intent.originChainId,
                    intent.destinationChainId,
                    intent.inputToken,
                    intent.outputToken,
                    intent.inputAmount,
                    intent.minOutputAmount,
                    intent.recipient,
                    intent.nonce,
                    intent.deadline
                ]
            )
        );
    }

    /**
     * Agent heuristic evaluation for liquidity profitability
     */
    public async evaluateProfitability(intent: CrossChainIntent): Promise<boolean> {
        const currentTime = BigInt(Math.floor(Date.now() / 1000));
        if (intent.deadline <= currentTime) {
            console.warn(`[AGENT] Intent discarded: Expired deadline.`);
            return false;
        }

        // Mock heuristic: Real systems inspect off-chain orderbook pricing / pool reserves
        // Assume Solver requires 0.35% minimum spread to cover bridge capital lock-up & gas
        const expectedExchangeRate = 1.0035; 
        const nominalRatio = Number(intent.inputAmount) / Number(intent.minOutputAmount);

        if (nominalRatio >= expectedExchangeRate) {
            console.log(`[AGENT] Profitable intent detected. Ratio: ${nominalRatio.toFixed(4)}`);
            return true;
        }

        console.log(`[AGENT] Unprofitable intent. Margin insufficient.`);
        return false;
    }

    public async processIntent(intent: CrossChainIntent): Promise<Hex | null> {
        try {
            const intentHash = this.calculateIntentHash(intent);
            
            // Step 1: Pre-flight state verification
            const alreadyExecuted = await this.destPublicClient.readContract({
                address: this.contractAddress,
                abi: INTENT_SETTLER_ABI,
                functionName: "intentExecuted",
                args: [intentHash]
            });

            if (alreadyExecuted) {
                console.warn(`[AGENT] Intent ${intentHash} has already been filled.`);
                return null;
            }

            // Step 2: Risk and Yield Model
            const isViable = await this.evaluateProfitability(intent);
            if (!isViable) return null;

            // Step 3: Transaction Execution on Destination Chain
            console.log(`[AGENT] Submitting settlement on destination chain for user ${intent.recipient}...`);
            const txHash = await this.destWalletClient.writeContract({
                address: this.contractAddress,
                abi: INTENT_SETTLER_ABI,
                functionName: "executeSettlement",
                args: [intent, intent.minOutputAmount]
            });

            console.log(`[AGENT] Settlement tx submitted: ${txHash}`);
            
            const receipt = await this.destPublicClient.waitForTransactionReceipt({ hash: txHash });
            if (receipt.status === "success") {
                console.log(`[AGENT] Settlement confirmed in block ${receipt.blockNumber}`);
                return txHash;
            } else {
                throw new Error("Transaction execution reverted on-chain.");
            }
        } catch (error) {
            console.error(`[AGENT ERROR] Failed to process intent:`, error);
            return null;
        }
    }
}
```

---

### 7. Edge Cases & Failure Modes

1. **Chain Reorganizations (Deep Reorgs)**:
   - *Failure*: Solver mengisi pesanan di Destination Chain, namun transaksi escrow pengguna di Source Chain dibatalkan akibat 2-block atau 64-block reorganization.
   - *Mitigasi*: Solver harus menerapkan model *dynamic finality tracking*. Transaksi hanya dianggap valid setelah melewati parameter $k$-konfirmasi (misal: 64 blok di Ethereum, *safe head* di Optimism).

2. **Toxic Front-Running & Bridge Latency Race**:
   - *Failure*: Dua agen mencoba menyelesaikan intent yang sama secara serentak di Destination Chain. Agen yang kalah kehilangan gas fee transaksi revert (*gas bleeding*).
   - *Mitigasi*: Penggunaan *private relays* (contoh: Flashbots Protect) atau *Dutch Auction bidding windows* di mana hak eksekusi dialokasikan secara deterministik untuk rentang blok tertentu.

3. **Oracle L2 Sequencer Downtime**:
   - *Failure*: L2 Sequencer rantai tujuan *down* setelah dana di-escrow pada rantai asal. Deadline intent terlewati, dan Solver gagal mengirim likuiditas tepat waktu.
   - *Mitigasi*: Penerapan mekanisme *Circuit Breaker* dan fallback timelock darurat. Pengguna memiliki wewenang membatalkan intent (*cancellation reclaim*) setelah `block.timestamp > intent.deadline + GRACE_PERIOD`.

---

### 8. Trade-offs & Alternatif Solusi

| Parameter Desain | Lock-and-Mint Bridges | Canonical Messaging (Burn-Mint) | Intent-Based Fillers (Model Terpilih) |
| :--- | :--- | :--- | :--- |
| **Latensi Eksekusi** | Tinggi (15-60 menit tergantung layer finality) | Sedang (Tergantung settlement rollup) | **Ultra Rendah** (Sub-detik hingga hitungan detik) |
| **Efisiensi Modal** | Rendah (Likuiditas terkunci pasif pada bridge) | Tinggi (Native supply bergerak lintas rantai) | **Tinggi** (Likuiditas solver aktif berputar cepat) |
| **Kompleksitas Off-chain**| Nol (User menunggu relay otomatis) | Rendah (Otomatis via protocol relayer) | **Tinggi** (Membutuhkan Solver Bot, monitoring mempool) |
| **Vektor Serangan** | Kritis: Pembobolan brankas escrow utama | Kritis: Kerentanan minting bug token canonical | **Terisolasi**: Solver menanggung risiko modal personal |

---

### 9. Best Practices & Standar Industri

1. **Permit2 Protocol Integration**: Alih-alih `approve()` konvensional yang memboroskan gas dan memicu risiko *unlimited allowance*, gunakan Uniswap Permit2 (`permitTransferFrom`) dengan tanda tangan bertanda waktu pendek.
2. **Defensive Callbacks Protection**: Selalu terapkan pola *Checks-Effects-Interactions* ketat pada settlement functions guna mencegah *cross-chain reentrancy attacks* ketika berinteraksi dengan token arbitrary (ERC-777 atau callback hook tokens).
3. **Strict Domain Validation**: Pisahkan `DOMAIN_SEPARATOR` secara statis per `block.chainid` aktual untuk menghindari serangan tanda tangan duplikat (*cross-network signature replay*).
4. **Invariant Testing via Formal Tools**: Validasi matematika konservasi likuiditas:
   $$\sum \text{Balance}_{\text{Vault}} \ge \sum \text{Escrow}_{\text{Active}}$$
   Gunakan pengujian fuzzing properti (*Foundry Echidna/Medusa*) untuk memverifikasi bahwa total modal terkunci selalu ekuivalen dengan total intent terbuka.

---

### 10. Hands-on Lab Exercise

#### Skenario:
Simulasikan Autonomous Solver yang memproses Cross-Chain Intent di mana modal pengguna berada di Arbitrum (Source) dan dieksekusi di Optimism (Destination) menggunakan node simulasi lokal (Foundry Anvil).

#### Langkah-langkah:

1. **Inisialisasi Lingkungan**:
   Jalankan node lokal Anvil untuk mensimulasikan dua rantai:
   ```bash
   anvil --port 8545 --chain-id 42161 & # Simulated Arbitrum
   anvil --port 8546 --chain-id 10 &    # Simulated Optimism
   ```

2. **Kompilasi & Deployment Kontrak**:
   Deploy `IntentCrossChainSettler.sol` pada kedua rantai lokal. Catat alamat kontrak yang dihasilkan.

3. **Inisiasi Intent Escrow**:
   Kirimkan transaksi `openIntentEscrow` pada chain 42161 dari dompet pengguna, dengan detail target rantai tujuan 10.

4. **Konfigurasi dan Eksekusi Script Agent**:
   Buat file `runSolver.ts`, impor kelas `AutonomousSolverEngine`, isi variabel `privateKey` solver, dan delegasikan eksekusi pemenuhan likuiditas:
   ```typescript
   import { AutonomousSolverEngine, CrossChainIntent } from "./solverAgent";

   async function main() {
       const solver = new AutonomousSolverEngine(
           "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80", // Anvil 0 default key
           "http://127.0.0.1:8546",
           "0x5FbDB2315678afecb367f032d93F642f64180aa3" // Local Contract Address
       );

       const sampleIntent: CrossChainIntent = {
           user: "0x70997970C51812dc3A010C7d01b50e0d17dc79C8",
           originChainId: 8545n,
           destinationChainId: 10n,
           inputToken: "0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512",
           outputToken: "0x9fE46736679d2D9a65F0992F2272dE9f3c7fa6e0",
           inputAmount: 1000000000000000000n, // 1.0 Input
           minOutputAmount: 990000000000000000n, // 0.99 Output
           recipient: "0x70997970C51812dc3A010C7d01b50e0d17dc79C8",
           nonce: 1n,
           deadline: BigInt(Math.floor(Date.now() / 1000) + 3600)
       };

       const txHash = await solver.processIntent(sampleIntent);
       console.log("Lab Execution Complete. Result Tx:", txHash);
   }

   main();
   ```

5. **Verifikasi State**:
   Jalankan query call via RPC `cast call <DEST_CONTRACT> "intentExecuted(bytes32)" <INTENT_HASH>` pada port 8546 dan konfirmasi nilai return bernilai `true` (`0x0000000000000000000000000000000000000000000000000000000000000001`). Periksa bahwa saldo akun pengguna telah bertambah secara akurat.