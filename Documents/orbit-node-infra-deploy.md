

# ORBIT — Infrastructure Implementation & Design Plan

## 0) What this document is

This document explains how we will build, secure, and run the AWS environment for the ORBIT platform. It translates the high-level architecture into practical implementation steps, focusing on **how** the infrastructure operates, **why** specific design choices were made, and **how** it is managed day-to-day.

This plan reflects a mature, "bank-grade" infrastructure baseline deployed entirely via Infrastructure as Code (CloudFormation).

## 1) Goals

We will deliver an AWS environment where:

* **Zero-Trust Security is Built-In:** All compute resources reside in strictly private subnets with no direct internet exposure.
* **Separation of Concerns:** Compute is segmented across three distinct servers (Core App, Core DB, and Node) to mirror real-world banking infrastructure and prevent resource contention.
* **Cost Control is Automated:** Infrastructure runs on a schedule (e.g., IST 9 AM - 9 PM) using automated tagging, while persistent data survives Start/Stop cycles.
* **Access is Seamless but Secure:** The team and sponsors can access services securely via AWS Systems Manager (SSM) or a dedicated VPN, eliminating IP whitelisting headaches.
* **High Availability Ready:** The network foundation supports Multi-AZ deployments out of the box.

---

## 2) Key Decisions We Are Using (and Why)

### 2.1 Private Compute Only (Zero Trust)

* **Decision:** We are deploying all EC2 instances into private subnets (`PrivateAppSubnet0`).
* **Why:** To simulate a secure banking environment, servers cannot have public IPs. All outbound internet traffic routes safely through NAT Gateways, and inbound access is strictly controlled.

### 2.2 Three-Server Architecture

* **Decision:** We are consolidating the platform into three specific `t3.xlarge` Ubuntu servers:
1. **Core App Server:** Hosts ORBIT.Core UI and API Docker containers.
2. **Core DB Server:** Dedicated entirely to the Neo4j Knowledge Graph.
3. **Node Server:** A combined host for ORBIT.Node (Agent/MCP), Wazuh, Presidio, and the Node-local Neo4j instance.


* **Why:** This enforces the architectural rule separating "App" from "DB" at the platform level, while optimizing compute costs compared to running four or more disjointed servers.

### 2.3 Access Method: SSM & Internal Routing

* **Decision:** Default access is via **AWS SSM Session Manager**, backed by strict Security Groups allowing traffic only from an `AllowedInternalCidr` (like a Client VPN or Bastion host).
* **Why:** SSM acts as a secure remote console without needing open SSH ports on the internet. It guarantees auditable, VPN-like access from anywhere via the AWS Console or CLI.

### 2.4 Automated Cost Control (FinOps)

* **Decision:** All instances are tagged with `Schedule: OfficeHours`.
* **Why:** An EventBridge/Lambda automation will use this tag to shut down the DEV environment outside of working hours, drastically reducing EC2 costs while 200GB gp3 EBS volumes ensure data safety.

---

## 3) Architecture (What Will Exist in AWS)

### 3.1 AWS Building Blocks

* **Multi-AZ VPC:** A customized virtual network (`10.20.0.0/16` default) spanning 2 or 3 Availability Zones.
* **Public Subnets & NAT Gateways:** Used strictly for routing private server traffic out to the internet for updates/downloads.
* **Private Subnets:** Where the actual ORBIT servers sit safely hidden from the internet.
* **S3 Gateway Endpoint:** Keeps AWS S3 traffic (like Docker pulls or backups) within the internal AWS network, reducing NAT Gateway data processing costs.
* **IAM Instance Profiles:** Gives EC2 instances permission to be managed securely without access keys.

### 3.2 Minimum Baseline Specs

* **Core App Server:** `t3.xlarge` (4 vCPU, 16 GB RAM), 200 GB gp3 EBS Volume.
* **Core DB Server:** `t3.xlarge` (4 vCPU, 16 GB RAM), 200 GB gp3 EBS Volume.
* **Node Server:** `t3.xlarge` (4 vCPU, 16 GB RAM), 200 GB gp3 EBS Volume.

> *Note: All sizes are parameterized in the CloudFormation template, allowing instant scaling up/down without redesigning the stack.*

### 3.3 Service Communication & Ports

Security Groups enforce least-privilege access. Traffic is restricted internally:

| Source | Destination | Purpose | Network Rule / Port |
| --- | --- | --- | --- |
| Sponsor / Team (VPN/SSM) | Core App & Node | View UI / APIs | `TCP 443` (Nginx/HTTPS) |
| Sponsor / Team (VPN/SSM) | Core DB & Node | View Neo4j Graph | `TCP 7473` (Neo4j HTTPs) |
| System Admin | All Servers | Secure Shell | `TCP 22` (SSH via Internal IP) |
| ORBIT.Core | Node Server | MCP Communication | `TCP 7000` (MCP Protocol) |
| Application Layer | Core DB | Neo4j Bolt Data queries | `TCP 7687` (Bolt Protocol) |

---

## 4) Implementation Approach

We are utilizing a **consolidated Infrastructure as Code (IaC) approach** via a single CloudFormation template (`orbit_infrastructure_stack.yml`).

**Why a consolidated template?** Because this architecture enforces strict dependencies (e.g., EC2 instances cannot be created until the NAT Gateways and Private Route tables are active). The template manages these dependencies natively, ensuring a robust, one-click deployment that can be identically replicated across DEV, QA, and PROD.

---

## 5) Step-by-Step Build Plan

### Step 1 — Network Foundation Deployment

* **Action:** Deploy the VPC, IGW, Public Subnets, Private Subnets, and S3 Endpoints.
* **Validation:** Verify Route Tables are correctly associating NAT Gateways to Private Subnets.

### Step 2 — IAM & Security Initialization

* **Action:** Deploy the `OrbitInstanceRole` and least-privilege Security Groups.
* **Validation:** Confirm Security Groups are locked to the `AllowedInternalCidr` and no `0.0.0.0/0` (public internet) rules exist for inbound traffic.

### Step 3 — Compute & Storage Provisioning

* **Action:** Launch the 3 EC2 instances into `PrivateAppSubnet0` with attached 200GB gp3 block devices.
* **Validation:** Verify EC2 instances report running, and `MapPublicIpOnLaunch` successfully prevented public IPs from being assigned.

### Step 4 — Access Verification (The Golden Path)

* **Action:** Connect to the private instances.
* **Validation:** Navigate to AWS Systems Manager (SSM) -> Fleet Manager and successfully open a terminal session into the Core App, Core DB, and Node instances without requiring SSH keys.

### Step 5 — Baseline Platform Bootstrapping (Ansible)

* **Action:** OS hardening, Docker/Compose installation, and directory structure setup.
* **Validation:** Servers are ready for component owners to drop their Docker Compose files and launch the services.

---

## 6) Security Baseline

Even in the DEV environment, we enforce a strict security posture mapping to real-world banking compliance:

* **No Public IPs:** Compute is isolated.
* **No Hardcoded Credentials:** IAM Roles and Instance Profiles are used exclusively.
* **Immutable Infrastructure:** Changes are made via CloudFormation updates, preventing configuration drift.
* **Encrypted Storage:** High-performance `gp3` volumes are utilized, supporting AWS EBS encryption by default.

---

## 7) Operations Plan

### 7.1 Start/Stop Routine (Cost Saving)

* Instances are tagged with `Schedule: OfficeHours` and `Environment: DEV`.
* An AWS EventBridge cron rule triggers a Lambda function at 09:00 IST to start instances and 21:00 IST to stop them.
* **Impact:** Reduces compute costs by up to 50% without losing configuration or database state.

### 7.2 Backup & Recovery

* Persistent data lives on 200GB EBS volumes.
* If an EC2 instance is terminated or fails, the EBS volume can be remounted to a new instance, or restored via AWS EBS Snapshots.

### 7.3 Troubleshooting Approach

* **Cannot connect via SSM?** Check if the NAT Gateway is active (SSM agent needs outbound internet to register with AWS).
* **Services cannot talk to each other?** Validate the `AllowedInternalCidr` parameter matches the VPC/VPN CIDR, and that Security Group ports (7000, 7473, etc.) are open between the specific subnets.

---

