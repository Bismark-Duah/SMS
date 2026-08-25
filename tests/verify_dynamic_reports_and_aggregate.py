import os
import sys

# Ensure backend path is available
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.database import engine, Base, SessionLocal
from backend.app.models import (
    School, Program, Subject, ClassSection, SchoolStage,
    ElectiveCombination, Student, Score, Semester, AcademicYear
)
from backend.app.services.grading import GradingService
from backend.app.services.reports import ReportService
from backend.app.services.subject_enrollment import SubjectEnrollmentService

def run_tests():
    print("================================================================")
    print("TEST SUITE: Phase 2 Dynamic Reports & Adaptive Best 6 Engine")
    print("================================================================")

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        # 1. Setup Academic Period
        ay = db.query(AcademicYear).filter(AcademicYear.label == "2025/2026").first()
        if not ay:
            ay = AcademicYear(label="2025/2026", is_current=True)
            db.add(ay)
            db.commit()
            db.refresh(ay)

        sem = db.query(Semester).filter(Semester.name == "Semester 1", Semester.academic_year_id == ay.id).first()
        if not sem:
            sem = Semester(name="Semester 1", academic_year_id=ay.id, is_current=True)
            db.add(sem)
            db.commit()
            db.refresh(sem)

        # 2. Setup Subjects
        subjects_data = [
            ("English Language", "ENG", True),
            ("Core Mathematics", "CMATH", True),
            ("Social Studies", "SOC", True),
            ("Integrated Science", "INTSCI", True),
            ("Physics", "PHYS", False),
            ("Chemistry", "CHEM", False),
            ("Biology", "BIO", False),
            ("Elective Mathematics", "EMATH", False),
            ("Applied Electricity", "APPELEC", False),
            ("Literature in English", "LIT", False),
            ("Government", "GOV", False),
            ("History", "HIST", False),
            ("Economics", "ECON", False),
            ("French", "FREN", False),
        ]
        sub_map = {}
        for name, code, is_core in subjects_data:
            s = db.query(Subject).filter(Subject.name == name).first()
            if not s:
                s = Subject(name=name, code=code, is_core=is_core)
                db.add(s)
                db.commit()
                db.refresh(s)
            sub_map[name] = s

        # -------------------------------------------------------------
        # TEST CASE 1: STEM Pure Science Student (3 Cores + 5 Electives = 8 Subjects)
        # -------------------------------------------------------------
        stem_prog = db.query(Program).filter(Program.name == "JAK STEM Pure Science Track").first()
        if not stem_prog:
            stem_prog = Program(name="JAK STEM Pure Science Track", code="STEM-SCI")
            db.add(stem_prog)
            db.commit()
            db.refresh(stem_prog)

        # Configure 3 Track Cores (Excluding Integrated Science)
        stem_prog.core_subjects = [sub_map["English Language"], sub_map["Core Mathematics"], sub_map["Social Studies"]]
        db.commit()

        # Create STEM Student
        stem_student = db.query(Student).filter(Student.student_code == "STU-STEM-001").first()
        if not stem_student:
            stem_student = Student(
                student_code="STU-STEM-001",
                full_name="Kofi Owusu STEM",
                program_id=stem_prog.id,
                school_type="SHS"
            )
            db.add(stem_student)
            db.commit()
            db.refresh(stem_student)

        # Clear old scores
        db.query(Score).filter(Score.student_id == stem_student.id, Score.semester_id == sem.id).delete()
        db.commit()

        # Add 8 Subjects (3 Cores + 5 Electives)
        stem_scores_data = [
            # 3 Track Cores
            ("English Language", 85.0, "A1"),  # Point 1
            ("Core Mathematics", 82.0, "A1"),  # Point 1
            ("Social Studies", 74.0, "B2"),    # Point 2
            # 5 Electives
            ("Physics", 88.0, "A1"),           # Point 1
            ("Chemistry", 76.0, "B2"),         # Point 2
            ("Biology", 64.0, "B3"),           # Point 3
            ("Elective Mathematics", 85.0, "A1"), # Point 1
            ("Applied Electricity", 72.0, "B2"),  # Point 2
        ]
        created_stem_scores = []
        for sname, tot, grd in stem_scores_data:
            sc = Score(
                student_id=stem_student.id,
                subject_id=sub_map[sname].id,
                semester_id=sem.id,
                class_score=tot * 0.3,
                exam_score=tot * 0.7,
                total_score=tot,
                grade=grd,
                remark=GradingService.get_grade(tot)["remark"]
            )
            db.add(sc)
            created_stem_scores.append(sc)
        db.commit()

        # Test Adaptive Aggregate Breakdown for STEM Student
        stem_agg_breakdown = GradingService.calculate_shs_aggregate_breakdown(created_stem_scores, student=stem_student)
        stem_agg = stem_agg_breakdown["aggregate"]

        # Expected:
        # Top 3 Cores: English (1) + Core Maths (1) + Social Studies (2) = 4
        # Top 3 Electives: Physics (1) + Elective Maths (1) + Chemistry (2) = 4
        # Total Aggregate = 4 + 4 = 8
        print(f"[OK] STEM Student Best 6 Aggregate: {stem_agg}")
        print(f"   - Qualifying Cores: {[c['subject_name'] + ' (' + c['grade'] + ')' for c in stem_agg_breakdown['qualifying_cores']]}")
        print(f"   - Qualifying Electives: {[e['subject_name'] + ' (' + e['grade'] + ')' for e in stem_agg_breakdown['qualifying_electives']]}")

        assert stem_agg == 8, f"Expected STEM Aggregate 8, got {stem_agg}"
        assert len(stem_agg_breakdown["qualifying_cores"]) == 3
        assert len(stem_agg_breakdown["qualifying_electives"]) == 3

        # -------------------------------------------------------------
        # TEST CASE 2: Extended Arts Student (4 Cores + 6 Electives = 10 Subjects)
        # -------------------------------------------------------------
        arts_prog = db.query(Program).filter(Program.name == "Extended General Arts Track").first()
        if not arts_prog:
            arts_prog = Program(name="Extended General Arts Track", code="GART-EXT")
            db.add(arts_prog)
            db.commit()
            db.refresh(arts_prog)

        arts_prog.core_subjects = [
            sub_map["English Language"], sub_map["Core Mathematics"],
            sub_map["Integrated Science"], sub_map["Social Studies"]
        ]
        db.commit()

        arts_student = db.query(Student).filter(Student.student_code == "STU-ARTS-002").first()
        if not arts_student:
            arts_student = Student(
                student_code="STU-ARTS-002",
                full_name="Akua Agyemang Arts",
                program_id=arts_prog.id,
                school_type="SHS"
            )
            db.add(arts_student)
            db.commit()
            db.refresh(arts_student)

        db.query(Score).filter(Score.student_id == arts_student.id, Score.semester_id == sem.id).delete()
        db.commit()

        # Add 10 Subjects (4 Cores + 6 Electives)
        arts_scores_data = [
            # 4 Cores
            ("English Language", 84.0, "A1"),     # Point 1
            ("Core Mathematics", 72.0, "B2"),     # Point 2
            ("Integrated Science", 62.0, "B3"),   # Point 3 (Dropped from Best 3 cores!)
            ("Social Studies", 81.0, "A1"),       # Point 1
            # 6 Electives
            ("Literature in English", 86.0, "A1"), # Point 1
            ("Government", 82.0, "A1"),           # Point 1
            ("French", 88.0, "A1"),               # Point 1
            ("Economics", 74.0, "B2"),            # Point 2 (Dropped from Best 3 electives!)
            ("History", 71.0, "B2"),              # Point 2 (Dropped from Best 3 electives!)
            ("Biology", 60.0, "B3"),              # Point 3 (Dropped from Best 3 electives!)
        ]
        created_arts_scores = []
        for sname, tot, grd in arts_scores_data:
            sc = Score(
                student_id=arts_student.id,
                subject_id=sub_map[sname].id,
                semester_id=sem.id,
                class_score=tot * 0.3,
                exam_score=tot * 0.7,
                total_score=tot,
                grade=grd,
                remark=GradingService.get_grade(tot)["remark"]
            )
            db.add(sc)
            created_arts_scores.append(sc)
        db.commit()

        arts_agg_breakdown = GradingService.calculate_shs_aggregate_breakdown(created_arts_scores, student=arts_student)
        arts_agg = arts_agg_breakdown["aggregate"]

        # Expected:
        # Top 3 Cores: English (1) + Social Studies (1) + Core Maths (2) = 4
        # Top 3 Electives: Literature (1) + Government (1) + French (1) = 3
        # Total Aggregate = 4 + 3 = 7
        print(f"\n[OK] Extended Arts Student (10 Subjects) Best 6 Aggregate: {arts_agg}")
        print(f"   - Qualifying Cores: {[c['subject_name'] + ' (' + c['grade'] + ')' for c in arts_agg_breakdown['qualifying_cores']]}")
        print(f"   - Qualifying Electives: {[e['subject_name'] + ' (' + e['grade'] + ')' for e in arts_agg_breakdown['qualifying_electives']]}")

        assert arts_agg == 7, f"Expected Arts Aggregate 7, got {arts_agg}"
        assert len(arts_agg_breakdown["qualifying_cores"]) == 3
        assert len(arts_agg_breakdown["qualifying_electives"]) == 3

        # -------------------------------------------------------------
        # TEST CASE 3: Report Service JSON Data & PDF Generation (10 Subjects)
        # -------------------------------------------------------------
        report_json = ReportService.get_report_data(db, arts_student.id, sem.id)
        assert report_json is not None, "Report data should not be None"
        assert report_json["num_subjects"] == 10, f"Expected 10 subjects on report card, got {report_json['num_subjects']}"
        assert report_json["aggregate"] == 7, f"Report JSON aggregate should be 7, got {report_json['aggregate']}"
        assert report_json["aggregate_breakdown"] is not None
        print(f"\n[OK] Report Service JSON verified for 10-subject report card: {report_json['num_subjects']} subjects, Aggregate: {report_json['aggregate']}")

        # Test PDF Generation
        pdf_bytes = ReportService.generate_terminal_report(db, arts_student.id, sem.id)
        assert pdf_bytes is not None, "PDF generation should succeed"
        assert len(pdf_bytes) > 1000, f"PDF bytes should be substantial, got {len(pdf_bytes)} bytes"
        print(f"[OK] 10-Subject Terminal Report PDF generated successfully ({len(pdf_bytes)} bytes)")

        print("\n================================================================")
        print("SUCCESS: ALL PHASE 2 DYNAMIC REPORTS & BEST 6 TESTS PASSED 100%!")
        print("================================================================")

    finally:
        db.close()

if __name__ == "__main__":
    run_tests()
