================================================================================
ZCMC REGIONAL HEALTH EXCHANGE (ZAMBASULTA MARITIME REFERRAL NETWORK)
Ateneo de Zamboanga University (AdZU) Ideathon Submission Package
================================================================================

1. SYSTEM OVERVIEW
--------------------------------------------------------------------------------
This system is an offline-first, HL7 FHIR-compliant regional health information
exchange and referral coordination engine. It was built specifically for Zamboanga
City Medical Center (ZCMC) to solve the "ZAMBASULTA Factor" (connecting GIDA 
island clinics across Basilan, Sulu, and Tawi-Tawi with ZCMC via maritime tracking).

2. PREREQUISITES & INSTALLATION (ANY DEVICE)
--------------------------------------------------------------------------------
Requirements:
  - Python 3.9+ (Windows, macOS, or Linux)
  - pip (Python package installer)

Install the only two lightweight dependencies required:
  pip install fastapi uvicorn

(Optional for running unit tests):
  pip install httpx

3. HOW TO START THE SYSTEM
--------------------------------------------------------------------------------
Open terminal / command prompt in this directory ("AdZU_Ideathon") and run:

  python -m uvicorn main:app --reload --port 8000

Once the server is running, you can access the system from your browser:
  - Main Central Hub & Offline Referral Form:  http://localhost:8000
  - Maritime Dock & Port Radar Interface:       http://localhost:8000/dock.html
  - Leadership & DOH Analytics Dashboard:       http://localhost:8000/analytics.html
  - Interactive API Specification (Swagger):    http://localhost:8000/docs

4. HOW TO USE THE SYSTEM (DEMO STEPS)
--------------------------------------------------------------------------------
Step A: Issue an Offline Referral (Island Clinic)
  1. Open http://localhost:8000
  2. Disconnect your internet (or toggle offline in DevTools). Notice the green
     badge changes to "Offline Mode - Storing Locally".
  3. Fill out the form (e.g., patient name, origin hospital in Basilan/Sulu, 
     STAT priority, diagnosis) and click "ISSUE HL7 FHIR REFERRAL".
  4. The referral is safely stored in local encrypted browser storage (Outbox: 1).
  5. Reconnect to the internet and click "Sync Outbox" (or it auto-syncs).
     The record flushes to the central ZCMC database with zero data loss.

Step B: Track Maritime Sea Transit (Port Reception)
  1. Open http://localhost:8000/dock.html
  2. Coast Guard and dockside ambulance teams can see inbound boats across the sea.
  3. Click "Dispatched to Sea" -> "Arrived at Zamboanga Port" -> "Handed to ZCMC".
     This ensures surgical teams at ZCMC are prepared before the boat even docks.

Step C: Review Regional Analytics (Hospital Leadership & DOH)
  1. Open http://localhost:8000/analytics.html
  2. View live KPI cards (STAT cases, active boats, bed admissions).
  3. Inspect facility-by-facility referral breakdowns.
  4. Click "Export DOH Report (PDF)" to generate an official compliance document.

5. ARCHITECTURE & VERIFICATION
--------------------------------------------------------------------------------
- Models & Schema:   models.py (Fast SQLite + HL7 FHIR R4 ServiceRequest generator)
- Gateway & Sync:    main.py (REST endpoints + delta sync cursor)
- Design Tokens:     Montserrat / Source Sans 3 + Official ZCMC Forest/Gold Palette
- Verification:      Run "python test_suite.py" to execute unit & FHIR tests.
================================================================================
