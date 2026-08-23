from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Table
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .database import Base

# Many-to-many relationship table for Users and Roles
user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id"), primary_key=True),
    Column("role_id", Integer, ForeignKey("roles.id"), primary_key=True),
)

# Many-to-many relationship table for Class Sections and Subjects
class_section_subjects = Table(
    "class_section_subjects",
    Base.metadata,
    Column("class_section_id", Integer, ForeignKey("class_sections.id", ondelete="CASCADE"), primary_key=True),
    Column("subject_id", Integer, ForeignKey("subjects.id", ondelete="CASCADE"), primary_key=True),
)

# Many-to-many relationship table for Programs and Subjects
program_subjects = Table(
    "program_subjects",
    Base.metadata,
    Column("program_id", Integer, ForeignKey("programs.id", ondelete="CASCADE"), primary_key=True),
    Column("subject_id", Integer, ForeignKey("subjects.id", ondelete="CASCADE"), primary_key=True),
)

# Many-to-many relationship table for Departments and Subjects
department_subjects = Table(
    "department_subjects",
    Base.metadata,
    Column("department_id", Integer, ForeignKey("departments.id", ondelete="CASCADE"), primary_key=True),
    Column("subject_id", Integer, ForeignKey("subjects.id", ondelete="CASCADE"), primary_key=True),
)

class School(Base):
    __tablename__ = "schools"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, index=True)
    code = Column(String, unique=True, index=True, nullable=False)
    school_mode = Column(String, default="COMBINED")  # SHS_ONLY, BASIC_ONLY, COMBINED
    boarding_type = Column(String, default="BOARDING_AND_DAY")
    status = Column(String, default="ACTIVE")  # ACTIVE, SUSPENDED
    address = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    email = Column(String, nullable=True)
    logo_url = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    users = relationship("User", back_populates="school", cascade="all, delete-orphan")
    students = relationship("Student", back_populates="school", cascade="all, delete-orphan")

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    gender = Column(String, nullable=True)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=True)
    school_id = Column(Integer, ForeignKey("schools.id", ondelete="CASCADE"), nullable=True, default=1)

    school = relationship("School", back_populates="users")
    roles = relationship("Role", secondary=user_roles, back_populates="users")
    teacher_assignments = relationship("TeacherAssignment", back_populates="teacher")
    children = relationship("Student", back_populates="parent")
    department = relationship("Department", foreign_keys=[department_id])

class Role(Base):
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    
    users = relationship("User", secondary=user_roles, back_populates="roles")

class AcademicYear(Base):
    __tablename__ = "academic_years"

    id = Column(Integer, primary_key=True, index=True)
    label = Column(String, unique=True, index=True, nullable=False)
    is_current = Column(Boolean, default=False)
    
    semesters = relationship("Semester", back_populates="academic_year")

class Semester(Base):
    __tablename__ = "semesters"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    academic_year_id = Column(Integer, ForeignKey("academic_years.id"), nullable=False)
    is_current = Column(Boolean, default=False)
    start_date = Column(DateTime, nullable=True)
    end_date = Column(DateTime, nullable=True)
    
    academic_year = relationship("AcademicYear", back_populates="semesters")
    scores = relationship("Score", back_populates="semester")

class SchoolStage(Base):
    __tablename__ = "school_stages"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    school_type = Column(String, nullable=False)
    
    class_sections = relationship("ClassSection", back_populates="stage")

class ClassSection(Base):
    __tablename__ = "class_sections"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)
    stage_id = Column(Integer, ForeignKey("school_stages.id"), nullable=False)
    program_id = Column(Integer, ForeignKey("programs.id"), nullable=True)
    form_master_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    stage = relationship("SchoolStage", back_populates="class_sections")
    program = relationship("Program", back_populates="class_sections")
    students = relationship("Student", back_populates="class_section")
    teacher_assignments = relationship("TeacherAssignment", back_populates="class_section")
    subjects = relationship("Subject", secondary=class_section_subjects, back_populates="class_sections")
    form_master = relationship("User", foreign_keys=[form_master_id])

class Program(Base):
    __tablename__ = "programs"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    code = Column(String, nullable=True)
    school_id = Column(Integer, ForeignKey("schools.id", ondelete="CASCADE"), nullable=True)

    school = relationship("School")
    class_sections = relationship("ClassSection", back_populates="program")
    students = relationship("Student", back_populates="program")
    subjects = relationship("Subject", secondary=program_subjects, back_populates="programs")

class Department(Base):
    __tablename__ = "departments"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    code = Column(String, unique=True, index=True, nullable=False)
    hod_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    school_id = Column(Integer, ForeignKey("schools.id", ondelete="CASCADE"), nullable=True)

    school = relationship("School")
    hod = relationship("User", foreign_keys=[hod_id])
    subjects = relationship("Subject", secondary=department_subjects)

class House(Base):
    __tablename__ = "houses"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    gender = Column(String, nullable=False)
    school_id = Column(Integer, ForeignKey("schools.id", ondelete="CASCADE"), nullable=True)
    senior_in_charge_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    house_master_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    assistant_house_master_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    senior_in_charge_girls_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    house_master_girls_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    assistant_house_master_girls_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    school = relationship("School")
    senior_in_charge = relationship("User", foreign_keys=[senior_in_charge_id])
    house_master = relationship("User", foreign_keys=[house_master_id])
    assistant_house_master = relationship("User", foreign_keys=[assistant_house_master_id])
    senior_in_charge_girls = relationship("User", foreign_keys=[senior_in_charge_girls_id])
    house_master_girls = relationship("User", foreign_keys=[house_master_girls_id])
    assistant_house_master_girls = relationship("User", foreign_keys=[assistant_house_master_girls_id])
    dormitories = relationship("Dormitory", back_populates="house", cascade="all, delete-orphan")
    students = relationship("Student", back_populates="house")

class Dormitory(Base):
    __tablename__ = "dormitories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    capacity = Column(Integer, default=30)
    house_id = Column(Integer, ForeignKey("houses.id", ondelete="CASCADE"), nullable=False)
    housemaster_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    house = relationship("House", back_populates="dormitories")
    housemaster = relationship("User", foreign_keys=[housemaster_id])
    students = relationship("Student", back_populates="dormitory")

class Subject(Base):
    __tablename__ = "subjects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    code = Column(String, unique=True, index=True)
    is_core = Column(Boolean, default=True)
    category = Column(String, default="Core")  # Core, Elective
    group_code = Column(String, nullable=True)  # Group A, Group B, Group C, Group D
    assessment_type = Column(String, default="External_WASSCE")  # External_WASSCE, Internal_Transcript, Basic_Cumulative
    school_level = Column(String, default="SHS")  # Basic, SHS, STEM
    
    scores = relationship("Score", back_populates="subject")
    class_sections = relationship("ClassSection", secondary=class_section_subjects, back_populates="subjects")
    programs = relationship("Program", secondary=program_subjects, back_populates="subjects")

class StudentGuardian(Base):
    __tablename__ = "student_guardians"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    guardian_name = Column(String, nullable=False)
    relationship_type = Column(String, nullable=True, default="Parent")
    primary_phone = Column(String, nullable=False)
    alternative_phone = Column(String, nullable=True)
    occupation = Column(String, nullable=True)
    residential_address = Column(String, nullable=True)

    student = relationship("Student", back_populates="guardians")

class StudentHealth(Base):
    __tablename__ = "student_health"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    blood_group = Column(String, nullable=True)
    allergies = Column(String, nullable=True)
    chronic_conditions = Column(String, nullable=True)
    doctor_clearance_status = Column(Boolean, default=False)
    emergency_contact = Column(String, nullable=True)
    height_cm = Column(Float, nullable=True)
    weight_kg = Column(Float, nullable=True)
    pe_limitations = Column(String, nullable=True)

    student = relationship("Student", back_populates="health_profile")

class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, index=True)
    student_code = Column(String, unique=True, index=True, nullable=False)
    full_name = Column(String, nullable=False)
    first_name = Column(String, nullable=True)
    middle_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    bece_index_number = Column(String(12), unique=True, index=True, nullable=True)
    enrolment_code = Column(String(15), unique=True, index=True, nullable=True)
    bece_raw_score = Column(Integer, nullable=True)
    bece_aggregate = Column(Integer, nullable=True)
    jhs_attended = Column(String, nullable=True)
    residential_status = Column(String, default="B")  # B: Boarding, D: Day
    enrollment_status = Column(String, default="Fully Registered")  # PLACED, FORM_COMPLETED, FULLY_REGISTERED
    elective_combination = Column(String, nullable=True)  # Chosen elective combination code/string
    
    class_name = Column(String, nullable=True, default="")
    school_type = Column(String, nullable=True, default="Basic")
    academic_year = Column(String, nullable=True, default="2025/2026")
    class_section_id = Column(Integer, ForeignKey("class_sections.id"))
    program_id = Column(Integer, ForeignKey("programs.id"), nullable=True)
    parent_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    form = Column(Integer, nullable=True)
    gender = Column(String, nullable=True)
    date_of_birth = Column(DateTime, nullable=True)
    address = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    guardian_name = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    status = Column(String, default="ACTIVE", server_default="ACTIVE")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    house_id = Column(Integer, ForeignKey("houses.id"), nullable=True)
    dormitory_id = Column(Integer, ForeignKey("dormitories.id"), nullable=True)
    school_id = Column(Integer, ForeignKey("schools.id", ondelete="CASCADE"), nullable=True, default=1)

    school = relationship("School", back_populates="students")

    # Cumulative Record Fields (Basic School continuous tracking)
    family_background_notes = Column(String, nullable=True)
    socio_economic_notes = Column(String, nullable=True)
    personality_traits = Column(String, nullable=True)
    leadership_notes = Column(String, nullable=True)
    teacher_observations = Column(String, nullable=True)
    co_curricular_activities = Column(String, nullable=True)
    hobbies_talents = Column(String, nullable=True)
    awards = Column(String, nullable=True)

    class_section = relationship("ClassSection", back_populates="students")
    program = relationship("Program", back_populates="students")
    parent = relationship("User", back_populates="children")
    scores = relationship("Score", back_populates="student")
    attendance = relationship("Attendance", back_populates="student")
    notifications = relationship("Notification", back_populates="student")
    fees = relationship("Fee", back_populates="student")
    house = relationship("House", back_populates="students")
    dormitory = relationship("Dormitory", back_populates="students")
    guardians = relationship("StudentGuardian", back_populates="student", cascade="all, delete-orphan")
    health_profile = relationship("StudentHealth", back_populates="student", uselist=False, cascade="all, delete-orphan")

class TeacherAssignment(Base):
    __tablename__ = "teacher_assignments"

    id = Column(Integer, primary_key=True, index=True)
    teacher_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False, index=True)
    class_section_id = Column(Integer, ForeignKey("class_sections.id"), nullable=False, index=True)
    semester_id = Column(Integer, ForeignKey("semesters.id"), nullable=False, index=True)

    teacher = relationship("User", back_populates="teacher_assignments")
    class_section = relationship("ClassSection", back_populates="teacher_assignments")
    subject = relationship("Subject")
    semester = relationship("Semester")

class Score(Base):
    __tablename__ = "scores"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False, index=True)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False, index=True)
    semester_id = Column(Integer, ForeignKey("semesters.id"), nullable=False, index=True)
    ex1 = Column(Float, nullable=True, default=0.0)
    ex2 = Column(Float, nullable=True, default=0.0)
    ass1 = Column(Float, nullable=True, default=0.0)
    ass2 = Column(Float, nullable=True, default=0.0)
    ind_proj = Column(Float, nullable=True, default=0.0)
    grp_work = Column(Float, nullable=True, default=0.0)
    pract_work = Column(Float, nullable=True, default=0.0)
    mid_sem = Column(Float, nullable=True, default=0.0)
    class_score = Column(Float, default=0.0)
    exam_score = Column(Float, default=0.0)
    total_score = Column(Float, default=0.0)
    grade = Column(String, nullable=True)
    remark = Column(String, nullable=True)
    rank_in_subject = Column(String, nullable=True)
    approval_status = Column(String, default="DRAFT", server_default="DRAFT")

    student = relationship("Student", back_populates="scores")
    subject = relationship("Subject", back_populates="scores")
    semester = relationship("Semester", back_populates="scores")

class Attendance(Base):
    __tablename__ = "attendance"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False, index=True)
    date = Column(DateTime, nullable=False, index=True)
    status = Column(String, nullable=False)
    # "daily" = official Form Master class register; "period" = subject lesson absence log
    attendance_type = Column(String, nullable=False, default="daily", server_default="daily")
    # Only set for period-type records — links to which subject lesson was missed
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=True, index=True)
    # Optional label like "Period 3 – 11:30 AM" for period-type records
    period_label = Column(String, nullable=True)
    # Teacher who logged the period absence (nullable for legacy records)
    logged_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    student = relationship("Student", back_populates="attendance")
    subject = relationship("Subject", foreign_keys=[subject_id])
    logged_by = relationship("User", foreign_keys=[logged_by_id])

class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    message = Column(String, nullable=False)
    type = Column(String, default="Attendance")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    is_read = Column(Boolean, default=False)

    student = relationship("Student", back_populates="notifications")

class Setting(Base):
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True, index=True)
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=True)
    key = Column(String, index=True, nullable=False)
    value = Column(String, nullable=False)

# ── Fee & Finance ─────────────────────────────────────────────────────────────

class Fee(Base):
    __tablename__ = "fees"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    fee_type = Column(String, nullable=False)
    description = Column(String, nullable=True)
    amount = Column(Float, nullable=False)
    amount_paid = Column(Float, default=0.0)
    due_date = Column(DateTime, nullable=True)
    academic_year = Column(String, nullable=True)
    term = Column(String, nullable=True)
    status = Column(String, default="Pending")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    student = relationship("Student", back_populates="fees")
    payments = relationship("Payment", back_populates="fee", cascade="all, delete-orphan")

class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    fee_id = Column(Integer, ForeignKey("fees.id"), nullable=False)
    amount_paid = Column(Float, nullable=False)
    payment_date = Column(DateTime, nullable=False, server_default=func.now())
    payment_method = Column(String, default="Cash")
    reference_no = Column(String, nullable=True)
    notes = Column(String, nullable=True)
    recorded_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    fee = relationship("Fee", back_populates="payments")
    recorder = relationship("User")

# ── Timetable ─────────────────────────────────────────────────────────────────

class Timetable(Base):
    __tablename__ = "timetable"

    id = Column(Integer, primary_key=True, index=True)
    class_section_id = Column(Integer, ForeignKey("class_sections.id"), nullable=False)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False)
    teacher_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    semester_id = Column(Integer, ForeignKey("semesters.id"), nullable=True)
    day_of_week = Column(Integer, nullable=False)
    period_number = Column(Integer, nullable=False)
    start_time = Column(String, nullable=True)
    end_time = Column(String, nullable=True)
    room = Column(String, nullable=True)

    class_section = relationship("ClassSection")
    subject = relationship("Subject")
    teacher = relationship("User")
    semester = relationship("Semester")

# ── Discipline Records ────────────────────────────────────────────────────────

class DisciplineRecord(Base):
    __tablename__ = "discipline_records"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    incident_type = Column(String, nullable=False)
    description = Column(String, nullable=False)
    action_taken = Column(String, nullable=True)
    incident_date = Column(DateTime, nullable=False, server_default=func.now())
    recorded_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    parent_notified = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    student = relationship("Student")
    recorder = relationship("User", foreign_keys=[recorded_by])

class StudentSemesterSummary(Base):
    __tablename__ = "student_semester_summaries"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    semester_id = Column(Integer, ForeignKey("semesters.id", ondelete="CASCADE"), nullable=False)
    attitude = Column(String, nullable=True)
    conduct = Column(String, nullable=True)
    interest = Column(String, nullable=True)
    form_teacher_remarks = Column(String, nullable=True)
    headteacher_remarks = Column(String, nullable=True)
    promoted_to = Column(String, nullable=True)

    student = relationship("Student")
    semester = relationship("Semester")

class MessageLog(Base):
    __tablename__ = "message_logs"

    id = Column(Integer, primary_key=True, index=True)
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=True)
    recipient_name = Column(String, nullable=True)
    recipient_phone = Column(String, nullable=True)
    channel = Column(String, nullable=False, default="SMS")
    message_type = Column(String, nullable=False, default="GENERAL")
    message_body = Column(String, nullable=False)
    overall_grade = Column(String, nullable=True)
    status = Column(String, nullable=False, default="SENT")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    sender = relationship("User", foreign_keys=[sender_id])
    student = relationship("Student", foreign_keys=[student_id])

# ── Exeat Management ─────────────────────────────────────────────────────────

class ExeatRecord(Base):
    __tablename__ = "exeat_records"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    exeat_type = Column(String, nullable=False, default="Day")
    reason = Column(String, nullable=False)
    destination = Column(String, nullable=False)
    expected_departure = Column(DateTime, nullable=False)
    expected_return = Column(DateTime, nullable=False)
    actual_departure = Column(DateTime, nullable=True)
    actual_return = Column(DateTime, nullable=True)
    parent_contact = Column(String, nullable=True)
    parent_approved = Column(Boolean, default=True)
    status = Column(String, nullable=False, default="Pending")
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    approved_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    gate_out_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    gate_in_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    approval_notes = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    student = relationship("Student", foreign_keys=[student_id])
    created_by = relationship("User", foreign_keys=[created_by_id])
    approved_by = relationship("User", foreign_keys=[approved_by_id])
    gate_out_by = relationship("User", foreign_keys=[gate_out_by_id])
    gate_in_by = relationship("User", foreign_keys=[gate_in_by_id])

# ── Academic Hierarchy & Report Card Publishing ─────────────────────────────

class ClassSectionReportStatus(Base):
    __tablename__ = "class_section_report_statuses"

    id = Column(Integer, primary_key=True, index=True)
    class_section_id = Column(Integer, ForeignKey("class_sections.id", ondelete="CASCADE"), nullable=False)
    semester_id = Column(Integer, ForeignKey("semesters.id", ondelete="CASCADE"), nullable=False)
    is_published = Column(Boolean, default=False)
    published_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    published_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    class_section = relationship("ClassSection")
    semester = relationship("Semester")
    published_by = relationship("User")

class ClassSubjectScoreStatus(Base):
    __tablename__ = "class_subject_score_statuses"

    id = Column(Integer, primary_key=True, index=True)
    class_section_id = Column(Integer, ForeignKey("class_sections.id", ondelete="CASCADE"), nullable=False)
    subject_id = Column(Integer, ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False)
    semester_id = Column(Integer, ForeignKey("semesters.id", ondelete="CASCADE"), nullable=False)
    status = Column(String, nullable=False, default="Draft")
    approved_by_hod_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    approved_at = Column(DateTime, nullable=True)

    class_section = relationship("ClassSection")
    subject = relationship("Subject")
    semester = relationship("Semester")
    approved_by_hod = relationship("User")


# ── Storekeeper & Inventory Management ─────────────────────────────────────

class Asset(Base):
    __tablename__ = "assets"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    category = Column(String, nullable=False, default="Furniture")
    serial_number = Column(String, nullable=True)
    quantity = Column(Integer, default=1)
    unit_cost = Column(Float, default=0.0)
    location = Column(String, nullable=True)
    status = Column(String, default="Good")
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    school = relationship("School")


class TextbookAllocation(Base):
    __tablename__ = "textbook_allocations"

    id = Column(Integer, primary_key=True, index=True)
    book_title = Column(String, nullable=False)
    barcode_id = Column(String, nullable=False, index=True)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    issued_date = Column(DateTime, server_default=func.now())
    expected_return_date = Column(DateTime, nullable=True)
    actual_return_date = Column(DateTime, nullable=True)
    status = Column(String, default="Issued")
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=True)

    subject = relationship("Subject")
    student = relationship("Student")
    school = relationship("School")


class UniformItem(Base):
    __tablename__ = "uniform_items"

    id = Column(Integer, primary_key=True, index=True)
    item_name = Column(String, nullable=False)
    size = Column(String, nullable=True)
    quantity_in_stock = Column(Integer, default=0)
    unit_price = Column(Float, default=0.0)
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=True)

    school = relationship("School")


class UniformDisbursement(Base):
    __tablename__ = "uniform_disbursements"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    item_id = Column(Integer, ForeignKey("uniform_items.id"), nullable=False)
    quantity = Column(Integer, default=1)
    disbursed_date = Column(DateTime, server_default=func.now())
    remarks = Column(String, nullable=True)
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=True)

    student = relationship("Student")
    item = relationship("UniformItem")
    school = relationship("School")


class GatePassLog(Base):
    __tablename__ = "gate_pass_logs"

    id = Column(Integer, primary_key=True, index=True)
    exeat_id = Column(Integer, ForeignKey("exeat_records.id"), nullable=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    action = Column(String, nullable=False)
    timestamp = Column(DateTime, server_default=func.now())
    officer_name = Column(String, nullable=True)
    notes = Column(String, nullable=True)
    school_id = Column(Integer, ForeignKey("schools.id"), nullable=True)

    exeat = relationship("ExeatRecord")
    student = relationship("Student")
    school = relationship("School")


# ── Final Year Student Clearance ──────────────────────────────────────────

class StudentClearanceRecord(Base):
    __tablename__ = "student_clearance_records"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False, unique=True)
    academic_year = Column(String, nullable=True)
    
    storekeeper_cleared = Column(Boolean, default=False)
    storekeeper_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    storekeeper_notes = Column(String, nullable=True)
    
    bursar_cleared = Column(Boolean, default=False)
    bursar_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    bursar_notes = Column(String, nullable=True)
    
    housemaster_cleared = Column(Boolean, default=False)
    housemaster_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    housemaster_notes = Column(String, nullable=True)
    
    headmaster_cleared = Column(Boolean, default=False)
    headmaster_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    headmaster_notes = Column(String, nullable=True)
    
    status = Column(String, default="Pending") # Pending | Fully Cleared
    completed_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    student = relationship("Student")
    storekeeper_by = relationship("User", foreign_keys=[storekeeper_by_id])
    bursar_by = relationship("User", foreign_keys=[bursar_by_id])
    housemaster_by = relationship("User", foreign_keys=[housemaster_by_id])
    headmaster_by = relationship("User", foreign_keys=[headmaster_by_id])


class AdmissionVoucher(Base):
    __tablename__ = "admission_vouchers"

    id = Column(Integer, primary_key=True, index=True)
    serial_code = Column(String(30), unique=True, index=True, nullable=False)
    pin_code = Column(String(10), nullable=False)
    bece_index_number = Column(String(12), index=True, nullable=True)
    status = Column(String, default="AVAILABLE", server_default="AVAILABLE") # AVAILABLE, SENT_VIA_SMS, USED
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    used_at = Column(DateTime(timezone=True), nullable=True)
    school_id = Column(Integer, ForeignKey("schools.id", ondelete="CASCADE"), nullable=True, default=1)

    school = relationship("School")


