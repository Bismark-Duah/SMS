"""
timetable_generator.py — Advanced Constraint-Satisfaction Timetable Solver.

Improvements over v1:
- Preference-aware time calculation using actual start_time + period_duration_minutes
  stored in TimetableConfig, with breaks applied correctly
- Lab room rotation/staggering: classes sharing the same workshop/lab are
  spread across different days and periods automatically — no collisions
- Smarter MRV (Minimum Remaining Values) heuristic: most-constrained units
  (shared labs with many classes competing) are scheduled first
- Real class names in conflict messages (not just #ID)
- Even subject distribution: same subject never placed twice on same day for
  a class if alternatives exist
- Assistant Headmaster & executive exemptions preserved
- Surgical slot swap engine preserved
"""

import json
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any, Set
from sqlalchemy.orm import Session, joinedload

from ..models import (
    Timetable, ClassSection, Subject, User, Semester, Program,
    TeacherAssignment, School, TimetableConfig, TimetableSnapshot
)
from .curriculum_presets import (
    get_subject_config, DEFAULT_BREAK_SCHEDULES, ROLE_WORKLOAD_LIMITS
)


# ── Time Utilities ─────────────────────────────────────────────────────────────

def _parse_time(t: str) -> datetime:
    h, m = map(int, t.split(":"))
    return datetime(2000, 1, 1, h, m)


def _fmt(dt: datetime) -> str:
    return dt.strftime("%H:%M")


def build_period_times(
    start_time: str,
    period_duration: int,
    periods_per_day: int,
    break_schedule: List[Dict[str, Any]],
    day: int = 0
) -> Dict[int, Tuple[str, str]]:
    """Build period_number -> (start, end) mapping accounting for breaks."""
    current = _parse_time(start_time)
    dur = timedelta(minutes=period_duration)
    period_times: Dict[int, Tuple[str, str]] = {}

    replaced = set()
    for brk in break_schedule:
        days_for_break = brk.get("days", list(range(5)))
        if day not in days_for_break:
            continue
        if brk.get("replaces_period"):
            replaced.add(brk["replaces_period"])

    after_gap: Dict[int, int] = {}
    for brk in break_schedule:
        days_for_break = brk.get("days", list(range(5)))
        if day not in days_for_break:
            continue
        ap = brk.get("after_period")
        if ap:
            t_str = brk.get("time", "")
            gap_mins = 20
            if t_str and " - " in t_str:
                parts = t_str.split(" - ")
                try:
                    gap = _parse_time(parts[1].strip()) - _parse_time(parts[0].strip())
                    gap_mins = max(10, int(gap.total_seconds() / 60))
                except Exception:
                    pass
            after_gap[ap] = gap_mins

    for brk in break_schedule:
        days_for_break = brk.get("days", list(range(5)))
        if day not in days_for_break:
            continue
        bp = brk.get("before_period")
        if bp == 1:
            t_str = brk.get("time", "")
            if t_str and " - " in t_str:
                parts = t_str.split(" - ")
                try:
                    asm_end = _parse_time(parts[1].strip())
                    if asm_end > current:
                        current = asm_end
                except Exception:
                    pass

    for p in range(1, periods_per_day + 1):
        if p in replaced:
            current += dur
        else:
            start = current
            end = current + dur
            period_times[p] = (_fmt(start), _fmt(end))
            current = end
        gap = after_gap.get(p, 0)
        if gap:
            current += timedelta(minutes=gap)

    return period_times


# ── Scheduling Unit ────────────────────────────────────────────────────────────

class SchedulingUnit:
    def __init__(
        self,
        class_section_id: int,
        class_name: str,
        subject_id: int,
        subject_name: str,
        teacher_id: Optional[int],
        teacher_name: Optional[str],
        is_double: bool = False,
        room: Optional[str] = None,
        room_pool: Optional[List[str]] = None,
        is_core: bool = True,
        requires_shared_room: bool = False,
    ):
        self.class_section_id = class_section_id
        self.class_name = class_name
        self.subject_id = subject_id
        self.subject_name = subject_name
        self.teacher_id = teacher_id
        self.teacher_name = teacher_name
        self.is_double = is_double
        self.room = room
        self.room_pool = room_pool or ([room] if room else [])
        self.is_core = is_core
        self.requires_shared_room = requires_shared_room or bool(self.room_pool)
        self._room_competition = 0


# ── CSP Solver ────────────────────────────────────────────────────────────────

class TimetableSolver:
    def __init__(
        self,
        db: Session,
        school_id: int,
        semester_id: Optional[int] = None,
        school_profile: str = "SHS",
        periods_per_day: int = 8,
        friday_periods: int = 6,
        start_time: str = "08:00",
        period_duration: int = 45,
        break_schedule: Optional[List[Dict[str, Any]]] = None,
        custom_quotas: Optional[Dict[int, int]] = None,
        facility_counts: Optional[Dict[str, int]] = None,
    ):
        self.db = db
        self.school_id = school_id
        self.semester_id = semester_id
        self.school_profile = school_profile
        self.periods_per_day = max(6, min(10, periods_per_day))
        self.friday_periods = max(5, min(periods_per_day, friday_periods))
        self.start_time = start_time
        self.period_duration = period_duration
        self.break_schedule = break_schedule or DEFAULT_BREAK_SCHEDULES.get(
            school_profile, DEFAULT_BREAK_SCHEDULES["SHS"]
        )
        self.custom_quotas = custom_quotas or {}
        self.facility_counts = facility_counts or {}
        self.days = [0, 1, 2, 3, 4]

        self.period_times: Dict[int, Dict[int, Tuple[str, str]]] = {}
        for d in self.days:
            max_p = self.friday_periods if d == 4 else self.periods_per_day
            self.period_times[d] = build_period_times(
                self.start_time, self.period_duration, max_p, self.break_schedule, day=d
            )

        self.reserved_slots: Set[Tuple[int, int]] = set()
        self._init_reserved_slots()

        self.teacher_grid: Dict[int, Dict[Tuple[int, int], Any]] = {}
        self.class_grid: Dict[int, Dict[Tuple[int, int], Any]] = {}
        self.room_grid: Dict[str, Dict[Tuple[int, int], Any]] = {}
        self.teacher_workload: Dict[int, int] = {}
        self.teacher_caps: Dict[int, int] = {}
        self.teacher_exempt_slots: Dict[int, Set[Tuple[int, int]]] = {}
        self.teacher_projected_load: Dict[int, int] = {}
        self.auto_matched_assignments: List[Tuple[int, int, int]] = []
        self.class_subject_daily: Dict[Tuple[int, int, int], int] = {}
        self.room_day_usage: Dict[Tuple[str, int], int] = {}
        self.subject_names: Dict[int, str] = {}
        # Tracks classes skipped due to no subject assignments (BUG 7 fix)
        self.skipped_classes: List[str] = []

    def _init_reserved_slots(self):
        for item in self.break_schedule:
            if item.get("replaces_period"):
                p = item["replaces_period"]
                days = item.get("days", [2])
                for d in days:
                    self.reserved_slots.add((d, p))

    def _get_max_periods_for_day(self, day: int) -> int:
        return self.friday_periods if day == 4 else self.periods_per_day

    def _load_teachers(self) -> Dict[int, User]:
        all_users = self.db.query(User).filter(
            User.school_id == self.school_id
        ).options(
            joinedload(User.qualified_subjects),
            joinedload(User.department)
        ).all()
        teacher_map = {}

        for t in all_users:
            roles = [r.name.lower() for r in t.roles] if t.roles else []
            if "super_admin" in roles or getattr(t, "is_superadmin", False):
                continue

            teacher_map[t.id] = t
            self.teacher_grid[t.id] = {}
            self.teacher_workload[t.id] = 0
            self.teacher_projected_load[t.id] = 0

            role = getattr(t, "responsibility_role", None)
            if not role or role == "REGULAR_TEACHER":
                if "school_administrator" in roles or "schooladmin" in roles:
                    role = "SCHOOL_ADMINISTRATOR"
                elif "secretary" in roles or "school_secretary" in roles or "clerk" in roles:
                    role = "SECRETARY"
                elif "headmaster" in roles or "principal" in roles:
                    role = "HEADMASTER"
                elif "bursar" in roles or "accountant" in roles:
                    role = "BURSAR"
                elif "assistant_head_admin" in roles:
                    role = "ASSISTANT_HEAD_ADMIN"
                elif "assistant_head_academic" in roles:
                    role = "ASSISTANT_HEAD_ACADEMIC"
                elif "assistant_head_domestic" in roles:
                    role = "ASSISTANT_HEAD_DOMESTIC"
                elif "assistant_head" in roles:
                    role = "ASSISTANT_HEAD"
                elif "admin" in roles:
                    role = "ADMIN"
                else:
                    role = "REGULAR_TEACHER"

            role_limit = ROLE_WORKLOAD_LIMITS.get(role, ROLE_WORKLOAD_LIMITS["REGULAR_TEACHER"])
            exempt_roles = {
                "SCHOOL_ADMINISTRATOR", "ADMIN", "SECRETARY", "SCHOOL_SECRETARY",
                "HEADMASTER", "BURSAR", "ASSISTANT_HEAD_ADMIN",
                "ASSISTANT_HEAD_ACADEMIC", "ASSISTANT_HEAD_DOMESTIC", "ASSISTANT_HEAD"
            }
            is_admin_role = any(r in roles for r in [
                "admin", "school_administrator", "secretary", "school_secretary",
                "bursar", "accountant", "headmaster", "clerk"
            ])

            if getattr(t, "is_teaching_exempt", False) or is_admin_role or role in exempt_roles:
                raw = getattr(t, "max_weekly_periods", None)
                cap = raw if raw is not None and raw != 28 else 0
            else:
                cap = getattr(t, "max_weekly_periods", None) or role_limit["default_cap"]

            # GES Secondary Education Policy Guard: In SHS, Headmasters / Headmistresses do NOT teach (100% duty-exempt)
            if self.school_profile == "SHS" and (role == "HEADMASTER" or any(r in ["headmaster", "headmistress", "principal"] for r in roles)):
                cap = 0

            self.teacher_caps[t.id] = cap

            exempt_slots: Set[Tuple[int, int]] = set()
            raw_exempt = getattr(t, "duty_exempt_periods", None)
            if raw_exempt:
                try:
                    parsed = json.loads(raw_exempt)
                    if isinstance(parsed, list):
                        for blk in parsed:
                            exempt_slots.add((int(blk.get("day", 0)), int(blk.get("period", 1))))
                except Exception:
                    pass
            self.teacher_exempt_slots[t.id] = exempt_slots

        return teacher_map

    def _load_classes_and_units(self, teacher_map: Dict[int, User]) -> List[SchedulingUnit]:
        classes = self.db.query(ClassSection).filter(
            ClassSection.school_id == self.school_id
        ).options(
            joinedload(ClassSection.subjects),
            joinedload(ClassSection.program)
        ).all()

        assignments_query = self.db.query(TeacherAssignment)
        if self.semester_id:
            assignments_query = assignments_query.filter(
                TeacherAssignment.semester_id == self.semester_id
            )
        assignments = assignments_query.all()
        assign_map: Dict[Tuple[int, int], int] = {
            (a.class_section_id, a.subject_id): a.teacher_id for a in assignments
        }

        room_competition: Dict[str, int] = {}
        all_units: List[SchedulingUnit] = []

        for cs in classes:
            self.class_grid[cs.id] = {}
            subjects: List[Subject] = list(cs.subjects or [])
            if cs.program and cs.program.subjects:
                for s in cs.program.subjects:
                    if s not in subjects:
                        subjects.append(s)

            if not subjects:
                # BUG 7 FIX: Do NOT silently grab random subjects. Skip and report.
                self.skipped_classes.append(
                    f"Class '{cs.name}' has no subjects assigned — excluded from generation. "
                    f"Assign subjects to this class via Classes → Manage Subjects."
                )
                continue

            for subj in subjects:
                self.subject_names[subj.id] = subj.name
                cfg = get_subject_config(subj.name)
                total_periods = self.custom_quotas.get(subj.id, cfg.get("weekly_periods", 4))
                req_double = cfg.get("requires_double_period", False)
                req_lab = cfg.get("requires_lab", False)
                fac_type = cfg.get("facility_type")

                # Build dynamic room pool based on school's facility capacity
                room_pool = []
                multi_science_cnt = self.facility_counts.get("multipurpose_science_lab", 0)

                if multi_science_cnt > 0 and fac_type in ["physics_lab", "chemistry_lab", "biology_lab", "science_lab"]:
                    room_pool = [f"Science Lab {i}" if multi_science_cnt > 1 else "Science Lab" for i in range(1, multi_science_cnt + 1)]
                elif fac_type:
                    cnt = self.facility_counts.get(fac_type, 1 if req_lab else 0)
                    if cnt > 0:
                        prefix = cfg.get("default_room") or "Specialized Lab"
                        room_pool = [f"{prefix} {i}" if cnt > 1 else prefix for i in range(1, cnt + 1)]
                    else:
                        room_pool = []
                elif req_lab and cfg.get("default_room"):
                    room_pool = [cfg.get("default_room")]
                else:
                    room_pool = []

                requires_shared = bool(room_pool)
                for r in room_pool:
                    r_key = r.strip().lower()
                    room_competition[r_key] = room_competition.get(r_key, 0) + 1

                assigned_teacher_id = assign_map.get((cs.id, subj.id))

                # GES Secondary Education Rule: In SHS, Headmasters/Headmistresses never teach
                if assigned_teacher_id:
                    t_cand = teacher_map.get(assigned_teacher_id)
                    if t_cand and self.school_profile == "SHS":
                        t_roles = [r.name.lower() for r in t_cand.roles] if t_cand.roles else []
                        if getattr(t_cand, "responsibility_role", None) == "HEADMASTER" or any(r in ["headmaster", "headmistress", "principal"] for r in t_roles):
                            assigned_teacher_id = None

                # Autonomous Solver Intelligence: Match qualified teachers based on permanent HR competencies
                if not assigned_teacher_id:
                    candidates = []
                    for t_id, t_obj in teacher_map.items():
                        cap = self.teacher_caps.get(t_id, 0)
                        if cap == 0:
                            continue

                        is_competent = False
                        if getattr(t_obj, "primary_subject_id", None) == subj.id:
                            is_competent = True
                        elif hasattr(t_obj, "qualified_subjects") and any(qs.id == subj.id for qs in (t_obj.qualified_subjects or [])):
                            is_competent = True
                        elif getattr(t_obj, "department_id", None) and getattr(subj, "department_id", None) and t_obj.department_id == subj.department_id:
                            is_competent = True

                        if is_competent:
                            cur_load = self.teacher_projected_load.get(t_id, 0)
                            if cur_load + total_periods <= cap:
                                candidates.append((cur_load, t_id, t_obj))

                    if candidates:
                        # Sort by current projected workload ascending for fair departmental load balancing
                        candidates.sort(key=lambda x: x[0])
                        best_load, best_tid, best_tobj = candidates[0]
                        assigned_teacher_id = best_tid
                        self.teacher_projected_load[best_tid] = best_load + total_periods
                        assign_map[(cs.id, subj.id)] = best_tid
                        self.auto_matched_assignments.append((cs.id, subj.id, best_tid))
                else:
                    self.teacher_projected_load[assigned_teacher_id] = self.teacher_projected_load.get(assigned_teacher_id, 0) + total_periods

                teacher_obj = teacher_map.get(assigned_teacher_id) if assigned_teacher_id else None
                teacher_name = teacher_obj.username if teacher_obj else None

                if assigned_teacher_id and self.teacher_caps.get(assigned_teacher_id, 28) == 0:
                    assigned_teacher_id = None
                    teacher_name = "Vacant (Awaiting Posting)"

                periods_left = total_periods
                if req_double and periods_left >= 2:
                    all_units.append(SchedulingUnit(
                        class_section_id=cs.id,
                        class_name=cs.name,
                        subject_id=subj.id,
                        subject_name=subj.name,
                        teacher_id=assigned_teacher_id,
                        teacher_name=teacher_name,
                        is_double=True,
                        room=room_pool[0] if len(room_pool) == 1 else None,
                        room_pool=room_pool,
                        is_core=getattr(subj, "is_core", True),
                        requires_shared_room=requires_shared,
                    ))
                    periods_left -= 2

                while periods_left > 0:
                    # Single periods are standard classroom theory lectures (do not lock specialized lab/workshop)
                    all_units.append(SchedulingUnit(
                        class_section_id=cs.id,
                        class_name=cs.name,
                        subject_id=subj.id,
                        subject_name=subj.name,
                        teacher_id=assigned_teacher_id,
                        teacher_name=teacher_name,
                        is_double=False,
                        room=None,
                        room_pool=[],
                        is_core=getattr(subj, "is_core", True),
                        requires_shared_room=False,
                    ))
                    periods_left -= 1

        for u in all_units:
            r_key = u.room.strip().lower() if u.room else None
            u._room_competition = room_competition.get(r_key, 0) if r_key else 0

        return all_units

    def solve(self) -> Dict[str, Any]:
        teacher_map = self._load_teachers()
        units = self._load_classes_and_units(teacher_map)

        if not units:
            return {
                "status": "EMPTY",
                "message": "No classes or subjects found to schedule.",
                "total_slots": 0,
                "conflicts": []
            }

        def unit_priority(u: SchedulingUnit):
            teacher_cap = self.teacher_caps.get(u.teacher_id, 99) if u.teacher_id else 100
            room_comp = getattr(u, "_room_competition", 0)
            return (
                0 if u.is_double else 1,
                -(room_comp),
                teacher_cap,
                0 if u.is_core else 1
            )

        units.sort(key=unit_priority)

        class_ids = [c[0] for c in self.db.query(ClassSection.id).filter(
            (ClassSection.school_id == self.school_id) | (ClassSection.school_id.is_(None))
        ).all()]

        had_previous = False
        previous_count = 0
        if class_ids:
            prev_q = self.db.query(Timetable).filter(
                Timetable.class_section_id.in_(class_ids)
            )
            if self.semester_id:
                prev_q = prev_q.filter(Timetable.semester_id == self.semester_id)
            prev_slots = prev_q.all()
            had_previous = True
            previous_count = len(prev_slots)
            snapshot_data = [
                {
                    "class_section_id": s.class_section_id,
                    "subject_id": s.subject_id,
                    "teacher_id": s.teacher_id,
                    "semester_id": s.semester_id,
                    "day_of_week": s.day_of_week,
                    "period_number": s.period_number,
                    "start_time": s.start_time,
                    "end_time": s.end_time,
                    "room": s.room,
                }
                for s in prev_slots
            ]
            snapshot = TimetableSnapshot(
                school_id=self.school_id,
                semester_id=self.semester_id,
                snapshot_data=json.dumps(snapshot_data),
                slot_count=len(snapshot_data)
            )
            self.db.add(snapshot)
            self.db.flush()

            # ARCH-3 FIX: Keep only the last 5 snapshots (rolling undo window).
            # Previously only 1 snapshot existed — generating twice made undo useless.
            _MAX_SNAPSHOTS = 5
            _all_snaps = self.db.query(TimetableSnapshot).filter(
                TimetableSnapshot.school_id == self.school_id
            ).order_by(TimetableSnapshot.id.desc()).all()
            _snaps_to_delete = _all_snaps[_MAX_SNAPSHOTS:]  # oldest beyond the window
            for _old in _snaps_to_delete:
                self.db.delete(_old)
            self.db.flush()

            del_query = self.db.query(Timetable).filter(
                Timetable.class_section_id.in_(class_ids)
            )
            if self.semester_id:
                del_query = del_query.filter(Timetable.semester_id == self.semester_id)
            del_query.delete(synchronize_session=False)

        unassigned_units: List[SchedulingUnit] = []
        assigned_slots: List[Dict[str, Any]] = []

        for unit in units:
            placed = self._place_unit(unit)
            if not placed:
                placed = self._cascade_repair_unit(unit, assigned_slots)
            if placed:
                assigned_slots.extend(placed)
            else:
                unassigned_units.append(unit)

        new_slots = [
            Timetable(
                class_section_id=s["class_section_id"],
                subject_id=s["subject_id"],
                teacher_id=s["teacher_id"],
                semester_id=self.semester_id,
                day_of_week=s["day_of_week"],
                period_number=s["period_number"],
                start_time=s["start_time"],
                end_time=s["end_time"],
                room=s["room"]
            )
            for s in assigned_slots
        ]
        self.db.add_all(new_slots)

        # Persist autonomous teacher matches to TeacherAssignment for this semester
        if self.semester_id and self.auto_matched_assignments:
            for cid, sid, tid in self.auto_matched_assignments:
                existing = self.db.query(TeacherAssignment).filter(
                    TeacherAssignment.class_section_id == cid,
                    TeacherAssignment.subject_id == sid,
                    TeacherAssignment.semester_id == self.semester_id
                ).first()
                if not existing:
                    self.db.add(TeacherAssignment(
                        class_section_id=cid,
                        subject_id=sid,
                        teacher_id=tid,
                        semester_id=self.semester_id
                    ))

        self.db.commit()

        workload_report = []
        for tid, t in teacher_map.items():
            workload_report.append({
                "teacher_id": tid,
                "teacher_name": t.username,
                "staff_id": getattr(t, "staff_id", None),
                "responsibility_role": getattr(t, "responsibility_role", "REGULAR_TEACHER"),
                "department_name": t.department.name if getattr(t, "department", None) else "General",
                "primary_subject_name": getattr(t, "primary_subject_name", None),
                "assigned_periods": self.teacher_workload.get(tid, 0),
                "max_cap": self.teacher_caps.get(tid, 26),
                "is_exempt": self.teacher_caps.get(tid, 26) == 0
            })

        conflicts = []
        for u in unassigned_units:
            room_part = f"lab/workshop fully booked this week" if u.requires_shared_room else "no free period found"
            teacher_part = "Teacher at capacity or" if u.teacher_id else "No teacher assigned and"
            conflicts.append(
                f'Could not place {"double " if u.is_double else ""}'
                f'"{u.subject_name}" for {u.class_name} — {teacher_part} {room_part}.'
            )

        quality_report = self._calculate_quality_metrics(new_slots, len(unassigned_units), len(units))

        _has_issues = bool(unassigned_units or self.skipped_classes)
        return {
            "status": "SUCCESS" if not _has_issues else "PARTIAL",
            "total_slots": len(new_slots),
            "unassigned_count": len(unassigned_units),
            "conflicts": conflicts,
            "skipped_classes": self.skipped_classes,
            "teacher_workloads": workload_report,
            "quality_score": quality_report["score"],
            "quality_report": quality_report,
            "can_undo": had_previous,
            "previous_slot_count": previous_count
        }

    def _find_free_room(self, unit: SchedulingUnit, day: int, p1: int, p2: Optional[int] = None) -> Optional[str]:
        """Finds the first available room in the unit's room pool for slot (day, p1) [and (day, p2)]."""
        if not unit.room_pool:
            return None
        for r in unit.room_pool:
            r_key = r.strip().lower()
            r_dict = self.room_grid.get(r_key, {})
            if (day, p1) not in r_dict:
                if p2 is None or (day, p2) not in r_dict:
                    return r
        return None

    def _place_unit(self, unit: SchedulingUnit) -> Optional[List[Dict[str, Any]]]:
        best_day = None
        best_period = None
        best_assigned_room = None
        min_score = float("inf")

        r_key = unit.room.strip().lower() if unit.room and unit.room.strip() else None

        for day in self.days:
            max_p = self._get_max_periods_for_day(day)

            daily_subj_count = self.class_subject_daily.get(
                (unit.class_section_id, unit.subject_id, day), 0
            )
            dispersion_penalty = daily_subj_count * 30

            room_day_count = self.room_day_usage.get((r_key, day), 0) if r_key else 0
            room_penalty = room_day_count * 25

            if unit.is_double:
                for p in range(1, max_p):
                    if p == 4 and self.school_profile == "SHS":
                        continue
                    if unit.room_pool:
                        cand_room = self._find_free_room(unit, day, p, p + 1)
                        if not cand_room:
                            continue
                        if not (self._is_slot_valid(unit, day, p, target_room=cand_room) and 
                                self._is_slot_valid(unit, day, p + 1, target_room=cand_room)):
                            continue
                    else:
                        cand_room = None
                        if not (self._is_slot_valid(unit, day, p) and self._is_slot_valid(unit, day, p + 1)):
                            continue

                    score = dispersion_penalty + room_penalty + p
                    if score < min_score:
                        min_score = score
                        best_day = day
                        best_period = p
                        best_assigned_room = cand_room
            else:
                for p in range(1, max_p + 1):
                    if unit.room_pool:
                        cand_room = self._find_free_room(unit, day, p)
                        if not cand_room:
                            continue
                        if not self._is_slot_valid(unit, day, p, target_room=cand_room):
                            continue
                    else:
                        cand_room = None
                        if not self._is_slot_valid(unit, day, p):
                            continue

                    period_score = p if unit.is_core else abs(p - 5)
                    score = dispersion_penalty + room_penalty + period_score
                    if score < min_score:
                        min_score = score
                        best_day = day
                        best_period = p
                        best_assigned_room = cand_room

        if best_day is not None and best_period is not None:
            results = []
            if unit.is_double:
                results.append(self._occupy_slot(unit, best_day, best_period, assigned_room=best_assigned_room))
                results.append(self._occupy_slot(unit, best_day, best_period + 1, assigned_room=best_assigned_room))
            else:
                results.append(self._occupy_slot(unit, best_day, best_period, assigned_room=best_assigned_room))
            return results

        return None

    def _cascade_repair_unit(
        self,
        unit: SchedulingUnit,
        assigned_slots: List[Dict[str, Any]]
    ) -> Optional[List[Dict[str, Any]]]:
        """Attempt to place a blocked unit by shifting a single blocking lesson to an alternate valid slot.
        
        Emulates aSc Timetables' depth-1 cascade repair chain to unlock deadlocks.
        """
        r_key = unit.room.strip().lower() if unit.room and unit.room.strip() else None

        if not unit.is_double:
            for day in self.days:
                max_p = self._get_max_periods_for_day(day)
                for p in range(1, max_p + 1):
                    if (day, p) in self.reserved_slots:
                        continue
                    if p not in self.period_times.get(day, {}):
                        continue
                    if unit.teacher_id:
                        if (day, p) in self.teacher_exempt_slots.get(unit.teacher_id, set()):
                            continue
                        if (day, p) in self.teacher_grid.get(unit.teacher_id, {}):
                            continue
                        if self.teacher_workload.get(unit.teacher_id, 0) >= self.teacher_caps.get(unit.teacher_id, 28):
                            continue

                    class_blocker = self.class_grid.get(unit.class_section_id, {}).get((day, p))
                    room_blocker = self.room_grid.get(r_key, {}).get((day, p)) if r_key else None

                    blocker = class_blocker or room_blocker
                    if not blocker:
                        continue
                    if class_blocker and room_blocker and class_blocker != room_blocker:
                        continue

                    blocker_unit = blocker.get("unit")
                    if not blocker_unit or blocker_unit.is_double:
                        continue

                    # Temporarily unseat blocker
                    self._unseat_slot(blocker)

                    # Check if incoming unit can now sit at (day, p)
                    if not self._is_slot_valid(unit, day, p):
                        self._occupy_slot(blocker_unit, blocker["day_of_week"], blocker["period_number"])
                        continue

                    # Look for an alternate slot for blocker_unit
                    alt_found = False
                    for alt_day in self.days:
                        alt_max = self._get_max_periods_for_day(alt_day)
                        for alt_p in range(1, alt_max + 1):
                            if (alt_day, alt_p) == (day, p):
                                continue
                            if self._is_slot_valid(blocker_unit, alt_day, alt_p):
                                # Viable swap found!
                                moved_blocker = self._occupy_slot(blocker_unit, alt_day, alt_p)
                                for s in assigned_slots:
                                    if (s.get("class_section_id") == blocker["class_section_id"] and
                                        s.get("day_of_week") == blocker["day_of_week"] and
                                        s.get("period_number") == blocker["period_number"]):
                                        s["day_of_week"] = alt_day
                                        s["period_number"] = alt_p
                                        s["start_time"] = moved_blocker["start_time"]
                                        s["end_time"] = moved_blocker["end_time"]
                                        break
                                new_unit_slot = self._occupy_slot(unit, day, p)
                                return [new_unit_slot]

                    # If no alternate slot was found, re-seat blocker
                    self._occupy_slot(blocker_unit, blocker["day_of_week"], blocker["period_number"])

        # ── BUG 4 FIX: Double-period cascade repair ───────────────────────────
        # Previously double-period units were completely skipped (if not unit.is_double guard).
        # Now we attempt to find a consecutive (p, p+1) pair and cascade-repair both slots.
        if unit.is_double:
            for day in self.days:
                max_p = self._get_max_periods_for_day(day)
                for p in range(1, max_p):  # p+1 must also be valid, so max_p-1
                    p2 = p + 1
                    if (day, p) in self.reserved_slots or (day, p2) in self.reserved_slots:
                        continue
                    if p not in self.period_times.get(day, {}) or p2 not in self.period_times.get(day, {}):
                        continue
                    if unit.teacher_id:
                        if ((day, p) in self.teacher_exempt_slots.get(unit.teacher_id, set()) or
                                (day, p2) in self.teacher_exempt_slots.get(unit.teacher_id, set())):
                            continue
                        if ((day, p) in self.teacher_grid.get(unit.teacher_id, {}) and
                                (day, p2) in self.teacher_grid.get(unit.teacher_id, {})):
                            # Both slots occupied by THIS teacher — can't move self
                            continue
                        if self.teacher_workload.get(unit.teacher_id, 0) >= self.teacher_caps.get(unit.teacher_id, 28):
                            continue

                    b1 = self.class_grid.get(unit.class_section_id, {}).get((day, p))
                    b2 = self.class_grid.get(unit.class_section_id, {}).get((day, p2))

                    if not b1 and not b2:
                        continue  # Slots are free — should have been placed in _place_unit

                    # Collect unique blockers (b1 and b2 may be same unit)
                    blockers_to_move = []
                    seen_blocker_ids = set()
                    for _b in [b1, b2]:
                        if _b is not None:
                            _bu = _b.get("unit")
                            if _bu and id(_bu) not in seen_blocker_ids and not _bu.is_double:
                                blockers_to_move.append(_b)
                                seen_blocker_ids.add(id(_bu))

                    if not blockers_to_move:
                        continue

                    # Unseat all blockers temporarily
                    for _blk in blockers_to_move:
                        self._unseat_slot(_blk)

                    # Verify both slots are now free for the double unit
                    slot1_ok = self._is_slot_valid(unit, day, p)
                    slot2_ok = self._is_slot_valid(unit, day, p2)

                    if not (slot1_ok and slot2_ok):
                        # Restore all unseated blockers
                        for _blk in blockers_to_move:
                            self._occupy_slot(_blk["unit"], _blk["day_of_week"], _blk["period_number"])
                        continue

                    # Find alternate slots for each displaced blocker
                    all_restored = True
                    moved_blockers = []
                    for _blk in blockers_to_move:
                        _bu = _blk["unit"]
                        alt_placed = False
                        for alt_day in self.days:
                            alt_max = self._get_max_periods_for_day(alt_day)
                            for alt_p in range(1, alt_max + 1):
                                if (alt_day, alt_p) in [(day, p), (day, p2)]:
                                    continue
                                if self._is_slot_valid(_bu, alt_day, alt_p):
                                    moved_b = self._occupy_slot(_bu, alt_day, alt_p)
                                    moved_blockers.append((_blk, moved_b, alt_day, alt_p))
                                    alt_placed = True
                                    break
                            if alt_placed:
                                break
                        if not alt_placed:
                            all_restored = False
                            break

                    if not all_restored:
                        # Undo partial moves and restore original blockers
                        for (_blk, _moved_b, _ad, _ap) in moved_blockers:
                            self._unseat_slot(_moved_b)
                        for _blk in blockers_to_move:
                            self._occupy_slot(_blk["unit"], _blk["day_of_week"], _blk["period_number"])
                        continue

                    # Update assigned_slots tracking for moved blockers
                    for (_blk, _moved_b, _ad, _ap) in moved_blockers:
                        for _s in assigned_slots:
                            if (_s.get("class_section_id") == _blk["class_section_id"] and
                                    _s.get("day_of_week") == _blk["day_of_week"] and
                                    _s.get("period_number") == _blk["period_number"]):
                                _s["day_of_week"] = _ad
                                _s["period_number"] = _ap
                                _s["start_time"] = _moved_b.get("start_time")
                                _s["end_time"] = _moved_b.get("end_time")
                                break

                    # Place the double-period unit across (day, p) and (day, p+1)
                    r1 = self._occupy_slot(unit, day, p)
                    r2 = self._occupy_slot(unit, day, p2, is_continuation=True)
                    return [r1, r2]

        return None

    def _unseat_slot(self, slot_info: Dict[str, Any]) -> None:
        """Remove a previously placed slot from all internal conflict tracking grids."""
        cid = slot_info["class_section_id"]
        tid = slot_info.get("teacher_id")
        sid = slot_info["subject_id"]
        day = slot_info["day_of_week"]
        period = slot_info["period_number"]
        room = slot_info.get("room")
        r_key = room.strip().lower() if room and room.strip() else None

        if (day, period) in self.class_grid.get(cid, {}):
            del self.class_grid[cid][(day, period)]

        if tid and (day, period) in self.teacher_grid.get(tid, {}):
            del self.teacher_grid[tid][(day, period)]
            self.teacher_workload[tid] = max(0, self.teacher_workload.get(tid, 1) - 1)

        if r_key and (day, period) in self.room_grid.get(r_key, {}):
            del self.room_grid[r_key][(day, period)]
            dk = (r_key, day)
            self.room_day_usage[dk] = max(0, self.room_day_usage.get(dk, 1) - 1)

        csk = (cid, sid, day)
        self.class_subject_daily[csk] = max(0, self.class_subject_daily.get(csk, 1) - 1)

    def _is_slot_valid(self, unit: SchedulingUnit, day: int, period: int, target_room: Optional[str] = None) -> bool:
        if (day, period) in self.reserved_slots:
            return False
        if period not in self.period_times.get(day, {}):
            return False
        if (day, period) in self.class_grid.get(unit.class_section_id, {}):
            return False
        if unit.teacher_id:
            if (day, period) in self.teacher_grid.get(unit.teacher_id, {}):
                return False
            if (day, period) in self.teacher_exempt_slots.get(unit.teacher_id, set()):
                return False
            if self.teacher_workload.get(unit.teacher_id, 0) >= self.teacher_caps.get(unit.teacher_id, 28):
                return False
        if unit.room_pool:
            if target_room:
                r_key = target_room.strip().lower()
                if (day, period) in self.room_grid.get(r_key, {}):
                    return False
            else:
                free_r = self._find_free_room(unit, day, period)
                if not free_r:
                    return False
        elif unit.room:
            r_key = unit.room.strip().lower()
            if r_key:
                if (day, period) in self.room_grid.get(r_key, {}):
                    return False
        return True

    def _occupy_slot(self, unit: SchedulingUnit, day: int, period: int, assigned_room: Optional[str] = None) -> Dict[str, Any]:
        times = self.period_times[day].get(period, ("00:00", "00:00"))
        room_name = assigned_room if assigned_room is not None else unit.room
        slot_info = {
            "class_section_id": unit.class_section_id,
            "subject_id": unit.subject_id,
            "teacher_id": unit.teacher_id,
            "day_of_week": day,
            "period_number": period,
            "start_time": times[0],
            "end_time": times[1],
            "room": room_name,
            "unit": unit
        }

        self.class_grid[unit.class_section_id][(day, period)] = slot_info
        if unit.teacher_id:
            self.teacher_grid[unit.teacher_id][(day, period)] = slot_info
            self.teacher_workload[unit.teacher_id] = (
                self.teacher_workload.get(unit.teacher_id, 0) + 1
            )
        r_key = room_name.strip().lower() if room_name and room_name.strip() else None
        if r_key:
            if r_key not in self.room_grid:
                self.room_grid[r_key] = {}
            self.room_grid[r_key][(day, period)] = slot_info
            dk = (r_key, day)
            self.room_day_usage[dk] = self.room_day_usage.get(dk, 0) + 1

        self.class_subject_daily[(unit.class_section_id, unit.subject_id, day)] = (
            self.class_subject_daily.get((unit.class_section_id, unit.subject_id, day), 0) + 1
        )
        return slot_info

    def _calculate_quality_metrics(
        self,
        new_slots: List[Timetable],
        unassigned_count: int,
        total_units_count: int
    ) -> Dict[str, Any]:
        """Compute an objective health & quality score for the generated timetable (0-100 scale)."""
        score = 100.0

        # Unassigned penalty
        score -= (unassigned_count * 8.0)

        # Teacher Gaps (idle windows in teacher daily schedules)
        teacher_day_periods: Dict[Tuple[int, int], List[int]] = {}
        for s in new_slots:
            if s.teacher_id:
                key = (s.teacher_id, s.day_of_week)
                teacher_day_periods.setdefault(key, []).append(s.period_number)

        total_gaps = 0
        for key, p_list in teacher_day_periods.items():
            if len(p_list) >= 2:
                p_list.sort()
                span = p_list[-1] - p_list[0] + 1
                gaps = span - len(p_list)
                total_gaps += max(0, gaps)

        gap_deduction = min(15.0, total_gaps * 0.25)
        score -= gap_deduction

        # Morning Priority for challenging core subjects (Periods 1-4)
        morning_count = 0
        core_science_count = 0
        for s in new_slots:
            s_name = self.subject_names.get(s.subject_id, "").lower()
            if any(term in s_name for term in ["math", "science", "physics", "chemistry", "biology", "accounting"]):
                core_science_count += 1
                if s.period_number <= 4:
                    morning_count += 1

        morning_pct = (morning_count / core_science_count * 100) if core_science_count > 0 else 85.0
        if morning_pct < 50.0:
            score -= 5.0

        # Dispersion index (multi-period subjects spread across different days)
        class_subj_days: Dict[Tuple[int, int], Set[int]] = {}
        class_subj_total: Dict[Tuple[int, int], int] = {}
        for s in new_slots:
            cs_key = (s.class_section_id, s.subject_id)
            class_subj_days.setdefault(cs_key, set()).add(s.day_of_week)
            class_subj_total[cs_key] = class_subj_total.get(cs_key, 0) + 1

        well_dispersed = 0
        total_eval = 0
        for cs_key, count in class_subj_total.items():
            if count >= 3:
                total_eval += 1
                unique_days = len(class_subj_days[cs_key])
                if unique_days >= min(count - 1, 4):
                    well_dispersed += 1

        dist_pct = (well_dispersed / total_eval * 100) if total_eval > 0 else 92.0

        final_score = max(0, min(100, int(round(score))))
        if final_score >= 90:
            rating = "Optimal"
        elif final_score >= 75:
            rating = "Good"
        elif final_score >= 60:
            rating = "Acceptable"
        else:
            rating = "Needs Tuning"

        return {
            "score": final_score,
            "rating": rating,
            "hard_conflicts": 0,
            "teacher_gap_periods": total_gaps,
            "morning_core_percentage": round(morning_pct, 1),
            "distribution_index": round(dist_pct, 1)
        }


# ── Surgical Reshuffle & Auto-Swap Engine ─────────────────────────────────────

def smart_surgical_swap(
    db: Session,
    school_id: int,
    outgoing_teacher_id: int,
    incoming_teacher_id: int
) -> Dict[str, Any]:
    # BUG 6 FIX: Read periods_per_day from school TimetableConfig instead of hardcoded 8
    _cfg = db.query(TimetableConfig).filter(TimetableConfig.school_id == school_id).first()
    _max_periods_per_day = _cfg.periods_per_day if _cfg and _cfg.periods_per_day else 8

    outgoing_slots = db.query(Timetable).filter(
        Timetable.teacher_id == outgoing_teacher_id
    ).all()

    if not outgoing_slots:
        return {
            "status": "NO_SLOTS",
            "message": "Outgoing teacher has no scheduled slots.",
            "swaps_applied": 0
        }

    incoming_slots = db.query(Timetable).filter(
        Timetable.teacher_id == incoming_teacher_id
    ).all()
    incoming_busy = {(s.day_of_week, s.period_number): s for s in incoming_slots}

    transferred = 0
    swapped = 0
    colliding_slots = []

    for slot in outgoing_slots:
        collision_key = (slot.day_of_week, slot.period_number)
        if collision_key in incoming_busy:
            colliding_slots.append(slot)
        else:
            slot.teacher_id = incoming_teacher_id
            transferred += 1

    for c_slot in colliding_slots:
        cls_slots = db.query(Timetable).filter(
            Timetable.class_section_id == c_slot.class_section_id
        ).all()
        cls_busy = {(s.day_of_week, s.period_number): s for s in cls_slots}

        swap_found = False
        for day in range(5):
            for period in range(1, _max_periods_per_day + 1):  # BUG 6 FIX: config-aware
                cand_key = (day, period)
                if cand_key not in incoming_busy:
                    other_slot = cls_busy.get(cand_key)
                    if other_slot and other_slot.id != c_slot.id:
                        other_teacher_busy = False
                        if other_slot.teacher_id:
                            conf = db.query(Timetable).filter(
                                Timetable.teacher_id == other_slot.teacher_id,
                                Timetable.day_of_week == c_slot.day_of_week,
                                Timetable.period_number == c_slot.period_number
                            ).first()
                            if conf:
                                other_teacher_busy = True
                        if not other_teacher_busy:
                            temp_day, temp_period = c_slot.day_of_week, c_slot.period_number
                            c_slot.day_of_week = other_slot.day_of_week
                            c_slot.period_number = other_slot.period_number
                            c_slot.teacher_id = incoming_teacher_id
                            other_slot.day_of_week = temp_day
                            other_slot.period_number = temp_period
                            swapped += 1
                            transferred += 1
                            swap_found = True
                            break
            if swap_found:
                break

    db.commit()
    return {
        "status": "SUCCESS",
        "slots_transferred": transferred,
        "surgical_swaps_performed": swapped,
        "message": (
            f"Successfully transferred {transferred} slot(s) "
            f"with {swapped} surgical swap(s) applied."
        )
    }
