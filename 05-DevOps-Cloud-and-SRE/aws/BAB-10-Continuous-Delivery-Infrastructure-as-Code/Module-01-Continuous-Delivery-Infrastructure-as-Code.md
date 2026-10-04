# Modul 01: Continuous Delivery & Infrastructure as Code (IaC) pada AWS

## 1. Learning Objective
Setelah menyelesaikan modul ini, peserta diharapkan mampu:
- Merancang, mengotomatisasi, dan mengelola provisioning infrastruktur cloud skala enterprise menggunakan AWS CloudFormation dan AWS Cloud Development Kit (CDK v2).
- Membangun pipeline CI/CD zero-downtime berbasis AWS CodePipeline, AWS CodeBuild, dan AWS CodeDeploy dengan strategi deployment bertahap (Canary dan Linear).
- Mengimplementasikan paradigma GitOps pada Amazon Elastic Kubernetes Service (EKS) menggunakan ArgoCD untuk sinkronisasi state deklaratif yang rekonsiliatif.
- Merancang arsitektur Disaster Recovery (DR) lintas region (Multi-Region Failover) dengan metrik Recovery Time Objective (RTO) dan Recovery Point Objective (RPO) yang terukur menggunakan Route 53 Application Recovery Controller (ARC) dan replikasi data global.

## 2. Prerequisite
Sebelum mempelajari modul ini, peserta wajib memahami:
- Konsep dasar Amazon Web Services: VPC, Subnetting, Security Groups, IAM Roles & Policies, Route 53, ALB, ECS/EKS.
- Konsep dasar containerization: Docker container, Pods, Services, dan Ingress pada Kubernetes.
- Pemahaman praktis mengenai version control: Git branching model (Trunk-Based Development dan GitFlow).
- Dasar pemrograman modern: Python 3.x atau TypeScript (Node.js LTS) untuk pengembangan AWS CDK.
- Akses ke AWS CLI v2 terkonfigurasi dengan privileges setara `AdministratorAccess` pada sandbox/development account.

## 3. Concept
Continuous Delivery (CD) dan Infrastructure as Code (IaC) adalah dua pilar fundamental SRE yang mentransformasikan siklus hidup perangkat lunak dari proses manual yang rentan kesalahan menjadi pipeline deterministik, dapat diulang (*repeatable*), dan dapat diaudit (*auditable*).

IaC memperlakukan topologi infrastruktur jaringan, komputasi, dan penyimpanan setara dengan kode aplikasi. Perubahan infrastruktur didefinisikan secara deklaratif, diuji melalui linting dan static analysis, divalidasi dependensinya melalui graph engine, lalu dieksekusi secara otomatis.

Dalam continuous delivery modern, pipeline bertindak sebagai gerbang invariant kualitas perangkat lunak. Pipeline tidak hanya mengompilasi dan menguji kode, tetapi juga mengelola rilis bertahap (Canary Deployments) dengan monitor telemetri aktif. Jika degradasi terdeteksi, mekanisme automated rollback langsung dipicu untuk membatasi *blast radius*. Ketika sistem diperluas ke topologi multi-region, pipeline dan IaC menjamin paritas konfigurasi antar region guna memfasilitasi failover Disaster Recovery (DR) tanpa desinkronisasi arsitektur.

## 4. Why
Pendekatan konfigurasi manual berbasis antarmuka grafis (ClickOps) memiliki kelemahan struktural:
- **Configuration Drift:** Perbedaan tersembunyi antara environment Dev, Staging, dan Production yang memicu insiden saat rilis.
- **Human Error & Inconsistency:** Tingginya risiko kesalahan konfigurasi parameter keamanan (misalnya IAM Policy permissive atau security group terbuka ke `0.0.0.0/0`).
- **High MTTR (Mean Time to Recovery):** Saat bencana regional melanda, merekonstruksi infrastruktur secara manual membutuhkan waktu berjam-jam bahkan berhari-hari, melanggar batas SLA/RTO.
- **Uncontrolled Blast Radius:** Deployment model *all-at-once* (big bang) langsung mengekspos 100% trafik pengguna ke potensi cacat perangkat lunak.

Penerapan AWS IaC (CloudFormation/CDK), GitOps (ArgoCD), dan Canary Pipelines memitigasi risiko tersebut dengan menjamin:
1. **Auditability & Traceability:** Setiap baris konfigurasi terlacak di Git commit log.
2. **Deterministic Deployments:** State yang identik di seluruh environment.
3. **Automated Blast Radius Containment:** Hanya sebagian kecil trafik pengguna (misal 5%-10%) yang terpapar versi baru hingga metrik stabilitas terkonfirmasi.
4. **Resilience & Continuity:** Otomasi multi-region failover memastikan kelangsungan operasional sistem bisnis kritis.

## 5. What (Deep-Dive Teknis Lengkap)

### 5.1 AWS CloudFormation Internals
AWS CloudFormation adalah mesin deployment deklaratif berbasis template JSON/YAML.
- **Template Anatomy:** Terdiri dari seksi `AWSTemplateFormatVersion`, `Parameters`, `Mappings`, `Conditions`, `Resources` (wajib), dan `Outputs`.
- **Dependency Graph & Engine:** CloudFormation menganalisis dependensi implisit (via fungsi intrinsik `Ref` dan `Fn::GetAtt`) serta dependensi eksplisit (`DependsOn`) untuk membangun Directed Acyclic Graph (DAG). Eksekusi provisioning paralel dilakukan berdasarkan graf ini.
- **Change Sets:** Membandingkan state live dari stack dengan template yang diajukan. Mengidentifikasi apakah resource akan mengalami aksi *Add*, *Modify* (dengan atau tanpa replacement), atau *Remove*.
- **Drift Detection:** Membandingkan konfigurasi aktual resource AWS terhadap template yang didefinisikan saat deployment terakhir, mengidentifikasi manipulasi out-of-band.
- **Rollback Engine:** Jika satu resource gagal dibuat/diupdate, CloudFormation secara default mengembalikan seluruh perubahan ke *last known good state*. Fitur Stack Failure Options memungkinkan developer mengisolasi kegagalan untuk keperluan debugging.

### 5.2 AWS Cloud Development Kit (CDK v2)
AWS CDK adalah framework software development open-source untuk mendefinisikan infrastruktur cloud menggunakan bahasa pemrograman imperatif (TypeScript, Python, Go, Java, C#) yang kemudian disintesis menjadi template AWS CloudFormation deklaratif.
- **Constructs Hierarchy:**
  - **L1 Constructs (Cfn Resources):** Representasi pemetaan 1:1 langsung ke resource CloudFormation murni (misal: `CfnBucket`).
  - **L2 Constructs (AWS Curated):** Abstraksi level lebih tinggi dengan *sensible defaults*, konfigurasi keamanan terintegrasi, dan helper methods (misal: `s3.Bucket` dengan otomatisasi enkripsi SSE-KMS).
  - **L3 Constructs (Solutions / Patterns):** Komposisi beberapa resource L2 untuk merancang arsitektur siap pakai (misal: `NetworkLoadBalancedFargateService`).
- **Synthesis Engine:** Perintah `cdk synth` mengeksekusi kode aplikasi, membangun construct tree di memori, dan mengompilasinya menjadi satu himpunan artefak CloudFormation template dan asset metadata (`cdk.out`).
- **Asset Handling:** CDK mengotomatisasi pengunggahan Docker image ke Amazon ECR dan zip file source code Lambda ke Amazon S3 selama fase `cdk deploy`.

### 5.3 AWS CodePipeline, CodeBuild, dan Canary CodeDeploy
- **AWS CodePipeline:** Orkestrator alur kerja berbasis *event-driven* (EventBridge). Pipeline membagi alur kerja ke dalam *Stages* dan *Actions* (Source, Build, Test, Deploy). Menggunakan S3 bucket terenkripsi KMS sebagai penyimpanan artefak transit.
- **AWS CodeBuild:** Layanan build dan integrasi berbasis container yang terisolasi. Mengeksekusi instruksi dari file `buildspec.yml` yang terbagi atas fase: `install`, `pre_build`, `build`, dan `post_build`.
- **AWS CodeDeploy & Canary Deployment:** 
  CodeDeploy menggeser beban trafik aplikasi secara bertahap menggunakan konfigurasi deployment standar atau kustom:
  - `Canary10Percent5Minutes`: Mengalihkan 10% trafik ke versi baru, menunggu 5 menit seraya memonitor CloudWatch Alarms. Jika alarm berstatus `ALARM`, CodeDeploy langsung melakukan rollback seketika. Jika sehat, sisa 90% trafik dialihkan.
  - `Linear10PercentEvery1Minute`: Mengalihkan trafik bertahap sebesar 10% setiap menit hingga mencapai 100%.
  - Integrasi Lifecycle Event Hooks: `BeforeInstall`, `AfterInstall`, `ApplicationStart`, `BeforeAllowTraffic`, `AllowTraffic`, `AfterAllowTraffic`, dan `ApplicationStop`. Validasi performa integrasi end-to-end dieksekusi pada hook `BeforeAllowTraffic` dan `AfterAllowTraffic` via fungsi AWS Lambda.

### 5.4 GitOps Engine: ArgoCD pada Amazon EKS
GitOps memformalisasikan Git sebagai *single source of truth* untuk infrastruktur deklaratif dan aplikasi.
- **Pull-based vs Push-based:** Berbeda dengan pipeline CI/CD tradisional (push) yang membutuhkan kredensial IAM/Kubernetes dengan hak akses tinggi ke klaster EKS, ArgoCD beroperasi dari dalam klaster (pull).
- **Reconciliation Loop:** ArgoCD Application Controller secara periodik (default tiap 3 menit atau dipicu via Webhook Git) membandingkan `Target State` (manifest YAML/Helm/Kustomize di Git) dengan `Live State` (resource runtime di etcd EKS).
- **Sync & Self-Healing:** Jika terjadi drift (misalnya Pods diubah manual via `kubectl`), ArgoCD mendeteksi status `OutOfSync`. Jika fitur `self-healing` dan `automated-sync` diaktifkan, ArgoCD akan memulihkan live state agar kembali identik dengan deklarasi Git.
- **Argo Rollouts:** Extension controller Kubernetes yang menggantikan resource `Deployment` standar dengan kapabilitas canary, blue-green, traffic routing (via AWS ALB Ingress Controller atau Service Mesh), dan analisis otomatis berbasis metrik Prometheus/CloudWatch.

### 5.5 Disaster Recovery & Multi-Region Failover Architecture
Arsitektur kelangsungan bisnis AWS diklasifikasikan berdasarkan batas RTO (toleransi durasi downtime) dan RPO (toleransi kehilangan data transaksi):
- **Backup and Restore:** RTO/RPO dalam hitungan jam/hari. Snapshot disimpan dan direplikasi ke secondary region.
- **Pilot Light:** RTO/RPO dalam hitungan puluhan menit. Data inti direplikasi secara kontinu (misal Aurora Global Database atau DynamoDB Global Tables), komputasi dijalankan secara minimal atau dorman hingga dipicu failover.
- **Warm Standby:** RTO/RPO dalam hitungan menit. Komputasi berjalan di secondary region dengan kapasitas tereduksi, siap di-scale up secara horizontal saat failover.
- **Active-Active Multi-Region:** RTO near-zero, RPO near-zero. Beban trafik dilayani bersamaan oleh dua atau lebih region AWS.
- **Traffic Routing Engine:**
  - **Amazon Route 53 Application Recovery Controller (ARC):** Menyediakan kontrol kesiapan (*readiness checks*) dan routing controls terdistribusi lintas sel/region dengan jaminan availability 99.9999% pada control plane routing-nya.
  - **Global Accelerator / Route 53 Latency-based Routing:** Mengarahkan end-user ke endpoint regional paling optimal berdasarkan latensi jaringan global AWS.

## 6. How
Implementasi siklus hidup CD dan IaC end-to-end mengikuti alur metodologis:
1. **Definisikan Fondasi Infrastruktur (IaC):**
   - Bangun modul VPC, Subnet, dan Security Groups menggunakan AWS CDK L2 Constructs.
   - Buat cluster Amazon EKS multi-AZ terenkripsi dengan AWS KMS Customer Managed Key (CMK).
2. **Deploy GitOps Controller:**
   - Install ArgoCD ke dalam EKS menggunakan Helm chart resmi dengan CDK atau script bootstrapping.
   - Konfigurasi IAM Roles for Service Accounts (IRSA) untuk memberikan hak akses AWS secara granular ke workload Kubernetes tanpa hardcoded secret.
3. **Konfigurasi Continuous Integration (CI):**
   - Buat AWS CodePipeline yang menarik source code dari AWS CodeCommit atau GitHub.
   - Jalankan AWS CodeBuild untuk unit test, linting, build Docker image, vulnerability scan (Trivy), dan push artefak image ke Amazon ECR dengan tag immutable SHA Git commit.
4. **Perbarui State Manifest GitOps:**
   - CodeBuild mengupdate tag image pada repositori konfigurasi GitOps (environment repo) melalui commit otomatis.
5. **Continuous Deployment via ArgoCD & Canary:**
   - ArgoCD mendeteksi update commit di repo konfigurasi, lalu memicu sinkronisasi ke EKS.
   - Argo Rollouts mengambil alih proses deployment: mengalokasikan 10% trafik ke versi Canary, menjalankan analisis metrik selama interval waktu tertentu, mengevaluasi error rate dan response latency.
   - Jika metrik berada di bawah ambang batas error, trafik dinaikkan secara bertahap (25%, 50%, 100%). Jika terjadi anomali, sistem otomatis membatalkan rollout dan kembali ke versi stabil.
6. **Multi-Region Failover Strategy:**
   - Replikasi arsitektur yang sama ke region sekunder (misal `ap-southeast-1` primer dan `ap-southeast-3` sekunder).
   - Sinkronisasi data plane menggunakan Amazon Aurora Global Database atau DynamoDB Global Tables.
   - Monitor sistem secara terpusat dan lakukan pengalihan trafik via Route 53 ARC Routing Controls saat status kesehatan region primer mengalami degradasi fatal.

## 7. Analogy
Bayangkan proses rilis aplikasi seperti mendistribusikan pasokan air minum baru ke seluruh kota:
- **CloudFormation/CDK** adalah *cetak biru teknik sipil dan tim konstruksi otomatis*. Alih-alih menggali pipa tanah secara manual dengan cangkul (ClickOps), Anda memasukkan file cetak biru ke sistem robotik yang secara presisi membangun instalasi pipa air, pompa, dan katup persis sesuai instruksi matematika yang tidak pernah meleset.
- **GitOps (ArgoCD)** adalah *inspektur kualitas permanen di lokasi reservoir*. Sang inspektur membawa buku cetak biru master (Git). Setiap menit, ia membandingkan posisi setiap katup di lapangan dengan catatan cetak biru. Jika ada orang yang iseng memutar katup tanpa izin (drift), inspektur langsung memutarnya kembali ke posisi semula (reconciliation & self-healing).
- **Canary Deployment** adalah *proses pengujian air pada satu blok pemukiman kecil*. Daripada langsung membuka keran utama ke 100% warga kota (yang jika terkontaminasi akan meracuni semua orang sekaligus), pasokan air baru dialirkan ke 5% rumah tangga terlebih dahulu. Sensor air (CloudWatch/Prometheus) memantau kemurniannya secara intensif. Jika ditemukan zat berbahaya, katup otomatis ditutup dalam hitungan detik. Warga kota lainnya tetap aman menggunakan pasokan lama.
- **Disaster Recovery Multi-Region** adalah *sistem interkoneksi reservoir cadangan antar kota*. Jika reservoir Kota A mengalami gempa bumi total, operator sistem transmisi regional (Route 53 ARC) segera memutar katup pipa transmisi utama untuk mengalirkan air dari reservoir Kota B yang sudah berada dalam kondisi siaga, mencegah krisis pasokan air total.

## 8. Diagram (ASCII)

```text
+-------------------+      +--------------------+      +---------------------------------+
|   Developer Git   | ---> |  AWS CodePipeline  | ---> |          AWS CodeBuild          |
|  (App & IaC Repo) |      |   (Event-Driven)   |      | (Test, Build Image, Scan Trivy) |
+-------------------+      +--------------------+      +---------------------------------+
                                                                        |
                                                         Push Image     | Push Tag Commit
                                                         & Manifest     v
                                                    +-------------------------------+
                                                    |  Amazon ECR / GitOps Config   |
                                                    +-------------------------------+
                                                                    |
                                                                    v
+======================================= AWS REGION 1 (PRIMARY) =======================================+
|                                                                                                      |
|  +------------------------------------------------------------------------------------------------+  |
|  | Amazon EKS Cluster                                                                             |  |
|  |                                                                                                |  |
|  |  +------------------------+        Reconciliation Loop        +-----------------------------+  |  |
|  |  | ArgoCD Operator        | ================================> | Argo Rollouts Controller    |  |  |
|  |  | (GitOps Pull Engine)   |                                   | (Canary Analysis Strategy)  |  |  |
|  |  +------------------------+                                   +-----------------------------+  |  |
|  |                                                                             |                  |  |
|  |                                                        Split Traffic        v                  |  |
|  |                                                    +----------------------------------+        |  |
|  |                                                    | Application Load Balancer (ALB)  |        |  |
|  |                                                    +----------------------------------+        |  |
|  |                                                              /              \                  |  |
|  |                                                90% Traffic  /                \ 10% Traffic     |  |
|  |                                                            v                  v                |  |
|  |                                                   +-------------+     +-------------+          |  |
|  |                                                   | Stable Pods |     | Canary Pods |          |  |
|  |                                                   +-------------+     +-------------+          |  |
|  +------------------------------------------------------------------------------------------------+  |
|                                                               | Data Replicaton                      |
|                                                               v                                      |
|                                                    +--------------------+                            |
|                                                    | DynamoDB Global /  |                            |
|                                                    | Aurora Global DB   |                            |
+====================================================+====================+============================+
                                                                |
                                                                | Asynchronous Data Stream
                                                                v
+====================================== AWS REGION 2 (SECONDARY) =====================================+
|                                                    +--------------------+                            |
|                                                    | Secondary Replica  |                            |
|                                                    | (Warm Standby)     |                            |
|                                                    +--------------------+                            |
|                                                               ^                                      |
|  +------------------------------------------------------------|-----------------------------------+  |
|  | Amazon EKS Cluster (Secondary Standby)                     |                                   |  |
|  |                                                            |                                   |  |
|  |  +--------------------+        Reconciliation Loop        +--------------------------------+   |  |
|  |  | ArgoCD Operator    | ================================> | ALB Ingress & Standby Workload |   |  |
|  |  +--------------------+                                   +--------------------------------+   |  |
|  +------------------------------------------------------------------------------------------------+  |
+======================================================================================================+
                                                                ^
                                                                | Multi-Region Failover
                                                    +------------------------+
                                                    |  Route 53 ARC Routing  |
                                                    |  Control Plane         |
                                                    +------------------------+
                                                                ^
                                                                | DNS Ingress
                                                            [ Clients ]
```

## 9. Simple Example
Contoh template AWS CloudFormation minimal (`s3_bucket_declared.yaml`) yang mendefinisikan sebuah S3 Bucket dengan enkripsi AWS-KMS yang dikelola secara deklaratif beserta output ARN-nya:

```yaml
AWSTemplateFormatVersion: '2010-09-09'
Description: 'CloudFormation Stack Sederhana untuk S3 Bucket Terenkripsi'

Parameters:
  EnvironmentName:
    Type: String
    Default: dev
    AllowedValues:
      - dev
      - staging
      - prod
    Description: 'Nama environment target deployment.'

Resources:
  EncryptedApplicationBucket:
    Type: AWS::S3::Bucket
    DeletionPolicy: Retain
    UpdateReplacePolicy: Retain
    Properties:
      BucketName: !Sub 'enterprise-audit-logs-${EnvironmentName}-${AWS::AccountId}'
      BucketEncryption:
        ServerSideEncryptionConfiguration:
          - ServerSideEncryptionByDefault:
              SSEAlgorithm: AES256
      PublicAccessBlockConfiguration:
        BlockPublicAcls: true
        BlockPublicPolicy: true
        IgnorePublicAcls: true
        RestrictPublicBuckets: true
      VersioningConfiguration:
        Status: Enabled

Outputs:
  BucketArn:
    Description: 'ARN dari S3 Bucket yang berhasil diprovisioning'
    Value: !GetAtt EncryptedApplicationBucket.Arn
    Export:
      Name: !Sub '${EnvironmentName}-ApplicationBucketArn'
```

Instruksi validasi dan eksekusi menggunakan AWS CLI:
```bash
# Validasi sintaks template
aws cloudformation validate-template --template-body file://s3_bucket_declared.yaml

# Eksekusi deployment stack
aws cloudformation deploy \
  --template-file s3_bucket_declared.yaml \
  --stack-name CoreAuditBucket-Dev \
  --parameter-overrides EnvironmentName=dev \
  --no-fail-on-empty-changeset
```

## 10. Practical Example (AWS CDK v2 TypeScript)
Berikut adalah implementasi nyata AWS CDK v2 menggunakan TypeScript yang mendefinisikan pipeline CI/CD lengkap: AWS CodePipeline terhubung dengan CodeBuild, ECR repository, dan mekanisme deployment canary dengan CodeDeploy pada ECS Fargate:

```typescript
import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as ecr from 'aws-cdk-lib/aws-ecr';
import * as codepipeline from 'aws-cdk-lib/aws-codepipeline';
import * as codepipeline_actions from 'aws-cdk-lib/aws-codepipeline-actions';
import * as codebuild from 'aws-cdk-lib/aws-codebuild';
import * as ecs from 'aws-cdk-lib/aws-ecs';
import * as codedeploy from 'aws-cdk-lib/aws-codedeploy';
import * as cloudwatch from 'aws-cdk-lib/aws-cloudwatch';
import * as iam from 'aws-cdk-lib/aws-iam';

export class EnterpriseContinuousDeliveryStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // 1. Storage Artefak Pipeline terenkripsi
    const artifactBucket = new s3.Bucket(this, 'PipelineArtifactBucket', {
      encryption: s3.BucketEncryption.S3_MANAGED,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      enforceSSL: true,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
    });

    // 2. Registri Kontainer (ECR)
    const appRepository = new ecr.Repository(this, 'ApplicationRepository', {
      repositoryName: 'enterprise-microservice',
      imageScanOnPush: true,
      imageTagMutability: ecr.TagMutability.IMMUTABLE,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    });

    // 3. Project AWS CodeBuild
    const buildProject = new codebuild.PipelineProject(this, 'MicroserviceBuildProject', {
      projectName: 'Microservice-Build-And-Scan',
      environment: {
        buildImage: codebuild.LinuxBuildImage.AMAZON_LINUX_2_ARM_3,
        privileged: true, // Dibutuhkan untuk membangun Docker daemon
        computeType: codebuild.ComputeType.MEDIUM,
      },
      environmentVariables: {
        REPOSITORY_URI: { value: appRepository.repositoryUri },
      },
      buildSpec: codebuild.BuildSpec.fromObject({
        version: '0.2',
        phases: {
          pre_build: {
            commands: [
              'echo Masuk ke Amazon ECR...',
              'aws ecr get-login-password --region $AWS_DEFAULT_REGION | docker login --username AWS --password-stdin $REPOSITORY_URI',
              'COMMIT_HASH=$(echo $CODEBUILD_RESOLVED_SOURCE_VERSION | cut -c 1-7)',
              'IMAGE_TAG=${COMMIT_HASH:=latest}',
            ],
          },
          build: {
            commands: [
              'echo Membangun Docker Image...',
              'docker build -t $REPOSITORY_URI:latest .',
              'docker tag $REPOSITORY_URI:latest $REPOSITORY_URI:$IMAGE_TAG',
            ],
          },
          post_build: {
            commands: [
              'echo Melakukan push image ke ECR...',
              'docker push $REPOSITORY_URI:latest',
              'docker push $REPOSITORY_URI:$IMAGE_TAG',
              'echo Menghasilkan artefak deployment...',
              'printf \'[{"name":"web","imageUri":"%s"}]\' $REPOSITORY_URI:$IMAGE_TAG > imagedefinitions.json',
            ],
          },
        },
        artifacts: {
          files: ['imagedefinitions.json', 'appspec.yaml'],
        },
      }),
    });

    appRepository.grantPullPush(buildProject.grantPrincipal);

    // 4. Artefak Pipeline
    const sourceOutput = new codepipeline.Artifact('SourceArtifact');
    const buildOutput = new codepipeline.Artifact('BuildArtifact');

    // 5. CloudWatch Alarm untuk Canary Rollback
    const http5xxAlarm = new cloudwatch.Alarm(this, 'CanaryHighHttp5xxAlarm', {
      metric: new cloudwatch.Metric({
        namespace: 'AWS/ApplicationELB',
        metricName: 'HTTPCode_Target_5XX_Count',
        statistic: 'Sum',
        period: cdk.Duration.minutes(1),
      }),
      threshold: 5,
      evaluationPeriods: 2,
      comparisonOperator: cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
    });

    // 6. Definisi Orchestration AWS CodePipeline
    const pipeline = new codepipeline.Pipeline(this, 'DeliveryPipeline', {
      pipelineName: 'Enterprise-Microservice-CD',
      artifactBucket: artifactBucket,
      restartExecutionOnUpdate: true,
      stages: [
        {
          stageName: 'Source',
          actions: [
            // Contoh menggunakan koneksi CodeStar Source (misal GitHub/BitBucket)
            new codepipeline_actions.CodeStarConnectionsSourceAction({
              actionName: 'SourceCodeCheckout',
              owner: 'enterprise-org',
              repo: 'microservice-core',
              branch: 'main',
              connectionArn: 'arn:aws:codeconnections:ap-southeast-1:112233445566:connection/demo-uuid',
              output: sourceOutput,
            }),
          ],
        },
        {
          stageName: 'Build-and-Test',
          actions: [
            new codepipeline_actions.CodeBuildAction({
              actionName: 'ExecuteContainerBuild',
              project: buildProject,
              input: sourceOutput,
              outputs: [buildOutput],
            }),
          ],
        },
      ],
    });
  }
}
```

## 11. Real World Example
Kasus nyata pada institusi FinTech perbankan digital skala regional:

**Konteks Masalah:**
Aplikasi transaksi inti perbankan (*Core Payment Engine*) mengalami downtime selama 42 menit saat rilis versi `v2.4.0` karena kesalahan sintaks pada skrip migrasi database dan perubahan variabel environment yang tidak terdeteksi di staging. Rilis manual via ClickOps menyebabkan kegagalan rollback yang berujung pada pelanggaran SLA finansial, ancaman denda regulator, dan kerugian finansial senilai ratusan juta rupiah.

**Solusi Terimplementasi:**
1. **Standarisasi IaC Penuh:** Seluruh topologi VPC, AWS EKS, Aurora MySQL, dan ElastiCache dimigrasikan ke AWS CDK v2 TypeScript dengan strict unit testing menggunakan `@aws-cdk/assertions`. Tidak ada resource yang dapat dimodifikasi di console AWS (Console read-only enforcement via SCP AWS Organizations).
2. **GitOps Workflow dengan ArgoCD:** Transisi ke repositori GitOps terpisah (`payment-engine-gitops-manifests`). Setiap promosi staging ke production dilakukan melalui Pull Request (PR) yang ditinjau oleh dua Principal SRE.
3. **Automated Canary Deployment dengan Argo Rollouts:**
   - Strategi Canary: Langkah 1 = 5% trafik selama 10 menit. Langkah 2 = 20% trafik selama 15 menit. Langkah 3 = 50% selama 15 menit. Langkah 4 = 100%.
   - Analisis Metrik: Menggunakan metrik Prometheus internal via query PromQL:
     `sum(rate(http_requests_total{status=~"5.*",app="payment"}[2m])) / sum(rate(http_requests_total{app="payment"}[2m])) * 100`.
   - Threshold batas: Jika HTTP Error Rate >= 0.5% atau Latensi p99 >= 250ms selama fase canary, Argo Rollouts langsung membatalkan deployment (*abort*) dalam tempo kurang dari 5 detik, mengembalikan rute trafik sepenuhnya ke Pods versi stabil.
4. **Disaster Recovery Multi-Region:**
   - Active-Passive (Warm Standby) antara `ap-southeast-1` (Singapura) dan `ap-southeast-3` (Jakarta).
   - Replikasi database real-time dengan Aurora Global Database (latensi replikasi sub-detik).
   - Kontrol failover diatur oleh Route 53 ARC Routing Control via script automated health evaluation. RTO turun dari 4 jam menjadi 3 menit 20 detik, dan RPO berkurang dari 1 jam menjadi di bawah 1 detik.

## 12. Trade-offs

| Dimensi Arsitektur | Opsi A | Opsi B | Trade-off Analisis |
| :--- | :--- | :--- | :--- |
| **IaC Engine** | **AWS CloudFormation (YAML/JSON)** | **AWS CDK (TypeScript/Python)** | CloudFormation memiliki kurva pembelajaran rendah dan status engine bawaan AWS murni tanpa abstraksi tambahan. Namun, CDK menyediakan modularitas, penanganan string dinamis, logic looping kompleks, penulisan unit test infrastruktur, dan pengurangan ribuan baris boilerplate YAML dengan L2/L3 constructs. |
| **Delivery Model** | **Push-Based CD (CodePipeline / GitHub Actions)** | **Pull-Based GitOps (ArgoCD di EKS)** | Push-based mudah diintegrasikan dari CI dan tidak memerlukan agent di dalam cluster, namun membutuhkan kredensial IAM dengan privilege tinggi yang diekspos ke runner CI. GitOps pull-based membatasi akses kredensial hanya di dalam VPC cluster, mencegah configuration drift otomatis, namun membebankan overhead komputasi dan manajemen siklus hidup controller di Kubernetes. |
| **Release Strategy** | **Blue-Green Deployment** | **Canary Deployment** | Blue-Green menggandakan kebutuhan kapasitas resource secara simultan (biaya komputasi meningkat 2x lipat saat proses rilis), tetapi proses rollback instan (hanya switch listener target group). Canary jauh lebih hemat kapasitas komputasi dan memitigasi blast radius secara bertahap, namun membutuhkan perancangan arsitektur routing dan metriks analisis yang jauh lebih kompleks. |
| **Disaster Recovery** | **Active-Passive (Warm Standby)** | **Active-Active (Multi-Region)** | Warm Standby jauh lebih murah biaya operasionalnya (hanya membayar minimal compute di region pasif) dengan kompleksitas data consistency rendah. Active-Active memberikan RTO zero, namun membutuhkan arsitektur sinkronisasi data dua arah multi-master yang sangat rumit, potensi *data write-conflict*, dan biaya infrastruktur AWS berganda secara konstan. |

## 13. When To Use
- Gunakan **AWS CloudFormation** jika organisasi mewajibkan standardisasi template statis tanpa dependency runtime bahasa pemrograman pihak ketiga, atau untuk deployment solusi Service Catalog.
- Gunakan **AWS CDK** jika infrastruktur Anda kompleks, membutuhkan abstractions L3 enterprise yang dapat dibagikan antar divisi (construct library internal), atau membutuhkan validasi unit testing (`jest`/`pytest`) sebelum proses sintesis template.
- Gunakan **ArgoCD (GitOps)** jika beban kerja Anda dominan berjalan di Amazon EKS dan tim engineering membutuhkan kontrol rekonsiliasi state cluster secara otomatis tanpa membagikan kubeconfig/IAM admin role ke sistem CI eksternal.
- Gunakan **Canary Deployment** untuk aplikasi transaksi misi-kritis (misal checkout e-commerce, payment gateway, streaming media) di mana kegagalan fungsional sekecil apa pun berdampak fatal terhadap metrik finansial bisnis.
- Gunakan **Multi-Region DR (Route 53 ARC)** jika kepatuhan regulasi mewajibkan business continuity ketika terjadi catastrophic outage pada satu region AWS utuh.

## 14. When NOT To Use
- Jangan gunakan **AWS CDK** jika tim operasional Anda tidak memiliki kapabilitas pemrograman perangkat lunak modern (software engineering literacy). Menggunakan CDK tanpa pemahaman siklus hidup package management (npm/pip) justru akan menimbulkan komplikasi dependency drift.
- Jangan gunakan **GitOps dengan ArgoCD** untuk mengelola resource infrastruktur AWS non-Kubernetes tingkat rendah (seperti VPC, Direct Connect, IAM) kecuali menggunakan operator orkestrasi khusus seperti AWS Controllers for Kubernetes (ACK) atau Crossplane yang sudah sangat matang di organisasi Anda.
- Jangan gunakan **Canary Deployment** jika aplikasi Anda memiliki dependensi skema database relasional yang mengalami *breaking change* yang tidak backward-compatible (non-additive changes). Versi aplikasi lama dan versi canary harus selalu dapat membaca skema database yang sama secara bersamaan.
- Jangan gunakan **Active-Active Multi-Region** untuk sistem beban kerja yang membutuhkan jaminan konkurensi data strictly-acidic dengan frekuensi update ekstrem dan sensitif terhadap *distributed cross-region locking*, karena latensi transmisi cahaya antar-region (speed of light latency limit) akan menghancurkan throughput transaksi.

## 15. Common Mistakes
1. **Hardcoding Secret Credentials di dalam Template IaC:** Menuliskan password database, private keys, atau API token secara plaintext pada deklarasi CloudFormation/CDK.  
   *Solusi:* Gunakan AWS Secrets Manager atau AWS Systems Manager Parameter Store dengan dynamic references (`resolve:secretsmanager:...`).
2. **Circular Dependencies pada CloudFormation Stacks:** Mengaitkan output Stack A sebagai parameter Stack B, sementara Stack B mengembalikan nilai output yang dibutuhkan Stack A. Hal ini mengunci stack dalam status `CREATE_FAILED` permanen.  
   *Solusi:* Dekomposisi arsitektur, pisahkan layer fondasi jaringan, data, dan layer komputasi ke dalam hirarki berarah linear tanpa siklus.
3. **Database Schema Breaking Migration pada Canary Rollout:** Mengubah kolom database secara destruktif (misal rename/drop column) bersamaan dengan deployment aplikasi canary. Pods lama langsung crash karena kolom hilang.  
   *Solusi:* Gunakan pola *Expand and Contract (Parallel Run)*. Tahap 1: Tambahkan kolom baru (expand). Tahap 2: Rilis aplikasi canary yang menulis ke kedua kolom atau kolom baru. Tahap 3: Hapus kolom lama setelah 100% traffic stabil dan versi lama pensiun (contract).
4. **Mengabaikan Health Check Target Group ALB pada Pipeline:** Menyetel threshold canary tanpa mengevaluasi konfigurasi unhealthiness probe. Akibatnya, CodeDeploy menganggap traffic deployment sukses padahal pod/kontainer baru terus-menerus mengalami restart loop (`CrashLoopBackOff`).
5. **GitOps Configuration Drift via kubectl edit manual:** SRE melakukan patching darurat langsung di EKS cluster via `kubectl edit`. Ketika ArgoCD melakukan rekonsiliasi periodik, perubahan manual tersebut di-overwrite secara otomatis dan membingungkan operator.  
   *Solusi:* Lakukan modifikasi hanya melalui Git commit atau gunakan flag `ignoreDifferences` secara selektif jika mutlak diperlukan.

## 16. Best Practices
1. **Immutability of Application Artifacts:** Jangan pernah mem-push container image dengan tag mutable seperti `:latest` ke production. Gunakan tag berbasis immutable Git SHA (`:a1b2c3d`) untuk menjamin auditabilitas dan reprodusibilitas.
2. **Prinsip Least Privilege pada Pipeline Roles:** Buat IAM Execution Role terpisah untuk AWS CodeBuild, CodePipeline, dan ArgoCD IRSA. Batasi scope CloudFormation service role hanya untuk mengelola resource yang relevan dengan aplikasi target.
3. **Automate Pre-Commit dan Static Security Analysis:** Integrasikan `cfn-nag`, `cdk-nag`, `checkov`, atau `trivy` di dalam pipeline CI untuk mencegat pelanggaran compliance (misal S3 bucket tanpa enkripsi, security group port 22 terbuka) sebelum kode masuk ke tahap provisioning.
4. **Desain Database Toleran Canary:** Terapkan database migrations yang selalu *backward-compatible* minimal 1 versi ke belakang.
5. **Automated Rollback Triggers Berbasis SLO/SLI:** Pasang CloudWatch Alarms atau Prometheus Rules yang memantau metrik Service Level Indicators (SLI) riil: tingkat error 5xx, latensi P99, dan saturation metrics saat deployment berlangsung.

## 17. Troubleshooting

| Gejala Masalah | Kemungkinan Akar Masalah | Langkah Investigasi & Mitigasi |
| :--- | :--- | :--- |
| CloudFormation Stack terkunci dalam status `UPDATE_ROLLBACK_FAILED`. | Sebuah resource eksternal menghalangi rollback (misalnya S3 Bucket tidak kosong saat CloudFormation mencoba menghapusnya). | 1. Buka tab Events pada CloudFormation Console.<br>2. Identifikasi Logical Resource ID yang gagal.<br>3. Gunakan AWS CLI: `aws cloudformation continue-update-rollback --stack-name <NAME> --resources-to-skip <RESOURCE_ID>`.<br>4. Perbaiki resource manual tersebut lalu sesuaikan IaC template. |
| ArgoCD menampilkan status `SharedResourceWarning` atau stuck di `OutOfSync`. | Ada dua `Application` berbeda yang mengklaim ownership atas Kubernetes resource (Kind, Name, Namespace) yang identik. | 1. Periksa manifest kedua repo GitOps.<br>2. Cari deklarasi resource duplikat via `argocd app get <NAME>`.<br>3. Pindahkan resource ke salah satu application owner atau gunakan Kustomize namespace prefixing. |
| Canary CodeDeploy langsung memicu automated rollback pada tahap 10%. | CloudWatch Alarm yang dikonfigurasi terpicu, atau Lifecycle Hook Lambda script (`BeforeAllowTraffic`) me-return status `Failed`. | 1. Buka CodeDeploy Deployment History, klik `Lifecycle Event Hooks`.<br>2. Periksa CloudWatch Logs untuk Lambda validation function.<br>3. Periksa Target Group Health metrics pada ALB untuk melihat apakah Pods canary crash atau gagal pass `/healthz` probe. |
| Argo Rollouts Canary terhenti (*stuck*) dan tidak menaikkan weight trafik. | Prometheus/Metric Analysis server tidak dapat dijangkau oleh controller, atau format query PromQL salah sintaks. | 1. Jalankan `kubectl describe analysisrun <RUN_NAME> -n <NAMESPACE>`.<br>2. Analisis output pada bagian `Status.Message`.<br>3. Pastikan network policy EKS mengizinkan egress dari Rollouts controller ke Prometheus endpoint. |

## 18. Exercise
Selesaikan instruksi berikut:
1. Buat sebuah template AWS CloudFormation (`network-base.yaml`) yang memprovisikan sebuah VPC dengan 2 Public Subnet, 2 Private Subnet, Internet Gateway, dan 1 NAT Gateway di Availability Zone pertama.
2. Buat script AWS CDK v2 TypeScript yang mengonsumsi output VPC di atas (menggunakan `Vpc.fromLookup`), kemudian memprovisikan Amazon ECR Repository dengan lifecycle rule: maksimal menyimpan 10 images terakhir.
3. Jalankan sintesis CDK (`cdk synth`) dan simpan template CloudFormation yang dihasilkan ke file `cdk-generated-ecr.yaml`.
4. Lakukan validasi static security check pada file hasil sintesis menggunakan tool open-source `checkov` atau `cfn-nag`. Perbaiki semua peringatan berlevel *HIGH* atau *CRITICAL*.

## 19. Challenge
Rancang arsitektur Continuous Delivery bertaraf enterprise untuk platform perbankan multi-region yang memenuhi spesifikasi berikut:
- **Zero-Downtime Releases:** Gunakan strategi Argo Rollouts Canary pada dua cluster EKS (Primary: `ap-southeast-1`, Secondary: `ap-southeast-3`).
- **Telemetry Verification:** Canary harus otomatis menganalisis metrik CloudWatch/Prometheus setiap 60 detik selama 5 fase persentase trafik (5%, 15%, 30%, 60%, 100%).
- **Multi-Region Automated Failover:** Buat arsitektur Route 53 Application Recovery Controller (ARC) yang membaca sinyal synthetic canary health probe. Jika region primary mengalami kegagalan (error rate > 5% selama 3 menit berurutan), routing control harus secara deterministik mengalihkan 100% trafik publik ke region secondary.
- **Tuliskan desain arsitektur teknis lengkap beserta blok kode manifest Kubernetes (Argo Rollout spec), CloudWatch Alarm, dan skrip automation controller-nya.**

## 20. Summary
Continuous Delivery dan Infrastructure as Code bukan sekadar pilihan tooling, melainkan kapabilitas rekayasa fundamental untuk menjaga stabilitas dan kecepatan inovasi pada AWS Cloud. Melalui CloudFormation dan CDK v2, tim engineer dapat memprogram infrastruktur dengan prinsip modularitas, pengujian otomatis, dan idempotensi. 

Penggabungan AWS CodePipeline/CodeBuild dengan model GitOps terdistribusi berbasis ArgoCD pada Amazon EKS menjembatani pemisahan antara CI (pembangunan artefak aplikasi immutable) dan CD (rekonsiliasi state cluster dan progressive delivery). 

Dengan melengkapi sistem menggunakan strategi Canary Deployment yang dikendalikan oleh analisis metrik otomatis dan failover multi-region via Route 53 ARC, organisasi mencapai resiliensi operasional tinggi—menjaga blast radius insiden serendah mungkin sekaligus menjamin kontinuitas bisnis saat terjadi bencana regional.

---