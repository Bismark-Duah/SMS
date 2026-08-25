class GradingService:
    @staticmethod
    def calculate_total(class_score: float, exam_score: float) -> float:
        """Calculates total based on 30% class and 70% exam weightage."""
        return class_score + exam_score

    @staticmethod
    def get_grade(total: float, db = None) -> dict:
        """Returns grade and remark for a given total score (0-100)."""
        close_db = False
        if db is None:
            from ..database import SessionLocal
            db = SessionLocal()
            close_db = True
            
        try:
            from ..models import Setting
            import json
            
            standard_setting = db.query(Setting).filter(Setting.key == "grading_standard").first()
            school_mode_setting = db.query(Setting).filter(Setting.key == "school_mode").first()
            mode = school_mode_setting.value if school_mode_setting else "COMBINED"
            standard = standard_setting.value if standard_setting else ("BECE" if mode == "BASIC_ONLY" else "WAEC")
            
            if standard == "CUSTOM":
                rules_setting = db.query(Setting).filter(Setting.key == "grading_rules").first()
                if rules_setting and rules_setting.value:
                    rules = json.loads(rules_setting.value)
                    rules = sorted(rules, key=lambda x: x.get("min_score", 0), reverse=True)
                    for rule in rules:
                        if total >= rule.get("min_score", 0):
                            return {"grade": str(rule.get("grade")), "remark": str(rule.get("remark"))}

            if standard == "BECE":
                if total >= 80:
                    return {"grade": "1", "remark": "EXCELLENT"}
                elif total >= 70:
                    return {"grade": "2", "remark": "VERY GOOD"}
                elif total >= 60:
                    return {"grade": "3", "remark": "GOOD"}
                elif total >= 55:
                    return {"grade": "4", "remark": "CREDIT"}
                elif total >= 50:
                    return {"grade": "5", "remark": "CREDIT"}
                elif total >= 45:
                    return {"grade": "6", "remark": "PASS"}
                elif total >= 40:
                    return {"grade": "7", "remark": "PASS"}
                elif total >= 35:
                    return {"grade": "8", "remark": "WEAK PASS"}
                else:
                    return {"grade": "9", "remark": "FAIL"}
            else:
                if total >= 80:
                    return {"grade": "A1", "remark": "Excellent"}
                elif total >= 70:
                    return {"grade": "B2", "remark": "Very Good"}
                elif total >= 60:
                    return {"grade": "B3", "remark": "Good"}
                elif total >= 55:
                    return {"grade": "C4", "remark": "Credit"}
                elif total >= 50:
                    return {"grade": "C5", "remark": "Credit"}
                elif total >= 45:
                    return {"grade": "C6", "remark": "Credit"}
                elif total >= 40:
                    return {"grade": "D7", "remark": "Pass"}
                elif total >= 35:
                    return {"grade": "E8", "remark": "Pass"}
                else:
                    return {"grade": "F9", "remark": "Fail"}
        finally:
            if close_db:
                db.close()

    @staticmethod
    def get_grade_point(grade: str, db = None) -> int:
        """Returns the grade point (1-9) for a given grade string."""
        close_db = False
        if db is None:
            from ..database import SessionLocal
            db = SessionLocal()
            close_db = True
            
        try:
            from ..models import Setting
            import json
            
            standard_setting = db.query(Setting).filter(Setting.key == "grading_standard").first()
            standard = standard_setting.value if standard_setting else "WAEC"
            
            if standard == "CUSTOM":
                rules_setting = db.query(Setting).filter(Setting.key == "grading_rules").first()
                if rules_setting and rules_setting.value:
                    rules = json.loads(rules_setting.value)
                    for rule in rules:
                        if str(rule.get("grade")) == str(grade):
                            return int(rule.get("point", 9))
            
            points = {
                "1": 1, "2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7, "8": 8, "9": 9,
                "A1": 1, "B2": 2, "B3": 3, "C4": 4, "C5": 5, "C6": 6, "D7": 7, "E8": 8, "F9": 9
            }
            return points.get(str(grade), 9)
        finally:
            if close_db:
                db.close()

    @classmethod
    def calculate_shs_aggregate_breakdown(cls, scores: list, student = None) -> dict:
        """
        Calculates official WAEC/GES 'Best 6' Aggregate and returns detailed breakdown.
        Criteria:
        - Top 3 Track Core Subjects (e.g. English, Core Maths, Social/Science based on program track)
        - Top 3 Best Elective Subjects (from 3, 4, 5, 6+ electives)
        Returns:
        {
            "aggregate": int (6 to 54),
            "qualifying_cores": list,
            "qualifying_electives": list,
            "all_cores": list,
            "all_electives": list
        }
        """
        if not scores:
            return {
                "aggregate": 54,
                "qualifying_cores": [],
                "qualifying_electives": [],
                "all_cores": [],
                "all_electives": []
            }

        # 1. Determine Track Core Subjects
        configured_core_ids = set()
        if student and hasattr(student, 'program') and student.program and hasattr(student.program, 'core_subjects') and student.program.core_subjects:
            configured_core_ids = {s.id for s in student.program.core_subjects}

        core_scores = []
        elective_scores = []

        for s in scores:
            if not s.subject:
                elective_scores.append(s)
                continue

            sub_id = s.subject.id
            sub_name = (s.subject.name or "").lower()
            sub_code = (s.subject.code or "").upper()
            is_sub_core = getattr(s.subject, 'is_core', False)

            if configured_core_ids:
                if sub_id in configured_core_ids:
                    core_scores.append(s)
                else:
                    elective_scores.append(s)
            else:
                # Fallback heuristic for standard core identification
                if is_sub_core or sub_code.startswith("CORE_") or any(k in sub_name for k in ["english language", "core mathematics", "integrated science", "social studies"]):
                    if "elective" not in sub_name and "add" not in sub_name:
                        core_scores.append(s)
                    else:
                        elective_scores.append(s)
                else:
                    elective_scores.append(s)

        # 2. Sort Core Scores (lowest point = best grade)
        sorted_cores = sorted(core_scores, key=lambda x: cls.get_grade_point(x.grade, None))
        top_cores = sorted_cores[:3]

        # 3. Sort Elective Scores (lowest point = best grade)
        sorted_electives = sorted(elective_scores, key=lambda x: cls.get_grade_point(x.grade, None))
        top_electives = sorted_electives[:3]

        # 4. Calculate Aggregate (Sum of Top 3 Cores + Top 3 Electives)
        total_aggregate = 0

        for c in top_cores:
            total_aggregate += cls.get_grade_point(c.grade, None)

        # If fewer than 3 cores were sat, pad missing required slots with 9
        if len(top_cores) < 3:
            total_aggregate += (3 - len(top_cores)) * 9

        for e in top_electives:
            total_aggregate += cls.get_grade_point(e.grade, None)

        # If fewer than 3 electives were sat, pad missing required slots with 9
        if len(top_electives) < 3:
            total_aggregate += (3 - len(top_electives)) * 9

        return {
            "aggregate": total_aggregate,
            "qualifying_cores": [
                {"subject_name": c.subject.name if c.subject else "Core", "grade": c.grade, "point": cls.get_grade_point(c.grade)}
                for c in top_cores
            ],
            "qualifying_electives": [
                {"subject_name": e.subject.name if e.subject else "Elective", "grade": e.grade, "point": cls.get_grade_point(e.grade)}
                for e in top_electives
            ],
            "all_cores_count": len(core_scores),
            "all_electives_count": len(elective_scores)
        }

    @classmethod
    def calculate_shs_aggregate(cls, scores: list, student = None) -> int:
        """
        Calculates WASSCE 'Best 6' Aggregate (Top 3 Track Cores + Top 3 Electives).
        Returns integer aggregate between 6 and 54.
        """
        breakdown = cls.calculate_shs_aggregate_breakdown(scores, student)
        return breakdown["aggregate"]

