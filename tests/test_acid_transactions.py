import unittest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.app.models import Base, School, Voucher, VoucherOrder
from backend.app.services.payment_orchestrator import fulfill_voucher_order_atomic

class TestAcidTransactions(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=self.engine)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()

        # Seed test school
        school = School(id=1, name="Achimota School", code="ACHIMOTA")
        self.session.add(school)

        # Seed pre-generated available voucher
        voucher = Voucher(
            id=10,
            serial_code="ACH-2026-0001",
            pin_code="123456",
            school_id=1,
            status="AVAILABLE"
        )
        self.session.add(voucher)

        # Seed pending order
        order = VoucherOrder(
            id=100,
            order_reference="VCH-2026-TEST01",
            school_id=1,
            applicant_name="Kwame Mensah",
            applicant_phone="0244111222",
            applicant_email="kwame@test.local",
            amount=100.0,
            payment_gateway="PAYSTACK",
            status="PENDING"
        )
        self.session.add(order)
        self.session.commit()

    def tearDown(self):
        self.session.close()

    def test_fulfill_voucher_order_atomic_success(self):
        """Verifies atomic voucher order fulfillment, status transitions, and voucher linking."""
        res = fulfill_voucher_order_atomic("VCH-2026-TEST01", "gw_test_12345", self.session)
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["serial_number"], "ACH-2026-0001")
        self.assertEqual(res["pin"], "123456")

        # Verify database state
        order = self.session.query(VoucherOrder).filter(VoucherOrder.order_reference == "VCH-2026-TEST01").first()
        self.assertEqual(order.status, "DELIVERED")
        self.assertEqual(order.voucher_id, 10)
        self.assertEqual(order.gateway_reference, "gw_test_12345")

        voucher = self.session.query(Voucher).filter(Voucher.id == 10).first()
        self.assertEqual(voucher.status, "PURCHASED")
        self.assertEqual(voucher.purchased_by_phone, "0244111222")

    def test_fulfill_voucher_order_idempotent(self):
        """Verifies that duplicate webhook fulfillment triggers do not re-assign or double-charge."""
        res1 = fulfill_voucher_order_atomic("VCH-2026-TEST01", "gw_test_1", self.session)
        self.assertEqual(res1["status"], "success")

        res2 = fulfill_voucher_order_atomic("VCH-2026-TEST01", "gw_test_2", self.session)
        self.assertEqual(res2["status"], "success")
        self.assertIn("already fulfilled", res2["message"])

    def test_fulfill_voucher_order_auto_generate_on_empty_pool(self):
        """Verifies that if pre-generated vouchers are exhausted, a new voucher is atomically generated."""
        self.session.query(Voucher).filter(Voucher.id == 10).update({"status": "USED"})
        
        new_order = VoucherOrder(
            id=101,
            order_reference="VCH-2026-TEST02",
            school_id=1,
            applicant_name="Ama Serwaa",
            applicant_phone="0244999888",
            amount=100.0,
            payment_gateway="PAYSTACK",
            status="PENDING"
        )
        self.session.add(new_order)
        self.session.commit()

        res = fulfill_voucher_order_atomic("VCH-2026-TEST02", "gw_test_new", self.session)
        self.assertEqual(res["status"], "success")
        self.assertTrue(res["serial_number"].startswith("ADM-2026-"))
        self.assertEqual(len(res["pin"]), 6)

if __name__ == "__main__":
    unittest.main()
