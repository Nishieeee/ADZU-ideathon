"""
ZCMC Regional Health Exchange: Data Models & Storage Layer
Lightweight SQLite + JSON store enforcing HL7 FHIR compliance and append-only delta sync logs.
"""
import sqlite3
import json
import time
import os
from typing import Dict, Any, List, Optional

DB_PATH = os.path.join(os.path.dirname(__file__), "zcmc_exchange.db")

def get_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def init_db(db_path: str = DB_PATH) -> None:
    conn = get_connection(db_path)
    with conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS referrals (
                id TEXT PRIMARY KEY,
                patient_name TEXT NOT NULL,
                philhealth_id TEXT,
                origin_facility TEXT NOT NULL,
                destination_facility TEXT NOT NULL,
                urgency TEXT NOT NULL,
                primary_diagnosis TEXT NOT NULL,
                transit_status TEXT NOT NULL,
                fhir_resource TEXT NOT NULL,
                updated_at REAL NOT NULL,
                created_at REAL NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sync_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                referral_id TEXT NOT NULL,
                action TEXT NOT NULL,
                version INTEGER NOT NULL,
                client_id TEXT NOT NULL,
                timestamp REAL NOT NULL,
                payload TEXT NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_referral_updated ON referrals(updated_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sync_timestamp ON sync_log(timestamp)")
    conn.close()

def build_fhir_service_request(
    referral_id: str,
    patient_name: str,
    philhealth_id: Optional[str],
    origin_facility: str,
    destination_facility: str,
    urgency: str,
    diagnosis: str,
    clinical_notes: str
) -> Dict[str, Any]:
    """Generates an HL7 FHIR R4 ServiceRequest compliant resource structure."""
    return {
        "resourceType": "ServiceRequest",
        "id": referral_id,
        "status": "active",
        "intent": "order",
        "priority": urgency.lower(),
        "subject": {
            "display": patient_name,
            "identifier": {
                "system": "https://philhealth.gov.ph",
                "value": philhealth_id or "UNKNOWN"
            }
        },
        "requester": {
            "display": origin_facility
        },
        "performer": [
            {"display": destination_facility}
        ],
        "reasonCode": [
            {
                "text": diagnosis
            }
        ],
        "note": [
            {
                "text": clinical_notes,
                "time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            }
        ]
    }

def upsert_referral(
    referral_id: str,
    patient_name: str,
    philhealth_id: Optional[str],
    origin_facility: str,
    destination_facility: str,
    urgency: str,
    diagnosis: str,
    transit_status: str,
    fhir_resource: Dict[str, Any],
    client_id: str = "edge-client",
    db_path: str = DB_PATH
) -> Dict[str, Any]:
    now = time.time()
    conn = get_connection(db_path)
    fhir_json = json.dumps(fhir_resource)
    with conn:
        conn.execute("""
            INSERT INTO referrals (
                id, patient_name, philhealth_id, origin_facility, destination_facility,
                urgency, primary_diagnosis, transit_status, fhir_resource, updated_at, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                patient_name=excluded.patient_name,
                philhealth_id=excluded.philhealth_id,
                origin_facility=excluded.origin_facility,
                destination_facility=excluded.destination_facility,
                urgency=excluded.urgency,
                primary_diagnosis=excluded.primary_diagnosis,
                transit_status=excluded.transit_status,
                fhir_resource=excluded.fhir_resource,
                updated_at=excluded.updated_at
        """, (
            referral_id, patient_name, philhealth_id, origin_facility,
            destination_facility, urgency, diagnosis, transit_status,
            fhir_json, now, now
        ))
        
        # Append to sync audit ledger
        conn.execute("""
            INSERT INTO sync_log (referral_id, action, version, client_id, timestamp, payload)
            VALUES (?, 'UPSERT', 1, ?, ?, ?)
        """, (referral_id, client_id, now, fhir_json))
        
    conn.close()
    return {
        "id": referral_id,
        "status": "persisted",
        "updated_at": now
    }

def get_all_referrals(db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("""
        SELECT id, patient_name, philhealth_id, origin_facility, destination_facility,
               urgency, primary_diagnosis, transit_status, fhir_resource, updated_at, created_at
        FROM referrals ORDER BY updated_at DESC
    """)
    rows = cur.fetchall()
    conn.close()
    result = []
    for r in rows:
        item = dict(r)
        item["fhir_resource"] = json.loads(item["fhir_resource"])
        result.append(item)
    return result

def pull_deltas(since_timestamp: float, db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("""
        SELECT referral_id, action, version, client_id, timestamp, payload
        FROM sync_log
        WHERE timestamp > ?
        ORDER BY timestamp ASC
    """, (since_timestamp,))
    rows = cur.fetchall()
    conn.close()
    deltas = []
    for r in rows:
        d = dict(r)
        d["payload"] = json.loads(d["payload"])
        deltas.append(d)
    return deltas
