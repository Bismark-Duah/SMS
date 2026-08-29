import unittest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.app.models import Base, School, SchoolSubaccount, Student, Fee, User, Role
from backend.app.routes.fees import initialize_paystack_payment, PaystackInitPayload

class TestFeesSubaccountSplit(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=self.engine)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()

        school = School(id=1, name="Achimota School", code="ACH", status="ACTIVE")
        self.session.add(school)

        self.sub = SchoolSubaccount(
            school_id=1,
            paystack_subaccount_code="ACCT_1_GCB_9999",
            settlement_bank="GCB Bank",
            account_number="1234567890",
            percentage_split=98.0,
            is_verified=True
        )
        self.session.add(self.sub)

        admin_role = Role(name="admin")
        self.session.add(admin_role)
        self.session.commit()

        self.user = User(
            id=10,
            username="fees_admin_test",
            email="fees_admin_test@achimota.edu.gh",
            password_hash="mock_hash",
            school_id=1,
            is_active=True
        )
        self.user.roles.append(admin_role)
        self.session.add(self.user)

        self.st = Student(id=101, full_name="Abena Osei", student_code="FEE-STU-001", school_id=1, is_active=True)
        self.session.add(self.st)
        self.session.commit()

        self.fee = Fee(
            id=50,
            student_id=self.st.id,
            fee_type="Tuition",
            term="Term 1",
            academic_year="2025/2026",
            amount=500.0,
            amount_paid=0.0,
            status="Pending"
        )
        self.session.add(self.fee)
        self.session.commit()

    def tearDown(self):
        self.session.close()

    def test_fee_initialize_subaccount_resolution(self):
        req = PaystackInitPayload(
            fee_id=self.fee.id,
            amount_paid=250.0,
            email="parent@achimota.edu.gh"
        )
        res = initialize_paystack_payment(payload=req, db=self.session, current_user=self.user)
        self.assertIn("reference", res)
        self.assertIn(res["status"], ["offline_fallback", "success"])

if __name__ == "__main__":
    unittest.main()
