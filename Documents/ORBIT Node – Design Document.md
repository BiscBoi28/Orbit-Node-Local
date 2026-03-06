**1\) System Design Overview (Components \+ Interfaces \+ Dataflow)**

### **Wazuh (Security telemetry \+ UI)**

* **Input:** Telemetry from **Wazuh agents on Assets**  
* **Produces:** Alerts, vulnerability findings, asset/host metadata  
* **Sends to ORC:** `{asset_id, alert/actions taken in HITL, timestamps, severity}`  
* **UI pages we provide/create:**  
  * **HITL page** (shows action cards from ORC, captures approve/reject/status)  
    * HITL also captures Crown Jewel \= Yes/No and Asset Subscription \= Yes/No before ORC forwards to Core  
  * **Graph/Neo4j visualization page** (read-only visualization via Bloom/NeoDash)  
* **Receives from ORC:** Validated & formatted **Action Cards**

—----------------------------------------------------------------------------------------------------------------------------

### **ORC (Orchestrator / Node Agent)**

* **Receives from Wazuh:** Alerts/vulns \+ asset metadata  
  * **Pending assignment** is handled via **Wazuh workflow**  
* **Requests Presidio scans:** Sends “chunk/targets” on a schedule or event-triggered  
* **Receives from Presidio:** Sensitivity metadata \+ scores  
* **Writes Neo4j (single writer):**  
  * Asset nodes  
  * Vulnerability/alert nodes (from Wazuh)  
  * Sensitivity score/data nodes (from Presidio)  
  * Relationships between them  
* **Core interaction:**  
  * **Sends to Core:** consolidated updates `{asset_id, sensitivity summary, metadata/evidence refs} (can include action summary)`  
  * **Receives from Core:** raw **Action Cards**  
  * **Validates/enriches Action Cards using Neo4j**, formats for HITL/Wazuh UI  
  * **Sends to Wazuh UI:** Action Cards  
  * **Sends back to Core:** HITL decisions \+ execution/status updates

—----------------------------------------------------------------------------------------------------------------------------

### **Presidio (Sensitivity engine)**

* **Receives from ORC:** scan requests / chunks (files, sample payloads, dataset pointers)  
* **Returns to ORC:** detected entity types \+ confidence \+ sensitivity score (+ crown-jewel indicator if defined)  
* *(One instance per node in prototype)*

—----------------------------------------------------------------------------------------------------------------------------

### **Neo4j (Graph store)**

* **Receives updates only from ORC**  
* Stores:  
  * Assets  
  * Vulnerabilities/alerts (these vulnerabilities are not sent to the core)  
  * Sensitivity scores / data assets  
  * Links: `Asset → HAS_VULN`, `Asset → GENERATED_ALERT`, `Asset → STORES_SENSITIVE_DATA`  
* **Visualization:** Bloom/NeoDash reads Neo4j for graphs/dashboards

—----------------------------------------------------------------------------------------------------------------------------

### **Core (Action-card generator)**

* **Receives from ORC:** vulnerability \+ sensitivity \+ metadata/evidence references (periodic \+ event-driven)  
* **Produces:** Action Cards (what to do, why, urgency)  
* **Sends to ORC:** Action Cards  
* **Receives from ORC:** HITL decisions \+ progress/status (so the loop is closed)

—----------------------------------------------------------------------------------------------------------------------------

## **Identity key (prototype decision)**

* **asset\_id \= AWS EC2 instance-id** (best for clean joining)  
* also store hostname \+ private IP as secondary fields

—----------------------------------------------------------------------------------------------------------------------------

## **Dataflow (arrows version)**

* **Assets (Wazuh agent)** → **Wazuh** → **ORC**  
* **ORC** → **Presidio** → **ORC**  
* **ORC** → **Neo4j**  
* **ORC** → **Core** → **ORC**  
* **ORC** → **Wazuh UI (HITL)** → **ORC**  
* **Bloom/NeoDash** → **Neo4j** (read-only)

**2\) Workstream Ownership and Definition of Done**

### **A) Infrastructure / Sandbox (Status: Infrastructure baseline provisioned (AWS resources created) by Vinay)**

**Target:** everyone can build against *real running services* (not mocks).

* Bring up AWS stack (existing 2 EC2s) and ensure access via SSM  
* `wazuh-dev`: Wazuh manager \+ dashboard \+ API reachable  
* `orbit-node`: Docker \+ Neo4j \+ Presidio \+ Juice Shop running  
* Wazuh agent installed on `orbit-node`  
   **Done when:** each service has a health check \+ port-forward instructions \+ creds shared.

---

### **B) Orchestrator (ORC) (Ayush, support: Anushka)**

**Target:** the “bus” that moves metadata between components (no heavy logic initially).  
 **Done when:** one end-to-end loop works with dummy/stub action cards.

---

### **C) Wazuh Integration \+ UI (Sharif and Naveen)**

**Target:** Wazuh is the security signal source \+ the HITL front-end.  
 **Done when:** ORC can pull Wazuh signals and action cards can be displayed/acknowledged.

---

### **D) Presidio Scanning (Anushka, support: Ayush)**

**Target:** consistent sensitivity metadata for assets using safe test data.  
 **Done when:** ORC can call Presidio and reliably get sensitivity output for the Juice Shop host.

---

### **E) Neo4j Schema \+ Queries (Yashav, support: Naveen)**

**Target:** stable graph model \+ reusable Cypher templates.  
 **Done when:** ORC can write without schema changes and NeoDash/Bloom can show meaningful views.

---

### **F) Core Interface (Assumption for this Scope: A dummy system, and triggered manually)**

**Target:** action cards loop works even if Core is incomplete.  
 **Done when:** ORC can send summary and receive action cards deterministically.

---

**Note:** Ownership listed is for the current sprint/prototype phase and may be reassigned during integration

## 

## **3\) Integration Plan and Deployment Approach**

### **Phase 0: Contracts freeze \+ ownership confirmation**

**Everyone**

* Freeze: asset\_id strategy, payload schemas, “chunk” definition, action card fields

* Decide: do we use Wazuh alerts only or alerts \+ vuln feed?  
   **Output:** 1-page contract doc. No one breaks it without group approval.

---

### **Phase 1: Platform bring-up \+ parallel scaffolding**

**Infra owner**

* Services up and reachable (Wazuh / Neo4j / Presidio / Juice Shop)  
   **Others start in parallel (using endpoints)**  
* ORC owner: project skeleton \+ clients (Wazuh, Presidio, Neo4j, Core)  
* Neo4j owner: schema templates \+ sample queries  
* Presidio owner: sample data \+ scoring rules \+ API examples  
* Wazuh owner: API extraction proof \+ UI page skeleton

**Checkpoint 1:** every component has a “hello-world” call against real services.

---

### **Phase 2: First integration loop (no Core dependency yet)**

**Primary integration:**

* Wazuh → ORC → Neo4j  
* ORC → Presidio → ORC → Neo4j

**Parallel work continues:**

* Neo4j: refine schema only if needed (avoid breaking changes)  
* Wazuh UI: build HITL page UI but action cards can be mock data for now  
* Presidio: ensure stable outputs and no raw data leakage

**Checkpoint 2:** Neo4j graph shows at least 1 asset with both:

* a Wazuh signal (alert/vuln)

* a Presidio sensitivity score

---

### **Phase 3: Core action card loop**

* ORC → Core summary export (real Core or stub)  
* Core → ORC action cards  
* ORC → Wazuh HITL page action cards display

**Checkpoint 3:** action card appears in HITL UI sourced from ORC.

---

### **Phase 4: HITL close-loop \+ status updates**

* HITL approval/reject in Wazuh UI  
* ORC updates Neo4j \+ reports status back to Core

**Checkpoint 4:** graph shows action card status transitions (New → Approved/Rejected → Completed).

---

### **Phase 5: Stabilize \+ demo polish**

* event-driven where possible \+ heartbeat/resync fallback  
* dedupe \+ retries \+ failure handling  
* NeoDash/Bloom saved views \+ “top risky assets” dashboard  
* final demo script

**Checkpoint 5:** repeatable sponsor demo.

---

### **Notes on “example bank”**

* Prototype target: **OWASP Juice Shop** as a representative customer-facing app

* Plus small synthetic “bank-like” CSV/log for PAN/account patterns (Presidio-friendly)

---

### **Deployment Approach (Prototype): Docker-first on Ubuntu 22.04 LTS**

**Objective:** Minimize environment setup friction while keeping the design upgrade-friendly and compatible with security agents.

**OS Choice:**  
 All EC2 instances for the prototype will use **Ubuntu 22.04 LTS** to maximize compatibility, especially for installing and operating agents (e.g., Wazuh agent) and avoiding version-support issues.

#### **Containerization Strategy**

We will run the majority of ORBIT prototype services using **Docker containers** to ensure:

* consistent dependencies across machines,  
* fast bring-up and reset,  
* simple upgrades/rollback,  
* clean separation between services.

**Host separation (current 2-EC2 prototype):**

1. **wazuh-dev (EC2)**  
   * Runs the **Wazuh stack** (manager \+ dashboard \+ API) via Docker (or official supported deployment).  
   * Keeps the heaviest monitoring component isolated and stable.  
2. **orbit-node (EC2)**  
   * Runs the remaining services via Docker:  
     * **Neo4j** (graph database)  
     * **Presidio analyzer** (sensitivity engine)  
     * **OWASP Juice Shop** (prototype “example bank-like app”)  
     * **ORC (Orchestrator)** service

**Open Questions**: 

* Are we going to be using actions/alerts generated by wazuh as well? (currently assumed to be true, and sending these alerts to ORC → Core → ORC → wazuh HITL)  
  * Answer:  We limit the alert/actions to the ones generated by the action cards generated by the Core and the corresponding alerts and action status from Wazuh. We do not address the rest of Wazuh alerts, expect existing staff to do the same. Important to mark ORBIT actions cards uniquely in Wazuh dashboard  
* If true, then for prototype, do we use:  
  * (A) Alerts/events only, or  
  * (B) Vulnerability detection too (CVE feed/config)?

