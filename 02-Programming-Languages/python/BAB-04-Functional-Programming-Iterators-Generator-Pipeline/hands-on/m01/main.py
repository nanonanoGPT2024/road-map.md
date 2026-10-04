from collections.abc import Generator, Iterable, Iterator
from dataclasses import dataclass
import hashlib
import json
import logging
import sys
from typing import Final, Optional

# Setup Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("AuditEngine")

AUDIT_THRESHOLD: Final[float] = 10_000.00

@dataclass(frozen=True, slots=True)
class LogPayload:
    """Struktur data immutable dengan performa tinggi & footprint memori rendah."""
    timestamp: str
    ip_address: str
    status_code: int
    amount: float
    raw_hash: str


def raw_log_reader(file_path: str) -> Generator[str, None, None]:
    """Lazy file reader: membaca file baris demi baris tanpa alokasi eager."""
    logger.info(f"Membuka stream berkas audit: {file_path}")
    try:
        with open(file_path, mode="r", encoding="utf-8") as file_handle:
            for line_no, line in enumerate(file_handle, start=1):
                clean_line = line.strip()
                if clean_line:  # Abaikan baris kosong
                    yield clean_line
    except FileNotFoundError:
        logger.error(f"File log audit tidak ditemukan: {file_path}")
        raise
    except OSError as err:
        logger.critical(f"I/O error saat membaca {file_path}: {err}")
        raise


def json_deserializer(stream: Iterable[str]) -> Generator[dict, None, None]:
    """Parsing string JSON Lines menjadi dictionary secara lazy dengan penanganan galat."""
    for raw_string in stream:
        try:
            parsed_data = json.loads(raw_string)
            yield parsed_data
        except json.JSONDecodeError as err:
            logger.warning(f"Melewati record korup: {raw_string[:50]}... Error: {err}")
            continue


def record_transformer(stream: Iterable[dict]) -> Generator[LogPayload, None, None]:
    """Transformasi dictionary mentah ke immutable domain model ber-tipe data statis."""
    for record in stream:
        try:
            payload = LogPayload(
                timestamp=record["timestamp"],
                ip_address=record["ip_address"],
                status_code=int(record["status_code"]),
                amount=float(record.get("amount", 0.0)),
                raw_hash=hashlib.sha256(json.dumps(record, sort_keys=True).encode("utf-8")).hexdigest()
            )
            yield payload
        except (KeyError, ValueError) as err:
            logger.warning(f"Skema log invalid: {record}. Error: {err}")
            continue


def suspicious_activity_filter(stream: Iterable[LogPayload]) -> Generator[LogPayload, None, None]:
    """Pure business logic filter: HTTP 401/403 dengan amount signifikan."""
    for payload in stream:
        if payload.status_code in (401, 403) and payload.amount >= AUDIT_THRESHOLD:
            yield payload


def audit_alert_sink(stream: Iterable[LogPayload]) -> int:
    """Consumer terminal stage: Mengonsumsi stream akhir dan memicu aksi analitik."""
    processed_alerts = 0
    for anomaly in stream:
        processed_alerts += 1
        # Mengirim alert ke SIEM / Security Operations Center
        logger.warning(
            f"SECURITY ALERT [{processed_alerts}] | IP: {anomaly.ip_address} | "
            f"Code: {anomaly.status_code} | Amount: ${anomaly.amount:,.2f} | "
            f"Hash: {anomaly.raw_hash[:8]}..."
        )
    return processed_alerts


# ============================================================================
# Driver Execution Pipeline Orchestrator
# ============================================================================
def execute_pipeline(log_file_path: str) -> None:
    """Merakit dan mengeksekusi pipeline stream processing."""
    # Pipeline composition: Deklarasi jalur aliran data
    # Evaluasi BELUM terjadi di sini (Zero Execution Overhead)
    file_stream = raw_log_reader(log_file_path)
    dict_stream = json_deserializer(file_stream)
    payload_stream = record_transformer(dict_stream)
    filtered_stream = suspicious_activity_filter(payload_stream)

    # Eksekusi ditarik secara lazy oleh sink terminal
    logger.info("Memulai pemrosesan transaksi...")
    total_anomalies = audit_alert_sink(filtered_stream)
    logger.info(f"Selesai. Total anomali mencurigakan terdeteksi: {total_anomalies}")


if __name__ == "__main__":
    import tempfile
    
    # Mock data generator untuk testing runtime
    with tempfile.NamedTemporaryFile("w+", delete=False, encoding="utf-8") as temp_log:
        temp_log.write('{"timestamp": "2026-03-31T01:00:00Z", "ip_address": "192.168.1.10", "status_code": 200, "amount": 150.0}\n')
        temp_log.write('{"timestamp": "2026-03-31T01:00:01Z", "ip_address": "10.0.0.99", "status_code": 401, "amount": 1250000.0}\n') # Anomali
        temp_log.write('{"timestamp": "2026-03-31T01:00:02Z", "ip_address": "10.0.0.99", "status_code": 403, "amount": 900.0}\n')     # Normal (< threshold)
        temp_log.write('CORRUPT_JSON_DATA_STREAM\n')                                                                                   # Korup
        temp_log.write('{"timestamp": "2026-03-31T01:00:03Z", "ip_address": "172.16.0.4", "status_code": 403, "amount": 45000.0}\n')   # Anomali
        temp_log_path = temp_log.name

    execute_pipeline(temp_log_path)
