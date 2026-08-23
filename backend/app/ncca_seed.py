from sqlalchemy.orm import Session
from .models import Program, Subject, SchoolStage, program_subjects

def seed_ncca_curriculum(db: Session):
    """
    Seeds Basic School subjects and 16 NaCCA SHS/STEM Learning Areas with Group A, B, C, D subject classifications.
    """
    # 1. Seed Basic School Subjects
    basic_subjects_data = [
        # Creche & Nursery / KG
        {"name": "Sensory & Motor Skills", "code": "SMS-KG", "is_core": True, "category": "Core", "group_code": None, "assessment_type": "Basic_Cumulative", "school_level": "Basic"},
        {"name": "Rhymes, Phonics & Language", "code": "RPL-KG", "is_core": True, "category": "Core", "group_code": None, "assessment_type": "Basic_Cumulative", "school_level": "Basic"},
        {"name": "Early Numeracy", "code": "NUM-KG", "is_core": True, "category": "Core", "group_code": None, "assessment_type": "Basic_Cumulative", "school_level": "Basic"},
        {"name": "Creative Play & Drawing", "code": "CPD-KG", "is_core": True, "category": "Core", "group_code": None, "assessment_type": "Basic_Cumulative", "school_level": "Basic"},
        {"name": "Language and Literacy", "code": "LIT-KG", "is_core": True, "category": "Core", "group_code": None, "assessment_type": "Basic_Cumulative", "school_level": "Basic"},
        {"name": "Our World Our People", "code": "OWOP-BAS", "is_core": True, "category": "Core", "group_code": None, "assessment_type": "Basic_Cumulative", "school_level": "Basic"},
        {"name": "Physical Development", "code": "PD-KG", "is_core": True, "category": "Core", "group_code": None, "assessment_type": "Basic_Cumulative", "school_level": "Basic"},
        
        # Primary & JHS
        {"name": "English Language", "code": "ENG-BAS", "is_core": True, "category": "Core", "group_code": None, "assessment_type": "Basic_Cumulative", "school_level": "Basic"},
        {"name": "Mathematics", "code": "MATH-BAS", "is_core": True, "category": "Core", "group_code": None, "assessment_type": "Basic_Cumulative", "school_level": "Basic"},
        {"name": "Science", "code": "SCI-BAS", "is_core": True, "category": "Core", "group_code": None, "assessment_type": "Basic_Cumulative", "school_level": "Basic"},
        {"name": "Social Studies", "code": "SOC-BAS", "is_core": True, "category": "Core", "group_code": None, "assessment_type": "Basic_Cumulative", "school_level": "Basic"},
        {"name": "Religious and Moral Education", "code": "RME-BAS", "is_core": True, "category": "Core", "group_code": None, "assessment_type": "Basic_Cumulative", "school_level": "Basic"},
        {"name": "History of Ghana", "code": "HIST-BAS", "is_core": True, "category": "Core", "group_code": None, "assessment_type": "Basic_Cumulative", "school_level": "Basic"},
        {"name": "Computing", "code": "COMP-BAS", "is_core": True, "category": "Core", "group_code": None, "assessment_type": "Basic_Cumulative", "school_level": "Basic"},
        {"name": "Creative Arts and Design", "code": "CAD-BAS", "is_core": True, "category": "Core", "group_code": None, "assessment_type": "Basic_Cumulative", "school_level": "Basic"},
        {"name": "Career Technology", "code": "CT-BAS", "is_core": True, "category": "Core", "group_code": None, "assessment_type": "Basic_Cumulative", "school_level": "Basic"},
        {"name": "Ghanaian Language", "code": "GHL-BAS", "is_core": True, "category": "Core", "group_code": None, "assessment_type": "Basic_Cumulative", "school_level": "Basic"},
        {"name": "French", "code": "FRE-BAS", "is_core": False, "category": "Elective", "group_code": None, "assessment_type": "Basic_Cumulative", "school_level": "Basic"},
        {"name": "Physical and Health Education", "code": "PEH-BAS", "is_core": True, "category": "Core", "group_code": None, "assessment_type": "Basic_Cumulative", "school_level": "Basic"},
    ]

    # 2. Seed SHS & STEM Core & Elective Subjects
    shs_subjects_data = [
        # Group A Core Subjects
        {"name": "Core Mathematics", "code": "MATH-SHS", "is_core": True, "category": "Core", "group_code": "Group A", "assessment_type": "External_WASSCE", "school_level": "SHS"},
        {"name": "Social Studies (SHS)", "code": "SOC-SHS", "is_core": True, "category": "Core", "group_code": "Group A", "assessment_type": "External_WASSCE", "school_level": "SHS"},
        {"name": "English Language (SHS)", "code": "ENG-SHS", "is_core": True, "category": "Core", "group_code": "Group A", "assessment_type": "External_WASSCE", "school_level": "SHS"},
        {"name": "General Science (Core)", "code": "GSCI-SHS", "is_core": True, "category": "Core", "group_code": "Group A", "assessment_type": "External_WASSCE", "school_level": "SHS"},
        {"name": "PEH (Core)", "code": "PEH-SHS", "is_core": True, "category": "Core", "group_code": "Group A", "assessment_type": "Internal_Transcript", "school_level": "SHS"},
        {"name": "Robotics and Coding (Form 2)", "code": "ROB-F2", "is_core": True, "category": "Core", "group_code": "Group A", "assessment_type": "Internal_Transcript", "school_level": "SHS"},

        # Science Electives
        {"name": "Biology", "code": "BIO-SHS", "is_core": False, "category": "Elective", "group_code": "Group B", "assessment_type": "External_WASSCE", "school_level": "SHS"},
        {"name": "Chemistry", "code": "CHEM-SHS", "is_core": False, "category": "Elective", "group_code": "Group B", "assessment_type": "External_WASSCE", "school_level": "SHS"},
        {"name": "Physics", "code": "PHYS-SHS", "is_core": False, "category": "Elective", "group_code": "Group B", "assessment_type": "External_WASSCE", "school_level": "SHS"},
        {"name": "Additional Mathematics", "code": "AMATH-SHS", "is_core": False, "category": "Elective", "group_code": "Group C", "assessment_type": "External_WASSCE", "school_level": "SHS"},
        {"name": "Computer Science (Elective)", "code": "CS-SHS", "is_core": False, "category": "Elective", "group_code": "Group C", "assessment_type": "External_WASSCE", "school_level": "SHS"},
        {"name": "ICT (Elective)", "code": "ICT-SHS", "is_core": False, "category": "Elective", "group_code": "Group C", "assessment_type": "External_WASSCE", "school_level": "SHS"},
        {"name": "Geography", "code": "GEO-SHS", "is_core": False, "category": "Elective", "group_code": "Group C", "assessment_type": "External_WASSCE", "school_level": "SHS"},
        {"name": "Agriculture (Elective)", "code": "AGRI-SHS", "is_core": False, "category": "Elective", "group_code": "Group C", "assessment_type": "External_WASSCE", "school_level": "SHS"},

        # Business Electives
        {"name": "Business Management", "code": "BM-SHS", "is_core": False, "category": "Elective", "group_code": "Group B", "assessment_type": "External_WASSCE", "school_level": "SHS"},
        {"name": "Financial Accounting", "code": "ACC-SHS", "is_core": False, "category": "Elective", "group_code": "Group B", "assessment_type": "External_WASSCE", "school_level": "SHS"},
        {"name": "Cost Accounting", "code": "CACC-SHS", "is_core": False, "category": "Elective", "group_code": "Group B", "assessment_type": "External_WASSCE", "school_level": "SHS"},
        {"name": "Economics", "code": "ECON-SHS", "is_core": False, "category": "Elective", "group_code": "Group B", "assessment_type": "External_WASSCE", "school_level": "SHS"},

        # General Arts & Humanities
        {"name": "Government", "code": "GOVT-SHS", "is_core": False, "category": "Elective", "group_code": "Group B", "assessment_type": "External_WASSCE", "school_level": "SHS"},
        {"name": "History (SHS)", "code": "HIST-SHS", "is_core": False, "category": "Elective", "group_code": "Group B", "assessment_type": "External_WASSCE", "school_level": "SHS"},
        {"name": "Literature in English", "code": "LIT-SHS", "is_core": False, "category": "Elective", "group_code": "Group B", "assessment_type": "External_WASSCE", "school_level": "SHS"},
        {"name": "Christian Religious Studies", "code": "CRS-SHS", "is_core": False, "category": "Elective", "group_code": "Group B", "assessment_type": "External_WASSCE", "school_level": "SHS"},
        {"name": "Islamic Religious Studies", "code": "IRS-SHS", "is_core": False, "category": "Elective", "group_code": "Group B", "assessment_type": "External_WASSCE", "school_level": "SHS"},
        {"name": "French (Elective)", "code": "FRE-SHS", "is_core": False, "category": "Elective", "group_code": "Group C", "assessment_type": "External_WASSCE", "school_level": "SHS"},
        {"name": "Arabic", "code": "ARAB-SHS", "is_core": False, "category": "Elective", "group_code": "Group C", "assessment_type": "External_WASSCE", "school_level": "SHS"},
        {"name": "Music", "code": "MUS-SHS", "is_core": False, "category": "Elective", "group_code": "Group C", "assessment_type": "External_WASSCE", "school_level": "SHS"},

        # Business Electives
        {"name": "Clerical Office Duties", "code": "COD-SHS", "is_core": False, "category": "Elective", "group_code": "Group C", "assessment_type": "External_WASSCE", "school_level": "SHS"},
        {"name": "Typewriting & Keyboarding", "code": "TYPE-SHS", "is_core": False, "category": "Elective", "group_code": "Group C", "assessment_type": "External_WASSCE", "school_level": "SHS"},

        # Agriculture Electives
        {"name": "Forestry", "code": "FOR-SHS", "is_core": False, "category": "Elective", "group_code": "Group C", "assessment_type": "External_WASSCE", "school_level": "SHS"},
        {"name": "Horticulture", "code": "HORT-SHS", "is_core": False, "category": "Elective", "group_code": "Group C", "assessment_type": "External_WASSCE", "school_level": "SHS"},

        # Technical, TVET & Applied Technology
        {"name": "Applied Electricity", "code": "AE-SHS", "is_core": False, "category": "Elective", "group_code": "Group B", "assessment_type": "External_WASSCE", "school_level": "SHS"},
        {"name": "Electronics", "code": "ELEC-SHS", "is_core": False, "category": "Elective", "group_code": "Group B", "assessment_type": "External_WASSCE", "school_level": "SHS"},
        {"name": "Auto Mechanics", "code": "AUTO-SHS", "is_core": False, "category": "Elective", "group_code": "Group B", "assessment_type": "External_WASSCE", "school_level": "SHS"},
        {"name": "Auto Electricals", "code": "AUTOELE-SHS", "is_core": False, "category": "Elective", "group_code": "Group B", "assessment_type": "External_WASSCE", "school_level": "SHS"},
        {"name": "Refrigeration & Air Conditioning", "code": "RAC-SHS", "is_core": False, "category": "Elective", "group_code": "Group B", "assessment_type": "External_WASSCE", "school_level": "SHS"},
        {"name": "Mechanical Engineering Craft Practice", "code": "MECP-SHS", "is_core": False, "category": "Elective", "group_code": "Group B", "assessment_type": "External_WASSCE", "school_level": "SHS"},
        {"name": "Plumbing & Pipe Fitting", "code": "PLUMB-SHS", "is_core": False, "category": "Elective", "group_code": "Group B", "assessment_type": "External_WASSCE", "school_level": "SHS"},
        {"name": "Welding & Fabrication", "code": "WELD-SHS", "is_core": False, "category": "Elective", "group_code": "Group B", "assessment_type": "External_WASSCE", "school_level": "SHS"},
        {"name": "Building Construction", "code": "BC-SHS", "is_core": False, "category": "Elective", "group_code": "Group B", "assessment_type": "External_WASSCE", "school_level": "SHS"},
        {"name": "Woodwork", "code": "WW-SHS", "is_core": False, "category": "Elective", "group_code": "Group B", "assessment_type": "External_WASSCE", "school_level": "SHS"},
        {"name": "Metalwork", "code": "MW-SHS", "is_core": False, "category": "Elective", "group_code": "Group B", "assessment_type": "External_WASSCE", "school_level": "SHS"},
        {"name": "Technical Drawing", "code": "TD-SHS", "is_core": False, "category": "Elective", "group_code": "Group B", "assessment_type": "External_WASSCE", "school_level": "SHS"},
        {"name": "Design & Communication Tech", "code": "DCT-SHS", "is_core": False, "category": "Elective", "group_code": "Group B", "assessment_type": "External_WASSCE", "school_level": "SHS"},
        {"name": "Catering & Hospitality", "code": "CATER-SHS", "is_core": False, "category": "Elective", "group_code": "Group B", "assessment_type": "External_WASSCE", "school_level": "SHS"},
        {"name": "Garment Making & Fashion", "code": "GARMENT-SHS", "is_core": False, "category": "Elective", "group_code": "Group B", "assessment_type": "External_WASSCE", "school_level": "SHS"},
        {"name": "Cosmetology & Beauty Therapy", "code": "COSM-SHS", "is_core": False, "category": "Elective", "group_code": "Group B", "assessment_type": "External_WASSCE", "school_level": "SHS"},

        # Visual Arts
        {"name": "General Knowledge in Art", "code": "GKA-SHS", "is_core": False, "category": "Elective", "group_code": "Group B", "assessment_type": "External_WASSCE", "school_level": "SHS"},
        {"name": "Graphic Design", "code": "GD-SHS", "is_core": False, "category": "Elective", "group_code": "Group B", "assessment_type": "External_WASSCE", "school_level": "SHS"},
        {"name": "Picture Making", "code": "PM-SHS", "is_core": False, "category": "Elective", "group_code": "Group B", "assessment_type": "External_WASSCE", "school_level": "SHS"},
        {"name": "Ceramics", "code": "CER-SHS", "is_core": False, "category": "Elective", "group_code": "Group B", "assessment_type": "External_WASSCE", "school_level": "SHS"},
        {"name": "Sculpture", "code": "SCULP-SHS", "is_core": False, "category": "Elective", "group_code": "Group B", "assessment_type": "External_WASSCE", "school_level": "SHS"},
        {"name": "Textiles", "code": "TEX-SHS", "is_core": False, "category": "Elective", "group_code": "Group B", "assessment_type": "External_WASSCE", "school_level": "SHS"},
        {"name": "Leatherwork", "code": "LW-SHS", "is_core": False, "category": "Elective", "group_code": "Group B", "assessment_type": "External_WASSCE", "school_level": "SHS"},
        {"name": "Basketry", "code": "BASK-SHS", "is_core": False, "category": "Elective", "group_code": "Group B", "assessment_type": "External_WASSCE", "school_level": "SHS"},

        # STEM Core & Specializations
        {"name": "Engineering Science", "code": "ENG-STEM", "is_core": False, "category": "Elective", "group_code": "Group B", "assessment_type": "External_WASSCE", "school_level": "STEM"},
        {"name": "Biomedical Science", "code": "BIOM-STEM", "is_core": False, "category": "Elective", "group_code": "Group B", "assessment_type": "External_WASSCE", "school_level": "STEM"},
        {"name": "Manufacturing Engineering", "code": "MFG-STEM", "is_core": False, "category": "Elective", "group_code": "Group B", "assessment_type": "External_WASSCE", "school_level": "STEM"},
        {"name": "Aviation & Aerospace Eng", "code": "AV-STEM", "is_core": False, "category": "Elective", "group_code": "Group B", "assessment_type": "External_WASSCE", "school_level": "STEM"},
        {"name": "Robotics Engineering", "code": "ROB-STEM", "is_core": False, "category": "Elective", "group_code": "Group B", "assessment_type": "External_WASSCE", "school_level": "STEM"},
        {"name": "Artificial Intelligence & Data Science", "code": "AI-STEM", "is_core": False, "category": "Elective", "group_code": "Group B", "assessment_type": "External_WASSCE", "school_level": "STEM"},
        {"name": "Cybersecurity & Network Security", "code": "CYBER-STEM", "is_core": False, "category": "Elective", "group_code": "Group B", "assessment_type": "External_WASSCE", "school_level": "STEM"},
        {"name": "Renewable Energy Technology", "code": "RE-STEM", "is_core": False, "category": "Elective", "group_code": "Group B", "assessment_type": "External_WASSCE", "school_level": "STEM"},
        {"name": "STEM Group C Lab Practical", "code": "LAB-STEM", "is_core": False, "category": "Elective", "group_code": "Group C", "assessment_type": "Internal_Transcript", "school_level": "STEM"},
    ]

    all_subjects = basic_subjects_data + shs_subjects_data

    subject_map = {}
    for sdata in all_subjects:
        existing = db.query(Subject).filter((Subject.name == sdata["name"]) | (Subject.code == sdata["code"])).first()
        if not existing:
            subj = Subject(**sdata)
            db.add(subj)
            db.flush()
            subject_map[sdata["name"]] = subj
        else:
            # Update metadata fields if present
            existing.category = sdata["category"]
            existing.group_code = sdata["group_code"]
            existing.assessment_type = sdata["assessment_type"]
            existing.school_level = sdata["school_level"]
            subject_map[sdata["name"]] = existing

    # 3. Seed 16 NaCCA Learning Areas (Programs)
    nacca_programs = [
        # SHS / SHTS Programs (9)
        {"name": "General Science", "code": "GSCI"},
        {"name": "General Arts", "code": "GART"},
        {"name": "Business", "code": "BUSE"},
        {"name": "Applied Technology", "code": "APTECH"},
        {"name": "Home Economics", "code": "HOMEC"},
        {"name": "Visual and Performing Arts", "code": "VPA"},
        {"name": "Agriculture", "code": "AGRIC"},
        {"name": "Languages", "code": "LANG"},
        {"name": "Global Studies", "code": "GLOB"},

        # STEM Programs (7)
        {"name": "STEM Engineering", "code": "STEM-ENG"},
        {"name": "STEM Biomedical Science", "code": "STEM-BIOM"},
        {"name": "STEM Manufacturing", "code": "STEM-MFG"},
        {"name": "STEM Information Technology", "code": "STEM-IT"},
        {"name": "STEM Computer Science", "code": "STEM-CS"},
        {"name": "STEM Aviation and Aerospace", "code": "STEM-AV"},
        {"name": "STEM Robotics", "code": "STEM-ROB"},
    ]

    for pdata in nacca_programs:
        existing_p = db.query(Program).filter(Program.name == pdata["name"]).first()
        if not existing_p:
            prog = Program(**pdata)
            db.add(prog)

    db.commit()

    # Ensure standard School Stages exist in DB
    stages_data = [
        {"name": "Creche", "school_type": "Basic"},
        {"name": "Nursery", "school_type": "Basic"},
        {"name": "Kindergarten", "school_type": "Basic"},
        {"name": "Primary", "school_type": "Basic"},
        {"name": "JHS", "school_type": "Basic"},
        {"name": "SHS", "school_type": "SHS"},
        {"name": "STEM", "school_type": "SHS"},
    ]
    for stg in stages_data:
        ex_stg = db.query(SchoolStage).filter(SchoolStage.name == stg["name"]).first()
        if not ex_stg:
            db.add(SchoolStage(**stg))

    db.commit()
    seed_standard_departments(db)
    return {"message": "NaCCA New Curriculum & Basic School templates seeded successfully."}


def seed_standard_departments(db: Session):
    """
    Seeds and aligns standard SHS academic departments with their discipline-specific subjects.
    Ensures subjects like Social Studies belong to Social Sciences, English to Languages, etc.
    """
    from .models import Department, Subject

    department_mappings = [
        {
            "name": "GENERAL SCIENCE DEPARTMENT (SCIENCE DEPARTMENT)",
            "code": "SCI",
            "subjects": [
                "General Science (Core)", "Science", "Biology", "Chemistry", "Physics",
                "Biomedical Science", "Engineering Science", "Aviation & Aerospace Eng",
                "Agriculture (Elective)", "General Agriculture", "Crop Husbandry and Horticulture",
                "Animal Husbandry", "Fisheries", "Forestry", "Horticulture", "STEM Group C Lab Practical"
            ]
        },
        {
            "name": "MATHEMATICS DEPARTMENT",
            "code": "MATH",
            "subjects": [
                "Core Mathematics", "Mathematics", "Early Numeracy", "Additional Mathematics"
            ]
        },
        {
            "name": "LANGUAGES DEPARTMENT",
            "code": "LANG",
            "subjects": [
                "English Language (SHS)", "English Language", "Rhymes, Phonics & Language",
                "Language and Literacy", "Literature in English", "French (Elective)",
                "French", "Ghanaian Language", "Arabic", "Music", "Twi (Asante / Akuapem)", "Twi (Asante)",
                "Twi (Akuapem)", "Fante", "Ewe", "Ga", "Dagbani", "Nzema", "Dagaare",
                "Dangme", "Kasem", "Gonja"
            ]
        },
        {
            "name": "SOCIAL SCIENCES DEPARTMENT (HUMANITIES)",
            "code": "SOC",
            "subjects": [
                "Social Studies (SHS)", "Social Studies", "Our World Our People", "History of Ghana",
                "History (SHS)", "Government", "Geography", "Economics",
                "Religious and Moral Education", "Christian Religious Studies", "Islamic Religious Studies"
            ]
        },
        {
            "name": "ICT & COMPUTING DEPARTMENT",
            "code": "ICT",
            "subjects": [
                "Computing", "Robotics and Coding (Form 2)", "Computer Science (Elective)",
                "ICT (Elective)", "Robotics Engineering", "Artificial Intelligence & Data Science",
                "Cybersecurity & Network Security"
            ]
        },
        {
            "name": "BUSINESS DEPARTMENT",
            "code": "BUS",
            "subjects": [
                "Business Management", "Financial Accounting", "Cost Accounting",
                "Clerical Office Duties", "Typewriting & Keyboarding"
            ]
        },
        {
            "name": "HOME ECONOMICS DEPARTMENT",
            "code": "HEC",
            "subjects": [
                "Food and Nutrition", "Clothing and Textiles", "Management in Living",
                "Sensory & Motor Skills", "Physical Development", "Catering & Hospitality",
                "Garment Making & Fashion", "Cosmetology & Beauty Therapy",
                "Physical and Health Education", "PEH (Core)"
            ]
        },
        {
            "name": "TECHNICAL & APPLIED TECHNOLOGY DEPARTMENT",
            "code": "TECH",
            "subjects": [
                "Applied Electricity", "Electronics", "Auto Mechanics", "Auto Electricals",
                "Refrigeration & Air Conditioning", "Mechanical Engineering Craft Practice",
                "Plumbing & Pipe Fitting", "Welding & Fabrication", "Building Construction",
                "Woodwork", "Metalwork", "Technical Drawing", "Career Technology",
                "Design & Communication Tech", "Design and Communication Technology",
                "Manufacturing Engineering", "Engineering Science", "Renewable Energy Technology"
            ]
        },
        {
            "name": "VISUAL ARTS & DESIGN DEPARTMENT",
            "code": "ART",
            "subjects": [
                "General Knowledge in Art", "Art and Design Foundation", "Art and Design Studio",
                "Graphic Design", "Picture Making", "Ceramics", "Sculpture", "Textiles",
                "Leatherwork", "Jewellery", "Basketry", "Creative Play & Drawing",
                "Creative Arts and Design", "Design & Communication Tech"
            ]
        }
    ]

    for ddata in department_mappings:
        dept = db.query(Department).filter(Department.name == ddata["name"]).first()
        if not dept:
            dept = db.query(Department).filter(Department.code == ddata["code"]).first()
        if not dept:
            dept = Department(name=ddata["name"], code=ddata["code"])
            db.add(dept)
            db.flush()
        
        target_subjects = db.query(Subject).filter(Subject.name.in_(ddata["subjects"])).all()
        dept.subjects = target_subjects

    db.commit()
