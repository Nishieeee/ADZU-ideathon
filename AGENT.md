# Project Operating Guide: ADZU-ideathon

## 1. Local Runtime & Commands
- **Dev Server:** `cd AdZU_Ideathon; python -m uvicorn main:app --reload --port 8000`
- **Unit & Conformance Tests:** `python -m unittest discover -s AdZU_Ideathon -p "test_suite.py"`
- **Static Assets / Web App:** Served directly via FastAPI StaticFiles at `http://localhost:8000`

## 2. Architecture & Conventions
- **Tier 3 Vault Specification:** [[projects/side-projects/ADZU-ideathon.md]]
- **Code Standards:** 
  - FastAPI gateway + SQLite persistence in `AdZU_Ideathon/`
  - HL7 FHIR R4 ServiceRequest standard for referral payloads
  - Offline-first browser storage and sync cursors
  - Adhere strictly to existing directory structures; zero speculative abstractions
- **Verification Rule:** Every code modification must be verified via `python -m unittest discover -s AdZU_Ideathon -p "test_suite.py"` before task completion.
