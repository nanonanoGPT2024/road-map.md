# Module 02: Ingress Controllers, cert-manager TLS Automasi, dan Kubernetes Gateway API

---
[⬅️ Module 01: Service Types & CoreDNS](./Module-01-Service-Types-kube-proxy-IPVS-dan-CoreDNS.md) | [📋 Silabus Induk](../README.md) | [Evaluasi & Quiz BAB 05 ➡️](./BAB-05-Quiz-dan-Challenge.md)
---

## 1. Learning Objective
Setelah menyelesaikan modul ini, pembelajar diharapkan mampu:
1. Memahami perbedaan fundamental antara routing Layer 4 (Service LoadBalancer) vs routing Layer 7 (HTTP/HTTPS **Ingress**).
2. Mengonfigurasi **Ingress Controller** (Nginx / Traefik) dan mendeklarasikan aturan routing berbasis Host (*Virtual Hosting*) dan Path (*Path-based routing*).
3. Mengotomatisasi penerbitan dan pembaruan sertifikat SSL/TLS gratis (Let's Encrypt) menggunakan **`cert-manager`** melalui tantangan ACME HTTP-01 dan DNS-01.
4. Memahami kelemahan model Ingress monolitik dan bagaimana **Kubernetes Gateway API** mengatasinya melalui arsitektur berorientasi peran (*Role-Oriented Design*).
5. Mengimplementasikan pembagian lalu lintas (*traffic splitting*) dan manipulasi header menggunakan **Gateway** dan **HTTPRoute**.

---

## 2. Prerequisite
- Memahami konsep Service ClusterIP dan EndpointSlices ([Module 01 BAB 05](Module-01-Service-Types-kube-proxy-IPVS-dan-CoreDNS.md)).
- Memahami konsep Secret tipe `kubernetes.io/tls` ([BAB 04 Module 02](../BAB-04-Konfigurasi-Secrets-dan-Decoupled-Architecture/Module-02-Secrets-External-Secrets-Operator-dan-Encryption.md)).
- Pemahaman protokol HTTP/1.1, HTTP/2, TLS Handshake, dan DNS A/CNAME records.

---

## 3. Concept
Jika Anda memiliki 20 microservices yang berbeda di dalam kluster dan ingin mengekspos semuanya ke internet menggunakan `type: LoadBalancer`, cloud provider (AWS/GCP) akan membuat 20 Network Load Balancer terpisah yang memakan biaya ratusan dollar per bulan. Selain itu, Layer 4 Load Balancer tidak bisa membaca path URL HTTP (seperti `/api/v1` vs `/auth`).

**Ingress** bertindak sebagai gerbang masuk cerdas Layer 7 (Application Layer) di tepi kluster:
- Mengonsolidasikan seluruh routing HTTP/HTTPS ke dalam satu IP publik tunggal.
- Melakukan terminasi SSL/TLS (HTTPS decryption) terpusat.
- Merutekan traffic ke Service internal berdasarkan domain (*Host Header*) dan path URL (*Request URI*).

Di Kubernetes modern, Ingress berevolusi menjadi **Gateway API**: standar generasi berikutnya yang memisahkan tanggung jawab infrastruktur jaringan (dikelola SysAdmin/Platform Team) dari aturan routing aplikasi (dikelola App Developers).

---

## 4. Why?
1. **Efisiensi Biaya Cloud (Cost Consolidation)**: Menggunakan 1 instance Ingress Controller yang berbagi 1 Cloud Load Balancer untuk melayani ratusan domain dan ribuan microservices.
2. **Automasi Total Siklus Hidup SSL/TLS**: Menghilangkan risiko insiden sertifikat SSL kedaluwarsa (*expired certificate outage*) dengan otomasi pembaruan 90-harian Let's Encrypt via `cert-manager`.
3. **Pemisahan Kewenangan (Role Separation via Gateway API)**: Developer tidak perlu hak admin kluster untuk mengubah routing path API mereka, dan Admin platform dapat mengunci kebijakan keamanan TLS secara terpusat.

---

## 5. What?
### Komparasi Arsitektur: Ingress vs Gateway API

| Fitur | Ingress Klasik (v1) | Gateway API Modern (v1 GA) |
|---|---|---|
| **Model Desain** | Monolitik tunggal (`kind: Ingress`). | Berorientasi Peran: `GatewayClass` (Infra), `Gateway` (Cluster Ops), `HTTPRoute` (Devs). |
| **Dukungan Protokol** | Terbatas pada HTTP/HTTPS. | Multi-protokol native: HTTP, HTTPS, gRPC, TCP, TLS, UDP. |
| **Fitur Lanjutan (Canary/Headers)** | Bergantung pada annotasi vendor yang kaku (`nginx.ingress.kubernetes.io/...`). | Standar bawaan resmi: Traffic splitting (50:50), request header modifier, redirect/rewrite. |
| **Routing Lintas Namespace** | Sangat sulit dan tidak aman. | Native aman via `ReferenceGrant`. |

---

## 6. How? Alur Kerja Ingress Controller & cert-manager

```text
       [ Internet Client: https://api.mycompany.com/checkout ]
                                  |
                                  v :443 (TLS Encrypted)
+-----------------------------------------------------------------------------------+
|                        AWS Network Load Balancer (NLB)                            |
+-----------------------------------------------------------------------------------+
                                  |
                                  v
+-----------------------------------------------------------------------------------+
|               Ingress Controller Pod (ingress-nginx / Traefik)                    |
|                                                                                   |
|  1. TLS Termination: Membaca Secret 'mycompany-tls' (Dikelola cert-manager)       |
|  2. Evaluasi Routing Rules:                                                       |
|     - Host: api.mycompany.com? -> MATCH!                                          |
|     - Path: /checkout?          -> MATCH! Target: checkout-svc:8080               |
+-----------------------------------------------------------------------------------+
                                  |
                                  v (Forward HTTP unencrypted via ClusterIP)
+-----------------------------------------------------------------------------------+
|                       Service: checkout-svc (ClusterIP)                           |
+-----------------------------------------------------------------------------------+
                                  |
                                  v
                    [ Pods Backend: checkout-api ]
```

### Alur Automasi ACME Let's Encrypt (`cert-manager`):
1. `cert-manager` memantau annotasi Ingress: `cert-manager.io/cluster-issuer: letsencrypt-prod`.
2. `cert-manager` otomatis membuat objek `Certificate` dan `Order`.
3. Menjalankan tantangan **HTTP-01**: Let's Encrypt memvalidasi kepemilikan domain dengan mengakses file token di `http://api.mycompany.com/.well-known/acme-challenge/<token>`.
4. Jika valid, Let's Encrypt menerbitkan sertifikat SSL x509 yang disimpan otomatis ke Kubernetes Secret tipe `kubernetes.io/tls`.

---

## 7. Analogy
Bayangkan bandara kedatangan internasional:
- **Service LoadBalancer (L4)** adalah taksi pangkalan di luar bandara yang langsung mengantar penumpang ke alamat tertentu tanpa tahu apa isi koper penumpang.
- **Ingress Controller (L7)** adalah petugas imigrasi di dalam bandara. Petugas memeriksa dokumen paspor penumpang (Host header dan Path URL), lalu mengarahkan penumpang ke loket bea cukai yang tepat (`/customs`) atau loket transit (`/transit`).
- **cert-manager** adalah kantor perpanjangan paspor diplomatik otomatis. Tiga puluh hari sebelum paspor kedaluwarsa, petugas otomatis mencetak paspor baru dan menaruhnya di saku Anda tanpa perlu Anda mengantri.
- **Gateway API** adalah bandara modern di mana manajer bandara membangun gerbang fisik (`Gateway`), maskapai penerbangan mengatur jadwal penerbangan (`HTTPRoute`), dan keduanya tidak saling mengganggu kewenangan.

---

## 8. Diagram: Arsitektur Gateway API (Role-Oriented Design)

```text
[ Peran: Cloud / Platform Provider ]
  └── GatewayClass: "envoy-gateway" (Definisi controller implementasi)
            |
            v
[ Peran: Cluster Operator / SRE ]
  └── Gateway: "public-gateway" (Mendengarkan Port 80 & 443, mengunci sertifikat SSL TLS)
            |
            +------------------------------------+
            | (Izinkan namespace dev melampirkan rute)
            v                                    v
[ Peran: Tim Checkout App ]            [ Peran: Tim Auth App ]
  └── HTTPRoute: "checkout-route"        └── HTTPRoute: "auth-route"
      Path: /checkout                        Path: /login, /oauth
      Target: checkout-service:8080          Target: auth-service:8080
```

---

## 9. Simple Example: Ingress Nginx dengan Host & Path Routing

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: platform-ingress
  namespace: production
  annotations:
    kubernetes.io/ingress.class: "nginx"
    # Menghapus prefix path saat diteruskan ke backend jika diperlukan
    nginx.ingress.kubernetes.io/rewrite-target: /$2
spec:
  ingressClassName: nginx
  rules:
  - host: api.mycompany.com
    http:
      paths:
      # Routing ke Payment Service
      - path: /payment(/|$)(.*)
        pathType: ImplementationSpecific
        backend:
          service:
            name: payment-service
            port:
              number: 8080
      # Routing ke Order Service
      - path: /order(/|$)(.*)
        pathType: ImplementationSpecific
        backend:
          service:
            name: order-service
            port:
              number: 8080
```

---

## 10. Practical Example: Automasi SSL/TLS dengan cert-manager

### 1. Deklarasi `ClusterIssuer` (Let's Encrypt Production):
```yaml
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: security@mycompany.com
    privateKeySecretRef:
      name: letsencrypt-prod-account-key
    solvers:
    - http01:
        ingress:
          class: nginx
```

### 2. Ingress dengan TLS Automasi Otomatis:
```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: secure-api-ingress
  namespace: production
  annotations:
    # Trigger otomatis cert-manager!
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
spec:
  ingressClassName: nginx
  tls:
  - hosts:
    - api.mycompany.com
    secretName: api-mycompany-tls # cert-manager akan membuat Secret ini secara otomatis!
  rules:
  - host: api.mycompany.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: api-service
            port:
              number: 8080
```

---

## 11. Practical Example: Kubernetes Gateway API (HTTPRoute dengan Traffic Split)

Menerapkan Canary Deployment 80% ke versi stabil (v1) dan 20% ke versi eksperimental (v2) tanpa annotasi regex yang rumit:

```yaml
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: payment-canary-route
  namespace: production
spec:
  parentRefs:
  - name: production-gateway # Mengaitkan rute ke Gateway bersama
  hostnames:
  - "pay.mycompany.com"
  rules:
  - matches:
    - path:
        type: PathPrefix
        value: /v1/checkout
    backendRefs:
    - name: payment-service-v1
      port: 8080
      weight: 80 # 80% traffic
    - name: payment-service-v2
      port: 8080
      weight: 20 # 20% traffic
```

---

## 12. Trade-offs: Ingress vs Gateway API

| Dimensi | Ingress Controller | Gateway API |
|---|---|---|
| **Kematangan Ekosistem** | Sangat matang, ribuan tutorial, standar 10 tahun terakhir. | Standar baru modern (GA sejak 2023), adopsi bertumbuh cepat. |
| **Kemudahan Pemula** | Sangat mudah untuk 1 file YAML sederhana. | Butuh pemahaman konsep multi-resource (`Gateway` vs `Route`). |
| **Advanced Traffic Control** | Butuh annotasi vendor spesifik (tidak portabel antar Ingress). | Portabel 100% di semua provider implementasi. |
| **Dukungan gRPC & TCP** | Kaku dan terbatas. | First-class citizen (`GRPCRoute`, `TCPRoute`, `TLSRoute`). |

---

## 13. When To Use
- Gunakan **Ingress Controller** (seperti `ingress-nginx` atau `traefik`) untuk seluruh ekspos web API standar yang membutuhkan routing path dan domain.
- Gunakan **`cert-manager`** wajib di seluruh kluster produksi untuk eliminasi manajemen manual sertifikat SSL.
- Adopsi **Gateway API** untuk proyek baru atau infrastruktur multi-tim yang menuntut canary release, cross-namespace routing, dan streaming gRPC.

---

## 14. When NOT To Use
- Jangan gunakan Ingress untuk traffic non-HTTP (misal: koneksi raw TCP database PostgreSQL, koneksi MQTT IoT, atau VPN Wireguard). Gunakan Service bertipe `LoadBalancer` Layer 4!
- Jangan gunakan `ClusterIssuer` staging di produksi, karena Let's Encrypt Staging akan menerbitkan sertifikat untrusted (browser akan menampilkan layar merah peringatan).

---

## 15. Common Mistakes
1. **Lupa menginstal Ingress Controller**: Mendefinisikan file `kind: Ingress` tetapi tidak ada controller (seperti Nginx Pod) yang berjalan di kluster. Ingress resource akan diam selamanya tanpa IP publik.
2. **Sertifikat Let's Encrypt Rate-Limited**: Melakukan testing pembuatan sertifikat berkali-kali menggunakan `letsencrypt-prod`, memicu pemblokiran IP oleh Let's Encrypt selama 7 hari. Selalu uji coba di `letsencrypt-staging` terlebih dahulu!
3. **Konflik Path Overlap**: Mendefinisikan `/api` dan `/` tanpa memperhatikan urutan dan `pathType` (`Prefix` vs `Exact`), menyebabkan request selalu masuk ke backend default.

---

## 16. Best Practices
### Must Have
- Selalu tentukan `ingressClassName: nginx` secara eksplisit alih-alih hanya mengandalkan annotasi usang `kubernetes.io/ingress.class`.
- Amankan endpoint API dengan redirect otomatis HTTP ke HTTPS:
  ```yaml
  annotations:
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
  ```

### Recommended
- Konfigurasikan buffer upload size jika API Anda menerima upload file besar:
  ```yaml
  annotations:
    nginx.ingress.kubernetes.io/proxy-body-size: "50m"
  ```
- Terapkan Rate Limiting di level Ingress untuk mencegah serangan DDoS Layer 7:
  ```yaml
  annotations:
    nginx.ingress.kubernetes.io/limit-rps: "20"
  ```

### Advanced
- Di arsitektur enterprise, gunakan Gateway API dengan integrasi OAuth2-Proxy untuk menerapkan autentikasi Single Sign-On (SSO) terpusat sebelum request diteruskan ke backend.

---

## 17. Troubleshooting Guide
### Problem 1: Ingress `ADDRESS` kosong (`<none>`)
- **Penyebab**: Ingress Controller belum dialokasikan IP publik oleh Cloud Provider, atau Service ingress-nginx bertipe LoadBalancer masih `Pending`.
- **Diagnosa**:
  ```bash
  kubectl get ingress -n production
  kubectl get svc -n ingress-nginx
  ```
- **Solusi**: Periksa status Cloud Load Balancer di dashboard AWS/GCP Anda.

### Problem 2: Sertifikat SSL tidak kunjung terbit dari cert-manager
- **Penyebab**: Tantangan HTTP-01 gagal karena domain belum diarahkan ke IP publik Ingress di DNS registrar.
- **Diagnosa**:
  ```bash
  kubectl describe certificate <nama-cert>
  kubectl describe challenge
  ```
  Pesan error umum: `Waiting for HTTP-01 challenge propagation: 404 Not Found`.

---

## 18. Exercises
### Level: Easy
1. Periksa apakah kluster Anda memiliki IngressClass terdaftar:
   `kubectl get ingressclass`
2. Buat Ingress sederhana yang merutekan domain lokal `app.local` ke Service Nginx port 80.

### Level: Medium
1. Konfigurasikan path-based routing pada satu Ingress: path `/app1` ke Service 1, path `/app2` ke Service 2.
2. Uji coba pengujian URL menggunakan `curl -H "Host: app.local" http://<ingress-ip>/app1`.

### Level: Hard
1. Install cert-manager di kluster Anda menggunakan Helm atau manifest resmi.
2. Buat `ClusterIssuer` ACME Let's Encrypt Staging.
3. Sambungkan ke Ingress dan verifikasi bahwa Secret TLS otomatis terbuat di namespace Anda.

---

## 19. Challenge
Rancang arsitektur Edge Routing untuk Super-App E-Commerce:
- Domain publik: `https://tokokita.com`.
- Path `/api/v1/auth` diarahkan ke Service Auth.
- Path `/api/v1/catalog` diarahkan ke Service Catalog.
- Path `/api/v1/pay` diarahkan ke Gateway API dengan Canary Traffic Split: 90% ke `payment-v1` dan 10% ke `payment-v2`.
- Otomatisasi sertifikat SSL HTTPS menggunakan cert-manager Let's Encrypt Production.
Tuliskan seluruh konfigurasi manifest Ingress, ClusterIssuer, dan HTTPRoute secara terpadu.

---

## 20. Summary
- **Ingress Controller** bertindak sebagai reverse proxy Layer 7 cerdas yang menggabungkan banyak rute HTTP/HTTPS di balik satu IP publik.
- **`cert-manager`** menghilangkan kerumitan manual pembaruan sertifikat SSL dengan otomatisasi ACME Let's Encrypt.
- **Kubernetes Gateway API** memodernisasi Ingress dengan pemisahan peran tim (*Role-Oriented Design*), dukungan multi-protokol (gRPC/TCP), dan fitur canary traffic splitting bawaan.

---
[⬅️ Module 01: Service Types & CoreDNS](./Module-01-Service-Types-kube-proxy-IPVS-dan-CoreDNS.md) | [📋 Silabus Induk](../README.md) | [Evaluasi & Quiz BAB 05 ➡️](./BAB-05-Quiz-dan-Challenge.md)
---
