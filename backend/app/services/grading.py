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
    def calculate_shs_aggregate(cls, scores: list) -> int:
        """
        Calculates WASSCE 'Best 6' Aggregate.
        Criteria:
        - 4 Core Subjects: English, Maths, Int. Science, Social Studies (Required)
        - 2 Best Elective Subjects
        Returns: Total aggregate (6 to 54)
        """
        core_english = None
        core_maths = None
        core_science = None
        core_social = None

        for s in scores:
            name_lower = (s.subject.name or "").lower()
            code_upper = (s.subject.code or "").upper()

            if "english" in name_lower or code_upper == "CORE_ENG":
                if not core_english or s.total_score > core_english.total_score:
                    core_english = s
            elif ("mathematics" in name_lower or "maths" in name_lower or "math" in name_lower) and "add" not in name_lower and "elective" not in name_lower or code_upper == "CORE_MATH":
                if not core_maths or s.total_score > core_maths.total_score:
                    core_maths = s
            elif ("science" in name_lower or "sci" in name_lower) and "agricultural" not in name_lower and "elective" not in name_lower and "physics" not in name_lower and "chemistry" not in name_lower and "biology" not in name_lower or code_upper == "CORE_SCI":
                if not core_science or s.total_score > core_science.total_score:
                    core_science = s
            elif "social" in name_lower or code_upper == "CORE_SOC":
                if not core_social or s.total_score > core_social.total_score:
                    core_social = s

        total_aggregate = 0
        
        # Core English
        if core_english:
            total_aggregate += cls.get_grade_point(core_english.grade)
        else:
            total_aggregate += 9
            
        # Core Maths
        if core_maths:
            total_aggregate += cls.get_grade_point(core_maths.grade)
        else:
            total_aggregate += 9
            
        # Core Science
        if core_science:
            total_aggregate += cls.get_grade_point(core_science.grade)
        else:
            total_aggregate += 9
            
        # Core Social
        if core_social:
            total_aggregate += cls.get_grade_point(core_social.grade)
        else:
            total_aggregate += 9

        # Best 2 Electives
        all_possible_electives = []
        for s in scores:
            if s not in [core_english, core_maths, core_science, core_social]:
                all_possible_electives.append(s)
                
        elective_points = sorted([cls.get_grade_point(e.grade) for e in all_possible_electives])
        best_electives = elective_points[:2]
        
        total_aggregate += sum(best_electives)
        
        # Pad missing electives with 9
        if len(best_electives) < 2:
            total_aggregate += (2 - len(best_electives)) * 9

        return total_aggregate
