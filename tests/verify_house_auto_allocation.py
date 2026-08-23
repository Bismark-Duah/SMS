"""
verify_house_auto_allocation.py — Automated Verification for Auto House & Dorm Allocation
"""

import os
import sys
import unittest
from datetime import datetime

# Set path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "backend")))

from app.database import SessionLocal, engine, Base
from app.models import Student, House, Dormitory, ClassSection, Program
from app.services.allocation import allocate_student_house_and_dorm, auto_allocate_all_unassigned


class TestHouseAutoAllocation(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)
        cls.db = SessionLocal()

        # Clean existing test objects if necessary
        cls.db.query(Student).filter(Student.student_code.like("ALLOC-TEST-%")).delete(synchronize_session=False)
        cls.db.query(Dormitory).filter(Dormitory.name.like("Alloc Dorm %")).delete(synchronize_session=False)
        cls.db.query(House).filter(House.name.like("Alloc House %")).delete(synchronize_session=False)
        cls.db.commit()

        # Setup test Houses (1 Male, 1 Female, 1 Co-ed)
        cls.house_male = House(name="Alloc House Male", gender="Boys")
        cls.house_female = House(name="Alloc House Female", gender="Girls")
        cls.house_coed = House(name="Alloc House Coed", gender="Both")
        cls.db.add_all([cls.house_male, cls.house_female, cls.house_coed])
        cls.db.commit()

        # Setup test Dormitories
        cls.dorm_male = Dormitory(name="Alloc Dorm Male 1", house_id=cls.house_male.id)
        cls.dorm_female = Dormitory(name="Alloc Dorm Female 1", house_id=cls.house_female.id)
        cls.db.add_all([cls.dorm_male, cls.dorm_female])
        cls.db.commit()

    @classmethod
    def tearDownClass(cls):
        cls.db.query(Student).filter(Student.student_code.like("ALLOC-TEST-%")).delete(synchronize_session=False)
        cls.db.query(Dormitory).filter(Dormitory.name.like("Alloc Dorm %")).delete(synchronize_session=False)
        cls.db.query(House).filter(House.name.like("Alloc House %")).delete(synchronize_session=False)
        cls.db.commit()
        cls.db.close()

    def test_01_male_boarder_auto_allocation(self):
        st = Student(
            student_code="ALLOC-TEST-001",
            full_name="Kwame Auto Test",
            gender="Male",
            residential_status="Boarding"
        )
        self.db.add(st)
        self.db.commit()

        res = allocate_student_house_and_dorm(self.db, st)
        self.assertIsNotNone(st.house_id)
        self.assertIsNotNone(st.dormitory_id)
        self.assertEqual(st.dormitory_id, self.dorm_male.id)

    def test_02_female_boarder_auto_allocation(self):
        st = Student(
            student_code="ALLOC-TEST-002",
            full_name="Ama Auto Test",
            gender="Female",
            residential_status="Boarding"
        )
        self.db.add(st)
        self.db.commit()

        res = allocate_student_house_and_dorm(self.db, st)
        self.assertIsNotNone(st.house_id)
        self.assertIsNotNone(st.dormitory_id)
        self.assertEqual(st.dormitory_id, self.dorm_female.id)

    def test_03_day_student_auto_allocation(self):
        st = Student(
            student_code="ALLOC-TEST-003",
            full_name="Kofi Day Student",
            gender="Male",
            residential_status="Day"
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
            st = Student(
                student_code=f"ALLOC-TEST-BULK-{i}",
                full_name=f"Bulk Candidate {i}",
                gender="Male" if i % 2 == 0 else "Female",
                residential_status="Boarding"
            )
            students.append(st)
        self.db.add_all(students)
        self.db.commit()

        stats = auto_allocate_all_unassigned(self.db)
        self.assertGreaterEqual(stats["allocated_count"], 5)


if __name__ == "__main__":
    unittest.main()
