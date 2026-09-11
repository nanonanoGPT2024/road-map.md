# 🐳 DOCKER MASTERY: ZERO TO PRODUCTION HERO

Kurikulum pembelajaran komprehensif, mendalam, dan terstruktur untuk menguasai teknologi containerization modern dengan **Docker**, berdasarkan standar industri resmi [roadmap.sh/docker](https://roadmap.sh/docker).

---

## 🎯 Tujuan Kurikulum (Learning Objectives)
Setelah menyelesaikan seluruh kurikulum ini, pembelajar akan mampu:
1. **Memahami Fondasi Kernel**: Mengerti secara mendalam cara kerja Linux Namespaces, Cgroups v2, dan OverlayFS yang menjadi tulang punggung container.
2. **Menguasai Lifecycle & CLI**: Mengoperasikan Docker CLI dengan efisien, mengontrol lifecycle container, menangani exit codes, restart policies, dan resource limits.
3. **Engineering Dockerfile Mutakhir**: Merancang Dockerfile multi-stage, menerapkan caching layer optimal, base image minimalis (Distroless / Scratch / Alpine), dan memangkas ukuran image hingga 90%.
4. **Manajemen Penyimpanan**: Mengelola volume persistensi, bind mounts, migrasi data, dan automated backup.
5. **Jaringan Container Tingkat Lanjut**: Mengonfigurasi bridge network kustom, host networking, embedded DNS, dan memahami translasi tabel iptables.
6. **Orkestrasi Multi-Container**: Membangun arsitektur microservices terintegrasi dengan Docker Compose V2, dependency conditions, dan healthchecks.
7. **Pengerasan Keamanan (Hardening)**: Menjalankan Docker dalam Rootless Mode, non-root user execution, dropping Linux capabilities, read-only root filesystems, dan CVE scanning.
8. **BuildKit & Multi-Architecture**: Memanfaatkan BuildKit cache mounts, secret mounts, dan melakukan cross-compilation AMD64/ARM64 dengan Docker Buildx.
9. **Observabilitas & Troubleshooting**: Mengonfigurasi logging drivers dengan log rotation, monitoring metrik dengan cAdvisor/Prometheus, dan melakukan diagnostik insiden OOMKilled.
10. **Operasional Produksi**: Mengelola private registry (Harbor/ECR), integrasi systemd, automated updates dengan Watchtower, dan strategi image pruning.

---

## 🗺️ Peta Jalur Belajar (Roadmap & Silabus)

```text
[01. Linux Primitives & Docker Architecture]
                    ↓
[02. Container Lifecycle & CLI Mastery]
                    ↓
[03. Dockerfile Engineering & Image Optimization]
                    ↓
[04. Docker Storage, Volumes, & Persistence]
                    ↓
[05. Docker Networking Deep Dive & DNS]
                    ↓
[06. Multi-Container Orchestration with Docker Compose]
                    ↓
[07. Security Hardening & Rootless Docker]
                    ↓
[08. Advanced BuildKit & Multi-Architecture (Buildx)]
                    ↓
[09. Logging, Monitoring, & Production Troubleshooting]
                    ↓
[10. Production Deployment, Registries, & Maintenance]
                    ↓
[🏆 CAPSTONE PROJECT: Enterprise Microservices Infrastructure]
```

---

## 📚 Struktur Direktori Kurikulum

- [BAB 01 — Fondasi & Arsitektur Docker](./BAB-01-Fondasi-dan-Arsitektur-Docker/)
  - [Module 01: Container vs VM, OCI, containerd, runc, & Docker Daemon](./BAB-01-Fondasi-dan-Arsitektur-Docker/Module-01-Container-vs-VM-OCI-containerd-runc-Daemon.md)
  - [Module 02: Linux Namespaces, Cgroups v2, & Storage Driver (OverlayFS)](./BAB-01-Fondasi-dan-Arsitektur-Docker/Module-02-Linux-Namespaces-Cgroups-v2-Storage-Driver-OverlayFS.md)
  - [Evaluasi & Quiz BAB 01](./BAB-01-Fondasi-dan-Arsitektur-Docker/BAB-01-Quiz-dan-Challenge.md)
- [BAB 02 — Container Lifecycle & CLI Mastery](./BAB-02-Container-Lifecycle-dan-CLI-Mastery/)
  - [Module 01: Siklus Hidup Container, State Machine, & Command CLI Esensial](./BAB-02-Container-Lifecycle-dan-CLI-Mastery/Module-01-Siklus-Hidup-Container-State-Machine-dan-CLI-Esensial.md)
  - [Module 02: Healthchecks, Restart Policies, & Resource Constraints](./BAB-02-Container-Lifecycle-dan-CLI-Mastery/Module-02-Healthchecks-Restart-Policies-dan-Resource-Constraints.md)
  - [Evaluasi & Quiz BAB 02](./BAB-02-Container-Lifecycle-dan-CLI-Mastery/BAB-02-Quiz-dan-Challenge.md)
- [BAB 03 — Dockerfile Engineering & Image Optimization](./BAB-03-Dockerfile-Engineering-dan-Image-Optimization/)
  - [Module 01: Anatomi Image Layer, Caching Strategy, & Instruksi Fundamental](./BAB-03-Dockerfile-Engineering-dan-Image-Optimization/Module-01-Anatomi-Image-Layer-Caching-Strategy-dan-Instruksi-Fundamental.md)
  - [Module 02: Multi-Stage Builds, Distroless, & Minimal Base Images](./BAB-03-Dockerfile-Engineering-dan-Image-Optimization/Module-02-Multi-Stage-Builds-Distroless-dan-Minimal-Base-Images.md)
  - [Evaluasi & Quiz BAB 03](./BAB-03-Dockerfile-Engineering-dan-Image-Optimization/BAB-03-Quiz-dan-Challenge.md)
- [BAB 04 — Docker Storage, Volumes, & Persistence](./BAB-04-Docker-Storage-Volumes-dan-Persistence/)
  - [Module 01: Bind Mounts, Named Volumes, & tmpfs Memory Mounts](./BAB-04-Docker-Storage-Volumes-dan-Persistence/Module-01-Bind-Mounts-Named-Volumes-dan-tmpfs-Memory-Mounts.md)
  - [Module 02: Volume Backup, Restore, Migration, & Multi-Container Shared Storage](./BAB-04-Docker-Storage-Volumes-dan-Persistence/Module-02-Volume-Backup-Restore-Migration-dan-Multi-Container-Sharing.md)
  - [Evaluasi & Quiz BAB 04](./BAB-04-Docker-Storage-Volumes-dan-Persistence/BAB-04-Quiz-dan-Challenge.md)
- [BAB 05 — Docker Networking Deep Dive & DNS](./BAB-05-Docker-Networking-Deep-Dive/)
  - [Module 01: Network Drivers (Bridge, Host, None, Macvlan) & Port Forwarding](./BAB-05-Docker-Networking-Deep-Dive/Module-01-Network-Drivers-Bridge-Host-None-Macvlan-dan-Port-Mapping.md)
  - [Module 02: Embedded DNS, User-Defined Bridges, & Network Segmentation](./BAB-05-Docker-Networking-Deep-Dive/Module-02-Embedded-DNS-User-Defined-Bridge-dan-iptables-Filtering.md)
  - [Evaluasi & Quiz BAB 05](./BAB-05-Docker-Networking-Deep-Dive/BAB-05-Quiz-dan-Challenge.md)
- [BAB 06 — Multi-Container dengan Docker Compose V2](./BAB-06-Multi-Container-dengan-Docker-Compose/)
  - [Module 01: Declarative Compose V2, Services, Dependencies, & Healthchecks](./BAB-06-Multi-Container-dengan-Docker-Compose/Module-01-Declarative-Compose-V2-Services-Dependencies-dan-Healthchecks.md)
  - [Module 02: Multi-Environment Compose, Overrides, & Profiles](./BAB-06-Multi-Container-dengan-Docker-Compose/Module-02-Multi-Environment-Compose-Overrides-dan-Profiles.md)
  - [Evaluasi & Quiz BAB 06](./BAB-06-Multi-Container-dengan-Docker-Compose/BAB-06-Quiz-dan-Challenge.md)
- [BAB 07 — Security Hardening & Rootless Docker](./BAB-07-Docker-Security-Hardening-dan-Rootless/)
  - [Module 01: Rootless Mode, Non-Root Users, Capabilities, & Read-Only Filesystem](./BAB-07-Docker-Security-Hardening-dan-Rootless/Module-01-Rootless-Mode-Non-Root-Users-Capabilities-dan-ReadOnly-FS.md)
  - [Module 02: Vulnerability Scanning (Docker Scout, Trivy), Seccomp, & Image Signing](./BAB-07-Docker-Security-Hardening-dan-Rootless/Module-02-Vulnerability-Scanning-Docker-Scout-Trivy-dan-Seccomp.md)
  - [Evaluasi & Quiz BAB 07](./BAB-07-Docker-Security-Hardening-dan-Rootless/BAB-07-Quiz-dan-Challenge.md)
- [BAB 08 — Advanced BuildKit & Multi-Architecture](./BAB-08-Advanced-BuildKit-dan-Multi-Architecture/)
  - [Module 01: BuildKit Engine, Secret Mounts, Cache Mounts, & SSH Forwarding](./BAB-08-Advanced-BuildKit-dan-Multi-Architecture/Module-01-BuildKit-Engine-Secret-Mounts-Cache-Mounts-dan-SSH-Forwarding.md)
  - [Module 02: Multi-Architecture Builds, Cross-Compilation (AMD64/ARM64), & Buildx](./BAB-08-Advanced-BuildKit-dan-Multi-Architecture/Module-02-Multi-Architecture-Cross-Compilation-AMD64-ARM64-Buildx.md)
  - [Evaluasi & Quiz BAB 08](./BAB-08-Advanced-BuildKit-dan-Multi-Architecture/BAB-08-Quiz-dan-Challenge.md)
- [BAB 09 — Logging, Monitoring, & Troubleshooting](./BAB-09-Logging-Monitoring-dan-Troubleshooting/)
  - [Module 01: Docker Logging Drivers, Log Rotation, & Centralized Shippers](./BAB-09-Logging-Monitoring-dan-Troubleshooting/Module-01-Docker-Logging-Drivers-Log-Rotation-dan-Shippers.md)
  - [Module 02: Performance Profiling, cAdvisor, Prometheus, & OOM Exit Codes](./BAB-09-Logging-Monitoring-dan-Troubleshooting/Module-02-Performance-Profiling-cAdvisor-dan-OOM-Exit-Codes.md)
  - [Evaluasi & Quiz BAB 09](./BAB-09-Logging-Monitoring-dan-Troubleshooting/BAB-09-Quiz-dan-Challenge.md)
- [BAB 10 — Production Deployment & Container Registries](./BAB-10-Production-Deployment-dan-Container-Registries/)
  - [Module 01: Container Registry Architecture (Harbor, ECR, GHCR), Auth, & Tagging](./BAB-10-Production-Deployment-dan-Container-Registries/Module-01-Container-Registry-Architecture-Harbor-ECR-Auth.md)
  - [Module 02: Production Deployment: Systemd Units, Watchtower, & Automated Pruning](./BAB-10-Production-Deployment-dan-Container-Registries/Module-02-Production-Deployment-Systemd-Watchtower-Pruning.md)
  - [Evaluasi & Quiz BAB 10](./BAB-10-Production-Deployment-dan-Container-Registries/BAB-10-Quiz-dan-Challenge.md)
- [🏆 CAPSTONE PROJECT: Enterprise Microservices Infrastructure](./CAPSTONE-PROJECT-Production-Grade-Microservices-Docker.md)

---

## 🛠️ Prasyarat (Prerequisites)
- Memahami dasar sistem operasi Linux (Terminal, Shell commands, file permissions).
- Memahami dasar jaringan komputer (Port, IP address, HTTP protocol).
- Node.js v18+ terinstall untuk menjalankan script simulasi di folder `hands-on/`.
- Docker Engine / Docker Desktop (opsional namun sangat disarankan untuk latihan riil).
