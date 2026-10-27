# Step-by-Step Implementation Plan: Full ZCMC Regional Health Exchange Prototype

## Executive Overview
This implementation plan outlines the construction of the full prototype for the **ZCMC Regional Health Exchange (ZAMBASULTA)** for the Ateneo de Zamboanga University (AdZU) Ideathon. The architecture directly addresses ZCMC's core pain points (delays in care, duplicate diagnostics, inefficient coordination, administrative overhead, and policy blind spots) across three user roles: **Patients**, **Local LGU Clinics**, and **ZCMC Regional Apex**.

---

## Architecture Blueprint & 3-User Flow

```
[Step 1: Patient Encounter]
        │
        ▼
   Patient Intake (Citizen Portal)
   Symptom & Healthcare Needs Evaluation
        │
        ▼
[Step 2: Intelligent Capability-Based Routing Engine]
        │
   Does the local LGU clinic have the required service?
        ├─ Yes ──► Treat & Discharge at Local LGU Clinic
        └─ No  ──► Escalate Referral to ZCMC Regional Apex
                   (With Physician Manual Override Option)
        │
        ▼
[Step 3: Edge Security & Resilient Offline Stash]
        │
   Is internet connectivity available?
        ├─ Yes ──► Instant HL7 FHIR R4 Ingestion
        └─ No  ──► Sealed with Client-Side AES-GCM-256 in Device Vault
                   (Auto-forwards when connectivity is restored)
        │
        ▼
[Step 4: Bi-Directional Medical Data Cross-Matching (ZCMC Apex)]
        │
   • Match Patient via PhilHealth ID / MPI
   • Query ZCMC Historical Database vs Island Clinic Encounter
   • Cross-match prior CT/X-Rays, labs, blood types, and allergies
   • Eliminate repeated diagnostic procedures & save patient costs
        │
        ▼
[Step 5: Maritime Reception & Handoff]
        │
   • Live Sea Corridor Radar (Basilan 18-24 NM, Sulu 80-95 NM, Tawi-Tawi 180-210 NM)
   • Port Pier 1 Slipway emergency ambulance dispatch
   • Direct ZCMC ER Trauma / ICU bed pre-allocation (Zero delay)
```

---

## Implementation Roadmap

### Phase 1: Database & Domain Model Enhancement
**Goal:** Expand the SQLite database (`models.py`) to support facility capability profiles, prior clinical diagnostics (preventing duplicate testing), and the 3 user entities.

- [ ] **Task 1.1: Clinic Service Capabilities Registry**
  - Create table `facility_capabilities` (`facility_name`, `level`, `island_province`, `services_json`, `is_surgical`, `has_icu`, `has_blood_bank`).
  - Pre-seed with ZAMBASULTA facilities:
    - *Mapun Municipal Hospital* (Primary RHU: maternal outpatient, malaria screening; no surgery/ICU).
    - *Luuk District Hospital* (Level 1: basic surgery, primary lab; no ICU/neuro).
    - *Lamitan District Hospital* (Level 1: basic surgery, standard trauma stabilization).
    - *Basilan General Hospital* (Level 2: general surgery, CEmONC, NICU).
    - *Sulu Provincial Hospital* (Level 2: trauma surgery, blood station, emergency suites).
    - *Tawi-Tawi IPHO Bongao* (Level 2: general surgery, satellite hemodialysis).
    - *ZCMC* (Level 3 Apex: full subspecialties, neurosurgery, cath lab, pediatric ICU).
- [ ] **Task 1.2: Diagnostic & Clinical History Repository**
  - Create table `patient_diagnostics` (`id`, `philhealth_id`, `patient_name`, `test_type`, `facility_origin`, `result_summary`, `imaging_url`, `timestamp`, `is_valid`).
  - Stores blood types, known drug allergies, CT/X-Ray summaries, and recent CBC/urinalysis.
- [ ] **Task 1.3: Verification**
  - Run database migration test and ensure backward compatibility with existing referrals.

---

### Phase 2: Intelligent Routing & Capability Engine
**Goal:** Build the backend routing decision boundary that determines whether a patient can be treated at their municipal LGU clinic or must be escalated across maritime corridors to ZCMC.

- [ ] **Task 2.1: Implement `/api/route` Decision Endpoint**
  - Input: `patient_complaint`, `required_service` (e.g., `#PrimaryConsult`, `#EmergencyCesarean`, `#Craniotomy`, `#SevereTrauma`), `patient_location` (island).
  - Logic: Match requested service against local facility capability registry.
  - Output: `recommended_destination` (Local Clinic vs ZCMC), `rationale`, and `estimated_transit_nm`.
- [ ] **Task 2.2: Clinician Override Guard**
  - Allow attending island physicians to override automated routing with custom clinical justification.
- [ ] **Task 2.3: Unit Testing**
  - Add test cases in `test_suite.py` asserting routine cases route to LGU RHUs and critical/surgical cases route to ZCMC.

---

### Phase 3: Bi-Directional Medical Data Cross-Matching Engine
**Goal:** Solve ZCMC's primary pain point of **repeated diagnostic procedures** by cross-matching island referral data with historical records.

- [ ] **Task 3.1: Implement `/api/crossmatch` Reconciliation Endpoint**
  - Input: `philhealth_id` and `patient_name`.
  - Logic:
    1. Query existing historical records in central ZCMC storage.
    2. Query diagnostic history from island origin.
    3. Cross-match prior tests:
       - CT / X-Rays within 72h $\rightarrow$ Marked as **ACTIVE / REUSABLE** (prevent re-scan).
       - Documented allergies $\rightarrow$ Highlighted as **CRITICAL ALERTS**.
       - Blood typing $\rightarrow$ Verified against regional blood bank.
       - Missing diagnostics $\rightarrow$ Flagged as **REQUIRED UPON ARRIVAL**.
  - Output: Consolidated HL7 FHIR `DiagnosticReport` & `Observation` bundle.
- [ ] **Task 3.2: Automated Savings & Resource Metric**
  - Compute saved diagnostic procedures and out-of-pocket costs prevented per patient.

---

### Phase 4: Frontend UI Portals (Tailored to the 3 Users)
**Goal:** Deploy specialized, clean, responsive interfaces matching the ZCMC Warm Clinical Ivory design system.

- [ ] **Task 4.1: Patient / Citizen Triage View (`static/patient.html`)**
  - Clean mobile-first interface for community intake.
  - Step-by-step symptom check with plain-language questions.
  - Visual routing outcome: "Your nearest clinic is Lamitan District Hospital" vs "Referred to ZCMC Tertiary Apex".
  - Digital Referral Passport with encrypted QR token.
- [ ] **Task 4.2: Local Clinic Triage & Edge Vault (`static/index.html`)**
  - Integrated Capability Matcher: Clinicians select needed service; engine highlights whether to treat locally or escalate.
  - One-tap escalation to ZCMC with HL7 FHIR R4 bundling.
  - Client-side Web Crypto `AES-GCM-256` offline vault with Island Outage simulation toggle.
- [ ] **Task 4.3: ZCMC Apex Command Center (`static/zcmc.html` & `static/dock.html`)**
  - Inbound Sea Corridor Radar with real-time transit times across Basilan Strait, Sulu Sea, and Tawi-Tawi.
  - **Cross-Match Inspector Modal:** Displays prior diagnostics side-by-side with incoming vitals, visibly checking off tests to prevent duplicate work.
  - Port Pier 1 Emergency Berthing handoff with Coast Guard VHF Ch 16 communication protocol.

---

### Phase 5: Resilient Offline-First Synchronization
**Goal:** Guarantee rock-solid store-and-forward operation for island health units during fiber severances or sea transits.

- [ ] **Task 5.1: Web Crypto AES-GCM-256 Client Vault Pipeline**
  - 100,000-iteration PBKDF2 key derivation.
  - Automatic background sync when browser network state shifts from offline to online.
- [ ] **Task 5.2: Monotonic Timestamp Delta Cursor**
  - Fast, low-bandwidth delta synchronization over 2G / satellite links via `/api/sync/pull?since={ts}`.

---

### Phase 6: End-to-End Verification & Pitch Demonstration Script
**Goal:** Verify full pipeline integrity and formulate the live demonstration flow for the ideathon judges.

- [ ] **Task 6.1: Comprehensive Unit & Integration Test Suite**
  - Test routing engine decisions.
  - Test medical data cross-matching and duplicate test prevention.
  - Test offline vault encryption and batch synchronization.
- [ ] **Task 6.2: Ideathon Live Demo Walkthrough**
  - Stage 1: Patient in Sulu enters acute symptoms; router determines service unavailable locally in Jolo $\rightarrow$ escalates to ZCMC.
  - Stage 2: Island outage strikes $\rightarrow$ data is sealed in AES-256 vault on device.
  - Stage 3: Connection restored in transit $\rightarrow$ auto-sync pushes referral to ZCMC Hub.
  - Stage 4: ZCMC Emergency Chief opens dashboard $\rightarrow$ cross-matching engine flags recent Sulu CT scan as valid $\rightarrow$ cancels repeat scan, saves ₱6,500, alerts Pier 1 ambulance team.

---

## Execution Readiness Checklist

| Milestone | Deliverables | Verification Check |
| :--- | :--- | :--- |
| **Phase 1: Schemas** | `facility_capabilities`, `patient_diagnostics` tables in `models.py` | Python test suite passes |
| **Phase 2: Router** | `/api/route` endpoint with capability registry | Test suite verifies routing boundaries |
| **Phase 3: Cross-Match** | `/api/crossmatch` deduplication engine | Confirms prior tests reused, duplicate tests prevented |
| **Phase 4: Portals** | `patient.html`, enhanced `index.html`, `dock.html`, and `components.js` | UI responsive on mobile & desktop |
| **Phase 5: Offline Sync** | Background auto-flush on reconnect + outbox vault | Simulated outage test in browser |
| **Phase 6: Demo** | Complete verified walkthrough | Live demonstration verified on port 8000 |
