"""
curriculum_presets.py - Ghanaian Academic Curriculum Presets and Timetable Templates.
Supports:
1. Public Basic Schools (Statutory GES / NaCCA Layout)
2. Private Basic Schools (Autonomous Custom Hours & Enrichment Subjects)
3. Senior High Schools (SHS Department Track Layouts)
"""

from typing import Dict, Any, List

# ── Role Workload & Period Caps ───────────────────────────────────────────────
ROLE_WORKLOAD_LIMITS: Dict[str, Dict[str, Any]] = {
    "SCHOOL_ADMINISTRATOR": {
        "title": "School Administrator (Office & IT)",
        "min_periods": 0,
        "max_periods": 0,
        "default_cap": 0,
        "is_exempt": True,
        "description": "100% Exempt from teaching for SIS records, portal management, and office administration."
    },
    "ADMIN": {
        "title": "School Administrator / IT Admin",
        "min_periods": 0,
        "max_periods": 0,
        "default_cap": 0,
        "is_exempt": True,
        "description": "100% Exempt from teaching for administrative, IT, and campus management duties."
    },
    "SECRETARY": {
        "title": "School Secretary / Registrar",
        "min_periods": 0,
        "max_periods": 0,
        "default_cap": 0,
        "is_exempt": True,
        "description": "100% Exempt from teaching for secretarial, admissions, correspondence, and recordkeeping duties."
    },
    "SCHOOL_SECRETARY": {
        "title": "School Secretary / Registrar",
        "min_periods": 0,
        "max_periods": 0,
        "default_cap": 0,
        "is_exempt": True,
        "description": "100% Exempt from teaching for secretarial, admissions, correspondence, and recordkeeping duties."
    },
    "HEADMASTER": {
        "title": "Headmaster / Headmistress / Principal",
        "min_periods": 0,
        "max_periods": 0,
        "default_cap": 0,
        "is_exempt": True,
        "description": "100% Exempt from teaching for overall institutional leadership and governance."
    },
    "BURSAR": {
        "title": "Bursar / Financial Officer",
        "min_periods": 0,
        "max_periods": 0,
        "default_cap": 0,
        "is_exempt": True,
        "description": "100% Exempt from teaching for bursary, fees, and financial administration."
    },
    "ASSISTANT_HEAD_ADMIN": {
        "title": "Assistant Headmaster (Administration)",
        "min_periods": 0,
        "max_periods": 6,
        "default_cap": 0,
        "is_exempt": True,
        "description": "Senior institutional executive overseeing school administration and staff discipline. Exempt by default (0 periods)."
    },
    "ASSISTANT_HEAD_ACADEMIC": {
        "title": "Assistant Headmaster (Academic)",
        "min_periods": 0,
        "max_periods": 6,
        "default_cap": 0,
        "is_exempt": True,
        "description": "Senior institutional executive overseeing curriculum, exams, and timetables. Exempt by default (0 periods)."
    },
    "ASSISTANT_HEAD_DOMESTIC": {
        "title": "Assistant Headmaster (Domestic)",
        "min_periods": 0,
        "max_periods": 6,
        "default_cap": 0,
        "is_exempt": True,
        "description": "Senior institutional executive overseeing boarding houses and campus welfare. Exempt by default (0 periods)."
    },
    "ASSISTANT_HEAD": {
        "title": "Assistant Headmaster / Headmistress",
        "min_periods": 0,
        "max_periods": 6,
        "default_cap": 0,
        "is_exempt": True,
        "description": "Exempted by default for full-time administrative and executive duties."
    },
    "HOD": {
        "title": "Head of Department (HOD)",
        "min_periods": 10,
        "max_periods": 18,
        "default_cap": 16,
        "is_exempt": False,
        "description": "Reduced teaching load for departmental supervision, vetting, and lab inventory."
    },
    "HOUSEMASTER": {
        "title": "Senior Housemaster / Housemistress",
        "min_periods": 12,
        "max_periods": 20,
        "default_cap": 18,
        "is_exempt": False,
        "description": "Reduced load for boarding house inspections, roll-calls, and student welfare."
    },
    "COUNSELOR": {
        "title": "Guidance & Counseling Coordinator",
        "min_periods": 10,
        "max_periods": 18,
        "default_cap": 16,
        "is_exempt": False,
        "description": "Protected free periods during school hours for student counseling sessions."
    },
    "SPORTS_MASTER": {
        "title": "Sports Master / Physical Education Head",
        "min_periods": 12,
        "max_periods": 22,
        "default_cap": 18,
        "is_exempt": False,
        "description": "Protected afternoon periods for team training and sports administration."
    },
    "REGULAR_TEACHER": {
        "title": "Subject Master / Teacher",
        "min_periods": 18,
        "max_periods": 28,
        "default_cap": 26,
        "is_exempt": False,
        "description": "Standard full-time teaching workload."
    }
}


# ── Break & Special Activity Presets ─────────────────────────────────────────
DEFAULT_BREAK_SCHEDULES: Dict[str, List[Dict[str, Any]]] = {
    "PUBLIC_BASIC": [
        {
            "title": "MORNING DEVOTION & ASSEMBLY",
            "type": "assembly",
            "time": "07:30 - 08:00",
            "before_period": 1,
            "days": [0, 1, 2, 3, 4]
        },
        {
            "title": "SNACK & BREAKFAST BREAK",
            "type": "snack_break",
            "time": "09:30 - 09:50",
            "after_period": 2,
            "days": [0, 1, 2, 3, 4]
        },
        {
            "title": "MID-DAY LUNCH & RECESS",
            "type": "lunch_break",
            "time": "11:20 - 12:00",
            "after_period": 4,
            "days": [0, 1, 2, 3, 4]
        }
    ],
    "PRIVATE_BASIC": [
        {
            "title": "MORNING WORSHIP & DEVOTION",
            "type": "assembly",
            "time": "07:30 - 08:00",
            "before_period": 1,
            "days": [0, 1, 2, 3, 4]
        },
        {
            "title": "SNACK & FRUIT BREAK",
            "type": "snack_break",
            "time": "09:30 - 10:00",
            "after_period": 2,
            "days": [0, 1, 2, 3, 4]
        },
        {
            "title": "MID-DAY LUNCH BREAK",
            "type": "lunch_break",
            "time": "12:00 - 12:45",
            "after_period": 5,
            "days": [0, 1, 2, 3, 4]
        },
        {
            "title": "EXTRA-CURRICULAR & CLUBS",
            "type": "clubs",
            "time": "02:45 - 03:30",
            "after_period": 7,
            "days": [2, 4]  # Wednesday and Friday
        }
    ],
    "SHS": [
        {
            "title": "DAILY MORNING ASSEMBLY / DEVOTION",
            "type": "assembly",
            "time": "07:30 - 08:00",
            "before_period": 1,
            "days": [0, 1, 3, 4]  # Mon, Tue, Thu, Fri
        },
        {
            "title": "MID-WEEK CHAPEL / SCHOOL WORSHIP SERVICE",
            "type": "chapel",
            "time": "07:30 - 08:45",
            "replaces_period": 1,
            "days": [2]  # Wednesday
        },
        {
            "title": "BREAKFAST & SNACK BREAK",
            "type": "snack_break",
            "time": "09:30 - 09:50",
            "after_period": 2,
            "days": [0, 1, 2, 3, 4]
        },
        {
            "title": "MID-DAY LUNCH BREAK",
            "type": "lunch_break",
            "time": "11:20 - 12:00",
            "after_period": 4,
            "days": [0, 1, 2, 3, 4]
        },
        {
            "title": "CO-CURRICULAR / SPORTS & PHYSICAL EDUCATION",
            "type": "sports",
            "time": "01:30 - 02:45",
            "after_period": 6,
            "days": [4]  # Friday afternoon
        }
    ]
}


# ── Default Subject Period Quotas & Lab Requirements ─────────────────────────
DEFAULT_SUBJECT_CONFIGS: Dict[str, Dict[str, Any]] = {
    # ── SHS Core Subjects ──
    "Core Mathematics": {"weekly_periods": 6, "is_core": True, "requires_double_period": False, "requires_lab": False, "category": "SHS_CORE"},
    "English Language": {"weekly_periods": 6, "is_core": True, "requires_double_period": False, "requires_lab": False, "category": "SHS_CORE"},
    "Integrated Science": {"weekly_periods": 6, "is_core": True, "requires_double_period": True, "requires_lab": True, "default_room": "Science Lab", "category": "SHS_CORE"},
    "Social Studies": {"weekly_periods": 4, "is_core": True, "requires_double_period": False, "requires_lab": False, "category": "SHS_CORE"},
    "Information and Communication Technology": {"weekly_periods": 3, "is_core": True, "requires_double_period": True, "requires_lab": True, "default_room": "ICT Lab", "category": "SHS_CORE"},
    "Physical Education": {"weekly_periods": 2, "is_core": True, "requires_double_period": False, "requires_lab": False, "category": "SHS_CORE"},

    # ── SHS Science Electives ──
    "Physics": {"weekly_periods": 6, "is_core": False, "requires_double_period": True, "requires_lab": True, "default_room": "Physics Lab", "category": "SHS_SCIENCE"},
    "Chemistry": {"weekly_periods": 6, "is_core": False, "requires_double_period": True, "requires_lab": True, "default_room": "Chemistry Lab", "category": "SHS_SCIENCE"},
    "Biology": {"weekly_periods": 6, "is_core": False, "requires_double_period": True, "requires_lab": True, "default_room": "Biology Lab", "category": "SHS_SCIENCE"},
    "Elective Mathematics": {"weekly_periods": 6, "is_core": False, "requires_double_period": False, "requires_lab": False, "category": "SHS_SCIENCE"},

    # ── SHS Business Electives ──
    "Financial Accounting": {"weekly_periods": 6, "is_core": False, "requires_double_period": False, "requires_lab": False, "category": "SHS_BUSINESS"},
    "Cost Accounting": {"weekly_periods": 5, "is_core": False, "requires_double_period": False, "requires_lab": False, "category": "SHS_BUSINESS"},
    "Business Management": {"weekly_periods": 5, "is_core": False, "requires_double_period": False, "requires_lab": False, "category": "SHS_BUSINESS"},
    "Economics": {"weekly_periods": 5, "is_core": False, "requires_double_period": False, "requires_lab": False, "category": "SHS_BUSINESS"},

    # ── SHS General Arts Electives ──
    "Government": {"weekly_periods": 4, "is_core": False, "requires_double_period": False, "requires_lab": False, "category": "SHS_ARTS"},
    "Literature-in-English": {"weekly_periods": 5, "is_core": False, "requires_double_period": False, "requires_lab": False, "category": "SHS_ARTS"},
    "History": {"weekly_periods": 4, "is_core": False, "requires_double_period": False, "requires_lab": False, "category": "SHS_ARTS"},
    "Geography": {"weekly_periods": 5, "is_core": False, "requires_double_period": False, "requires_lab": False, "category": "SHS_ARTS"},
    "Christian Religious Studies": {"weekly_periods": 4, "is_core": False, "requires_double_period": False, "requires_lab": False, "category": "SHS_ARTS"},
    "Islamic Studies": {"weekly_periods": 4, "is_core": False, "requires_double_period": False, "requires_lab": False, "category": "SHS_ARTS"},
    "French": {"weekly_periods": 4, "is_core": False, "requires_double_period": False, "requires_lab": False, "category": "SHS_ARTS"},

    # ── SHS Home Economics & Visual Arts ──
    "Food and Nutrition": {"weekly_periods": 6, "is_core": False, "requires_double_period": True, "requires_lab": True, "default_room": "Home Econ Kitchen", "category": "SHS_VOCATIONAL"},
    "Clothing and Textiles": {"weekly_periods": 6, "is_core": False, "requires_double_period": True, "requires_lab": True, "default_room": "Textiles Workshop", "category": "SHS_VOCATIONAL"},
    "Management in Living": {"weekly_periods": 4, "is_core": False, "requires_double_period": False, "requires_lab": False, "category": "SHS_VOCATIONAL"},
    "General Knowledge in Art": {"weekly_periods": 5, "is_core": False, "requires_double_period": False, "requires_lab": False, "category": "SHS_ARTS"},
    "Graphic Design": {"weekly_periods": 6, "is_core": False, "requires_double_period": True, "requires_lab": True, "default_room": "Art Studio", "category": "SHS_ARTS"},
    "Picture Making": {"weekly_periods": 6, "is_core": False, "requires_double_period": True, "requires_lab": True, "default_room": "Art Studio", "category": "SHS_ARTS"},
    "Sculpture": {"weekly_periods": 6, "is_core": False, "requires_double_period": True, "requires_lab": True, "default_room": "Art Studio", "category": "SHS_ARTS"},

    # ── SHS Agricultural Science ──
    "General Agriculture": {"weekly_periods": 6, "is_core": False, "requires_double_period": True, "requires_lab": True, "default_room": "Agric Lab", "category": "SHS_AGRIC"},
    "Horticulture": {"weekly_periods": 5, "is_core": False, "requires_double_period": True, "requires_lab": False, "category": "SHS_AGRIC"},
    "Animal Husbandry": {"weekly_periods": 5, "is_core": False, "requires_double_period": True, "requires_lab": False, "category": "SHS_AGRIC"},

    # ── Basic School (Primary & JHS) Standard Curriculum ──
    "Mathematics": {"weekly_periods": 6, "is_core": True, "requires_double_period": False, "requires_lab": False, "category": "BASIC_CORE"},
    "English Language": {"weekly_periods": 7, "is_core": True, "requires_double_period": False, "requires_lab": False, "category": "BASIC_CORE"},
    "Integrated Science (Basic)": {"weekly_periods": 5, "is_core": True, "requires_double_period": True, "requires_lab": False, "category": "BASIC_CORE"},
    "Our World Our People (OWOP)": {"weekly_periods": 4, "is_core": True, "requires_double_period": False, "requires_lab": False, "category": "BASIC_CORE"},
    "Ghanaian Language & Culture": {"weekly_periods": 4, "is_core": True, "requires_double_period": False, "requires_lab": False, "category": "BASIC_CORE"},
    "Religious & Moral Education (RME)": {"weekly_periods": 3, "is_core": True, "requires_double_period": False, "requires_lab": False, "category": "BASIC_CORE"},
    "Creative Arts & Design": {"weekly_periods": 3, "is_core": True, "requires_double_period": True, "requires_lab": False, "category": "BASIC_CORE"},
    "Career Technology": {"weekly_periods": 3, "is_core": True, "requires_double_period": True, "requires_lab": False, "category": "BASIC_CORE"},
    "Computing (Basic)": {"weekly_periods": 3, "is_core": True, "requires_double_period": True, "requires_lab": True, "default_room": "ICT Lab", "category": "BASIC_CORE"},
    "Physical & Health Education (PHE)": {"weekly_periods": 2, "is_core": True, "requires_double_period": False, "requires_lab": False, "category": "BASIC_CORE"},

    # ── Private Basic School Enrichment Subjects ──
    "Phonics & Diction": {"weekly_periods": 3, "is_core": True, "requires_double_period": False, "requires_lab": False, "category": "PRIVATE_ENRICHMENT"},
    "Coding & Robotics": {"weekly_periods": 2, "is_core": False, "requires_double_period": True, "requires_lab": True, "default_room": "Robotics Lab", "category": "PRIVATE_ENRICHMENT"},
    "French (Basic)": {"weekly_periods": 3, "is_core": False, "requires_double_period": False, "requires_lab": False, "category": "PRIVATE_ENRICHMENT"},
    "Abacus & Mental Arithmetic": {"weekly_periods": 2, "is_core": False, "requires_double_period": False, "requires_lab": False, "category": "PRIVATE_ENRICHMENT"},
    "Music & Dance": {"weekly_periods": 2, "is_core": False, "requires_double_period": False, "requires_lab": False, "category": "PRIVATE_ENRICHMENT"},
}


def get_subject_config(subject_name: str) -> Dict[str, Any]:
    """Retrieve default period quota and lab settings for a subject, with fallback."""
    if not subject_name:
        return {"weekly_periods": 4, "is_core": True, "requires_double_period": False, "requires_lab": False}
    
    for name, cfg in DEFAULT_SUBJECT_CONFIGS.items():
        if name.lower() == subject_name.strip().lower():
            return cfg
        if subject_name.strip().lower() in name.lower() or name.lower() in subject_name.strip().lower():
            return cfg
    
    # Sensible default fallback
    return {
        "weekly_periods": 4,
        "is_core": True,
        "requires_double_period": False,
        "requires_lab": False
    }
