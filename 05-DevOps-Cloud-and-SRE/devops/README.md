# DEVOPS & SITE RELIABILITY ENGINEERING (SRE) MASTERY
**Panduan Komprehensif Otomasi Infrastruktur, CI/CD, Containerization, & Sistem Andal Berskala Global**  
*Berdasarkan kurikulum resmi [roadmap.sh/devops](https://roadmap.sh/devops)*

---

## 📌 Course Overview
DevOps bukan sekadar kumpulan alat (*tools*), melainkan gabungan dari filosofi budaya, praktik rekayasa perangkat lunak, dan seperangkat perkakas otomatisasi yang meningkatkan kemampuan organisasi untuk merilis aplikasi dan layanan dengan kecepatan tinggi, skalabilitas andal, dan keamanan tanpa kompromi.

Kursus ini dirancang untuk membawa pembelajar dari pemahaman dasar sistem operasi Linux, jaringan, dan container, hingga menguasai orkestrasi Kubernetes tingkat lanjut, otomasi Infrastructure as Code (IaC) dengan Terraform/OpenTofu, pipeline GitOps modern dengan ArgoCD, serta pemantauan observabilitas end-to-end berbasis Prometheus, Grafana, dan OpenTelemetry.

Materi disajikan secara **hands-on & practical-first**: setiap modul dilengkapi dengan contoh kode nyata, analisis trade-off arsitektur produksi, serta script laboratorium mandiri yang dapat langsung dijalankan dan diverifikasi.

---

## 🗺️ Learning Roadmap & Struktur Bab

```text
COURSE: DEVOPS & SRE MASTERY
│
├── BAB 01 — Fondasi Sistem Operasi & Linux Shell Automation
│   ├── Module 01: Arsitektur Kernel Linux, Manajemen Proses, & Konkurensi
│   └── Module 02: Otomasi Shell Scripting (Bash) & Diagnostik Sistem (Systemd, Journalctl, Htop)
│
├── BAB 02 — Jaringan, Protokol Internet, & Web Servers
│   ├── Module 01: Jaringan Komputer untuk DevOps (OSI, TCP/UDP, DNS, & TLS/SSL)
│   └── Module 02: Reverse Proxy & Web Server Hardening (Nginx & Envoy)
│
├── BAB 03 — Containerization dengan Docker Modern
│   ├── Module 01: Arsitektur Container, Namespaces, Cgroups, & Docker Runtime
│   └── Module 02: Optimasi Dockerfile Multi-Stage, Volume Persistence, & Docker Compose
│
├── BAB 04 — Orkestrasi Container dengan Kubernetes (K8s)
│   ├── Module 01: Arsitektur Control Plane, Pods, Deployments, & Service Networking
│   └── Module 02: Ingress Controller, ConfigMaps, Secrets, & Helm Package Management
│
├── BAB 05 — Infrastructure as Code (IaC) dengan Terraform & OpenTofu
│   ├── Module 01: Konsep Declarative IaC, State Management, & Provider HCL
│   └── Module 02: Modular Infrastructure, Remote Backend Locking (S3/DynamoDB), & Drift Detection
│
├── BAB 06 — Configuration Management & Server Provisioning (Ansible)
│   ├── Module 01: Idempotency, YAML Playbooks, Inventory Groups, & SSH Remote Exec
│   └── Module 02: Ansible Roles, Jinja2 Templating, & Ansible Vault untuk Secret
│
├── BAB 07 — Continuous Integration & Continuous Delivery (CI/CD)
│   ├── Module 01: Automated Pipeline dengan GitHub Actions & GitLab CI
│   └── Module 02: GitOps Modern dengan ArgoCD & Canary/Blue-Green Deployment
│
├── BAB 08 — Observabilitas Sistem: Metrik, Logging, & Tracing
│   ├── Module 01: Metrik Monitoring & Alerting (Prometheus, Node Exporter, & Grafana)
│   └── Module 02: Centralized Logging (Loki/Promtail) & Distributed Tracing (OpenTelemetry)
│
├── BAB 09 — DevSecOps, Secret Management, & Governance
│   ├── Module 01: Manajemen Kredensial Terpusat dengan HashiCorp Vault
│   └── Module 02: Security Scanning (Trivy, SonarQube) & Kebijakan Least Privilege (IAM)
│
├── BAB 10 — Reliability Engineering (SRE), Incident Response, & Cloud Cost (FinOps)
│   ├── Module 01: SLI, SLO, SLA, Error Budgets, & Post-Mortem Blameless Culture
│   └── Module 02: High Availability, Chaos Engineering, & Cloud Cost Optimization (FinOps)
│
└── CAPSTONE PROJECT: Enterprise Multi-Cloud GitOps Delivery Platform
```

---

## 🎯 Navigasi Materi

- [BAB 01 — Fondasi Sistem Operasi & Linux Shell Automation](./BAB-01-Sistem-Operasi-dan-Linux-Automation/)
  - [Module 01: Arsitektur Kernel Linux, Manajemen Proses, & Konkurensi](./BAB-01-Sistem-Operasi-dan-Linux-Automation/Module-01-Arsitektur-Kernel-Linux-Manajemen-Proses-dan-Konkurensi.md)
  - [Module 02: Otomasi Shell Scripting (Bash) & Diagnostik Sistem](./BAB-01-Sistem-Operasi-dan-Linux-Automation/Module-02-Otomasi-Shell-Scripting-dan-Diagnostik-Sistem.md)
  - [Evaluasi & Quiz BAB 01](./BAB-01-Sistem-Operasi-dan-Linux-Automation/BAB-01-Quiz-dan-Challenge.md)
- [BAB 02 — Jaringan, Protokol Internet, & Web Servers](./BAB-02-Jaringan-Protokol-dan-Web-Servers/)
  - [Module 01: Jaringan Komputer untuk DevOps (OSI, TCP/UDP, DNS, & TLS/SSL)](./BAB-02-Jaringan-Protokol-dan-Web-Servers/Module-01-Jaringan-Komputer-OSI-TCP-DNS-TLS.md)
  - [Module 02: Reverse Proxy & Web Server Hardening (Nginx & Envoy)](./BAB-02-Jaringan-Protokol-dan-Web-Servers/Module-02-Reverse-Proxy-Load-Balancing-Nginx-Envoy.md)
  - [Evaluasi & Quiz BAB 02](./BAB-02-Jaringan-Protokol-dan-Web-Servers/BAB-02-Quiz-dan-Challenge.md)
- [BAB 03 — Containerization dengan Docker Modern](./BAB-03-Containerization-Docker/)
  - [Module 01: Arsitektur Container, Namespaces, Cgroups, & Docker Runtime](./BAB-03-Containerization-Docker/Module-01-Arsitektur-Container-Namespaces-Cgroups-Runtime.md)
  - [Module 02: Optimasi Dockerfile Multi-Stage, Volume Persistence, & Docker Compose](./BAB-03-Containerization-Docker/Module-02-Optimasi-Dockerfile-Multi-Stage-Volume-Compose.md)
  - [Evaluasi & Quiz BAB 03](./BAB-03-Containerization-Docker/BAB-03-Quiz-dan-Challenge.md)
- [BAB 04 — Orkestrasi Container dengan Kubernetes (K8s)](./BAB-04-Kubernetes-Orchestration/)
  - [Module 01: Arsitektur Control Plane, Pods, Deployments, & Service Networking](./BAB-04-Kubernetes-Orchestration/Module-01-Arsitektur-Control-Plane-Pods-Deployments-Service-Networking.md)
  - [Module 02: Ingress Controller, ConfigMaps, Secrets, & Helm Package Management](./BAB-04-Kubernetes-Orchestration/Module-02-Ingress-Controller-ConfigMaps-Secrets-Helm.md)
  - [Evaluasi & Quiz BAB 04](./BAB-04-Kubernetes-Orchestration/BAB-04-Quiz-dan-Challenge.md)
- [BAB 05 — Infrastructure as Code (IaC) dengan Terraform & OpenTofu](./BAB-05-Infrastructure-as-Code-Terraform/)
  - [Module 01: Konsep Declarative IaC, State Management, & Provider HCL](./BAB-05-Infrastructure-as-Code-Terraform/Module-01-Declarative-IaC-HCL-State-Management.md)
  - [Module 02: Modular Infrastructure, Remote Backend Locking, & Drift Detection](./BAB-05-Infrastructure-as-Code-Terraform/Module-02-Modular-IaC-Remote-Backend-Drift-Detection.md)
  - [Evaluasi & Quiz BAB 05](./BAB-05-Infrastructure-as-Code-Terraform/BAB-05-Quiz-dan-Challenge.md)
- [BAB 06 — Configuration Management & Server Provisioning (Ansible)](./BAB-06-Configuration-Management-Ansible/)
  - [Module 01: Idempotency, YAML Playbooks, Inventory Groups, & SSH Remote Exec](./BAB-06-Configuration-Management-Ansible/Module-01-Idempotency-Playbooks-Inventory-SSH.md)
  - [Module 02: Ansible Roles, Jinja2 Templating, & Ansible Vault](./BAB-06-Configuration-Management-Ansible/Module-02-Ansible-Roles-Jinja2-Templates-Vault.md)
  - [Evaluasi & Quiz BAB 06](./BAB-06-Configuration-Management-Ansible/BAB-06-Quiz-dan-Challenge.md)
- [BAB 07 — Continuous Integration & Continuous Delivery (CI/CD)](./BAB-07-CICD-dan-GitOps/)
  - [Module 01: Pipeline Automation (GitHub Actions, GitLab CI), Caching, & Matrix Builds](./BAB-07-CICD-dan-GitOps/Module-01-Pipeline-Automation-GitHub-Actions-GitLab.md)
  - [Module 02: GitOps Modern dengan ArgoCD, Flux, & Canary Deployment (Argo Rollouts)](./BAB-07-CICD-dan-GitOps/Module-02-GitOps-Modern-ArgoCD-Canary-Deployment.md)
  - [Evaluasi & Quiz BAB 07](./BAB-07-CICD-dan-GitOps/BAB-07-Quiz-dan-Challenge.md)
- [BAB 08 — Observabilitas Sistem: Metrik, Logging, & Tracing](./BAB-08-Observabilitas-Monitoring-Logging/)
  - [Module 01: Monitoring & Metrik dengan Prometheus, Alertmanager, & Grafana](./BAB-08-Observabilitas-Monitoring-Logging/Module-01-Prometheus-Metrik-Alertmanager-Grafana.md)
  - [Module 02: Centralized Logging (Loki, ELK) & Distributed Tracing (OpenTelemetry, Jaeger)](./BAB-08-Observabilitas-Monitoring-Logging/Module-02-Centralized-Logging-Loki-Tracing-OpenTelemetry.md)
  - [Evaluasi & Quiz BAB 08](./BAB-08-Observabilitas-Monitoring-Logging/BAB-08-Quiz-dan-Challenge.md)
- [BAB 09 — DevSecOps, Secret Management, & Governance](./BAB-09-DevSecOps-dan-Security/)
  - [Module 01: Secret Management Terpusat dengan HashiCorp Vault & Dynamic Secrets](./BAB-09-DevSecOps-dan-Security/Module-01-HashiCorp-Vault-Centralized-Secrets.md)
  - [Module 02: DevSecOps, Vulnerability Scanning (Trivy), & Policy Governance (OPA/Kyverno)](./BAB-09-DevSecOps-dan-Security/Module-02-Vulnerability-Scanning-Trivy-IAM-Governance.md)
  - [Evaluasi & Quiz BAB 09](./BAB-09-DevSecOps-dan-Security/BAB-09-Quiz-dan-Challenge.md)
- [BAB 10 — Reliability Engineering (SRE) & FinOps](./BAB-10-SRE-Incident-dan-FinOps/)
  - [Module 01: SRE Fundamental: SLI, SLO, Error Budgets, & Blameless Post-Mortem](./BAB-10-SRE-Incident-dan-FinOps/Module-01-SLI-SLO-Error-Budgets-Blameless-PostMortem.md)
  - [Module 02: High Availability, Chaos Engineering, & FinOps (Cloud Cost Optimization)](./BAB-10-SRE-Incident-dan-FinOps/Module-02-High-Availability-Chaos-Engineering-FinOps.md)
  - [Evaluasi & Quiz BAB 10](./BAB-10-SRE-Incident-dan-FinOps/BAB-10-Quiz-dan-Challenge.md)
- [🏆 CAPSTONE PROJECT: Enterprise Multi-Cloud GitOps Delivery Platform](./CAPSTONE-PROJECT-Enterprise-GitOps-Platform.md)
