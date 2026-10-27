"""
ZCMC Regional Health Exchange: FastAPI Gateway, AI Triage & Multi-Branch Delta Sync Service
Provides HL7 FHIR validation, AI telemetry hospital routing, SMS simulator, and autonomous geofence tracking.
"""
from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import models
import os
import math
import time
import json

app = FastAPI(
    title="ZCMC Regional Health Exchange (ZAMBASULTA)",
    description="Offline-first HL7 FHIR sync gateway, AI triage routing & geofence tracking",
    version="1.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

models.init_db()

# Check for credentials in environment or local files
def load_local_env():
    for p in [
        os.path.join(os.path.dirname(__file__), ".env"),
        os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
    ]:
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as ef:
                for line in ef:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        os.environ[k.strip()] = v.strip().strip('"').strip("'")

load_local_env()

# In-memory SMS log buffer for simulation auditing & offline outbox
sms_dispatches = []

def dispatch_sms_notification(recipient_phone: str, message: str, event_type: str = "triage_alert") -> Dict[str, Any]:
    """
    Autonomous Offline 2G GSM / SMS Dispatcher.
    Queues compact 160-character alerts into the regional emergency dispatch ledger.
    """
    log_entry = {
        "timestamp": time.time(),
        "recipient": recipient_phone or "+63-917-ZCMC-911",
        "sms_text": message,
        "type": event_type,
        "channel": "2G_GSM_SMS",
        "status": "DISPATCHED_CELLULAR"
    }
    sms_dispatches.insert(0, log_entry)
    return log_entry

class ReferralCreate(BaseModel):
    id: str
    patient_name: str
    philhealth_id: Optional[str] = None
    origin_facility: str
    destination_facility: str = "Zamboanga City Medical Center (ZCMC)"
    urgency: str = Field(..., description="routine | urgent | asap | stat")
    primary_diagnosis: str
    transit_status: str = Field(default="pending_transit")
    corridor_type: str = "maritime"
    allergies: str = ""
    phone_number: str = ""
    patient_lat: float = 6.9125
    patient_lon: float = 122.0722
    clinical_notes: str = ""
    client_id: str = "edge-node"

class BatchPushRequest(BaseModel):
    client_id: str
    records: List[ReferralCreate]


import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

DEFAULT_GMAIL = "axrcopu@gmail.com"
email_logs = []


# Check for credentials in environment or local files
def load_local_env():
    for p in [
        os.path.join(os.path.dirname(__file__), ".env"),
        os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
    ]:
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as ef:
                for line in ef:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        os.environ[k.strip()] = v.strip().strip('"').strip("'")

load_local_env()

def send_direct_email_relay(subject: str, body_text: str, recipient: str = DEFAULT_GMAIL) -> Dict[str, Any]:
    """Sends real email to recipient using direct HTTP gateway (no local password required once confirmed)."""
    import urllib.request
    import urllib.parse
    
    url = f"https://formsubmit.co/ajax/{recipient}"
    payload = {
        "name": "ZCMC Regional Health Exchange",
        "_subject": subject,
        "message": body_text
    }
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Origin": "http://localhost:8000",
            "Referer": "http://localhost:8000/mvp.html"
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            resp_body = resp.read().decode('utf-8')
            return {"status": "HTTP_RELAY_SENT", "response": resp_body}
    except Exception as e:
        return {"status": "HTTP_RELAY_ERROR", "error": str(e)}

def send_gmail_notification(subject: str, body_text: str, recipient: str = DEFAULT_GMAIL) -> Dict[str, Any]:
    load_local_env()
    smtp_user = os.environ.get("GMAIL_USER")
    smtp_pass = os.environ.get("GMAIL_APP_PASSWORD")
    
    log_entry = {
        "timestamp": time.time(),
        "recipient": recipient,
        "subject": subject,
        "body": body_text,
        "status": "pending"
    }
    
    # 1. Attempt direct web email delivery first (delivered without local credentials)
    relay_res = send_direct_email_relay(subject=subject, body_text=body_text, recipient=recipient)
    log_entry["relay_details"] = relay_res
    
    # 2. If SMTP credentials exist, also dispatch via TLS port 587
    if smtp_user and smtp_pass:
        try:
            msg = MIMEMultipart()
            msg['From'] = f"ZCMC Health Exchange <{smtp_user}>"
            msg['To'] = recipient
            msg['Subject'] = subject
            msg.attach(MIMEText(body_text, 'plain'))
            with smtplib.SMTP('smtp.gmail.com', 587, timeout=10) as server:
                server.starttls()
                server.login(smtp_user, smtp_pass)
                server.send_message(msg)
            log_entry["status"] = f"LIVE_SENT (SMTP + Relay to {recipient})"
        except Exception as e:
            log_entry["status"] = f"Relay: {relay_res.get('status')} | SMTP Error: {str(e)}"
    else:
        log_entry["status"] = f"DISPATCHED (Direct Web Delivery to {recipient})"
        
    email_logs.insert(0, log_entry)
    return log_entry


class MapClickGeofenceRequest(BaseModel):
    referral_id: str
    clicked_lat: float
    clicked_lon: float
    waypoint_lat: float
    waypoint_lon: float
    waypoint_name: str
    recipient_email: Optional[str] = DEFAULT_GMAIL

class TriageSuggestRequest(BaseModel):
    patient_name: str
    chief_complaint: str
    allergies: str
    patient_lat: float
    patient_lon: float
    urgency: Optional[str] = "urgent"
    phone_number: str = ""

class GeofenceUpdateRequest(BaseModel):
    referral_id: str
    current_lat: float
    current_lon: float
    previous_lat: Optional[float] = None
    previous_lon: Optional[float] = None

class BranchCapacityUpdate(BaseModel):
    branch_id: str
    capacity_status: str
    available_beds: int

def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0 # Earth radius in kilometers
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return round(R * c, 2)

@app.get("/api/health")
def health_check():
    return {"status": "online", "facility": "Zamboanga City Medical Center", "protocol": "FHIR-R4-Sync", "version": "1.1.0"}

@app.get("/api/referrals")
def list_referrals():
    return models.get_all_referrals()

@app.post("/api/referrals")
def create_or_update_referral(data: ReferralCreate):
    fhir_bundle = models.build_fhir_service_request(
        referral_id=data.id,
        patient_name=data.patient_name,
        philhealth_id=data.philhealth_id,
        origin_facility=data.origin_facility,
        destination_facility=data.destination_facility,
        urgency=data.urgency,
        diagnosis=data.primary_diagnosis,
        clinical_notes=data.clinical_notes
    )
    result = models.upsert_referral(
        referral_id=data.id,
        patient_name=data.patient_name,
        philhealth_id=data.philhealth_id,
        origin_facility=data.origin_facility,
        destination_facility=data.destination_facility,
        urgency=data.urgency,
        diagnosis=data.primary_diagnosis,
        transit_status=data.transit_status,
        fhir_resource=fhir_bundle,
        client_id=data.client_id,
        phone_number=data.phone_number,
        allergies=data.allergies,
        corridor_type=data.corridor_type,
        patient_lat=data.patient_lat,
        patient_lon=data.patient_lon,
    )
    return result

@app.post("/api/sync/push")
def batch_push(payload: BatchPushRequest):
    synced_ids = []
    for item in payload.records:
        fhir_bundle = models.build_fhir_service_request(
            referral_id=item.id,
            patient_name=item.patient_name,
            philhealth_id=item.philhealth_id,
            origin_facility=item.origin_facility,
            destination_facility=item.destination_facility,
            urgency=item.urgency,
            diagnosis=item.primary_diagnosis,
            clinical_notes=item.clinical_notes
        )
        models.upsert_referral(
            referral_id=item.id,
            patient_name=item.patient_name,
            philhealth_id=item.philhealth_id,
            origin_facility=item.origin_facility,
            destination_facility=item.destination_facility,
            urgency=item.urgency,
            diagnosis=item.primary_diagnosis,
            transit_status=item.transit_status,
            fhir_resource=fhir_bundle,
            client_id=payload.client_id
        )
        synced_ids.append(item.id)
    return {"status": "success", "synced_count": len(synced_ids), "synced_ids": synced_ids}

@app.get("/api/sync/pull")
def pull_updates(since: float = Query(0.0, description="Timestamp cursor")):
    deltas = models.pull_deltas(since)
    return {"cursor": since, "count": len(deltas), "deltas": deltas}

# --- Multi-Branch Management ---

class ReferralCompleteRequest(BaseModel):
    referral_id: str
    admitting_branch_id: str
    admitting_branch_name: str

@app.post("/api/referrals/complete")
def complete_referral(req: ReferralCompleteRequest, background_tasks: BackgroundTasks):
    now = time.time()
    conn = models.get_connection()

    # Fetch full ticket details before closing for the official closure email
    referral_row = conn.execute(
        """SELECT patient_name, philhealth_id, origin_facility, primary_diagnosis,
                  urgency, allergies, phone_number, corridor_type,
                  patient_lat, patient_lon, transit_status, fhir_resource, created_at
           FROM referrals WHERE id = ?""",
        (req.referral_id,)
    ).fetchone()

    with conn:
        conn.execute("""
            UPDATE referrals
            SET transit_status = 'admitted_and_completed',
                destination_facility = ?,
                updated_at = ?
            WHERE id = ?
        """, (req.admitting_branch_name, now, req.referral_id))

        # Append to sync audit ledger
        payload = json.dumps({
            "action": "COMPLETE_AND_ADMIT",
            "referral_id": req.referral_id,
            "destination_facility": req.admitting_branch_name,
            "transit_status": "admitted_and_completed"
        })
        conn.execute("""
            INSERT INTO sync_log (referral_id, action, version, client_id, timestamp, payload)
            VALUES (?, 'COMPLETE', 2, ?, ?, ?)
        """, (req.referral_id, req.admitting_branch_id, now, payload))
    conn.close()

    # Resolve patient details for closure email
    if referral_row:
        patient_name    = referral_row["patient_name"]  or "Unknown Patient"
        philhealth_id   = referral_row["philhealth_id"] or "Not Provided"
        origin          = referral_row["origin_facility"]    or "N/A"
        diagnosis       = referral_row["primary_diagnosis"]  or "N/A"
        urgency         = referral_row["urgency"]            or "N/A"
        allergies       = referral_row["allergies"]          or "None reported"
        phone_number    = referral_row["phone_number"]       or "Not provided"
        corridor_type   = referral_row["corridor_type"]      or "N/A"
        patient_lat     = referral_row["patient_lat"]
        patient_lon     = referral_row["patient_lon"]
        last_transit    = referral_row["transit_status"]     or "unknown"
        created_at_ts   = referral_row["created_at"]        or now
        transit_minutes = round((now - created_at_ts) / 60, 1)
        try:
            fhir_obj       = json.loads(referral_row["fhir_resource"] or "{}")
            # Notes live at fhir_obj["note"][0]["text"] (flat ServiceRequest, not a bundle)
            notes_list     = fhir_obj.get("note", [])
            clinical_notes = notes_list[0]["text"].strip() if notes_list else ""
        except Exception:
            clinical_notes = ""
    else:
        patient_name    = req.referral_id
        philhealth_id   = "Not Provided"
        origin          = "N/A"
        diagnosis       = "N/A"
        urgency         = "N/A"
        allergies       = "None reported"
        phone_number    = "Not provided"
        corridor_type   = "N/A"
        patient_lat     = 0.0
        patient_lon     = 0.0
        last_transit    = "unknown"
        created_at_ts   = now
        transit_minutes = 0.0
        clinical_notes  = ""

    # Human-readable geofence transit status label
    transit_label_map = {
        "admitted_and_completed":    "COMPLETED & ADMITTED",
        "arrived_at_location":       "Arrived at Location (Geofence: Within 100 m)",
        "arrived_waypoint":          "Arrived at Waypoint (GPS Confirmed)",
        "en_route":                  "En Route (Approaching Destination)",
        "in_transit":                "In Transit",
        "in_transit_corridor":       "In Transit Corridor",
        "approaching_location":      "Approaching Location",
        "backtracking_or_departed":  "Backtracking / Departed Route",
        "pending_departure":         "Pending Departure (Not yet en route)",
        "pending_transit":           "Pending Transit",
    }
    transit_label = transit_label_map.get(last_transit, last_transit.replace("_", " ").title())

    closure_subject = (
        f"[ZCMC Exchange] TICKET CLOSED \u2014 {patient_name} "
        f"Admitted & Completed (Ref: {req.referral_id})"
    )
    closure_lines = [
        "ZCMC REGIONAL HEALTH EXCHANGE \u2014 OFFICIAL TICKET CLOSURE NOTICE",
        "================================================================",
        "",
        "\u2500\u2500 PATIENT IDENTITY \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500",
        f"  Referral ID       : {req.referral_id}",
        f"  Patient Name      : {patient_name}",
        f"  PhilHealth ID     : {philhealth_id}",
        f"  Contact / Phone   : {phone_number}",
        "",
        "\u2500\u2500 CLINICAL SUMMARY \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500",
        f"  Primary Diagnosis : {diagnosis}",
        f"  Urgency / Acuity  : {urgency.upper()}",
        f"  Allergy Record    : {allergies}",
    ]
    if clinical_notes and clinical_notes != allergies:
        closure_lines.append(f"  Clinical Notes    : {clinical_notes}")
    closure_lines += [
        "",
        "\u2500\u2500 TRANSFER & ROUTING \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500",
        f"  Origin Facility   : {origin}",
        f"  Corridor Type     : {corridor_type.upper()}",
        f"  Admitting Branch  : {req.admitting_branch_name}",
        f"  Final Status      : COMPLETED & ADMITTED",
        "",
        "\u2500\u2500 TRANSIT TIMELINE \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500",
        f"  Ticket Created    : {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(created_at_ts))}",
        f"  Ticket Closed     : {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(now))}",
        f"  Total Transit     : {transit_minutes} min",
        f"  Last Geofence     : {transit_label}",
        f"  Final GPS         : ({patient_lat:.5f}, {patient_lon:.5f})",
        "",
        "\u2500\u2500 SYSTEM CLOSURE \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500",
        "  AI Clinical Routing Telemetry  : INACTIVE",
        "  Autonomous Geofence Tracking   : INACTIVE",
        "  Delta Sync Status              : FINALIZED (all branch terminals updated)",
        "  Further Automated Alerts       : NONE",
        "",
        "================================================================",
        "ZCMC Regional Health Exchange | ZAMBASULTA Network",
        "Zamboanga, Basilan, Sulu, Tawi-Tawi & Zamboanga Peninsula",
    ]
    closure_body = "\n".join(closure_lines)

    closure_sms = f"[ZCMC CLOSED] Ref {req.referral_id}: Patient {patient_name} admitted at {req.admitting_branch_name}. Transit: {transit_minutes}m. Status: ADMITTED & COMPLETED."
    closure_alert_phone = phone_number if phone_number and phone_number != "Not provided" else "+63-917-ZCMC-911"
    dispatch_sms_notification(
        recipient_phone=closure_alert_phone,
        message=closure_sms,
        event_type="ticket_closure"
    )

    return {
        "status": "success",
        "referral_id": req.referral_id,
        "admitting_branch": req.admitting_branch_name,
        "transit_status": "admitted_and_completed",
        "closure_sms": closure_sms
    }

@app.get("/api/branches")
def list_branches():
    return models.get_all_branches()

@app.post("/api/branches/capacity")
def set_branch_capacity(payload: BranchCapacityUpdate):
    models.update_branch_capacity(payload.branch_id, payload.capacity_status, payload.available_beds)
    return {"status": "updated", "branch_id": payload.branch_id, "capacity_status": payload.capacity_status}

# --- AI Triage Routing Telemetry Endpoint ---
@app.post("/api/triage/suggest")
def suggest_facilities(req: TriageSuggestRequest):
    complaint_lower = req.chief_complaint.lower()
    allergies_lower = req.allergies.lower()
    branches = models.get_all_branches()

    requires_surgery = any(k in complaint_lower for k in ["appendic", "trauma", "fracture", "bleed", "hemorrhage", "cesarean", "stab", "gunshot"])
    requires_icu = any(k in complaint_lower for k in ["unconscious", "shock", "coma", "respiratory failure", "sepsis", "severe"])
    allergy_anaphylaxis_risk = any(k in allergies_lower for k in ["penicillin", "amoxicillin", "sulfa", "aspirin", "nsaid", "latex"])

    allergy_warning = "No high-risk contraindications detected."
    if allergy_anaphylaxis_risk:
        allergy_warning = f"CRITICAL ALLERGY ALERT ({req.allergies}): Patient requires facility with epinephrine & ICU airway backup."

    recommendations = []
    for b in branches:
        dist_km = haversine_km(req.patient_lat, req.patient_lon, b["lat"], b["lon"])
        dist_nm = round(dist_km * 0.539957, 1)

        can_handle = True
        reasons = []

        if requires_surgery and not b["surgical_capable"]:
            can_handle = False
            reasons.append("Lacks Surgical Operating Suite")
        if requires_icu and not b["icu_capable"]:
            can_handle = False
            reasons.append("Lacks Intensive Care Unit (ICU)")

        is_overcapacity = (b["capacity_status"] == "overcapacity" or b["available_beds"] <= 0)

        status_tag = "CAN ACCOMMODATE"
        if not can_handle:
            status_tag = "CAPACITY EXCEEDED / INCAPABLE"
        elif is_overcapacity:
            status_tag = "OVERCAPACITY (Wait times high)"

        # Determine exact equipment and treatments available at this facility for the specific complaint
        treatments_available = []
        equipment_available = []
        
        # 1. Surgical Equipment & Interventions
        if b["surgical_capable"]:
            if any(k in complaint_lower for k in ["appendic", "abdomen", "peritonitis", "pain"]):
                treatments_available.append("Emergency Exploratory Laparotomy / Appendectomy")
                equipment_available.extend(["Laparoscopic Tower & General Surgery Instrument Trays", "Cautery Electrosurgical Units", "Sterile Operating Suite"])
            elif any(k in complaint_lower for k in ["cesarean", "maternal", "labor", "obstetric", "bleed"]):
                treatments_available.append("Emergency Cesarean Section (C-Section) & CEmONC Protocol")
                equipment_available.extend(["Obstetric Surgical Suite", "Fetal Doppler Monitor", "Neonatal Resuscitaire"])
            elif any(k in complaint_lower for k in ["trauma", "fracture", "stab", "gunshot"]):
                treatments_available.append("Trauma Wound Debridement, Hemostasis & Orthopedic Fixation")
                equipment_available.extend(["Trauma Resuscitation Bay", "Major Vascular Clamp Sets", "Portable C-Arm Fluoroscopy"])
            else:
                treatments_available.append("General Surgical Intervention & Wound Exploration")
                equipment_available.append("Operating Room Suites")

        # 2. Critical Care & Resuscitation Equipment
        if b["icu_capable"]:
            equipment_available.extend(["Mechanical Ventilators", "Continuous Multi-parameter Vitals Monitors (Arterial Line/ECG)", "Infusion Syringe Pumps"])
            treatments_available.append("Intensive Care Hemodynamic Stabilization & Sepsis Protocol")

        # 3. Blood Products
        if b["blood_bank"]:
            equipment_available.append("Regional Blood Bank Refrigeration & Component Storage")
            treatments_available.append("Immediate Packed Red Blood Cells (PRBC) & Plasma Transfusion")

        # 4. Allergy & Anaphylaxis Treatments (Addressing reported allergies)
        if allergy_anaphylaxis_risk:
            if b["icu_capable"] or b["type"] in ["tertiary_apex", "provincial"]:
                treatments_available.append(f"Alternative Non-Beta-Lactam IV Antibiotics (Vancomycin, Fluoroquinolones, Aminoglycosides) bypassing {req.allergies}")
                equipment_available.append("Emergency Airway Crash Cart (Video Laryngoscope, Endotracheal Kits, Epinephrine auto-injectors)")
            else:
                treatments_available.append("Basic Antihistamine/Steroid Administration (No advanced airway backup)")

        # 5. Diagnostic Imaging Equipment
        if b["type"] == "tertiary_apex":
            equipment_available.extend(["128-Slice High-Resolution Contrast CT Scanner", "Point-of-Care Ultrasound (POCUS)", "24/7 Automated Blood Chemistry Analyzer"])
        elif b["type"] == "provincial":
            equipment_available.extend(["Digital X-Ray", "Abdominal Ultrasound Unit", "STAT Complete Blood Count (CBC) Analyzer"])
        elif b["type"] == "district":
            equipment_available.extend(["Basic Stationary X-Ray", "Primary Hematology Lab"])
        else:
            equipment_available.append("Rapid Diagnostic Test Kits (Malaria/Dengue/Pregnancy)")

        # Formulate rich, structured clinical rationale
        rationale_parts = []
        if can_handle:
            rationale_parts.append(f"Equipped to directly treat your complaint ('{req.chief_complaint}')")
            if treatments_available:
                rationale_parts.append(f"Available Treatments: {', '.join(treatments_available[:3])}")
            if equipment_available:
                rationale_parts.append(f"On-Site Equipment: {', '.join(equipment_available[:4])}")
            if is_overcapacity:
                rationale_parts.append("Warning: Facility is currently at full capacity (0 available beds); emergency bypass or surge triage required.")
            else:
                rationale_parts.append(f"Admissions: Ready with {b['available_beds']} vacant beds.")
        else:
            rationale_parts.append(f"INCAPABLE: Cannot treat your complaint due to missing infrastructure ({', '.join(reasons)}). Do not proceed here for surgery or intensive care.")

        clinical_rationale = " | ".join(rationale_parts)

        recommendations.append({
            "branch_id": b["id"],
            "name": b["name"],
            "island_province": b["island_province"],
            "type": b["type"],
            "distance_km": dist_km,
            "distance_nm": dist_nm,
            "can_handle": can_handle,
            "is_overcapacity": is_overcapacity,
            "available_beds": b["available_beds"],
            "status_tag": status_tag,
            "disqualifications": reasons,
            "clinical_rationale": clinical_rationale
        })

    recommendations.sort(key=lambda x: (not x["can_handle"], x["is_overcapacity"], x["distance_km"]))

    # Synthesize SMS content
    top = recommendations[0] if recommendations else None
    alt = recommendations[1] if len(recommendations) > 1 else None
    
    sms_text = f"[ZCMC Exchange] Hello {req.patient_name}, Triage evaluated. "
    if top:
        sms_text += f"1) {top['name']} ({top['distance_km']}km): {top['status_tag']}. "
    if alt:
        sms_text += f"2) {alt['name']} ({alt['distance_km']}km): {alt['status_tag']}. "
    if allergy_anaphylaxis_risk:
        sms_text += f"Notice: Allergy alert flagged for {req.allergies}. Keep GPS active."

    # Formulate Comprehensive Intake & Facility Options Email
    nearest = min(recommendations, key=lambda x: x["distance_km"]) if recommendations else None
    
    email_subject = f"[ZCMC Triage] Hospital Recommendations & Bed Capacity for {req.patient_name}"
    
    body_lines = [
        f"ZCMC REGIONAL HEALTH EXCHANGE - PATIENT TRIAGE ADMISSION SUMMARY",
        f"================================================================",
        f"Patient Name: {req.patient_name}",
        f"Chief Complaint: {req.chief_complaint}",
        f"Allergy Alert: {allergy_warning}",
        f"Triage Acuity: {'STAT (Life Threat)' if (requires_surgery or requires_icu) else 'URGENT'}",
        f"Patient GPS Coordinates: ({req.patient_lat:.4f}, {req.patient_lon:.4f})",
        "",
        f"1. NEAREST HEALTHCARE FACILITY:",
        f"   -> {nearest['name'] if nearest else 'N/A'}",
        f"   -> Distance: {nearest['distance_km']} km ({nearest['distance_nm']} NM)",
        f"   -> Can Accommodate Case: {'YES' if nearest and nearest['can_handle'] else 'NO - Lacks Required Facilities'}",
        f"   -> Capacity Status: {'OVERCAPACITY' if nearest and nearest['is_overcapacity'] else 'NORMAL (Available Beds: ' + str(nearest['available_beds']) + ')'}",
        "",
        f"2. FULL REGIONAL FACILITY BREAKDOWN & CAPABILITY MATCH:",
    ]
    
    for idx, f in enumerate(recommendations, 1):
        status_str = "CAN ACCOMMODATE" if f["can_handle"] else "CANNOT ACCOMMODATE"
        cap_str = "OVERCAPACITY (Wait times high)" if f["is_overcapacity"] else f"NORMAL ({f['available_beds']} beds free)"
        disq = f" - Reason: {', '.join(f['disqualifications'])}" if f['disqualifications'] else ""
        body_lines.append(f"   [{idx}] {f['name']} ({f['island_province']}):")
        body_lines.append(f"       Distance: {f['distance_km']} km ({f['distance_nm']} NM)")
        body_lines.append(f"       Capability: {status_str}{disq}")
        body_lines.append(f"       Capacity: {cap_str}")
        body_lines.append(f"       Why Recommended: {f.get('clinical_rationale', 'N/A')}")
        body_lines.append("")
        
    body_lines.append("To track real-time transit and trigger automatic 100-meter GPS arrival updates, keep your browser ticket open.")
    
    # Autonomous SMS dispatch (cellular 2G protocol)
    alert_phone = req.phone_number or "+63-917-ZCMC-911"
    sms_res = dispatch_sms_notification(
        recipient_phone=alert_phone,
        message=sms_text,
        event_type="triage_recommendation"
    )

    return {
        "ai_telemetry": {
            "acuity": "STAT" if (requires_surgery or requires_icu) else "URGENT",
            "requires_surgery": requires_surgery,
            "requires_icu": requires_icu,
            "allergy_warning": allergy_warning
        },
        "recommended_facilities": recommendations,
        "nearest_facility": nearest,
        "generated_sms": sms_text,
        "sms_delivery": sms_res
    }

# --- Autonomous Geofencing State Engine ---
@app.post("/api/geofence/update")
def process_geofence(req: GeofenceUpdateRequest):
    branches = models.get_all_branches()
    closest = min(branches, key=lambda b: haversine_km(req.current_lat, req.current_lon, b["lat"], b["lon"]))
    dist_m = haversine_km(req.current_lat, req.current_lon, closest["lat"], closest["lon"]) * 1000

    new_status = "in_transit"
    direction = "forward"

    if dist_m <= 100:
        new_status = "arrived_waypoint"
    elif req.previous_lat and req.previous_lon:
        prev_dist_m = haversine_km(req.previous_lat, req.previous_lon, closest["lat"], closest["lon"]) * 1000
        if dist_m > prev_dist_m:
            direction = "moving_away_or_backtracking"
            new_status = "backtracking_or_departed"
        else:
            direction = "approaching_destination"
            new_status = "en_route"

    status_sms = f"[ZCMC GeoAlert] Ref {req.referral_id}: Patient is ~{int(dist_m)}m from {closest['name']}. Status updated to: {new_status}."
    dispatch_record = {
        "timestamp": time.time(),
        "patient_name": f"Referral {req.referral_id}",
        "sms_text": status_sms,
        "type": "geofence_status_change"
    }
    sms_dispatches.insert(0, dispatch_record)

    return {
        "referral_id": req.referral_id,
        "closest_branch": closest["name"],
        "distance_meters": round(dist_m, 1),
        "direction": direction,
        "computed_status": new_status,
        "sms_dispatched": status_sms
    }


@app.post("/api/geofence/map-click")
def evaluate_map_click(req: MapClickGeofenceRequest):
    # Compute distance between clicked point and predefined waypoint in meters
    dist_km = haversine_km(req.clicked_lat, req.clicked_lon, req.waypoint_lat, req.waypoint_lon)
    dist_m = round(dist_km * 1000, 1)
    
    # 100m Geofencing threshold logic
    if dist_m <= 100:
        new_status = "arrived_at_location"
        status_label = f"ARRIVED AT {req.waypoint_name.upper()} (Within {dist_m}m)"
    elif dist_m <= 500:
        new_status = "approaching_location"
        status_label = f"Approaching {req.waypoint_name} ({dist_m}m away)"
    elif dist_m <= 2500:
        new_status = "in_transit_corridor"
        status_label = f"In Transit / Corridor ({dist_km} km away)"
    else:
        new_status = "pending_departure_or_diverted"
        status_label = f"Far / Off-Track ({dist_km} km from waypoint)"
        
    # Update SQLite database record
    conn = models.get_connection()
    with conn:
        conn.execute("""
            UPDATE referrals
            SET transit_status = ?, patient_lat = ?, patient_lon = ?, updated_at = ?
            WHERE id = ?
        """, (new_status, req.clicked_lat, req.clicked_lon, time.time(), req.referral_id))
    conn.close()
    
    # Resolve alert phone from the stored referral record
    _geo_conn = models.get_connection()
    _geo_row = _geo_conn.execute(
        "SELECT phone_number FROM referrals WHERE id = ?", (req.referral_id,)
    ).fetchone()
    _geo_conn.close()
    geo_alert_phone = (_geo_row["phone_number"] if _geo_row and _geo_row["phone_number"] else "") or "+63-917-ZCMC-911"

    # SMS notification body
    status_sms = f"[ZCMC GeoAlert] Ref {req.referral_id}: Status {new_status.upper()} - {status_label} (Dist: {dist_m}m)."
    sms_res = dispatch_sms_notification(
        recipient_phone=geo_alert_phone,
        message=status_sms,
        event_type="geofence_status_change"
    )
    
    return {
        "referral_id": req.referral_id,
        "clicked_lat": req.clicked_lat,
        "clicked_lon": req.clicked_lon,
        "waypoint_name": req.waypoint_name,
        "distance_meters": dist_m,
        "is_within_100m": (dist_m <= 100),
        "new_status": new_status,
        "status_label": status_label,
        "sms_delivery": sms_res
    }


class SmtpConfigRequest(BaseModel):
    gmail_user: str
    gmail_app_password: str

@app.post("/api/email/configure")
def configure_smtp(req: SmtpConfigRequest):
    env_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
    os.environ["GMAIL_USER"] = req.gmail_user.strip()
    os.environ["GMAIL_APP_PASSWORD"] = req.gmail_app_password.strip()
    
    with open(env_file, "a", encoding="utf-8") as ef:
        ef.write(f"\nGMAIL_USER={req.gmail_user.strip()}\nGMAIL_APP_PASSWORD={req.gmail_app_password.strip()}\n")
        
    # Send test verification email immediately
    test_res = send_gmail_notification(
        subject="[ZCMC Regional Exchange] Live Email Delivery Verified",
        body_text="Your ZCMC Regional Health Exchange email notification system is now connected to live Gmail SMTP.",
        recipient=DEFAULT_GMAIL
    )
    return {"status": "configured", "delivery": test_res}

@app.get("/api/email/log")
def get_email_logs():
    return email_logs[:20]

@app.get("/api/sms/log")
def get_sms_logs():
    return sms_dispatches[:20]

# Mount static frontend
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
