# ☸️ Kubernetes Mastery: From Core Architecture to Production GitOps Platform

Selamat datang di kurikulum **Kubernetes Mastery**! Kurikulum ini disusun secara komprehensif, terstruktur, mendalam, dan berbasis praktik nyata untuk membimbing Anda menguasai orkestrasi kontainer tingkat lanjut menggunakan standar industri [roadmap.sh/kubernetes](https://roadmap.sh/kubernetes).

---

## 🗺️ Peta Kurikulum (Curriculum Roadmap)

```text
                                [ KUBERNETES MASTERY ]
                                          |
    +-------------------------------------+-------------------------------------+
    |                                                                           |
    v                                                                           v
[ FONDASI & WORKLOADS ]                                             [ NETWORKING & STORAGE ]
├── BAB 01: Arsitektur Internal & Control Plane                     ├── BAB 05: Service Discovery, kube-proxy, Ingress
├── BAB 02: Pods, Lifecycle, Probes, & Multi-Container             ├── BAB 06: CNI (Calico/Cilium eBPF) & NetworkPolicies
├── BAB 03: Workload Controllers (Deployments, StatefulSets)        └── BAB 07: Storage, PersistentVolumes, PVC, & CSI
└── BAB 04: ConfigMaps, Secrets, & Decoupled Configuration                      |
                                                                                v
                                                                    [ SECURITY & GOVERNANCE ]
                                                                    ├── BAB 08: RBAC & Admission Controllers (Kyverno)
                                                                    └── BAB 09: Advanced Scheduling & Autoscaling (Karpenter)
                                                                                |
                                                                                v
                                                                    [ GITOPS & PRODUCTION ]
                                                                    ├── BAB 10: Helm, Kustomize, ArgoCD, & Troubleshooting
                                                                    └── 🏆 CAPSTONE PROJECT: Enterprise Multi-Tenant Cluster
```

---

## 📚 Daftar Bab Pembelajaran

- [BAB 01 — Arsitektur Internal & Control Plane Kubernetes](./BAB-01-Arsitektur-Internal-dan-Control-Plane/)
  - [Module 01: Arsitektur Control Plane (kube-apiserver, etcd Quorum, Controller Manager, Scheduler)](./BAB-01-Arsitektur-Internal-dan-Control-Plane/Module-01-Arsitektur-Control-Plane-apiserver-etcd-controller-scheduler.md)
  - [Module 02: Arsitektur Worker Node (kubelet, kube-proxy, CRI containerd, cgroup v2)](./BAB-01-Arsitektur-Internal-dan-Control-Plane/Module-02-Arsitektur-Worker-Node-kubelet-kube-proxy-CRI.md)
  - [Evaluasi & Quiz BAB 01](./BAB-01-Arsitektur-Internal-dan-Control-Plane/BAB-01-Quiz-dan-Challenge.md)
- [BAB 02 — Primitif Komputasi: Pod, Lifecycle, & Multi-Container Patterns](./BAB-02-Pod-Lifecycle-dan-Multi-Container-Patterns/)
  - [Module 01: Anatomi Pod, Pod Phase, Probes (Liveness, Readiness, Startup), & Graceful Termination](./BAB-02-Pod-Lifecycle-dan-Multi-Container-Patterns/Module-01-Anatomi-Pod-Lifecycle-Probes-dan-Termination.md)
  - [Module 02: Multi-Container Patterns: Sidecar, Init Container, Ambassador, & Ephemeral Containers](./BAB-02-Pod-Lifecycle-dan-Multi-Container-Patterns/Module-02-Multi-Container-Patterns-Sidecar-Init-dan-Ephemeral.md)
  - [Evaluasi & Quiz BAB 02](./BAB-02-Pod-Lifecycle-dan-Multi-Container-Patterns/BAB-02-Quiz-dan-Challenge.md)
- [BAB 03 — Workload Controllers: Deployments, StatefulSets, & DaemonSets](./BAB-03-Workload-Controllers/)
  - [Module 01: ReplicaSets, Deployments (RollingUpdate vs Recreate), & Rollback Strategy](./BAB-03-Workload-Controllers/Module-01-Deployments-RollingUpdate-Strategies-dan-Rollbacks.md)
  - [Module 02: StatefulSets (Stable Network ID, Headless Services) vs DaemonSets & Jobs/CronJobs](./BAB-03-Workload-Controllers/Module-02-StatefulSets-DaemonSets-Jobs-dan-CronJobs.md)
  - [Evaluasi & Quiz BAB 03](./BAB-03-Workload-Controllers/BAB-03-Quiz-dan-Challenge.md)
- [BAB 04 — Konfigurasi, Secrets, & Decoupled Architecture](./BAB-04-Konfigurasi-Secrets-dan-Decoupled-Architecture/)
  - [Module 01: ConfigMaps, Downward API, Volume Mounts vs Env Vars, & Hot-Reload](./BAB-04-Konfigurasi-Secrets-dan-Decoupled-Architecture/Module-01-ConfigMaps-Downward-API-dan-Hot-Reload.md)
  - [Module 02: Kubernetes Secrets, Opaque, TLS, External Secrets Operator (ESO), & Secret Encryption](./BAB-04-Konfigurasi-Secrets-dan-Decoupled-Architecture/Module-02-Secrets-External-Secrets-Operator-dan-Encryption.md)
  - [Evaluasi & Quiz BAB 04](./BAB-04-Konfigurasi-Secrets-dan-Decoupled-Architecture/BAB-04-Quiz-dan-Challenge.md)
- [BAB 05 — Kubernetes Networking, Service Discovery, & Ingress](./BAB-05-Networking-Service-Discovery-dan-Ingress/)
  - [Module 01: Service Types (ClusterIP, NodePort, LoadBalancer, Headless), kube-proxy IPVS, & CoreDNS](./BAB-05-Networking-Service-Discovery-dan-Ingress/Module-01-Service-Types-kube-proxy-IPVS-dan-CoreDNS.md)
  - [Module 02: Ingress Controller (Nginx, Traefik), IngressClass, cert-manager, & Gateway API](./BAB-05-Networking-Service-Discovery-dan-Ingress/Module-02-Ingress-Controllers-cert-manager-dan-Gateway-API.md)
  - [Evaluasi & Quiz BAB 05](./BAB-05-Networking-Service-Discovery-dan-Ingress/BAB-05-Quiz-dan-Challenge.md)
- [BAB 06 — Network Security & Isolation: CNI & NetworkPolicies](./BAB-06-Network-Security-CNI-dan-NetworkPolicies/)
  - [Module 01: Container Network Interface (CNI) Calico vs Cilium (eBPF) & Pod Routing](./BAB-06-Network-Security-CNI-dan-NetworkPolicies/Module-01-CNI-Calico-vs-Cilium-eBPF-dan-Routing.md)
  - [Module 02: Kubernetes NetworkPolicies (Default Deny, Ingress/Egress, CIDR & Namespace Selectors)](./BAB-06-Network-Security-CNI-dan-NetworkPolicies/Module-02-NetworkPolicies-Default-Deny-dan-Microsegmentation.md)
  - [Evaluasi & Quiz BAB 06](./BAB-06-Network-Security-CNI-dan-NetworkPolicies/BAB-06-Quiz-dan-Challenge.md)
- [BAB 07 — Storage, Persistence, & Container Storage Interface (CSI)](./BAB-07-Storage-Persistence-dan-CSI/)
  - [Module 01: PersistentVolumes (PV), PersistentVolumeClaims (PVC), & Reclaim Policies](./BAB-07-Storage-Persistence-dan-CSI/Module-01-PV-PVC-Lifecycle-dan-Reclaim-Policies.md)
  - [Module 02: StorageClasses, Dynamic Provisioning, CSI Drivers (EBS, Longhorn, Ceph), & Snapshots](./BAB-07-Storage-Persistence-dan-CSI/Module-02-StorageClasses-Dynamic-Provisioning-dan-CSI-Drivers.md)
  - [Evaluasi & Quiz BAB 07](./BAB-07-Storage-Persistence-dan-CSI/BAB-07-Quiz-dan-Challenge.md)
- [BAB 08 — Keamanan Cluster: RBAC, ServiceAccounts, & Admission Controllers](./BAB-08-Security-RBAC-dan-Admission-Controllers/)
  - [Module 01: Role-Based Access Control (RBAC), Roles, ClusterRoles, RoleBindings, & Least Privilege](./BAB-08-Security-RBAC-dan-Admission-Controllers/Module-01-RBAC-Roles-ClusterRoles-dan-Least-Privilege.md)
  - [Module 02: Pod Security Standards (PSS) & Admission Webhooks (Kyverno / OPA Gatekeeper)](./BAB-08-Security-RBAC-dan-Admission-Controllers/Module-02-Pod-Security-Standards-dan-Admission-Webhooks.md)
  - [Evaluasi & Quiz BAB 08](./BAB-08-Security-RBAC-dan-Admission-Controllers/BAB-08-Quiz-dan-Challenge.md)
- [BAB 09 — Scheduling Lanjutan & Autoscaling (HPA, VPA, Karpenter)](./BAB-09-Scheduling-Lanjutan-dan-Autoscaling/)
  - [Module 01: Advanced Scheduling: Taints & Tolerations, NodeAffinity, & PodTopologySpread](./BAB-09-Scheduling-Lanjutan-dan-Autoscaling/Module-01-Taints-Tolerations-NodeAffinity-dan-TopologySpread.md)
  - [Module 02: Autoscaling: Horizontal Pod Autoscaler (HPA v2), VPA, & Just-in-Time Karpenter](./BAB-09-Scheduling-Lanjutan-dan-Autoscaling/Module-02-Autoscaling-HPA-VPA-dan-Karpenter.md)
  - [Evaluasi & Quiz BAB 09](./BAB-09-Scheduling-Lanjutan-dan-Autoscaling/BAB-09-Quiz-dan-Challenge.md)
- [BAB 10 — Packaging (Helm/Kustomize), GitOps (ArgoCD), & Troubleshooting](./BAB-10-Packaging-GitOps-dan-Troubleshooting/)
  - [Module 01: Package Management dengan Helm v3 vs Declarative Kustomize Overlays](./BAB-10-Packaging-GitOps-dan-Troubleshooting/Module-01-Helm-v3-vs-Kustomize-Package-Management.md)
  - [Module 02: GitOps Delivery dengan ArgoCD & Production Troubleshooting Runbook](./BAB-10-Packaging-GitOps-dan-Troubleshooting/Module-02-GitOps-ArgoCD-dan-Production-Troubleshooting.md)
  - [Evaluasi & Quiz BAB 10](./BAB-10-Packaging-GitOps-dan-Troubleshooting/BAB-10-Quiz-dan-Challenge.md)
- [🏆 CAPSTONE PROJECT: Enterprise Multi-Tenant Microservices Kubernetes Platform](./CAPSTONE-PROJECT-Enterprise-MultiTenant-Microservices-K8s.md)

---

## 🛠️ Prasyarat (Prerequisites)
- Menguasai konsep dasar containerization, Dockerfile, image, dan Docker Compose ([Docker Mastery](../Docker/README.md)).
- Memahami dasar jaringan komputer (Subnetting, DNS, IP routing, HTTP/HTTPS reverse proxy).
- Pemahaman Linux command-line dan YAML syntax.
- Node.js v18+ terinstall untuk menjalankan script simulasi di folder `hands-on/`.
