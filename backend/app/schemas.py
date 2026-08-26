from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, field_validator

# --- Auth & Roles ---
class RoleBase(BaseModel):
    name: str

class Role(RoleBase):
    id: int
    class Config:
        from_attributes = True

class UserBase(BaseModel):
    username: str
    email: Optional[str] = None
    gender: Optional[str] = None

class UserCreate(UserBase):
    password: str
    role_names: List[str] = ["teacher"]

class User(UserBase):
    id: int
    is_active: bool
    roles: List[Role] = []
    department_id: Optional[int] = None
    children: List[int] = [] # List of student IDs

    @field_validator("children", mode="before")
    @classmethod
    def serialize_children(cls, v):
        if isinstance(v, list):
            return [x.id if hasattr(x, "id") else x for x in v]
        return v

    class Config:
        from_attributes = True

class LoginRequest(BaseModel):
    username: str
    password: str

# --- Academic Hierarchy ---
class SchoolStageCreate(BaseModel):
    name: str
    school_type: str

class ClassSectionCreate(BaseModel):
    name: str
    stage_id: int
    program_id: Optional[int] = None
    form_master_id: Optional[int] = None

class BatchArmCreate(BaseModel):
    stage_id: int
    program_id: Optional[int] = None
    number_of_arms: int = 1
    naming_style: str = "NUMBERS"  # "NUMBERS" (1,2,3), "LETTERS" (A,B,C)
    base_name: Optional[str] = None  # e.g. "Science", "Arts"

class SmartGenerateRequest(BaseModel):
    target_capacity: int = 45
    naming_style: str = "AUTO"  # "LETTERS" (A, B, C), "NUMBERS" (1, 2, 3)
    assign_students: bool = True
    stage_id: Optional[int] = None

class ProgramCreate(BaseModel):
    name: str

class ProgramCoreSubjectsUpdate(BaseModel):
    subject_ids: List[int]

class ElectiveCombinationCreate(BaseModel):
    name: str
    code: Optional[str] = None
    class_section_id: Optional[int] = None
    capacity: Optional[int] = 50
    is_active: Optional[bool] = True
    subject_ids: List[int] = []

class ElectiveCombinationUpdate(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    class_section_id: Optional[int] = None
    capacity: Optional[int] = None
    is_active: Optional[bool] = None
    subject_ids: Optional[List[int]] = None

class SubjectCreate(BaseModel):
    name: str
    code: Optional[str] = None
    is_core: bool = True
    is_active: Optional[bool] = True
    category: Optional[str] = "Core"
    group_code: Optional[str] = None
    assessment_type: Optional[str] = "External_WASSCE"
    school_level: Optional[str] = "SHS"

class StudentGuardianCreate(BaseModel):
    guardian_name: str
    relationship_type: Optional[str] = "Parent"
    primary_phone: str
    alternative_phone: Optional[str] = None
    occupation: Optional[str] = None
    residential_address: Optional[str] = None

class StudentHealthCreate(BaseModel):
    blood_group: Optional[str] = None
    allergies: Optional[str] = None
    chronic_conditions: Optional[str] = None
    doctor_clearance_status: Optional[bool] = False
    emergency_contact: Optional[str] = None
    height_cm: Optional[float] = None
    weight_kg: Optional[float] = None
    pe_limitations: Optional[str] = None

class CSSPSEnrollmentCreate(BaseModel):
    bece_index_number: str
    enrolment_code: str
    first_name: str
    middle_name: Optional[str] = None
    last_name: str
    gender: str
    date_of_birth: Optional[str] = None
    bece_raw_score: Optional[int] = None
    bece_aggregate: Optional[int] = None
    jhs_attended: Optional[str] = None
    program_id: Optional[int] = None
    residential_status: Optional[str] = "B" # B: Boarding, D: Day
    house_id: Optional[int] = None
    guardian_name: str
    primary_phone: str
    alternative_phone: Optional[str] = None
    residential_address: Optional[str] = None
    blood_group: Optional[str] = None
    genotype: Optional[str] = None
    allergies: Optional[str] = None
    medical_conditions: Optional[str] = None
    pe_limitations: Optional[str] = None
    emergency_contact: Optional[str] = None
    doctor_clearance_status: Optional[bool] = True

class CumulativeRecordUpdate(BaseModel):
    family_background_notes: Optional[str] = None
    socio_economic_notes: Optional[str] = None
    personality_traits: Optional[str] = None
    leadership_notes: Optional[str] = None
    teacher_observations: Optional[str] = None
    co_curricular_activities: Optional[str] = None
    hobbies_talents: Optional[str] = None
    awards: Optional[str] = None
    height_cm: Optional[float] = None
    weight_kg: Optional[float] = None
    medical_conditions: Optional[str] = None
    pe_limitations: Optional[str] = None


class AcademicYearCreate(BaseModel):
    label: str
    is_current: bool = False

class AcademicYearUpdate(BaseModel):
    label: str
    is_current: bool = False

class SemesterCreate(BaseModel):
    name: str
    academic_year_id: int
    is_current: bool = False
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None

class SemesterUpdate(BaseModel):
    name: str
    is_current: bool = False
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None

# --- Departments ---
class DepartmentBase(BaseModel):
    name: str
    code: str
    hod_id: Optional[int] = None

class DepartmentCreate(DepartmentBase):
    subject_ids: List[int] = []

class DepartmentResponse(DepartmentBase):
    id: int
    hod_name: Optional[str] = None
    subject_ids: List[int] = []
    subject_names: List[str] = []
    teacher_count: int = 0
    teacher_names: List[str] = []
    teachers: List[dict] = []

    class Config:
        from_attributes = True

# --- Boarding System ---
class DormitoryBase(BaseModel):
    name: str
    house_id: int
    capacity: Optional[int] = 30
    housemaster_id: Optional[int] = None

class DormitoryCreate(DormitoryBase):
    pass

class DormitoryResponse(DormitoryBase):
    id: int
    housemaster_name: Optional[str] = None
    capacity: int = 30
    occupied_count: int = 0

    class Config:
        from_attributes = True

class HouseBase(BaseModel):
    name: str
    gender: str # "Boys", "Girls", or "Both"
    house_type: Optional[str] = "BOARDING" # "BOARDING" or "ACADEMIC_SPORTS"
    senior_in_charge_id: Optional[int] = None
    house_master_id: Optional[int] = None
    assistant_house_master_id: Optional[int] = None
    senior_in_charge_girls_id: Optional[int] = None
    house_master_girls_id: Optional[int] = None
    assistant_house_master_girls_id: Optional[int] = None

class HouseCreate(HouseBase):
    pass

class HouseResponse(HouseBase):
    id: int
    senior_in_charge_name: Optional[str] = None
    house_master_name: Optional[str] = None
    assistant_house_master_name: Optional[str] = None
    senior_in_charge_girls_name: Optional[str] = None
    house_master_girls_name: Optional[str] = None
    assistant_house_master_girls_name: Optional[str] = None
    dormitories: List[DormitoryResponse] = []
    student_count: int = 0
    boarder_count: int = 0
    day_count: int = 0

    class Config:
        from_attributes = True

# --- Core Records ---
class StudentCreate(BaseModel):
    student_code: str
    full_name: str
    class_section_id: int
    program_id: Optional[int] = None
    parent_id: Optional[int] = None
    form: Optional[int] = None
    gender: Optional[str] = None
    date_of_birth: Optional[str] = None   # ISO date string YYYY-MM-DD
    address: Optional[str] = None
    phone: Optional[str] = None
    guardian_name: Optional[str] = None
    house_id: Optional[int] = None
    dormitory_id: Optional[int] = None
    bece_index_number: Optional[str] = None
    enrolment_code: Optional[str] = None
    bece_raw_score: Optional[int] = None
    bece_aggregate: Optional[int] = None
    residential_status: Optional[str] = "B"
    blood_group: Optional[str] = None
    genotype: Optional[str] = None
    allergies: Optional[str] = None
    chronic_conditions: Optional[str] = None
    pe_limitations: Optional[str] = None
    emergency_contact: Optional[str] = None
    doctor_clearance_status: Optional[bool] = True

class ScoreCreate(BaseModel):
    student_id: int
    subject_id: int
    semester_id: int
    ex1: Optional[float] = 0.0
    ex2: Optional[float] = 0.0
    ass1: Optional[float] = 0.0
    ass2: Optional[float] = 0.0
    ind_proj: Optional[float] = 0.0
    grp_work: Optional[float] = 0.0
    pract_work: Optional[float] = 0.0
    mid_sem: Optional[float] = 0.0
    class_score: float = 0.0
    exam_score: float = 0.0

class AttendanceCreate(BaseModel):
    student_id: int
    date: str # ISO format string or datetime
    status: str

# --- Teacher Assignments ---
class TeacherAssignmentCreate(BaseModel):
    teacher_id: int
    subject_id: int
    class_section_id: int
    semester_id: int

class TeacherAssignmentResponse(BaseModel):
    id: int
    teacher_id: int
    subject_id: int
    class_section_id: int
    semester_id: int

    class Config:
        from_attributes = True

class TeacherAssignmentDetail(BaseModel):
    id: int
    teacher_id: int
    teacher_name: str
    subject_id: int
    subject_name: str
    class_section_id: int
    class_section_name: str
    semester_id: int
    semester_name: str

    class Config:
        from_attributes = True

class TeacherPrivilegeCreate(BaseModel):
    teacher_id: int
    privilege_type: str
    target_id: Optional[int] = None

class TeacherPrivilegeDetail(BaseModel):
    id: str
    teacher_id: int
    teacher_name: Optional[str] = "Staff Member"
    privilege_type: str
    target_id: Optional[int] = None
    target_name: Optional[str] = None


# --- Exeat Management Schemas ---
class ExeatCreate(BaseModel):
    student_id: int
    exeat_type: str = "Day" # Day, Weekend, Medical, Special
    reason: str
    destination: str
    expected_departure: datetime
    expected_return: datetime
    parent_contact: Optional[str] = None
    parent_approved: bool = True
    approval_notes: Optional[str] = None

class ExeatUpdate(BaseModel):
    exeat_type: Optional[str] = None
    reason: Optional[str] = None
    destination: Optional[str] = None
    expected_departure: Optional[datetime] = None
    expected_return: Optional[datetime] = None
    parent_contact: Optional[str] = None
    parent_approved: Optional[bool] = None
    status: Optional[str] = None
    approval_notes: Optional[str] = None

class ExeatResponse(BaseModel):
    id: int
    student_id: int
    student_name: str
    student_code: str
    class_name: Optional[str] = None
    house_id: Optional[int] = None
    house_name: Optional[str] = None
    dormitory_name: Optional[str] = None
    gender: Optional[str] = None
    exeat_type: str
    reason: str
    destination: str
    expected_departure: datetime
    expected_return: datetime
    actual_departure: Optional[datetime] = None
    actual_return: Optional[datetime] = None
    parent_contact: Optional[str] = None
    parent_approved: bool
    status: str
    created_by_name: Optional[str] = None
    approved_by_name: Optional[str] = None
    approved_by_role: Optional[str] = None
    gate_out_by_name: Optional[str] = None
    gate_in_by_name: Optional[str] = None
    approval_notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class ExeatStats(BaseModel):
    currently_away: int
    pending_approvals: int
    overdue_returns: int
    total_this_term: int


# --- Academic Hierarchy & Broadsheet Schemas ---
class TeacherDepartmentAssign(BaseModel):
    teacher_id: int
    department_id: Optional[int] = None

class HODScoreApproval(BaseModel):
    class_section_id: int
    subject_id: int
    semester_id: int
    action: str = "approve" # approve | reject | submit

class BroadsheetRemarkItem(BaseModel):
    student_id: int
    attitude: Optional[str] = None
    conduct: Optional[str] = None
    interest: Optional[str] = None
    form_teacher_remarks: Optional[str] = None

class BroadsheetRemarksUpdate(BaseModel):
    class_section_id: int
    semester_id: int
    remarks: List[BroadsheetRemarkItem]

class BroadsheetStudentRow(BaseModel):
    student_id: int
    student_name: str
    student_code: str
    subject_scores: dict # {subject_name: total_score}
    total_marks: float
    average_mark: float
    class_rank: int
    aggregate: Optional[int] = None
    attitude: Optional[str] = None
    conduct: Optional[str] = None
    interest: Optional[str] = None
    form_teacher_remarks: Optional[str] = None

class BroadsheetResponse(BaseModel):
    class_section_id: int
    class_name: str
    semester_id: int
    semester_name: str
    form_master_name: Optional[str] = None
    publishing_mode: str # FORM_MASTER_DIRECT | ACADEMIC_HEAD_ONLY | HYBRID_BOTH
    is_published: bool
    subjects: List[dict] # [{id, name, code, is_core, status}]
    students: List[BroadsheetStudentRow]

class AcademicOverviewResponse(BaseModel):
    total_teachers: int
    total_departments: int
    overall_completion_percentage: float
    report_publishing_mode: str
    pending_hod_approvals: int
    published_classes_count: int
    total_classes_count: int


# ── Storekeeper & Inventory Schemas ──────────────────────────────────────────

class AssetCreate(BaseModel):
    name: str
    category: Optional[str] = "Furniture"
    serial_number: Optional[str] = None
    quantity: Optional[int] = 1
    unit_cost: Optional[float] = 0.0
    location: Optional[str] = None
    status: Optional[str] = "Good"

class AssetResponse(AssetCreate):
    id: int
    created_at: Optional[datetime] = None
    class Config:
        from_attributes = True

class TextbookIssueRequest(BaseModel):
    book_title: str
    barcode_id: str
    subject_id: Optional[int] = None
    student_id: int
    expected_return_date: Optional[str] = None

class UniformItemCreate(BaseModel):
    item_name: str
    size: Optional[str] = "Standard"
    quantity_in_stock: Optional[int] = 0
    unit_price: Optional[float] = 0.0

class UniformDisburseRequest(BaseModel):
    student_id: int
    item_id: int
    quantity: Optional[int] = 1
    remarks: Optional[str] = None

class GateVerifyRequest(BaseModel):
    student_code_or_index: str

class GateLogRequest(BaseModel):
    exeat_id: Optional[int] = None
    student_id: int
    action: str # EXIT_DEPARTURE | ENTRY_RETURN | VERIFICATION_DENIED | INCIDENT_REPORTED
    notes: Optional[str] = None


