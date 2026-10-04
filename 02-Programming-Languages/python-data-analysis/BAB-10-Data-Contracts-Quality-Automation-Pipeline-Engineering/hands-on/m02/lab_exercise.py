#!/usr/bin/env python3
"""
Lab Hands-on: Data Contracts, Quality Automation, & Pipeline Engineering
Topic: python-data-analysis | Module 02 Deep Dive

Simulates an enterprise-grade automated data pipeline with:
1. Strict Data Contract Enforcement (Schema types, semantic rules, SLAs).
2. Quality Automation Engine (Nullability, boundary conditions, regex formats).
3. Circuit-Breaker & Dead Letter Queue (DLQ) Routing for non-conforming data.
4. Metric Telemetry & Automated Quality Audit Reporting.
"""

import json
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

# --- ANSI Terminal Styling ---
RESET = "\033[0m"
BOLD = "\033[1m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
WHITE = "\033[37m"


@dataclass
class ContractViolation:
    """Represents a violation against the defined Data Contract."""
    record_id: str
    field_name: str
    violation_type: str
    actual_value: Any
    expected_rule: str
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class FieldConstraint:
    """Metadata constraints attached to individual schema fields."""
    expected_type: type
    required: bool = True
    nullable: bool = False
    custom_validator: Optional[Callable[[Any], bool]] = None
    validator_description: Optional[str] = None


class DataContract:
    """
    Formal Data Contract specification ensuring producer-consumer alignment.
    Encapsulates schema, constraints, and operational SLAs.
    """
    def __init__(self, contract_name: str, version: str):
        self.contract_name = contract_name
        self.version = version
        self.schema: Dict[str, FieldConstraint] = {}
        self.max_allowed_error_rate: float = 0.20  # Circuit breaker threshold (20%)

    def add_field(
        self,
        name: str,
        expected_type: type,
        required: bool = True,
        nullable: bool = False,
        validator: Optional[Callable[[Any], bool]] = None,
        validator_desc: Optional[str] = None
    ) -> "DataContract":
        """Builder method to register a contractual field constraint."""
        self.schema[name] = FieldConstraint(
            expected_type=expected_type,
            required=required,
            nullable=nullable,
            custom_validator=validator,
            validator_description=validator_desc
        )
        return self


class DataQualityEngine:
    """Automates quality validation rules against incoming ingestion batches."""
    def __init__(self, contract: DataContract):
        self.contract = contract

    def validate_record(self, record: Dict[str, Any], record_id_key: str = "event_id") -> List[ContractViolation]:
        """Validates a single record against the active data contract."""
        violations = []
        rec_id = str(record.get(record_id_key, "UNKNOWN_ID"))

        for field_name, constraint in self.contract.schema.items():
            # Check field presence
            if field_name not in record:
                if constraint.required:
                    violations.append(ContractViolation(
                        record_id=rec_id,
                        field_name=field_name,
                        violation_type="MISSING_REQUIRED_FIELD",
                        actual_value=None,
                        expected_rule="Field must be present in payload"
                    ))
                continue

            val = record[field_name]

            # Check nullability
            if val is None:
                if not constraint.nullable:
                    violations.append(ContractViolation(
                        record_id=rec_id,
                        field_name=field_name,
                        violation_type="UNEXPECTED_NULL",
                        actual_value=val,
                        expected_rule="Field is not nullable"
                    ))
                continue

            # Check data type
            if not isinstance(val, constraint.expected_type):
                violations.append(ContractViolation(
                    record_id=rec_id,
                    field_name=field_name,
                    violation_type="TYPE_MISMATCH",
                    actual_value=type(val).__name__,
                    expected_rule=f"Type must be {constraint.expected_type.__name__}"
                ))
                continue

            # Custom domain validation rules
            if constraint.custom_validator and not constraint.custom_validator(val):
                violations.append(ContractViolation(
                    record_id=rec_id,
                    field_name=field_name,
                    violation_type="SEMANTIC_ASSERTION_FAILED",
                    actual_value=val,
                    expected_rule=constraint.validator_description or "Custom constraint failed"
                ))

        return violations


class PipelineOrchestrator:
    """
    Simulates a resilient real-time streaming/batch pipeline stage.
    Applies quality checks, separates clean sink from Dead-Letter Queue (DLQ),
    and trips circuit breakers if contract violation rates exceed thresholds.
    """
    def __init__(self, engine: DataQualityEngine):
        self.engine = engine
        self.clean_sink: List[Dict[str, Any]] = []
        self.dead_letter_queue: List[Tuple[Dict[str, Any], List[ContractViolation]]] = []
        self.processed_count = 0

    def process_batch(self, raw_events: List[Dict[str, Any]]) -> None:
        """Executes ingestion, quality routing, and threshold checks."""
        print(f"\n{BOLD}{CYAN}=== PIPELINE EXECUTION INITIATED: {self.engine.contract.contract_name} ({self.engine.contract.version}) ==={RESET}")
        start_time = time.perf_counter()

        for event in raw_events:
            self.processed_count += 1
            violations = self.engine.validate_record(event)

            if not violations:
                self.clean_sink.append(event)
            else:
                self.dead_letter_queue.append((event, violations))

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        self._generate_audit_report(elapsed_ms)

    def _generate_audit_report(self, elapsed_ms: float) -> None:
        """Outputs structured telemetry and audits data health metrics."""
        total = self.processed_count
        clean = len(self.clean_sink)
        quarantined = len(self.dead_letter_queue)
        error_rate = (quarantined / total) if total > 0 else 0.0

        print(f"\n{BOLD}{MAGENTA}[Pipeline Quality Metrics Summary]{RESET}")
        print(f"Total Processed   : {WHITE}{total}{RESET}")
        print(f"Validated Clean   : {GREEN}{clean}{RESET}")
        print(f"DLQ Quarantined   : {RED}{quarantined}{RESET}")
        print(f"Error Rate        : {YELLOW if error_rate <= self.engine.contract.max_allowed_error_rate else RED}{error_rate:.2%}{RESET}")
        print(f"Execution Latency : {CYAN}{elapsed_ms:.2f} ms{RESET}")

        if quarantined > 0:
            print(f"\n{BOLD}{YELLOW}--- Dead-Letter Queue (DLQ) Diagnostic Inspection ---{RESET}")
            for event, violations in self.dead_letter_queue[:3]:
                rec_id = event.get("event_id", "UNKNOWN")
                print(f"Record [{BOLD}{rec_id}{RESET}] dropped into DLQ:")
                for v in violations:
                    print(f"  {RED}✖ [{v.violation_type}]{RESET} Field '{v.field_name}' -> "
                          f"Actual: {YELLOW}{repr(v.actual_value)}{RESET} | Expected: {WHITE}{v.expected_rule}{RESET}")
            if quarantined > 3:
                print(f"  ... and {quarantined - 3} more records quarantined.")

        # Circuit breaker validation
        print(f"\n{BOLD}SLA Circuit-Breaker Status:{RESET} ", end="")
        if error_rate > self.engine.contract.max_allowed_error_rate:
            print(f"{RED}{BOLD}TRIPPED (CIRCUIT OPEN)!{RESET}")
            print(f"{RED}Error rate ({error_rate:.2%}) breached contractual threshold ({self.engine.contract.max_allowed_error_rate:.2%}). "
                  f"Halting downstream sync to prevent data lake poisoning.{RESET}")
        else:
            print(f"{GREEN}{BOLD}PASSED (CIRCUIT CLOSED){RESET}")
            print(f"{GREEN}Pipeline healthy. Downstream analytics sync approved.{RESET}")


def run_lab():
    """Builds contract, generates synthetic real-world data, and tests pipeline resilience."""
    # 1. Setup Data Contract
    contract = DataContract("payment_orders_stream", "v2.1.0")
    contract.max_allowed_error_rate = 0.25  # 25% tolerance

    # Contractual Schema Definitions
    contract.add_field(
        name="event_id",
        expected_type=str,
        required=True,
        nullable=False,
        validator=lambda x: bool(re.match(r"^evt_[a-zA-Z0-9]{8}$", x)),
        validator_desc="Must match pattern 'evt_<alphanumeric_8>'"
    )
    contract.add_field(
        name="account_id",
        expected_type=str,
        required=True,
        nullable=False
    )
    contract.add_field(
        name="amount",
        expected_type=(int, float),
        required=True,
        nullable=False,
        validator=lambda x: 0.01 <= float(x) <= 1_000_000.0,
        validator_desc="Value must be between $0.01 and $1,000,000.00"
    )
    contract.add_field(
        name="currency",
        expected_type=str,
        required=True,
        nullable=False,
        validator=lambda x: x in {"USD", "EUR", "IDR", "SGD"},
        validator_desc="Must be one of ['USD', 'EUR', 'IDR', 'SGD']"
    )
    contract.add_field(
        name="metadata",
        expected_type=dict,
        required=False,
        nullable=True
    )

    # 2. Synthetic Test Payload (Mix of conforming and non-conforming records)
    test_batch = [
        # Valid Records
        {"event_id": "evt_ab12cd34", "account_id": "acc_001", "amount": 250.75, "currency": "USD", "metadata": {"source": "mobile"}},
        {"event_id": "evt_99887766", "account_id": "acc_002", "amount": 15000000.0, "currency": "IDR", "metadata": None},
        {"event_id": "evt_zz11yy22", "account_id": "acc_003", "amount": 42.00, "currency": "EUR"},
        {"event_id": "evt_ff33ee44", "account_id": "acc_004", "amount": 890.10, "currency": "SGD"},
        {"event_id": "evt_bb55aa66", "account_id": "acc_005", "amount": 10.50, "currency": "USD"},
        {"event_id": "evt_cc77dd88", "account_id": "acc_006", "amount": 99.99, "currency": "USD"},
        {"event_id": "evt_ee99aa00", "account_id": "acc_007", "amount": 312.45, "currency": "EUR"},

        # Invalid: Broken regex pattern on ID
        {"event_id": "invalid_id_99", "account_id": "acc_008", "amount": 100.0, "currency": "USD"},
        
        # Invalid: Negative Amount (Domain validation breach)
        {"event_id": "evt_bad00001", "account_id": "acc_009", "amount": -50.0, "currency": "USD"},
        
        # Invalid: Unsupported Currency
        {"event_id": "evt_bad00002", "account_id": "acc_010", "amount": 450.0, "currency": "BITCOIN"},
        
        # Invalid: Missing required field 'amount' & Type mismatch on account_id
        {"event_id": "evt_bad00003", "account_id": 999999, "currency": "USD"}
    ]

    # 3. Instantiate Quality Engine & Pipeline
    quality_engine = DataQualityEngine(contract)
    pipeline = PipelineOrchestrator(quality_engine)

    # 4. Execute Pipeline Ingestion
    pipeline.process_batch(test_batch)


if __name__ == "__main__":
    run_lab()