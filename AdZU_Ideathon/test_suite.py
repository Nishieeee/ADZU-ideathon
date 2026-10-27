"""
Behavioral & Structural Verification Suite for ZCMC Health Exchange
Validates HL7 FHIR conformance, offline delta synchronization, and API contracts.
"""
import unittest
import os
import json
import tempfile
import models

class TestZCMCReferralEngine(unittest.TestCase):
    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.db_path = self.temp_db.name
        self.temp_db.close()
        models.init_db(self.db_path)

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_fhir_service_request_compliance(self):
        """Verify generated payload satisfies HL7 FHIR R4 ServiceRequest resource schema."""
        fhir = models.build_fhir_service_request(
            referral_id="REF-TEST-001",
            patient_name="Amina H. Yusop",
            philhealth_id="12-345678901-2",
            origin_facility="Sulu Provincial Hospital",
            destination_facility="Zamboanga City Medical Center (ZCMC)",
            urgency="stat",
            diagnosis="Ectopic pregnancy with acute hemorrhage",
            clinical_notes="Patient requires immediate surgical intervention upon port arrival."
        )

        self.assertEqual(fhir["resourceType"], "ServiceRequest")
        self.assertEqual(fhir["id"], "REF-TEST-001")
        self.assertEqual(fhir["status"], "active")
        self.assertEqual(fhir["priority"], "stat")
        self.assertEqual(fhir["subject"]["display"], "Amina H. Yusop")
        self.assertEqual(fhir["subject"]["identifier"]["value"], "12-345678901-2")
        self.assertEqual(fhir["requester"]["display"], "Sulu Provincial Hospital")

    def test_offline_delta_sync_lifecycle(self):
        """Verify offline delta creation, local logging, and incremental cursor pull."""
        fhir_1 = models.build_fhir_service_request(
            "REF-DELTA-1", "Omar K. Hassan", None, "Basilan General Hospital",
            "ZCMC", "urgent", "Severe Dengue with Warning Signs", "IV fluid started."
        )

        res1 = models.upsert_referral(
            referral_id="REF-DELTA-1",
            patient_name="Omar K. Hassan",
            philhealth_id=None,
            origin_facility="Basilan General Hospital",
            destination_facility="ZCMC",
            urgency="urgent",
            diagnosis="Severe Dengue with Warning Signs",
            transit_status="in_maritime_transit",
            fhir_resource=fhir_1,
            client_id="boat-node-alpha",
            db_path=self.db_path
        )
        self.assertEqual(res1["status"], "persisted")

        # Pull deltas with cursor
        deltas = models.pull_deltas(since_timestamp=0.0, db_path=self.db_path)
        self.assertEqual(len(deltas), 1)
        self.assertEqual(deltas[0]["referral_id"], "REF-DELTA-1")
        self.assertEqual(deltas[0]["client_id"], "boat-node-alpha")
        self.assertEqual(deltas[0]["payload"]["resourceType"], "ServiceRequest")

        # Read all records
        all_records = models.get_all_referrals(db_path=self.db_path)
        self.assertEqual(len(all_records), 1)
        self.assertEqual(all_records[0]["transit_status"], "in_maritime_transit")

    def test_batch_store_and_forward_sync(self):
        """Verify multiple offline-collected edge referrals can be batch ingested cleanly."""
        batch_records = [
            ("ZCMC-SF-001", "Sharifa B. Datu", "Basilan General Hospital", "stat", "Postpartum hemorrhage"),
            ("ZCMC-SF-002", "Nur-Aina T. Alawi", "Sulu Provincial Hospital", "urgent", "Complicated appendicitis")
        ]
        
        for r_id, name, orig, prio, diag in batch_records:
            fhir = models.build_fhir_service_request(
                r_id, name, None, orig, "ZCMC", prio, diag, "Offline forward"
            )
            models.upsert_referral(
                referral_id=r_id,
                patient_name=name,
                philhealth_id=None,
                origin_facility=orig,
                destination_facility="ZCMC",
                urgency=prio,
                diagnosis=diag,
                transit_status="pending_transit",
                fhir_resource=fhir,
                client_id="island-terminal-01",
                db_path=self.db_path
            )

        records = models.get_all_referrals(db_path=self.db_path)
        self.assertGreaterEqual(len(records), 2)
        synced_ids = [r["id"] for r in records]
        self.assertIn("ZCMC-SF-001", synced_ids)
        self.assertIn("ZCMC-SF-002", synced_ids)

if __name__ == "__main__":
    unittest.main()
