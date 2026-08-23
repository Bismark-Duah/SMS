import hashlib
from typing import Optional, List, Dict
from sqlalchemy.orm import Session
from ..models import User, Role, Student

def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

def get_or_create_parent_role(db: Session) -> Role:
    role = db.query(Role).filter(Role.name == "parent").first()
    if not role:
        role = Role(name="parent")
        db.add(role)
        db.flush()
    return role

def _clean_phone(phone: Optional[str]) -> str:
    if not phone:
        return ""
    return "".join(c for c in phone if c.isdigit())

def _normalize_str(s: Optional[str]) -> str:
    if not s:
        return ""
    return s.strip().lower().replace("_", " ").replace("-", " ")

def find_matching_parent_user(db: Session, phone: Optional[str] = None, guardian_name: Optional[str] = None) -> Optional[User]:
    clean_p = _clean_phone(phone)
    name_clean = _normalize_str(guardian_name)

    if not clean_p and not name_clean:
        return None

    # Query all parent users
    parent_users = db.query(User).join(User.roles).filter(Role.name == "parent").all()

    # 1. Match by phone
    if clean_p and len(clean_p) >= 7:
        for u in parent_users:
            u_phone = _clean_phone(u.username) or _clean_phone(u.email)
            if u_phone and (clean_p == u_phone or u.username == f"parent_{clean_p}" or u.username == clean_p):
                return u

    # 2. Match by exact guardian name / email
    if name_clean:
        for u in parent_users:
            u_name = _normalize_str(u.username)
            u_email = _normalize_str(u.email.split("@")[0])
            if u_name == name_clean or u_email == name_clean:
                return u

    # 3. Match by partial guardian name
    if name_clean and len(name_clean) >= 4:
        for u in parent_users:
            u_name = _normalize_str(u.username)
            if u_name and (name_clean in u_name or u_name in name_clean):
                return u

    # 3. Fallback check among all active users if phone matches
    if clean_p:
        all_users = db.query(User).filter(User.is_active == True).all()
        for u in all_users:
            u_phone = _clean_phone(u.username) or _clean_phone(u.email)
            if u_phone and u_phone == clean_p:
                parent_role = get_or_create_parent_role(db)
                if parent_role not in u.roles:
                    u.roles.append(parent_role)
                return u

    return None

def auto_link_guardian_for_student(db: Session, student: Student, auto_create: bool = True) -> Optional[User]:
    """
    Automatically links a student to a guardian User account.
    If a matching guardian account exists, links the student to it (supporting multiple students per guardian).
    If no guardian exists and auto_create is True, creates a new guardian User account and links the student.
    """
    if student.parent_id:
        existing_parent = db.query(User).filter(User.id == student.parent_id).first()
        if existing_parent:
            return existing_parent

    # Try matching existing parent
    matching_user = find_matching_parent_user(db, phone=student.phone, guardian_name=student.guardian_name)
    if matching_user:
        student.parent_id = matching_user.id
        return matching_user

    # Auto-create if enabled and sufficient info is provided
    if auto_create and (student.phone or student.guardian_name):
        parent_role = get_or_create_parent_role(db)
        clean_p = _clean_phone(student.phone)
        
        if clean_p:
            base_username = f"parent_{clean_p}"
        elif student.guardian_name:
            base_username = student.guardian_name.strip().lower().replace(" ", "_")
        else:
            base_username = f"parent_std_{student.id or student.student_code}"

        # Ensure unique username
        username = base_username
        counter = 1
        while db.query(User).filter(User.username == username).first():
            username = f"{base_username}_{counter}"
            counter += 1

        email = f"{username}@guardian.school"

        new_parent = User(
            username=username,
            email=email,
            password_hash=_hash_password("Parent123"), # Default password
            is_active=True,
        )
        new_parent.roles.append(parent_role)
        db.add(new_parent)
        db.flush() # obtain new_parent.id

        student.parent_id = new_parent.id
        return new_parent

    return None

def link_students_for_parent_user(db: Session, parent_user: User) -> int:
    """
    Links existing unlinked students to a newly created/updated parent user
    if their guardian phone or name matches.
    """
    if not any(r.name == "parent" for r in parent_user.roles):
        return 0

    p_phone = _clean_phone(parent_user.username) or _clean_phone(parent_user.email)
    p_name = parent_user.username.lower().replace("_", " ")

    unlinked_students = db.query(Student).filter(Student.parent_id == None).all()
    linked_count = 0

    for std in unlinked_students:
        std_p = _clean_phone(std.phone)
        std_g = (std.guardian_name or "").strip().lower()

        match = False
        if p_phone and std_p and (p_phone in std_p or std_p in p_phone):
            match = True
        elif p_name and std_g and (p_name == std_g or std_g.startswith(p_name)):
            match = True

        if match:
            std.parent_id = parent_user.id
            linked_count += 1

    return linked_count

def auto_link_all_guardians(db: Session) -> Dict[str, int]:
    """
    Scans all students in the database and automatically links unlinked students to guardians.
    Creates new guardian accounts when necessary.
    """
    students = db.query(Student).all()
    newly_linked = 0
    already_linked = 0

    initial_parent_count = db.query(User).join(User.roles).filter(Role.name == "parent").count()

    for s in students:
        if s.parent_id:
            already_linked += 1
            continue
        
        had_parent_before = bool(s.parent_id)
        parent_user = auto_link_guardian_for_student(db, s, auto_create=True)
        if parent_user and not had_parent_before:
            newly_linked += 1

    final_parent_count = db.query(User).join(User.roles).filter(Role.name == "parent").count()
    created_guardians = max(0, final_parent_count - initial_parent_count)

    db.commit()

    return {
        "total_students": len(students),
        "already_linked": already_linked,
        "newly_linked": newly_linked,
        "created_guardians": created_guardians,
    }
