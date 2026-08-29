import unittest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.app.models import Base, School, TenantSmsConfig, User, Role
from backend.app.routes.messaging import get_sms_balance_and_telemetry
from backend.app.routes.settings import save_school_sms_config
from backend.app.routes.super_admin import list_all_tenant_sms_configs, approve_tenant_sender_id, reject_tenant_sender_id

class TestSmsBalanceAndApproval(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=self.engine)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()

        school = School(id=1, name="Achimota School", code="ACH", status="ACTIVE")
        self.session.add(school)

        admin_role = Role(name="admin")
        super_role = Role(name="super_admin")
        self.session.add_all([admin_role, super_role])
        self.session.commit()

        self.admin_user = User(id=1, username="admin_ach", email="admin_ach@achimota.edu.gh", password_hash="mock_hash", school_id=1, is_active=True)
        self.admin_user.roles.append(admin_role)

        self.super_user = User(id=2, username="superadmin", email="superadmin@edumanage.gh", password_hash="mock_hash", school_id=1, is_active=True)
        self.super_user.roles.append(super_role)

        self.session.add_all([self.admin_user, self.super_user])
        self.session.commit()

    def tearDown(self):
        self.session.close()

    def test_messaging_balance_endpoint(self):
        res = get_sms_balance_and_telemetry(db=self.session, current_user=self.admin_user)
        self.assertEqual(res["school_id"], 1)
        self.assertEqual(res["provider"], "HUBTEL")
        self.assertGreaterEqual(res["sms_units"], 0)
        self.assertIn("delivery_rate", res)

    def test_sender_id_submission_and_superadmin_approval_lifecycle(self):
        # 1. Institutional Admin submits custom Sender ID -> enters PENDING_APPROVAL
        res = save_school_sms_config(
            data={"sender_id": "ACHIMOTA"},
            db=self.session,
            current_user=self.admin_user
        )
        self.assertEqual(res["sender_id"], "ACHIMOTA")
        self.assertEqual(res["approval_status"], "PENDING_APPROVAL")

        # 2. Super-Admin views pending configs
        configs = list_all_tenant_sms_configs(db=self.session, current_user=self.super_user)
        self.assertTrue(any(c["sender_id"] == "ACHIMOTA" and c["status"] == "PENDING_APPROVAL" for c in configs))

        # 3. Super-Admin approves Sender ID
        appr = approve_tenant_sender_id(school_id=1, db=self.session, current_user=self.super_user)
        self.assertEqual(appr["status"], "ACTIVE")

        # Verify DB updated
        cfg = self.session.query(TenantSmsConfig).filter(TenantSmsConfig.school_id == 1).first()
        self.assertEqual(cfg.status, "ACTIVE")

        # 4. Super-Admin rejects Sender ID
        rej = reject_tenant_sender_id(school_id=1, db=self.session, current_user=self.super_user)
        self.assertEqual(rej["status"], "REJECTED")
        self.session.refresh(cfg)
        self.assertEqual(cfg.status, "REJECTED")

if __name__ == "__main__":
    unittest.main()
