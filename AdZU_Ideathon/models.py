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
                corridor_type TEXT DEFAULT 'maritime',
                allergies TEXT DEFAULT '',
                phone_number TEXT DEFAULT '',
                patient_lat REAL DEFAULT 0.0,
                patient_lon REAL DEFAULT 0.0,
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
        conn.execute("""
            CREATE TABLE IF NOT EXISTS branches (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                type TEXT NOT NULL,
                island_province TEXT NOT NULL,
                lat REAL NOT NULL,
                lon REAL NOT NULL,
                capacity_status TEXT DEFAULT 'normal',
                available_beds INTEGER DEFAULT 12,
                surgical_capable INTEGER DEFAULT 0,
                icu_capable INTEGER DEFAULT 0,
                blood_bank INTEGER DEFAULT 0
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_referral_updated ON referrals(updated_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sync_timestamp ON sync_log(timestamp)")

        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(referrals)")
        cols = [c[1] for c in cursor.fetchall()]
        for col_name, col_type in [
            ("corridor_type", "TEXT DEFAULT 'maritime'"),
            ("allergies", "TEXT DEFAULT ''"),
            ("phone_number", "TEXT DEFAULT ''"),
            ("patient_lat", "REAL DEFAULT 0.0"),
            ("patient_lon", "REAL DEFAULT 0.0"),
        ]:
            if col_name not in cols:
                conn.execute(f"ALTER TABLE referrals ADD COLUMN {col_name} {col_type}")

        cursor.execute("SELECT COUNT(*) FROM branches")
        if cursor.fetchone()[0] == 0:
            branch_seeds = [
                ("zcmc_apex", "Zamboanga City Medical Center (ZCMC)", "tertiary_apex", "Zamboanga City", 6.9125, 122.0722, "normal", 45, 1, 1, 1),
                ("basilan_gen", "Basilan General Hospital", "provincial", "Basilan", 6.7042, 121.9714, "normal", 14, 1, 1, 1),
                ("lamitan_dist", "Lamitan District Hospital", "district", "Basilan", 6.6492, 122.1331, "overcapacity", 0, 1, 0, 0),
                ("sulu_prov", "Sulu Provincial Hospital", "provincial", "Sulu", 6.0536, 121.0028, "normal", 18, 1, 1, 1),
                ("luuk_dist", "Luuk District Hospital", "district", "Sulu", 5.9619, 121.3208, "normal", 6, 0, 0, 0),
                ("tawi_ipho", "Tawi-Tawi IPHO Bongao", "provincial", "Tawi-Tawi", 5.0289, 119.7731, "normal", 20, 1, 1, 1),
                ("vitali_rhu", "Vitali Rural Health Unit", "rhu", "Zamboanga City", 7.3325, 122.2891, "normal", 4, 0, 0, 0)
            ]
            conn.executemany("""
                INSERT INTO branches (id, name, type, island_province, lat, lon, capacity_status, available_beds, surgical_capable, icu_capable, blood_bank)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, branch_seeds)
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


def get_all_branches(db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT * FROM branches")
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def update_branch_capacity(branch_id: str, capacity_status: str, available_beds: int, db_path: str = DB_PATH):
    conn = get_connection(db_path)
    with conn:
        conn.execute("""
            UPDATE branches
            SET capacity_status = ?, available_beds = ?
            WHERE id = ?
        """, (capacity_status, available_beds, branch_id))
    conn.close()
