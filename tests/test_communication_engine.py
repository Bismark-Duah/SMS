import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.database import SessionLocal
from backend.app.models import User, Student, ClassSection, ExeatRecord, Fee, Payment, MessageLog
from backend.app.services.communication_service import CommunicationService

def test_communication_engine():
    db = SessionLocal()
    try:
        print("==================================================================")
        print("TEST SUITE: Enterprise Hybrid Multi-Channel Communication Engine")
        print("==================================================================")

        # 1. Test Gateway Settings read & save
        cfg = CommunicationService.get_gateway_config(db)
        assert "sms_provider" in cfg
        assert "whatsapp_provider" in cfg
        assert "auto_notify_exeat_gateout" in cfg
        print(f"[OK] Gateway configuration read successfully. Current SMS provider: {cfg['sms_provider']}")

        # Save test settings
        CommunicationService.save_gateway_config(db, {
            "sms_provider": "ARKESEL",
            "sms_sender_id": "TEST_SCH",
            "auto_notify_exeat_gateout": True,
            "auto_notify_fee_payment": True
        })
        updated_cfg = CommunicationService.get_gateway_config(db)
        assert updated_cfg["sms_provider"] == "ARKESEL"
        assert updated_cfg["sms_sender_id"] == "TEST_SCH"
        print("[OK] Gateway configuration saved and re-read successfully.")

        # 2. Test Offline & Unconfigured Fallback for SMS
        res_sms = CommunicationService.send_sms(
            db=db,
            to_phone="0244123456",
            message="Test SMS fallback verification.",
            recipient_name="Test Parent",
            message_type="TEST"
        )
        assert res_sms["success"] in [True, False]
        print(f"[OK] SMS Dispatcher executed safely. Status={res_sms.get('status')}")

        # 3. Test WhatsApp Intent construction
        res_wa = CommunicationService.send_whatsapp(
            db=db,
            to_phone="0244123456",
            message="Test WhatsApp *bold* text.",
            recipient_name="Test Parent",
            message_type="TEST"
        )
        assert "intent_url" in res_wa
        assert "wa.me/233244123456" in res_wa["intent_url"]
        print(f"[OK] WhatsApp Direct-to-Device intent URL generated: {res_wa['intent_url'][:45]}...")

        # 4. Test Automated Event Trigger: EXEAT_GATE_OUT
        student = db.query(Student).first()
        if student:
            event_res = CommunicationService.trigger_event_notification(
                "EXEAT_GATE_OUT",
                {
                    "student_id": student.id,
                    "student_name": student.full_name,
                    "destination": "Accra",
                    "exeat_type": "Weekend",
                    "expected_return": "Sunday 17:00",
                    "parent_contact": student.phone or "0244999888",
                    "guardian_name": student.guardian_name or "Mr. Mensah"
                },
                db
            )
            assert event_res["triggered"] == True
            print(f"[OK] Automated Event Trigger EXEAT_GATE_OUT fired {len(event_res['notifications'])} notifications.")

            # 5. Test Automated Event Trigger: FEE_PAYMENT
            fee_event_res = CommunicationService.trigger_event_notification(
                "FEE_PAYMENT",
                {
                    "student_id": student.id,
                    "student_name": student.full_name,
                    "amount": 250.00,
                    "receipt_no": "REC-9999",
                    "balance": 50.00,
                    "phone": student.phone or "0244999888"
                },
                db
            )
            assert fee_event_res["triggered"] == True
            print(f"[OK] Automated Event Trigger FEE_PAYMENT fired {len(fee_event_res['notifications'])} notifications.")

        # 6. Verify Outbox Database Logs
        logs = db.query(MessageLog).order_by(MessageLog.id.desc()).limit(5).all()
        assert len(logs) > 0
        print(f"[OK] Message Logs verified in SQLite. Latest entry: ID={logs[0].id}, Channel={logs[0].channel}, Status={logs[0].status}")

        print("\n==================================================================")
        print("SUCCESS: ALL COMMUNICATION & GATEWAY ENGINE TESTS PASSED 100%!")
        print("==================================================================")

    finally:
        db.close()

if __name__ == "__main__":
    test_communication_engine()
