"""
Tests for Prompt 13: Grading System Edge Cases, SBA Component Weighting, and Precision.
Verifies score sanitization, boundary thresholds, SBA scaling, and WAEC/BECE aggregate calculations.
"""
import math
import unittest
from backend.app.services.grading import GradingService


class DummySubject:
    def __init__(self, id, name, code, is_core=False):
        self.id = id
        self.name = name
        self.code = code
        self.is_core = is_core


class DummyScore:
    def __init__(self, subject, grade):
        self.subject = subject
        self.grade = grade


class TestGradingEdgeCasesAndSBA(unittest.TestCase):
    def test_sanitize_score_edge_cases(self):
        """Verify sanitize_score handles None, strings, negative, NaN, Inf, and overflow."""
        self.assertEqual(GradingService.sanitize_score(None), 0.0)
        self.assertEqual(GradingService.sanitize_score(""), 0.0)
        self.assertEqual(GradingService.sanitize_score("invalid"), 0.0)
        self.assertEqual(GradingService.sanitize_score(-15.5), 0.0)
        self.assertEqual(GradingService.sanitize_score(150.0), 100.0)
        self.assertEqual(GradingService.sanitize_score(float("nan")), 0.0)
        self.assertEqual(GradingService.sanitize_score(float("inf")), 0.0)
        self.assertEqual(GradingService.sanitize_score(78.456), 78.46)

    def test_calculate_total_precision_and_weight_caps(self):
        """Verify calculate_total handles None, precision rounding, and weight caps."""
        self.assertEqual(GradingService.calculate_total(None, None), 0.0)
        self.assertEqual(GradingService.calculate_total(30.0, None), 30.0)
        self.assertEqual(GradingService.calculate_total(None, 65.0), 65.0)
        # Precision rounding
        self.assertEqual(GradingService.calculate_total(29.999, 50.001), 80.0)
        # Weight cap enforcement
        total_capped = GradingService.calculate_total(35.0, 75.0, class_weight=30.0, exam_weight=70.0)
        self.assertEqual(total_capped, 100.0)

    def test_scale_sba_components(self):
        """Verify continuous assessment components scale cleanly to target weights."""
        components = {
            "ex1": 10.0,
            "ex2": 10.0,
            "ass1": 10.0,
            "ass2": 10.0,
            "ind_proj": 20.0,
            "grp_work": 10.0,
            "pract_work": 10.0,
            "mid_sem": 0.0
        }
        # Raw sum = 80 out of 100
        # Scaled to 30% (SHS) -> 24.0
        shs_class = GradingService.scale_sba_components(components, target_weight=30.0, base_max=100.0)
        self.assertEqual(shs_class, 24.0)

        # Scaled to 50% (Basic School / JHS) -> 40.0
        basic_class = GradingService.scale_sba_components(components, target_weight=50.0, base_max=100.0)
        self.assertEqual(basic_class, 40.0)

        # Empty / None handling
        self.assertEqual(GradingService.scale_sba_components(None), 0.0)
        self.assertEqual(GradingService.scale_sba_components({}, target_weight=30.0), 0.0)

    def test_waec_boundary_scores(self):
        """Verify exact WAEC grade boundary transitions."""
        # 80 boundary
        self.assertEqual(GradingService.get_grade(80.0)["grade"], "A1")
        self.assertEqual(GradingService.get_grade(79.99)["grade"], "B2")
        # 70 boundary
        self.assertEqual(GradingService.get_grade(70.0)["grade"], "B2")
        self.assertEqual(GradingService.get_grade(69.99)["grade"], "B3")
        # 50 boundary
        self.assertEqual(GradingService.get_grade(50.0)["grade"], "C6")
        self.assertEqual(GradingService.get_grade(49.99)["grade"], "D7")
        # 40 boundary
        self.assertEqual(GradingService.get_grade(40.0)["grade"], "E8")
        self.assertEqual(GradingService.get_grade(39.99)["grade"], "F9")

    def test_shs_aggregate_empty_and_partial_handling(self):
        """Verify WAEC Best 6 aggregate handles empty or incomplete score sets safely."""
        # Completely empty scores -> default aggregate 54
        self.assertEqual(GradingService.calculate_shs_aggregate([]), 54)

        # Partial scores (only 2 cores, 1 elective)
        core1 = DummySubject(1, "Core Mathematics", "CORE_MATH", is_core=True)
        core2 = DummySubject(2, "English Language", "CORE_ENG", is_core=True)
        elec1 = DummySubject(3, "Elective Physics", "ELEC_PHY", is_core=False)

        scores = [
            DummyScore(core1, "A1"),  # point 1
            DummyScore(core2, "B2"),  # point 2
            DummyScore(elec1, "A1"),  # point 1
        ]
        # Top cores: [1, 2], missing 1 core -> +9 = 12
        # Top electives: [1], missing 2 electives -> +18 = 19
        # Total aggregate = 12 + 19 = 31
        aggregate = GradingService.calculate_shs_aggregate(scores)
        self.assertEqual(aggregate, 31)


if __name__ == "__main__":
    unittest.main()
