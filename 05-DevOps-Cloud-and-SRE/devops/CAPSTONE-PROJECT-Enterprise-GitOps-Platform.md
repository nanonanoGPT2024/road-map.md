# 🏆 CAPSTONE PROJECT: Enterprise Multi-Cloud GitOps Delivery Platform

Platform Rekayasa Infrastruktur, CI/CD Otomatis, Observabilitas Terpadu, DevSecOps, & SRE Reliability

---

## 1. Project Overview & Executive Summary
Proyek Capstone ini adalah puncak integrasi dari seluruh 10 BAB materi **DevOps & Site Reliability Engineering (SRE) Mastery Curriculum**. 

Sebagai Principal DevOps / Platform Architect, Anda diminta untuk merancang, membangun, mengamankan, dan mengoperasikan platform pengiriman software modern berskala enterprise untuk sistem perbankan & e-commerce multinasional (**FinBank Global**). Platform ini mengotomatisasi penyediaan infrastruktur multi-cloud dari nol hingga produksi, menerapkan tata kelola GitOps tanpa sentuhan manual (*Zero-Touch Production*), mengamankan rantai pasok software, dan menjamin ketersediaan $99.95\%$ dengan efisiensi biaya FinOps.

---

## 2. Comprehensive Technology Stack

| Domain | Teknologi Terpilih | Peran Arsitektur |
|---|---|---|
| **Sistem Operasi & Kernel** | Linux Debian / Alpine Linux | OS runtime worker node, kernel cgroups v2, dan network tuning |
| **Infrastructure as Code (IaC)** | Terraform / OpenTofu | Declarative provisioning VPC, Subnets, EKS, RDS, S3, IAM |
| **Server Provisioning** | Ansible | Hardening OS, SSH bastion management, agent bootstrapping |
| **Container Runtime** | Docker Multi-Stage & containerd | Containerization aplikasi minimalis non-root |
| **Container Orchestration** | Kubernetes (EKS / GKE) | Scheduling, Pod Autoscaling, Service Mesh, Ingress |
| **CI/CD Automation** | GitHub Actions | Automated lint, unit test, build, Trivy scan, Cosign sign |
| **GitOps Engine** | ArgoCD & Argo Rollouts | Reconciler state deklaratif, Canary progressive rollout |
| **Observabilitas (3 Pilar)** | Prometheus, Grafana, Loki, OpenTelemetry | Metrik, PromQL alerting, centralized JSON logs, distributed traces |
| **Secret Management** | HashiCorp Vault | Barrier AES-256 encryption, Dynamic DB credentials, K8s injector |
| **Security Governance** | Trivy, Cosign, Kyverno / OPA Gatekeeper | Supply chain security, non-root enforcement, admission control |
| **SRE & FinOps** | Karpenter, Chaos Mesh, Kubecost | Error budgets, fault injection GameDay, Spot instances autoscaling |

---

## 3. End-to-End Platform Architecture Diagram

```
+---------------------------------------------------------------------------------------------------------+
|                    ENTERPRISE GITOPS & SRE ARCHITECTURE (FINBANK GLOBAL)                                |
+---------------------------------------------------------------------------------------------------------+

 [ Developer ] ──> git push ──> [ GitHub App Code Repo ]
                                           │
                                           ▼ (Trigger Webhook)
 ┌───────────────────────────────────────────────────────────────────────────────────────────────────────┐
 │ GITHUB ACTIONS CI PIPELINE                                                                            │
 │  1. ESLint & Go Vet ──> 2. Unit Tests (85% Coverage) ──> 3. Trivy Security Scan (Block if Critical)  │
 │  4. Multi-Stage Docker Build ──> 5. Cosign Image Signing ──> 6. Push to AWS ECR Registry              │
 │  7. Bot Commit SHA update to GitOps Config Repo                                                       │
 └─────────────────────────────────────────┬─────────────────────────────────────────────────────────────┘
                                           │
                                           ▼ (Git Push Manifests)
 ┌───────────────────────────────────────────────────────────────────────────────────────────────────────┐
 │ GITOPS CONFIG REPOSITORY (github.com/finbank/k8s-gitops-manifests)                                    │
 │  ├── overlays/staging/ (Kustomize)                                                                    │
 │  └── overlays/production/                                                                             │
 └─────────────────────────────────────────┬─────────────────────────────────────────────────────────────┘
                                           │
                                           ▼ (Pulls desired state inside K8s)
 ┌───────────────────────────────────────────────────────────────────────────────────────────────────────┐
 │ KUBERNETES PRODUCTION CLUSTER (AWS EKS via Terraform)                                                 │
 │                                                                                                       │
 │  ┌─────────────────────────────────┐               ┌────────────────────────────────────────────────┐ │
 │  │ Kyverno Admission Controller    │               │ HashiCorp Vault Cluster                        │ │
 │  │ (Rejects Root & Unsigned Images)│               │ (Dynamic DB Creds with 1h TTL)                 │ │
 │  └─────────────────▲───────────────┘               └───────────────────────▲────────────────────────┘ │
 │                    │                                                       │                          │
 │  ┌─────────────────┴───────────────┐               ┌───────────────────────┴────────────────────────┐ │
 │  │ ArgoCD GitOps Reconciler        │ ──(Deploys)──>│ Argo Rollouts (Canary Controller)              │ │
 │  │ (Self-Healing & Auto-Prune)     │               │ - 10% Canary (5m) ──> 50% (10m) ──> 100%       │ │
 │  └─────────────────────────────────┘               └───────────────────────▲────────────────────────┘ │
 │                                                                            │                          │
 │  ┌─────────────────────────────────────────────────────────────────────────┴────────────────────────┐ │
 │  │ Workload Pods (Managed by Karpenter Graviton ARM64 Spot Instances)                               │ │
 │  │  [ Payment API Pods ] <──(emptyDir RAM)── [ Vault Agent Sidecar: Injected DB Secret ]             │ │
 │  │  (OpenTelemetry SDK: traces & structured logs -> OTel Collector)                                  │ │
 │  └─────────────────────────────────────────┬────────────────────────────────────────────────────────┘ │
 │                                            │                                                          │
 │  ┌─────────────────────────────────────────▼────────────────────────────────────────────────────────┐ │
 │  │ Observability Tier                                                                               │ │
 │  │  - Prometheus: Scrapes /metrics, evaluates Multi-Burn-Rate PromQL alerts                         │ │
 │  │  - Grafana Loki: Receives JSON logs with trace_id correlation                                    │ │
 │  │  - Jaeger / Tempo: Visualizes Waterfall Spans for latency bottlenecks                            │ │
 │  │  - Alertmanager: Dispatches SEV-1 alerts to PagerDuty & Slack #war-room                          │ │
 │  └──────────────────────────────────────────────────────────────────────────────────────────────────┘ │
 └───────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Implementation Milestones

### 🗺️ Milestone 1: Fondasi Jaringan & Declarative IaC (Terraform)
- **Tujuan**: Membangun VPC multi-tier (Public, Private, Database subnets) di 3 Availability Zones AWS.
- **Deliverables**:
  - Konfigurasi `versions.tf` dengan remote state S3 backend dan DynamoDB state locking.
  - Modul Terraform VPC, Internet Gateway, NAT Gateway redundant, dan Route Tables.
  - Provisioning cluster AWS EKS v1.30 dengan OIDC provider terintegrasi.
  - Database Amazon Aurora PostgreSQL Serverless v2 di private subnet terisolasi.

### 🗺️ Milestone 2: Server Bootstrapping & Configuration (Ansible)
- **Tujuan**: Mengonfigurasi Bastion Host dan node edge Linux dengan standar keamanan hardened CIS Benchmark.
- **Deliverables**:
  - Ansible Playbook dengan audit idempotency.
  - Menonaktifkan root SSH login, password authentication, dan mengonfigurasi UFW firewall.
  - Mengonfigurasi fail2ban, auditd daemon, dan sinkronisasi jam chrony NTP.

### 🗺️ Milestone 3: Containerization & Shift-Left DevSecOps (GitHub Actions)
- **Tujuan**: Membangun pipeline CI otomatis yang tidak dapat disusupi celah keamanan.
- **Deliverables**:
  - `Dockerfile` multi-stage berbasis `distroless/static-debian12:nonroot`.
  - Workflow GitHub Actions:
    - Linting & testing dengan coverage requirement minimal 85%.
    - Trivy image scan: Gagalkan build jika ada CVE level `CRITICAL`.
    - Penandatanganan container image menggunakan `cosign sign --yes`.
    - Push otomatis manifest update ke repository GitOps.

### 🗺️ Milestone 4: GitOps Deployment & Progressive Canary (ArgoCD & Argo Rollouts)
- **Tujuan**: Meniadakan akses `kubectl` langsung ke produksi; seluruh perubahan cluster melalui Git PR.
- **Deliverables**:
  - Pemasangan ArgoCD via Helm chart di namespace `argocd`.
  - Konfigurasi Root App of Apps pattern untuk microservices FinBank.
  - Implementasi Argo Rollout Canary dengan 4 tahap pembagian traffic (10%, 25%, 50%, 100%).
  - Pemasangan `AnalysisTemplate` Prometheus: jika error rate $> 0.5\%$ selama 2 menit, rollout otomatis dibatalkan (*auto-abort*).

### 🗺️ Milestone 5: Zero-Trust Secret Management (HashiCorp Vault)
- **Tujuan**: Menghilangkan seluruh password statis dan secret Kubernetes unencrypted.
- **Deliverables**:
  - Cluster Vault dengan Integrated Raft Storage.
  - Konfigurasi Vault Kubernetes Auth Method.
  - Pemasangan Vault Database Secret Engine yang menerbitkan kredensial PostgreSQL ephemeral (TTL 1 jam).
  - Pemasangan Vault Agent Sidecar Injector untuk merender kredensial ke `/vault/secrets/db-creds.json`.

### 🗺️ Milestone 6: Cluster Security Governance (Kyverno)
- **Tujuan**: Mencegah deployment pod yang melanggar standar kepatuhan PCI-DSS.
- **Deliverables**:
  - ClusterPolicy Kyverno:
    - Wajib `runAsNonRoot: true`.
    - Wajib `allowPrivilegeEscalation: false`.
    - Dilarang menggunakan tag `:latest`.
    - Verifikasi tanda tangan digital Cosign pada image sebelum pod dijadwalkan.

### 🗺️ Milestone 7: Observabilitas Tiga Pilar (Prometheus, Loki, OpenTelemetry)
- **Tujuan**: Visibilitas penuh end-to-end dari frontend hingga database query.
- **Deliverables**:
  - Pemasangan Kube-Prometheus-Stack (Prometheus, Alertmanager, Grafana).
  - Pemasangan Grafana Loki dan Promtail daemonset untuk JSON structured logging.
  - Instrumentasi aplikasi menggunakan OpenTelemetry SDK dengan W3C traceparent injection.
  - Pembuatan Grafana Unified Dashboard: Latency $p95$/$p99$, RPS, Error Rate %, dan tombol klik langsung ke Jaeger trace waterfall.

### 🗺️ Milestone 8: SRE Reliability, Chaos Engineering, & FinOps
- **Tujuan**: Membuktikan ketahanan sistem saat krisis dan memangkas pemborosan cloud.
- **Deliverables**:
  - Definisi SLO: $99.95\%$ availability per bulan bergulir.
  - Multi-Burn-Rate alert rules di Alertmanager (Burn Rate $> 14.4\text{x}$ mengirim PagerDuty SEV-1).
  - Simulasi GameDay Chaos Mesh: menyuntikkan latensi jaringan 150ms dan mematikan pod database master; verifikasi bahwa RTO $< 45\text{s}$ tercapai.
  - Pemasangan Karpenter Autoscaler dengan instance AWS Graviton ARM64 Spot, menghemat anggaran bulanan sebesar 68%.

---

## 5. Verification & Acceptance Testing Criteria

```text
+-------------------------------------------------------------------------------------------+
| KRITERIA PENGUJIAN AKHIR (CAPSTONE ACCEPTANCE TEST MATRIX)                                |
+-------------------------------------------------------------------------------------------+
| 1. IaC Idempotency      | `terraform plan` setelah apply menghasilkan "0 to add/change"   |
| 2. Zero-Static-Secret   | Tidak ada file .env atau secret plaintext di Git / K8s etcd     |
| 3. Image Security Gate  | Push image dengan CVE CRITICAL sengaja diblokir di CI           |
| 4. Policy Enforcement   | Manifest pod dengan `privileged: true` ditolak oleh Kyverno     |
| 5. GitOps Auto-Heal     | Manual `kubectl scale` langsung dikembalikan oleh ArgoCD        |
| 6. Canary Auto-Rollback | Buggy release memicu rollback otomatis tanpa intervensi manual  |
| 7. Correlated Traces    | TraceID di Grafana dapat membuka baris log error di Loki        |
| 8. SRE Feature Freeze   | Simulasi Error Budget habis otomatis mengunci pipeline deploy   |
| 9. FinOps Efficiency    | Karpenter berhasil menjadwalkan workload di Spot NodePool       |
+-------------------------------------------------------------------------------------------+
```

---

## 6. Post-Launch Operations & Runbook
Platform dilengkapi dengan dokumen operasional:
1. **On-Call Handover Guide**: Prosedur rotasi jadwal jaga mingguan.
2. **SEV-1 Incident Playbook**: Prosedur aktivasi Incident Commander dan ruang perang (*War Room*).
3. **Blameless Post-Mortem Template**: Standar penulisan evaluasi insiden dalam 48 jam.
4. **Cloud Cost Review Rhythm**: Pertemuan FinOps bulanan untuk mengevaluasi tagihan dan rekomendasi right-sizing.

---

## 7. Capstone Submission Checklist
- [ ] Seluruh kode IaC Terraform dan manifest Kubernetes tersimpan di repositori Git.
- [ ] Pipeline CI/CD GitHub Actions berjalan hijau (*pass*) dengan bukti pemindaian Trivy.
- [ ] Dokumentasi arsitektur lengkap dengan diagram dan keputusan trade-off.
- [ ] Rekaman video/log terminal uji coba Chaos Engineering dan pemulihan otomatis RTO.
- [ ] Laporan evaluasi FinOps yang menunjukkan penghematan biaya riil.

🏆 **Selamat! Dengan menyelesaikan Capstone Project ini, Anda telah menguasai seluruh spektrum kompetensi profesional seorang Senior DevOps & Site Reliability Engineer (SRE).**
