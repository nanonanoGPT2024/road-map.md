# Bab 09: Enterprise Security, Secrets Management, & Compliance
## Modul 01: Non-Human Identity (NHI), Dynamic Secrets Management, & Zero-Trust Execution Runtime untuk Autonomous Agents

---

### 1. Learning Objectives

Setelah menyelesaikan modul ini, Anda diharapkan mampu:
*   **Merancang & Mengimplementasikan Arsitektur Non-Human Identity (NHI)** untuk autonomous agent menggunakan prinsip *least privilege*, *ephemeral credentialing*, dan mutual TLS (mTLS) atau short-lived cryptographic tokens (OIDC/SPIFFE).
*   **Mengintegrasikan Dynamic Secrets Engine** (HashiCorp Vault / Cloud KMS) ke dalam siklus eksekusi agentic tool, membatasi masa aktif rahasia (*Time-To-Live* / TTL) di bawah 15 menit dengan rotasi otomatis.
*   **Membangun Dynamic Tool Execution Barrier** yang mengisolasi rahasia (*secrets*) dari konteks prompt LLM guna mengeliminasi vektor serangan *Indirect Prompt Injection* yang menargetkan pencurian kredensial.
*   **Mengonfigurasi Audit Trail Kriptografis Immutable** yang mematuhi standar kepatuhan SOC 2 Type II, HIPAA, dan NIST AI RMF (Risk Management Framework) untuk setiap tindakan otonom yang diambil oleh agent.

---

### 2. Concept Overview

Dalam paradigma rekayasa perangkat lunak tradisional, autentikasi dan otorisasi umumnya difokuskan pada identitas manusia (*Human Identities*) melalui SSO, MFA, dan sesi berbasis browser. Namun, ketika *autonomous agents* beroperasi secara mandiri—memanggil API pihak ketiga, mengeksekusi *query* basis data, memanipulasi infrastruktur, dan berkomunikasi dengan agent lain—mereka bertindak sebagai **Non-Human Identities (NHI)** dengan daya rusak (*blast radius*) yang sangat tinggi jika terkompromikan.

```
                    ┌──────────────────────────────────────────────┐
                    │           TRADITIONAL ANTI-PATTERN           │
                    │ LLM Context <──(Has Raw Keys)──> Raw API Key │
                    └──────────────────────┬───────────────────────┘
                                           │ Prompt Injection!
                                           ▼
                                [Leakage via Output]

═══════════════════════════════════════════════════════════════════════════════

                    ┌──────────────────────────────────────────────┐
                    │          ZERO-TRUST NHI MENTAL MODEL         │
                    │                                              │
                    │  ┌───────────┐      Opaque Tool Token        │
                    │  │ LLM Agent │ ───────────────────────────┐  │
                    │  └─────┬─────┘                            │  │
                    │        │ Tool Call (No Secrets)           │  │
                    │        ▼                                  ▼  │
                    │  ┌───────────┐     Dynamic Ephemeral   ┌─────┴────┐
                    │  │ Execution │ <────────────────────── │ Secrets  │
                    │  │  Barrier  │         Vault Lease     │  Broker  │
                    │  └─────┬─────┘                         └──────────┘
                    │        │ Mutual TLS / Scoped Request                 │
                    │        ▼                                             │
                    │  ┌───────────┐                                       │
                    │  │ Upstream  │ (Target Systems: DB, Cloud, External) │
                    │  └───────────┘                                       │
                    └──────────────────────────────────────────────────────┘
```

#### Mental Model: The Secret-Blind Agent
Agent tidak boleh mengetahui rahasia (API key, database password, cloud token). Agent hanya boleh mengetahui **referensi ke tindakan** (*capability reference*) dan token eksekusi sementara (*opaque capability ticket*). Rahasia diinjeksikan secara *just-in-time* (JIT) oleh lapisan runtime terisolasi (*Execution Barrier*) sesaat sebelum transmisi jaringan ke upstream service, lalu langsung dibersihkan dari memori (*zeroization*).

---

### 3. Why It Matters

1.  **Vulnerabilitas Prompt Injection (OWASP LLM01 & LLM02):**
    Jika agent memegang `OPENAI_API_KEY`, `AWS_SECRET_ACCESS_KEY`, atau `STRIPE_API_KEY` di *system prompt* atau *in-memory environment variables*, penyerang dapat memanipulasi input teks (misal: memproses email phising atau data web scraping berbahaya) untuk memaksa LLM mencetak kredensial tersebut ke respons output.
2.  **Stateless Ephemerality vs. State-holding Agents:**
    Pola *vibe-coding* sering kali mengandalkan `.env` lokal atau static secrets yang disalin langsung ke pipeline container. Jika sebuah node runtime agent terkompromikan, penyerang mendapatkan akses persisten tak terbatas (*unbounded persistence*).
3.  **Compliance Non-Negotiables:**
    SOC 2 Trust Services Criteria (CC6.1, CC6.3) dan ISO/IEC 27001 mewajibkan *least privilege*, pemisahan tugas (*separation of duties*), dan *revocability*. Menjalankan autonomous agent dengan kredensial statis multi-tenant membatalkan sertifikasi kepatuhan enterprise.

---

### 4. Arsitektur & Diagram Komponen

Diagram berikut mengilustrasikan alur Zero-Trust Secrets Brokering untuk Autonomous Agents:

```
+---------------------------------------------------------------------------------------------------------+
|                                    ENTERPRISE ZERO-TRUST RUNTIME                                        |
|                                                                                                         |
|  +--------------------+             1. Generate Plan (Tool & Params)             +-------------------+  |
|  |                    | -------------------------------------------------------> |                   |  |
|  |     LLM Core       |                                                          |  Security Policy  |  |
|  |   (Orchestrator)   | <------------------------------------------------------- |    PDP / OPA      |  |
|  |                    |             2. Policy Check Validated Ticket             +-------------------+  |
|  +--------------------+                                                                    |            |
|            |                                                                               |            |
|            | 3. Submit Intent (Opaque Ticket + Payload)                                    | Authorizes |
|            v                                                                               v            |
|  +---------------------------------------------------------------------------------------------------+  |
|  |                                    EXECUTION BARRIER (Isolated Node)                              |  |
|  |                                                                                                   |  |
|  |  +---------------------+   4. Request JIT Credential   +--------------------+                     |  |
|  |  |                     | ----------------------------> |                    |                     |  |
|  |  | Dynamic Credential  |                               |  HashiCorp Vault / |                     |  |
|  |  |      Broker         | <---------------------------- |     Cloud KMS      |                     |  |
|  |  +---------------------+   5. Ephemeral Lease (TTL=5m) +--------------------+                     |  |
|  |            |                                                                                      |  |
|  |            | 6. Attach Credential & Execute Request                                               |  |
|  |            v                                                                                      |  |
|  |  +---------------------+                             +----------------------+                     |  |
|  |  | HTTP / Tool Client  | --------------------------> | Upstream Enterprise  |                     |  |
|  |  |  (mTLS, Zeroized)   |                             | Systems (SQL, APIs)  |                     |  |
|  |  +---------------------+                             +----------------------+                     |  |
|  |            |                                                    |                                 |  |
|  |            | 7. Sanitize Output (Masking PII/Credentials)       |                                 |  |
|  +------------|----------------------------------------------------|---------------------------------+  |
|               |                                                    |                                    |
|               v                                                    v                                    |
|  +---------------------------------------------------------------------------------------------------+  |
|  |                            CRYPTOGRAPHIC AUDIT LOG BUS (WORM / Kafka)                             |  |
|  |                   HMAC-SHA256 Signed Execution Record + Actor ID + Inputs Hash                    |  |
|  +---------------------------------------------------------------------------------------------------+  |
+---------------------------------------------------------------------------------------------------------+
```

---

### 5. Deep Dive Mekanisme & Prinsip Kerja

#### A. OIDC-based Machine Authentication (Workload Identity)
Daripada menyimpan kredensial statis untuk mengotentikasi runtime agent ke vault, runtime memanfaatkan metadata platform (seperti Kubernetes Service Account Token, AWS IAM Role via Web Identity, atau SPIFFE/SPIRE SVID). Token JWT sementara ini ditukar (*assumed*) ke HashiCorp Vault untuk menghasilkan token client berumur sangat pendek (misal: 60 detik).

#### B. Dynamic Secrets Generation Engine
Setiap kali agent membutuhkan akses ke sumber daya eksternal (misal: PostgreSQL database), broker tidak mengambil password statis. Broker menginstruksikan backend rahasia Vault untuk menghasilkan user basis data unik secara dinamis:
```sql
CREATE ROLE "v-token-agent-xyz-1710000000" WITH LOGIN PASSWORD 'temporary-secret' VALID UNTIL '2026-03-30 12:15:00';
GRANT SELECT ON ALL TABLES IN SCHEMA public TO "v-token-agent-xyz-1710000000";
```
Setelah tugas selesai, atau setelah masa berlaku (TTL) habis, Vault secara otomatis mengeksekusi `REVOKE` dan `DROP ROLE`.

#### C. Memory Zeroization
Dalam runtime Python, string bersifat immutable dan garbage collector tidak langsung menimpa memori fisik tempat string tersebut berada. Untuk mengamankan rahasia tingkat tinggi, runtime harus menggunakan *bytearrays* atau *memory-locked buffers* (`mlock`) yang ditulis ulang dengan nilai null bytes (`0x00`) segera setelah payload HTTP didelegasikan ke socket kernel.

#### D. Non-Reversible Output Sanitization
Sebelum hasil eksekusi dikembalikan ke LLM Core, output melewati *Deductive Regex Engine* dan *Shannon Entropy Analyzer* untuk mendeteksi apakah upstream payload secara tidak sengaja mengembalikan token otentikasi, session cookies, atau PII (Personally Identifiable Information).

---

### 6. Production-Ready Code Implementation

Berikut adalah implementasi Python 3.12 enterprise-grade yang mengimplementasikan runtime execution barrier, interaksi dynamic secrets via Vault API, memory zeroization, dan immutable auditing.

```python
# architecture/security/agent_vault_runtime.py
from __future__ import annotations

import ctypes
import hashlib
import hmac
import json
import logging
import os
import re
import time
from dataclasses import asdict, dataclass
from typing import Any, Callable, Dict, Optional
import httpx
from pydantic import BaseModel, Field, SecretStr

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("EnterpriseSecurityAgentRuntime")


# ============================================================================
# 1. ENTITY DEFINITIONS & SCHEMAS
# ============================================================================

class ExecutionTicket(BaseModel):
    ticket_id: str
    agent_id: str
    target_tool: str
    action: str
    params: Dict[str, Any]
    issued_at: float = Field(default_factory=time.time)
    expires_at: float


class AuditRecord(BaseModel):
    ticket_id: str
    agent_id: str
    tool: str
    status: str
    request_hash: str
    response_hash: str
    timestamp: float
    signature: str


# ============================================================================
# 2. CRYPTOGRAPHIC ZEROIZATION UTILITY
# ============================================================================

class SecureBuffer:
    """
    Buffer yang menjamin pembersihan memori (zeroization) 
    secara eksplisit menggunakan ctypes setelah scope eksekusi selesai.
    """
    def __init__(self, secret_bytes: bytes):
        self._length = len(secret_bytes)
        self._buffer = (ctypes.c_char * self._length).from_buffer_copy(secret_bytes)

    @property
    def raw(self) -> bytes:
        return bytes(self._buffer)

    def zeroize(self) -> None:
        """Menimpa byte array di memori dengan karakter 0x00."""
        ctypes.memset(ctypes.addressof(self._buffer), 0, self._length)
        self._length = 0

    def __enter__(self) -> "SecureBuffer":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.zeroize()


# ============================================================================
# 3. SECRETS BROKER (VAULT JIT ENGINE)
# ============================================================================

class DynamicSecretsBroker:
    """
    Broker interaksi ke HashiCorp Vault API.
    Menghasilkan dynamic dynamic tokens dengan lease time terikat.
    """
    def __init__(self, vault_url: str, vault_token: SecretStr):
        self.vault_url = vault_url.rstrip("/")
        self._vault_token = vault_token

    async def get_dynamic_database_credentials(self, role: str) -> Dict[str, Any]:
        """
        Membuat ephemeral credential via Vault Dynamic Database Secret Engine.
        TTL default: 5 menit (300s).
        """
        endpoint = f"{self.vault_url}/v1/database/creds/{role}"
        headers = {"X-Vault-Token": self._vault_token.get_secret_value()}

        async with httpx.AsyncClient(timeout=5.0) as client:
            try:
                response = await client.get(endpoint, headers=headers)
                if response.status_code != 200:
                    raise PermissionError(f"Vault authorization failed: {response.text}")
                
                data = response.json()
                return {
                    "username": data["data"]["username"],
                    "password": data["data"]["password"],
                    "lease_id": data["lease_id"],
                    "lease_duration": data["lease_duration"]
                }
            except httpx.RequestError as exc:
                logger.critical(f"Network error communicating with Vault: {str(exc)}")
                raise SystemError("Vault infrastructure unavailable") from exc

    async def revoke_lease(self, lease_id: str) -> None:
        """Secara eksplisit mencabut lease sebelum TTL habis (Eager Revocation)."""
        endpoint = f"{self.vault_url}/v1/sys/leases/revoke"
        headers = {"X-Vault-Token": self._vault_token.get_secret_value()}
        payload = {"lease_id": lease_id}

        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.put(endpoint, headers=headers, json=payload)
            if resp.status_code == 204:
                logger.info(f"Lease {lease_id} successfully revoked.")
            else:
                logger.warning(f"Failed to revoke lease {lease_id}: {resp.text}")


# ============================================================================
# 4. IMMUTABLE AUDITOR
# ============================================================================

class CryptographicAuditor:
    def __init__(self, signing_key: bytes):
        self._key = signing_key

    def record_event(self, ticket: ExecutionTicket, raw_request: str, raw_response: str, status: str) -> AuditRecord:
        req_hash = hashlib.sha256(raw_request.encode()).hexdigest()
        res_hash = hashlib.sha256(raw_response.encode()).hexdigest()
        timestamp = time.time()

        canonical_string = f"{ticket.ticket_id}:{ticket.agent_id}:{ticket.target_tool}:{status}:{req_hash}:{res_hash}:{timestamp}"
        signature = hmac.new(self._key, canonical_string.encode(), hashlib.sha256).hexdigest()

        record = AuditRecord(
            ticket_id=ticket.ticket_id,
            agent_id=ticket.agent_id,
            tool=ticket.target_tool,
            status=status,
            request_hash=req_hash,
            response_hash=res_hash,
            timestamp=timestamp,
            signature=signature
        )

        # Di produksi, pancarkan ke Apache Kafka (WORM compliant sink)
        logger.info(f"[AUDIT LOGGED] {record.model_dump_json()}")
        return record


# ============================================================================
# 5. EXECUTION BARRIER (AGENT RUNTIME ENVIRONMENT)
# ============================================================================

class ZeroTrustExecutionBarrier:
    """
    Boundary runtime yang mengisolasi eksekusi aksi berbahaya dari LLM Context.
    Menerapkan masking, JIT secret fetching, zeroization, dan sanitasi respon.
    """
    SECRET_MASK_PATTERNS = [
        re.compile(r"(bearer\s+)[a-zA-Z0-9_\-\.]{20,}", re.IGNORECASE),
        re.compile(r"(\bpassword\b\s*[:=]\s*)[^\s,]+", re.IGNORECASE),
        re.compile(r"([0-9a-fA-F]{32,64})")  # Raw cryptographic hashes / tokens
    ]

    def __init__(self, secrets_broker: DynamicSecretsBroker, auditor: CryptographicAuditor):
        self.secrets_broker = secrets_broker
        self.auditor = auditor

    def _sanitize_output(self, payload: str) -> str:
        """Menghilangkan jejak token atau kredensial yang bocor dari service hulu."""
        sanitized = payload
        for pattern in self.SECRET_MASK_PATTERNS:
            sanitized = pattern.sub(r"\1[REDACTED_BY_BARRIER]", sanitized)
        return sanitized

    async def execute_tool(self, ticket: ExecutionTicket, execution_logic: Callable[[str, str], Any]) -> Dict[str, Any]:
        """
        Mengeksekusi tool action dengan dynamic JIT credential injection.
        LLM Agent HANYA meneruskan ticket, TIDAK PERNAH memegang password.
        """
        if time.time() > ticket.expires_at:
            raise TimeoutError("Execution ticket expired before invocation.")

        lease_id: Optional[str] = None
        raw_output = ""
        status = "FAILED"

        try:
            # 1. Dapatkan dynamic credentials (JIT)
            credentials = await self.secrets_broker.get_dynamic_database_credentials(
                role=f"agent-{ticket.target_tool}-executor"
            )
            lease_id = credentials["lease_id"]
            username = credentials["username"]
            raw_password = credentials["password"].encode("utf-8")

            # 2. Kunci password di buffer memori yang aman
            with SecureBuffer(raw_password) as secure_pwd:
                # 3. Eksekusi tugas menggunakan payload yang telah diinjeksi kredensial JIT
                logger.info(f"Executing '{ticket.target_tool}' with dynamic NHI '{username}'...")
                
                # Logic dieksekusi dengan melewatkan credential secara aman ke driver
                result = await execution_logic(username, secure_pwd.raw.decode("utf-8"))
                raw_output = json.dumps(result)
                status = "SUCCESS"

        except Exception as exc:
            raw_output = str(exc)
            logger.error(f"Execution failed on tool '{ticket.target_tool}': {raw_output}")
            raise
        finally:
            # 4. Cabut (Revoke) Lease secara eagerly jika telah selesai untuk meminimalisir window exploit
            if lease_id:
                await self.secrets_broker.revoke_lease(lease_id)

            # 5. Catat audit trail yang terverifikasi secara kriptografis
            self.auditor.record_event(
                ticket=ticket,
                raw_request=json.dumps(ticket.params),
                raw_response=raw_output,
                status=status
            )

        # 6. Bersihkan output sebelum dikembalikan ke LLM Context Window
        sanitized_response = self._sanitize_output(raw_output)
        return json.loads(sanitized_response)
```

---

### 7. Edge Cases & Failure Modes

| Edge Case / Failure Scenario | Akar Masalah | Mekanisme Pemulihan / Mitigasi |
| :--- | :--- | :--- |
| **Vault Service Partition (Split-brain)** | Node runtime tidak dapat menjangkau cluster Vault saat validasi dynamic credentials. | Menerapkan *Circuit Breaker* (misal: via `tenacity`). Jika Vault tidak merespons dalam 1.5 detik, eksekusi tool otomatis di-*reject* dengan status `INFRASTRUCTURE_UNAVAILABLE`. **Jangan pernah** beralih (*fallback*) ke static credentials. |
| **Indirect Tool Parameter Tampering** | LLM dimanipulasi melalui context injection untuk menyisipkan SQL Injection atau path traversal pada parameter tool. | Menerapkan Pydantic Strict Parsing dan validasi regex deterministik di level *Execution Barrier* sebelum kredensial dinamis digabungkan ke connection string. |
| **Lease Revocation Storm** | Agent mengeksekusi ratusan tool calls secara masif, membanjiri antrean revocations di Vault. | Menggunakan *Lease Tiering*: Gunakan short-lived generic dynamic leases (TTL 2 menit) dan biarkan background TTL worker Vault membersihkan data secara periodik jika *eager revocation* mengembalikan kode HTTP 429. |
| **Memory Dump Extraction via Core Dump** | Sistem Linux mengeksekusi memory dumping ketika proses agent mengalami segfault, mengekspos isi RAM. | Menggunakan flag kernel `prctl(PR_SET_DUMPABLE, 0)` pada Linux OS di proses inisialisasi runtime untuk memblokir core dumps. |

---

### 8. Trade-offs & Alternatif Solusi

#### Dynamic Secrets (HashiCorp Vault) vs. Centralized KMS Envelope Encryption vs. Static Env Injection

```
                  Complexity / Blast Radius Trade-off
    Low ──────────────────────────────────────────────────► High
Complexity:
    Static .env Variables <  KMS Envelope Decryption  <  Dynamic Vault Leases
Blast Radius:
    Catastrophic (Global) >  Moderate (Key-dependent) >  Minimal (Per-action/5-min)
Compliance:
    Fails SOC 2 / HIPAA   >  Requires Static Secrets  >  SOC 2 / ISO 27001 Native
```

*   **Static Env Injection (`.env`):**
    *   *Kelebihan:* Sangat mudah diimplementasikan, latency 0 ms.
    *   *Kekurangan:* Pelanggaran mutlak pada SOC 2; kebocoran container/prompt injection menghasilkan kompromi total.
*   **KMS Envelope Encryption (AWS KMS / GCP Cloud KMS):**
    *   *Kelebihan:* Mengenkripsi data at rest; payload dienkripsi dengan Data Encryption Key (DEK).
    *   *Kekurangan:* Nilai rahasia plaintext tetap harus hidup di memori runtime agent selama durasi container aktif; tidak membatalkan kredensial secara dinamis di target database.
*   **Dynamic Just-In-Time Leases (Solusi Terpilih):**
    *   *Kelebihan:* Kredensial tidak ada sebelum diminta, hanya valid selama masa TTL (misal 5 menit), diisolasi per-agent dan per-tindakan.
    *   *Kekurangan:* Menambah overhead latency jaringan (50-150ms per tool invocation) dan memperkenalkan ketergantungan ketersediaan tinggi pada sistem Vault.

---

### 9. Best Practices & Standar Industri

1.  **Strict Demarcation of Boundaries:** LLM tidak boleh memiliki konektivitas jaringan langsung ke Vault. Komunikasi hanya dilakukan melalui *Execution Barrier* mediator.
2.  **SPIFFE/SPIRE ID Integration:** Berikan identitas berbasis standar SVID (SPIFFE Verifiable Identity Document) kepada setiap agent container:
    `spiffe://enterprise.internal/ns/agents/sa/financial-auditor-agent`
3.  **WORM (Write Once, Read Many) Audit Logging:** Log yang dihasilkan oleh `CryptographicAuditor` harus disalurkan ke append-only datastore seperti AWS S3 dengan *Object Lock* yang aktif, atau cluster Kafka yang terisolasi.
4.  **Least Privilege Scoping:** Jangan pernah memberikan izin wildcard `*` pada Vault Engine policies. Batasi agent hanya pada path spesifik, contohnya:
    ```hcl
    path "database/creds/agent-readonly-db" {
      capabilities = ["read"]
    }
    ```

---

### 10. Hands-on Lab Exercise

#### Skenario:
Anda ditugaskan mengamankan sistem autonomous agent yang memiliki tool untuk mengambil riwayat transaksi keuangan pelanggan (`customer_db`). Anda harus membangun script validasi lokal yang memverifikasi bahwa:
1. Agent tidak memiliki akses ke database credentials.
2. Token JIT berhasil diambil, digunakan, dan langsung di-revoke.
3. Upstream sensitive data (seperti API key atau plaintext password) tersanitasi dari payload yang dikembalikan ke agent context.

#### Langkah 1: Persiapan Environment
Pasang dependencies yang dibutuhkan:
```bash
pip install httpx pydantic
```

#### Langkah 2: Buat Mock Vault Server & Driver Test
Simpan kode berikut sebagai `lab_security_runtime.py`:

```python
import asyncio
from pydantic import SecretStr
from agent_vault_runtime import (
    DynamicSecretsBroker, 
    CryptographicAuditor, 
    ZeroTrustExecutionBarrier, 
    ExecutionTicket
)

# 1. Mocking Vault Server Responses via HTTPX In-Memory Transport
class MockVaultTransport(httpx.AsyncBaseTransport):
    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "/v1/database/creds/" in url:
            return httpx.Response(
                status_code=200,
                json={
                    "lease_id": "database/creds/agent-db/mock-lease-12345",
                    "lease_duration": 300,
                    "data": {
                        "username": "u_agent_ephemeral_99",
                        "password": "dynamic-super-secure-pass-789"
                    }
                }
            )
        elif "/v1/sys/leases/revoke" in url:
            return httpx.Response(status_code=204)
        return httpx.Response(status_code=404)

# 2. Database Driver Simulasi
async def mock_database_executor(user: str, secret: str) -> dict:
    # Verifikasi kredensial sementara telah disalurkan dengan tepat
    assert user == "u_agent_ephemeral_99"
    assert secret == "dynamic-super-secure-pass-789"
    
    # Menyimulasikan query SQL yang secara tidak sengaja mengembalikan data sensitif
    return {
        "status": "COMPLETED",
        "rows": [
            {"account_id": 101, "balance": 54000.0, "system_auth_token": "bearer abcd1234efgh5678ijkl9012"}
        ]
    }

# 3. Main Test Suite
async def main():
    print("[*] Menginisialisasi Zero-Trust Security Runtime...")
    
    # Setup broker dengan custom transport
    mock_client = httpx.AsyncClient(transport=MockVaultTransport())
    broker = DynamicSecretsBroker(
        vault_url="http://vault.internal:8200", 
        vault_token=SecretStr("s.test-token-value")
    )
    
    # Overwrite instance client Vault dengan transport mock
    httpx.AsyncClient = lambda *args, **kwargs: mock_client

    auditor = CryptographicAuditor(signing_key=b"enterprise-audit-secret-key-101")
    barrier = ZeroTrustExecutionBarrier(secrets_broker=broker, auditor=auditor)

    ticket = ExecutionTicket(
        ticket_id="tkt-tx-99482",
        agent_id="finance-agent-alpha",
        target_tool="financial-db",
        action="QUERY_TRANSACTIONS",
        params={"customer_id": 101},
        expires_at=asyncio.get_event_loop().time() + 60.0
    )

    print("[*] Menjalankan tool call via Execution Barrier...")
    result = await barrier.execute_tool(ticket, mock_database_executor)

    print("\n[+] Eksekusi Berhasil.")
    print("[+] Sanitized Output untuk LLM Agent Context:")
    print(result)

    # Validasi bahwa token upstream berhasil di-redact oleh runtime
    row_data = result["rows"][0]["system_auth_token"]
    assert "REDACTED_BY_BARRIER" in row_data, "FAILED: Kredensial bocor ke LLM Context Window!"
    print("\n[✓] VERIFIKASI KEAMANAN SELESAI: Kredensial berhasil dibersihkan dan diaudit.")

if __name__ == "__main__":
    asyncio.run(main())
```

#### Langkah 3: Eksekusi dan Verifikasi
Jalankan skrip:
```bash
python lab_security_runtime.py
```

Output yang diharapkan:
```text
[*] Menginisialisasi Zero-Trust Security Runtime...
[*] Menjalankan tool call via Execution Barrier...
[INFO] Executing 'financial-db' with dynamic NHI 'u_agent_ephemeral_99'...
[INFO] Lease database/creds/agent-db/mock-lease-12345 successfully revoked.
[INFO] [AUDIT LOGGED] {"ticket_id":"tkt-tx-99482","agent_id":"finance-agent-alpha", ...}

[+] Eksekusi Berhasil.
[+] Sanitized Output untuk LLM Agent Context:
{'status': 'COMPLETED', 'rows': [{'account_id': 101, 'balance': 54000.0, 'system_auth_token': 'bearer [REDACTED_BY_BARRIER]'}]}

[✓] VERIFIKASI KEAMANAN SELESAI: Kredensial berhasil dibersihkan dan diaudit.
```