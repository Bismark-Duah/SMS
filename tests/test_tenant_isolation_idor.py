import unittest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.app.models import Base, School, Student, User, Role, Notification
from backend.app.routes.students import get_student, link_parent
from backend.app.routes.notifications import broadcast_notification, NotificationCreate
from fastapi import HTTPException

class TestTenantIsolationIDOR(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=self.engine)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()

        s1 = School(id=1, name="Achimota School", code="ACH", status="ACTIVE")
        s2 = School(id=2, name="Presec Legon", code="PRESEC", status="ACTIVE")
        self.session.add_all([s1, s2])

        admin_role = Role(name="admin")
        self.session.add(admin_role)
        self.session.commit()

        self.u1 = User(id=10, username="admin_ach", email="admin_ach@achimota.edu.gh", password_hash="mock_hash", school_id=1, is_active=True)
        self.u1.roles.append(admin_role)

        self.u2 = User(id=20, username="admin_presec", email="admin_presec@presec.edu.gh", password_hash="mock_hash", school_id=2, is_active=True)
        self.u2.roles.append(admin_role)

        self.st1 = Student(id=101, full_name="Kwame Mensah", student_code="ACH-001", school_id=1, is_active=True)
        self.st2 = Student(id=202, full_name="Kofi Annan", student_code="PRE-001", school_id=2, is_active=True)

        self.session.add_all([self.u1, self.u2, self.st1, self.st2])
        self.session.commit()

    def tearDown(self):
        self.session.close()

    def test_cross_tenant_student_read_raises_404(self):
        # Admin 1 queries Student 2 (School 2)
        with self.assertRaises(HTTPException) as ctx:
            get_student(student_id=self.st2.id, db=self.session, current_user=self.u1)
        self.assertEqual(ctx.exception.status_code, 404)

    def test_same_tenant_student_read_succeeds(self):
        # Admin 1 queries Student 1 (School 1)
        res = get_student(student_id=self.st1.id, db=self.session, current_user=self.u1)
        self.assertEqual(res["full_name"], "Kwame Mensah")
        self.assertEqual(res["school_id"], 1)

    def test_cross_tenant_parent_link_raises_404(self):
        # Admin 1 attempts to link parent to Student 2 (School 2)
        with self.assertRaises(HTTPException) as ctx:
            link_parent(student_id=self.st2.id, payload={"parent_id": 5}, db=self.session, current_user=self.u1)
        self.assertEqual(ctx.exception.status_code, 404)

    def test_broadcast_notification_scoped_to_school(self):
        payload = NotificationCreate(message="All students assembly at 8am", type="General")
        res = broadcast_notification(payload=payload, db=self.session, current_user=self.u1)
        
        self.assertEqual(res["count"], 1)
        notifs = self.session.query(Notification).all()
        self.assertEqual(len(notifs), 1)
        self.assertEqual(notifs[0].student_id, self.st1.id)

if __name__ == "__main__":
    unittest.main()
