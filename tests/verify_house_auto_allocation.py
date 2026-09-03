"""
verify_house_auto_allocation.py — Automated Verification for Auto House & Dorm Allocation
"""

import os
import sys
import uuid
import unittest
from datetime import datetime

# Setup path resolution
current_dir = os.path.dirname(os.path.abspath(__file__))
sms_root = os.path.abspath(os.path.join(current_dir, ".."))
backend_dir = os.path.join(sms_root, "backend")

if sms_root not in sys.path:
    sys.path.insert(0, sms_root)
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from backend.app.database import SessionLocal, engine, Base
from backend.app.models import Student, House, Dormitory, School
from backend.app.services.allocation import allocate_student_house_and_dorm, auto_allocate_all_unassigned


class TestHouseAutoAllocation(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)
        cls.db = SessionLocal()
        u_suffix = uuid.uuid4().hex[:6]

        # Setup test School
        cls.school = School(
            name=f"Alloc Academy {u_suffix}",
            code=f"ALC-{u_suffix}",
            school_mode="COMBINED"
        )
        cls.db.add(cls.school)
        cls.db.commit()
        cls.db.refresh(cls.school)

        # Setup test Houses (1 Male, 1 Female, 1 Co-ed)
        cls.house_male = House(name=f"Alloc House Male {u_suffix}", gender="Boys", school_id=cls.school.id)
        cls.house_female = House(name=f"Alloc House Female {u_suffix}", gender="Girls", school_id=cls.school.id)
        cls.house_coed = House(name=f"Alloc House Coed {u_suffix}", gender="Both", school_id=cls.school.id)
        cls.db.add_all([cls.house_male, cls.house_female, cls.house_coed])
        cls.db.commit()

        # Setup test Dormitories
        cls.dorm_male = Dormitory(name=f"Alloc Dorm Male {u_suffix}", house_id=cls.house_male.id)
        cls.dorm_female = Dormitory(name=f"Alloc Dorm Female {u_suffix}", house_id=cls.house_female.id)
        cls.db.add_all([cls.dorm_male, cls.dorm_female])
        cls.db.commit()

    @classmethod
    def tearDownClass(cls):
        cls.db.rollback()
        cls.db.close()

    def test_01_male_boarder_auto_allocation(self):
        u = uuid.uuid4().hex[:6]
        st = Student(
            student_code=f"ALLOC-M-{u}",
            full_name="Kwame Auto Test",
            gender="Male",
            residential_status="Boarding",
            school_id=self.school.id
        )
        self.db.add(st)
        self.db.commit()

        res = allocate_student_house_and_dorm(self.db, st)
        self.assertIsNotNone(st.house_id)
        self.assertIsNotNone(st.dormitory_id)
        self.assertEqual(st.dormitory_id, self.dorm_male.id)

    def test_02_female_boarder_auto_allocation(self):
        u = uuid.uuid4().hex[:6]
        st = Student(
            student_code=f"ALLOC-F-{u}",
            full_name="Ama Auto Test",
            gender="Female",
            residential_status="Boarding",
            school_id=self.school.id
        )
        self.db.add(st)
        self.db.commit()

        res = allocate_student_house_and_dorm(self.db, st)
        self.assertIsNotNone(st.house_id)
        self.assertIsNotNone(st.dormitory_id)
        self.assertEqual(st.dormitory_id, self.dorm_female.id)

    def test_03_day_student_auto_allocation(self):
        u = uuid.uuid4().hex[:6]
        st = Student(
            student_code=f"ALLOC-D-{u}",
            full_name="Kofi Day Student",
            gender="Male",
            residential_status="Day",
            school_id=self.school.id
        )
        self.db.add(st)
        self.db.commit()

        res = allocate_student_house_and_dorm(self.db, st)
        self.assertIsNotNone(st.house_id)
        # Day students should NOT be assigned to a boarding dormitory
        self.assertIsNone(st.dormitory_id)

    def test_04_bulk_auto_allocation(self):
        # Create 5 unassigned boarders
        students = []
        for i in range(5):
            u = uuid.uuid4().hex[:6]
            st = Student(
                student_code=f"ALLOC-BULK-{u}-{i}",
                full_name=f"Bulk Candidate {i}",
                gender="Male" if i % 2 == 0 else "Female",
                residential_status="Boarding",
                school_id=self.school.id
            )
            students.append(st)
        self.db.add_all(students)
        self.db.commit()

        stats = auto_allocate_all_unassigned(self.db)
        self.assertGreaterEqual(stats["allocated_count"], 5)


if __name__ == "__main__":
    unittest.main()
