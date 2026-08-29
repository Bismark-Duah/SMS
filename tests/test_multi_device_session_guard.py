import unittest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.app.models import Base, User, Role, UserDeviceSession
from backend.app.middleware.device_session_guard import (
    register_device_session,
    is_session_active,
    revoke_all_other_sessions
)

class TestMultiDeviceSessionGuard(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=self.engine)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()

        teacher_role = Role(id=1, name="teacher")
        parent_role = Role(id=2, name="parent")
        self.session.add_all([teacher_role, parent_role])

        teacher = User(
            id=10,
            username="teacher_kwame",
            email="kwame@school.edu.gh",
            password_hash="mock_hashed_pw",
            is_active=True
        )
        teacher.roles = [teacher_role]
        
        parent = User(
            id=20,
            username="parent_akosua",
            email="akosua@parent.local",
            password_hash="mock_hashed_pw",
            is_active=True
        )
        parent.roles = [parent_role]

        self.session.add_all([teacher, parent])
        self.session.commit()

    def tearDown(self):
        self.session.close()

    def test_staff_single_active_session_enforcement(self):
        """Verifies that staff login terminates previous sessions (1 active device policy)."""
        token1 = "jwt_token_device_1"
        token2 = "jwt_token_device_2"

        # Login 1 on Laptop
        sess1 = register_device_session(
            user_id=10,
            user_role="teacher",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0",
            client_ip="192.168.1.50",
            token=token1,
            db=self.session
        )
        self.assertTrue(sess1.is_active)
        self.assertTrue(is_session_active(token1, 10, self.session))

        # Login 2 on Phone
        sess2 = register_device_session(
            user_id=10,
            user_role="teacher",
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) Safari/604.1",
            client_ip="10.0.0.12",
            token=token2,
            db=self.session
        )
        self.assertTrue(sess2.is_active)
        self.assertTrue(is_session_active(token2, 10, self.session))

        # First session on laptop MUST now be deactivated
        self.assertFalse(is_session_active(token1, 10, self.session))

    def test_parent_multi_device_retention(self):
        """Verifies that parents/students are allowed up to 3 concurrent active devices."""
        t1 = "parent_token_pc"
        t2 = "parent_token_phone"

        register_device_session(user_id=20, user_role="parent", user_agent="Windows Chrome", client_ip="1.1.1.1", token=t1, db=self.session)
        register_device_session(user_id=20, user_role="parent", user_agent="Android Chrome", client_ip="1.1.1.2", token=t2, db=self.session)

        # Both should remain active
        self.assertTrue(is_session_active(t1, 20, self.session))
        self.assertTrue(is_session_active(t2, 20, self.session))

    def test_revoke_all_other_sessions(self):
        """Verifies user-initiated termination of all other sessions."""
        t1 = "token_a"
        t2 = "token_b"
        t3 = "token_c"

        register_device_session(user_id=20, user_role="parent", user_agent="Device A", client_ip="1.1.1.1", token=t1, db=self.session)
        register_device_session(user_id=20, user_role="parent", user_agent="Device B", client_ip="1.1.1.2", token=t2, db=self.session)
        register_device_session(user_id=20, user_role="parent", user_agent="Device C", client_ip="1.1.1.3", token=t3, db=self.session)

        revoked = revoke_all_other_sessions(user_id=20, current_token=t3, db=self.session)
        self.assertEqual(revoked, 2)
        self.assertFalse(is_session_active(t1, 20, self.session))
        self.assertFalse(is_session_active(t2, 20, self.session))
        self.assertTrue(is_session_active(t3, 20, self.session))

if __name__ == "__main__":
    unittest.main()
