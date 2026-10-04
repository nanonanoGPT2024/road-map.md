#!/usr/bin/env python3
"""
Incident Commander Workflow Automation Engine
SRE Chapter 06: Incident Lifecycle, On-Call, & Blameless Post-Mortem

Script ini merepresentasikan state machine manajemen insiden skala enterprise:
1. Menerima payload alert telemetri.
2. Mengklasifikasikan severity secara objektif (SEV-1 s/d SEV-4).
3. Mengelola siklus eskalasi on-call (Primary -> Secondary) berbasis SLA timeout.
4. Mencatat kronologi insiden (timeline reconstruction) secara real-time.
5. Menghasilkan artefak Blameless Post-Mortem Markdown secara otomatis.
"""

import sys
import json
import time
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional

# --- DOMAIN MODELS & ENUMS ---

class Severity:
    SEV1 = "SEV-1 (Critical Outage)"
    SEV2 = "SEV-2 (Major Degradation)"
    SEV3 = "SEV-3 (Moderate Impact)"
    SEV4 = "SEV-4 (Minor/Cosmetic)"

class IncidentState:
    TRIGGERED = "TRIGGERED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    MITIGATING = "MITIGATING"
    RESOLVED = "RESOLVED"

# --- CORE ENGINE IMPLEMENTATION ---

class IncidentManagementEngine:
    def __init__(self, oncall_schedule: Dict[str, str]):
        self.oncall_schedule = oncall_schedule
        self.timeline: List[Dict[str, str]] = []
        self.state: str = IncidentState.TRIGGERED
        self.incident_id: str = f"INC-{int(time.time())}"
        self.severity: str = Severity.SEV4
        self.incident_commander: Optional[str] = None
        self.tech_lead: Optional[str] = None
        self.comms_lead: Optional[str] = None
        self.title: str = ""
        self.description: str = ""
        self.action_items: List[Dict[str, str]] = []
        self.five_whys: List[str] = []

    def log_event(self, description: str, actor: str = "SYSTEM") -> None:
        """Mencatat kejadian ke timeline dengan presisi waktu UTC ISO-8601."""
        now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        entry = {
            "timestamp": now_utc,
            "actor": actor,
            "description": description
        }
        self.timeline.append(entry)
        print(f"[{entry['timestamp']}] [{entry['actor']}] {entry['description']}")

    def evaluate_severity(self, payload: Dict[str, Any]) -> str:
        """Menghitung severity level secara deterministik dari telemetri payload."""
        affected_pct = payload.get("affected_users_percentage", 0.0)
        revenue_loss_min = payload.get("estimated_revenue_loss_per_min", 0.0)
        core_service_down = payload.get("core_service_down", False)

        if core_service_down or affected_pct >= 20.0 or revenue_loss_min >= 5000.0:
            return Severity.SEV1
        elif affected_pct >= 5.0 or revenue_loss_min >= 1000.0:
            return Severity.SEV2
        elif affected_pct > 0.0:
            return Severity.SEV3
        return Severity.SEV4

    def ingest_alert(self, alert_payload: Dict[str, Any]) -> None:
        """Menerima dan memproses alert yang masuk ke sistem."""
        self.title = alert_payload.get("summary", "Unknown Anomaly Detected")
        self.description = alert_payload.get("details", "")
        self.severity = self.evaluate_severity(alert_payload)
        
        self.log_event(f"Alert ingested: '{self.title}' | Impact Analysis: {self.severity}")
        self.dispatch_notifications()

    def dispatch_notifications(self) -> None:
        """Mengatur routing notifikasi dan eskalasi berbasis peran."""
        primary_responder = self.oncall_schedule.get("primary")
        self.log_event(f"PAGING DISPATCHED: Alerting Level-1 Primary [{primary_responder}] via PagerDuty High-Urgency Voice/Push")
        
        if self.severity in [Severity.SEV1, Severity.SEV2]:
            self.log_event("HIGH SEVERITY PROTOCOL: Inisialisasi War Room & Escalation Path Otomatis", actor="ICS_ROUTER")
            self.tech_lead = self.oncall_schedule.get("tech_lead")
            self.comms_lead = self.oncall_schedule.get("comms_lead")
            self.log_event(f"Roles Pre-assigned: Tech Lead=[{self.tech_lead}], Comms Lead=[{self.comms_lead}]")

    def acknowledge_incident(self, responder: str, response_time_seconds: float, ack_sla_seconds: float = 300.0) -> None:
        """Memproses acknowledgement dengan evaluasi SLA eskalasi."""
        if response_time_seconds > ack_sla_seconds:
            # SLA terlanggar, picu eskalasi otomatis ke secondary
            escalation_target = self.oncall_schedule.get("secondary")
            self.log_event(
                f"SLA BREACH (MTTA): Responder primer gagal merespon dalam {ack_sla_seconds}s. "
                f"ESKALASI OTOMATIS dialihkan ke Secondary [{escalation_target}].",
                actor="ESCALATION_DAEMON"
            )
            self.incident_commander = escalation_target
        else:
            self.incident_commander = responder

        self.state = IncidentState.ACKNOWLEDGED
        self.log_event(f"Incident ACKNOWLEDGED. Incident Commander (IC) resmi dipegang oleh: {self.incident_commander}", actor=self.incident_commander)

    def transition_to_mitigation(self, strategy: str) -> None:
        """Mencatat perubahan status sistem menuju fase mitigasi teknis."""
        self.state = IncidentState.MITIGATING
        self.log_event(f"MITIGATION STRATEGY ACTIVATED: {strategy}", actor=self.tech_lead or self.incident_commander)

    def resolve_incident(self, resolution_notes: str) -> None:
        """Menyelesaikan status insiden dan mematikan alarm."""
        self.state = IncidentState.RESOLVED
        self.log_event(f"INCIDENT MITIGATED & RESOLVED: {resolution_notes}", actor=self.incident_commander)

    def generate_post_mortem(self, filename: Optional[str] = None) -> str:
        """Membuat dokumen artefak Blameless Post-Mortem terstruktur."""
        if not filename:
            filename = f"post-mortem-{self.incident_id.lower()}.md"

        # Rekonstruksi timeline Markdown
        timeline_md = "| Timestamp (UTC) | Actor | Event Description |\n|---|---|---|\n"
        for t in self.timeline:
            timeline_md += f"| `{t['timestamp']}` | **{t['actor']}** | {t['description']} |\n"

        # Rekonstruksi 5-Whys
        whys_md = ""
        for idx, why in enumerate(self.five_whys, 1):
            whys_md += f"{idx}. **Why?** {why}\n"
        if not whys_md:
            whys_md = "*Analisis 5-Whys belum dikonfigurasi.*\n"

        # Rekonstruksi Action Items
        actions_md = "| ID | Kategori | Item Deskripsi | PIC (Owner) | Type | Target Due Date |\n|---|---|---|---|---|---|\n"
        for a in self.action_items:
            actions_md += f"| {a.get('id')} | {a.get('category')} | {a.get('desc')} | @{a.get('owner')} | `{a.get('priority')}` | {a.get('due')} |\n"
        if not self.action_items:
            actions_md += "| - | - | *Belum ada action item yang didefinisikan* | - | - | - |\n"

        post_mortem_content = f"""# Blameless Post-Mortem Report: {self.title}

## Metadata & Identifikasi Insiden
- **Incident Reference:** `{self.incident_id}`
- **Severity Level:** **{self.severity}**
- **Current Operational Status:** `{self.state}`
- **Lead Responders:**
  - **Incident Commander (IC):** {self.incident_commander or "N/A"}
  - **Technical Lead:** {self.tech_lead or "N/A"}
  - **Communications Lead:** {self.comms_lead or "N/A"}

---

## 1. Executive Summary & Impact Analysis
- **Ringkasan Kejadian:** {self.description}
- **Dampak Bisnis:** Gangguan operasional pada alur transaksi kritis dengan metrik severitas {self.severity}.
- **Blameless Premise:** *Penyelidikan ini dilakukan dengan prinsip sosio-teknis sistemik tanpa mengatribusikan kesalahan pada kelalaian individu. Tujuan utama dokumen ini adalah eliminasi kerentanan arsitektural dan peningkatan kapabilitas pertahanan sistem.*

---

## 2. Chronological Timeline (UTC)
{timeline_md}

---

## 3. Systemic Root Cause Analysis (5-Whys Methodology)
{whys_md}

---

## 4. Remediation & Action Items (SMART Tracking)
{actions_md}

---

*Laporan digenerate secara otomatis oleh SRE Incident Commander Automation Engine pada `{datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}`.*
"""
        with open(filename, "w", encoding="utf-8") as f:
            f.write(post_mortem_content)
        
        self.log_event(f"Post-Mortem artifact successfully exported to: {filename}", actor="POSTMORTEM_GENERATOR")
        return filename

# --- DEMONSTRATION RUNNER ---

def main():
    print("=" * 80)
    print("SRE INCIDENT COMMANDER SYSTEM - SIMULASI WORKFLOW TERINTEGRASI")
    print("=" * 80)

    # 1. Definisi Roster On-Call Tim SRE
    oncall_roster = {
        "primary": "budi.santoso (Junior On-Call SRE)",
        "secondary": "alex.mercer (Staff Platform Engineer)",
        "tech_lead": "rudi.wijaya (Principal Database Architect)",
        "comms_lead": "sarah.azhari (Engineering Lead Manager)"
    }

    # Inisialisasi Engine
    engine = IncidentManagementEngine(oncall_schedule=oncall_roster)

    # 2. Simulasi Masuknya Alert Kritis dari Alertmanager
    mock_alert_payload = {
        "summary": "Core Checkout Payments Database Connection Exhaustion",
        "details": "Connection pooler PgBouncer menolak transaksi transfer (HTTP 503). Max connection client saturation mencapai 100%.",
        "affected_users_percentage": 34.5,
        "estimated_revenue_loss_per_min": 12500.0,
        "core_service_down": True
    }

    print("\n[Step 1: Penerimaan Alert Telemetri & Klasifikasi]")
    engine.ingest_alert(mock_alert_payload)

    # 3. Simulasi Eskalasi: Primary on-call sedang tidak merespon (misal: respons 350 detik, batas timeout 300 detik)
    print("\n[Step 2: Evaluasi Acknowledgement & Eskalasi PagerDuty]")
    time.sleep(1) # Delay simulasi
    engine.acknowledge_incident(responder=oncall_roster["primary"], response_time_seconds=350.0, ack_sla_seconds=300.0)

    # 4. Fase Mitigasi oleh Tech Lead
    print("\n[Step 3: Fase Mitigasi Teknis di War Room]")
    time.sleep(1)
    engine.transition_to_mitigation(
        strategy="Menerapkan circuit-breaking pada checkout API, restart cluster pgbouncer, dan alihkan traffic reporting ke read-replica."
    )

    # 5. Penyelesaian Insiden
    print("\n[Step 4: Pemulihan Sistem & Normalisasi SLI]")
    time.sleep(1)
    engine.resolve_incident(
        resolution_notes="Connection pool kembali normal pada 12% kapasitas. HTTP 503 kembali ke 0%. Error budget consumption berhenti."
    )

    # 6. Penyusunan Analisis 5-Whys Pasca Insiden
    engine.five_whys = [
        "Layanan transfer pembayaran gagal menghasilkan transaksi dan mengembalikan HTTP 503 kepada customer.",
        "Koneksi ke backend Postgres database mengalami starvation (penolakan koneksi aktif baru).",
        "Aplikasi batch analytics bulanan meluncurkan 50 background worker query secara simultan ke master node tanpa pool isolation.",
        "Konfigurasi Kubernetes CronJob tidak membedakan endpoint string database antara operational OLTP dan read-replica OLAP.",
        "Pipeline verifikasi lint manifest helm tidak memiliki static policy test (OPA Gatekeeper) untuk memvalidasi pemisahan credentials database."
    ]

    # 7. Penambahan Action Items Berbasis Rekayasa
    engine.action_items = [
        {
            "id": "ACT-101",
            "category": "PREVENT",
            "desc": "Implementasikan OPA Gatekeeper policy untuk memblokir deployment pod analitik yang mengarah ke endpoint database master.",
            "owner": "alex.mercer",
            "priority": "P0 (Blocker)",
            "due": "2023-11-10"
        },
        {
            "id": "ACT-102",
            "category": "MITIGATE",
            "desc": "Pasang Envoy connection limit rate-limiter di depan PgBouncer untuk auto-shed load saat koneksi > 85%.",
            "owner": "rudi.wijaya",
            "priority": "P1 (Critical)",
            "due": "2023-11-15"
        },
        {
            "id": "ACT-103",
            "category": "PROCESS",
            "desc": "Lakukan simulasi Chaos Engineering (GameDay) untuk skenario database starvation di cluster staging.",
            "owner": "budi.santoso",
            "priority": "P2 (Medium)",
            "due": "2023-11-25"
        }
    ]

    # 8. Otomasi Ekspor Dokumen Post-Mortem
    print("\n[Step 5: Pembuatan Artefak Blameless Post-Mortem]")
    output_doc = engine.generate_post_mortem()
    print(f"\n[SUKSES] Dokumen Post-Mortem berhasil digenerate: {output_doc}")
    print("=" * 80)

if __name__ == "__main__":
    main()