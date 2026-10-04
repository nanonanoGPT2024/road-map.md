#!/usr/bin/env python3
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Any, Generic, TypeGuard, TypeVar

# ============================================================================
# 1. CORE DOMAIN TYPES & STRUCTURAL PROTOCOLS
# ============================================================================

@dataclass(frozen=True)
class TransactionAuthorizedEvent:
    transaction_id: str
    account_id: str
    amount_cents: int
    currency: str

@dataclass(frozen=True)
class FraudSuspectedEvent:
    transaction_id: str
    risk_score: float
    flag_reasons: tuple[str, ...]

T_Event = TypeVar("T_Event", covariant=True)

class EventEnvelope(Generic[T_Event]):
    """Immutable envelope dengan covariant event data."""
    def __init__(self, trace_id: str, event_data: T_Event) -> None:
        self._trace_id = trace_id
        self._event_data = event_data

    @property
    def trace_id(self) -> str:
        return self._trace_id

    @property
    def payload(self) -> T_Event:
        return self._event_data

# ============================================================================
# 2. TYPE NARROWING GUARDS (RUNTIME-TO-STATIC BOUNDARY)
# ============================================================================

def is_authorized_event_dict(payload: dict[str, Any]) -> TypeGuard[dict[str, Any]]:
    """
    Validasi runtime untuk memastikan data mentah memiliki
    skema kunci yang benar untuk TransactionAuthorizedEvent.
    """
    required_keys = {"transaction_id", "account_id", "amount_cents", "currency"}
    if not required_keys.issubset(payload.keys()):
        return False
    return (
        isinstance(payload["transaction_id"], str)
        and isinstance(payload["account_id"], str)
        and isinstance(payload["amount_cents"], int)
        and isinstance(payload["currency"], str)
    )

def parse_authorized_event(raw_data: dict[str, Any]) -> TransactionAuthorizedEvent:
    if not is_authorized_event_dict(raw_data):
        raise ValueError(f"Schema violation for raw payload: {raw_data}")
    
    # Static Analyzer mengetahui data sudah tervalidasi
    return TransactionAuthorizedEvent(
        transaction_id=raw_data["transaction_id"],
        account_id=raw_data["account_id"],
        amount_cents=raw_data["amount_cents"],
        currency=raw_data["currency"]
    )

# ============================================================================
# 3. HIGH-PERFORMANCE TYPE-SAFE EVENT BUS
# ============================================================================

E_contra = TypeVar("E_contra", contravariant=True)

class EventHandler(Generic[E_contra]):
    """Handler contravariant: siap menerima event atau supertipe event tersebut."""
    async def handle(self, envelope: EventEnvelope[E_contra]) -> None:
        raise NotImplementedError

class LedgerPostingHandler(EventHandler[TransactionAuthorizedEvent]):
    async def handle(self, envelope: EventEnvelope[TransactionAuthorizedEvent]) -> None:
        txn = envelope.payload
        print(
            f"[LEDGER] [Trace: {envelope.trace_id}] Posting {txn.amount_cents} {txn.currency} "
            f"to Account: {txn.account_id} for Txn: {txn.transaction_id}"
        )

class UniversalAuditHandler(EventHandler[object]):
    """Handler universal: Menerima sembarang object event via contravariance."""
    async def handle(self, envelope: EventEnvelope[object]) -> None:
        print(f"[AUDIT LOG] [Trace: {envelope.trace_id}] Type: {type(envelope.payload).__name__}")

# ============================================================================
# 4. DISPATCH ENGINE PIPELINE
# ============================================================================

class EventBus:
    def __init__(self) -> None:
        self._handlers: dict[type[Any], list[Callable[[EventEnvelope[Any]], Awaitable[None]]]] = {}

    def register_handler(
        self,
        event_type: type[T_Event],
        handler: Callable[[EventEnvelope[T_Event]], Awaitable[None]]
    ) -> None:
        self._handlers.setdefault(event_type, []).append(handler)

    async def publish(self, envelope: EventEnvelope[Any]) -> None:
        event_cls = type(envelope.payload)
        registered = self._handlers.get(event_cls, [])
        if not registered:
            print(f"[BUS] Warning: No direct handler registered for {event_cls.__name__}")
            return
        
        # Eksekusi konkurensi aman
        await asyncio.gather(*(h(envelope) for h in registered))

# ============================================================================
# 5. INTEGRATION TEST EXECUTION
# ============================================================================

async def main() -> None:
    bus = EventBus()
    ledger_handler = LedgerPostingHandler()
    audit_handler = UniversalAuditHandler()

    # Registrasi Type-Safe
    bus.register_handler(TransactionAuthorizedEvent, ledger_handler.handle)
    bus.register_handler(TransactionAuthorizedEvent, audit_handler.handle)

    # Ingestion Payload mentah dari Gateway Eksternal
    raw_incoming_network_payload: dict[str, Any] = {
        "transaction_id": "tx_99824219",
        "account_id": "acc_corporate_01",
        "amount_cents": 5000000,
        "currency": "EUR"
    }

    # Transformasi boundary melalui TypeGuard
    clean_event = parse_authorized_event(raw_incoming_network_payload)
    envelope = EventEnvelope(trace_id="req-trace-uuid-8899", event_data=clean_event)

    # Pipeline Processing
    await bus.publish(envelope)

if __name__ == "__main__":
    asyncio.run(main())
