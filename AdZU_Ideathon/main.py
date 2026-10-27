"""
ZCMC Regional Health Exchange: FastAPI Gateway & Delta Sync Service
Provides HL7 FHIR validation endpoints, batch delta sync ingestion, and maritime status tracking.
"""
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import models
import os

app = FastAPI(
    title="ZCMC Regional Health Exchange (ZAMBASULTA)",
    description="Offline-first HL7 FHIR sync gateway for maritime patient referrals",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

models.init_db()

class ReferralCreate(BaseModel):
    id: str
    patient_name: str
    philhealth_id: Optional[str] = None
    origin_facility: str
    destination_facility: str = "Zamboanga City Medical Center (ZCMC)"
    urgency: str = Field(..., description="routine | urgent | asap | stat")
    primary_diagnosis: str
    transit_status: str = Field(default="pending_transit", description="pending_transit | in_maritime_transit | arrived_port | admitted_zcmc")
    clinical_notes: str = ""
    client_id: str = "edge-node"

class BatchPushRequest(BaseModel):
    client_id: str
    records: List[ReferralCreate]

@app.get("/api/health")
def health_check():
    return {"status": "online", "facility": "Zamboanga City Medical Center", "protocol": "FHIR-R4-Sync"}

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
        client_id=data.client_id
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

# Mount static frontend files if folder exists
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
