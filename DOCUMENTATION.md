# ZCMC Regional Health Exchange (ZAMBASULTA)
## Official System Architecture & Workflow Specification

This document details the problem statement, user personas, intelligent routing engine, bi-directional medical data cross-matching, and offline-first store-and-forward architecture for the Ateneo de Zamboanga University (AdZU) Ideathon.

---

## 1. ZCMC Core Pain Points & Solutions

| ZCMC Main Pain Point | How the System Solves It |
| :--- | :--- |
| **Delays in patient care** | Real-time maritime radar & port triage pre-alerts dispatch ambulance teams to Pier 1 prior to vessel arrival. |
| **Repeated diagnostic procedures** | Automated medical data cross-matching identifies prior labs/imaging from island facilities, eliminating redundant tests. |
| **Inefficient referral coordination** | Intelligent capability-based routing automatically directs patients to capable local LGU clinics first, escalating to ZCMC only when tertiary care is necessary. |
| **High administrative burden** | Single-entry intake forms auto-generate standardized HL7 FHIR R4 `ServiceRequest` records, ending redundant paper logs. |
| **Limited evidence-based decision-making** | Real-time DOH Region IX & BARMM surveillance telemetry on regional inflow, corridor transit times, and clinical acuity. |

---

## 2. The 3 User Personas

### 1. Patients (Citizens of ZAMBASULTA)
- **Role:** Primary healthcare seekers from rural and island communities (Basilan, Sulu, Tawi-Tawi, Zamboanga Peninsula).
- **Experience:** Encounter triage routing that ensures they receive care at their nearest local clinic whenever possible, and seamless, rapid transport to ZCMC when tertiary intervention is required without redundant testing fees.

### 2. Local Clinics (LGU Healthcare Units, RHUs & Island District Hospitals)
- **Role:** Municipal and provincial healthcare providers on the front lines.
- **Experience:** 
  - Automated capability check verifies whether the clinic can treat the patient locally.
  - If care must be escalated, one-tap referral issuance creates an encrypted HL7 FHIR record.
  - Zero-internet resilience: Works in full offline mode (GIDA Island Outage); data is sealed with AES-GCM-256 on the local device and forwards automatically once connectivity is restored.

### 3. ZCMC (Tertiary / Regional Apex Hospital)
- **Role:** The regional apex referral center handling trauma, intensive care, and specialized surgeries.
- **Experience:**
  - Real-time Sea Corridor Radar monitoring inbound vessels from Basilan Strait, Sulu Sea, and Tawi-Tawi.
  - Automated cross-matching matches the patient's island referral with ZCMC's historical database, preventing repeated labs or imaging.
  - Pre-allocated emergency beds and pre-alerted operating teams ready at Port Pier 1.

---

## 3. Application Workflow

```
[Patient Presenting Complaint]
             │
             ▼
[Step 1: Local LGU Clinic Triage & Capability Match]
             │
      ┌──────┴──────────────────────────┐
      ▼                                 ▼
[Service Available Locally]    [Service Exceeds Local Capacity]
      │                                 │
[Treat & Discharge at LGU]     [Escalate to ZCMC Apex Hospital]
                                        │
                                        ▼
                       [Step 2: Edge Security & Outbox]
                                        │
                         Is Internet Link Available?
                                ├─ Yes ──► Instant HL7 FHIR R4 Sync
                                └─ No  ──► Sealed with AES-GCM-256 in Device Vault
                                           (Auto-forwards when reconnected)
                                        │
                                        ▼
                       [Step 3: Bi-Directional Cross-Matching]
                                        │
                       • Cross-match PhilHealth ID / MPI
                       • Extract prior labs, vitals, imaging
                       • Eliminate repeated diagnostic procedures
                                        │
                                        ▼
                       [Step 4: Sea Corridor Radar & Port Handoff]
                                        │
                       • Maritime tracking (Basilan, Sulu, Tawi-Tawi)
                       • Pier 1 Slipway emergency ambulance dispatch
                       • Direct ZCMC ER Trauma admission (Zero delay)
```

---

## 4. Cryptographic & Data Architecture

- **Edge Encryption:** Client-Side native Web Crypto API `AES-GCM-256` with `PBKDF2` (100,000 iterations).
- **Interoperability Standard:** HL7 FHIR R4 (`ServiceRequest`, `Patient`).
- **Database:** SQLite with append-only sync logs (`sync_log`) and monotonic timestamp delta cursors (`/api/sync/pull?since={ts}`).
- **Network Scope:** ZAMBASULTA (Zamboanga City, Basilan 18-24 NM, Sulu 80-95 NM, Tawi-Tawi 180-210 NM).
