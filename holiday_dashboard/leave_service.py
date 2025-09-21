"""Business logic for the leave management workflow."""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Any, Dict, Iterable, List, Tuple

from .storage import load_state, save_state


LEAVE_TYPES = {
    "full": 1.0,
    "first_half": 0.5,
    "second_half": 0.5,
}

ANNUAL_ALLOCATION = 25.0
MAX_CARRY_OVER = 5.0
CARRY_OVER_EXPIRY_MONTH = 3
CARRY_OVER_EXPIRY_DAY = 31


class LeaveError(RuntimeError):
    """Custom exception raised when a leave request cannot be processed."""


def _iso_today() -> str:
    return dt.datetime.utcnow().date().isoformat()


def _ensure_employee(state: Dict[str, Any], employee_id: str) -> Dict[str, Any]:
    employees = state.setdefault("employees", {})
    if employee_id not in employees:
        raise LeaveError(f"Employee '{employee_id}' was not found")
    return employees[employee_id]


def _current_year() -> int:
    return dt.date.today().year


def _ensure_year_record(employee: Dict[str, Any], year: int) -> Dict[str, Any]:
    records = employee.setdefault("yearly_records", {})
    year_key = str(year)
    if year_key in records:
        return records[year_key]

    carry_over = _calculate_carry_over(employee, year)
    record = {
        "year": year,
        "allocation": ANNUAL_ALLOCATION,
        "carry_over": carry_over,
        "carry_over_expiry": dt.date(year, CARRY_OVER_EXPIRY_MONTH, CARRY_OVER_EXPIRY_DAY).isoformat(),
        "applications": [],
    }
    records[year_key] = record
    return record


def _get_or_create_year_record(
    state: Dict[str, Any], employee: Dict[str, Any], year: int
) -> Dict[str, Any]:
    records = employee.setdefault("yearly_records", {})
    year_key = str(year)
    if year_key in records:
        return records[year_key]
    record = _ensure_year_record(employee, year)
    save_state(state)
    return record


def _calculate_carry_over(employee: Dict[str, Any], year: int) -> float:
    previous_year = str(year - 1)
    records = employee.get("yearly_records", {})
    previous_record = records.get(previous_year)
    if not previous_record:
        return 0.0

    used_current_allocation = sum(
        app.get("allocation_breakdown", {}).get("current_year", 0.0)
        for app in previous_record.get("applications", [])
        if app.get("status") == "approved"
    )
    unused_current = max(0.0, previous_record.get("allocation", 0.0) - used_current_allocation)
    return float(min(MAX_CARRY_OVER, unused_current))


def list_employees() -> Iterable[Dict[str, Any]]:
    state = load_state()
    return state.get("employees", {}).values()


def create_employee(name: str, employee_id: str | None = None) -> Dict[str, Any]:
    state = load_state()
    employees = state.setdefault("employees", {})

    employee_id = employee_id or uuid.uuid4().hex[:8]
    if employee_id in employees:
        raise LeaveError(f"Employee with id '{employee_id}' already exists")

    employee = {
        "id": employee_id,
        "name": name,
        "created_at": _iso_today(),
        "yearly_records": {},
    }
    employees[employee_id] = employee
    _ensure_year_record(employee, _current_year())
    save_state(state)
    return employee


def get_employee(employee_id: str) -> Dict[str, Any]:
    state = load_state()
    return _ensure_employee(state, employee_id)


def _find_application(state: Dict[str, Any], application_id: str) -> Dict[str, Any]:
    applications = state.setdefault("applications", {})
    if application_id not in applications:
        raise LeaveError(f"Leave application '{application_id}' was not found")
    return applications[application_id]


def _collect_year_record(state: Dict[str, Any], employee_id: str, year: int) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    employee = _ensure_employee(state, employee_id)
    record = _get_or_create_year_record(state, employee, year)
    return employee, record


def apply_for_leave(
    employee_id: str,
    date: str,
    leave_type: str,
    reason: str | None = None,
    requested_by: str | None = None,
) -> Dict[str, Any]:
    if leave_type not in LEAVE_TYPES:
        raise LeaveError(
            "leave_type must be one of 'full', 'first_half', or 'second_half'"
        )

    try:
        leave_date = dt.datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError as exc:  # pragma: no cover - defensive
        raise LeaveError("date must be in YYYY-MM-DD format") from exc

    state = load_state()
    employee, record = _collect_year_record(state, employee_id, leave_date.year)

    application_id = uuid.uuid4().hex
    application = {
        "id": application_id,
        "employee_id": employee_id,
        "year": leave_date.year,
        "date": leave_date.isoformat(),
        "leave_type": leave_type,
        "duration": LEAVE_TYPES[leave_type],
        "reason": reason,
        "requested_by": requested_by or employee.get("name"),
        "status": "pending",
        "created_at": dt.datetime.utcnow().isoformat() + "Z",
        "history": [],
    }

    record.setdefault("applications", []).append(application)
    state.setdefault("applications", {})[application_id] = application
    save_state(state)
    return application


def _available_allocation(record: Dict[str, Any]) -> Tuple[float, float]:
    approved = [
        app
        for app in record.get("applications", [])
        if app.get("status") == "approved"
    ]
    used_carry_over = sum(
        app.get("allocation_breakdown", {}).get("carry_over", 0.0) for app in approved
    )
    used_current_year = sum(
        app.get("allocation_breakdown", {}).get("current_year", 0.0) for app in approved
    )
    remaining_carry_over = max(0.0, record.get("carry_over", 0.0) - used_carry_over)
    remaining_current = max(0.0, record.get("allocation", ANNUAL_ALLOCATION) - used_current_year)
    return remaining_carry_over, remaining_current


def _allocate_for_date(
    record: Dict[str, Any],
    leave_date: dt.date,
    duration: float,
) -> Dict[str, float]:
    remaining_carry, remaining_current = _available_allocation(record)
    breakdown = {"carry_over": 0.0, "current_year": 0.0}

    expiry = dt.datetime.strptime(record["carry_over_expiry"], "%Y-%m-%d").date()
    if leave_date <= expiry:
        use_carry = min(duration, remaining_carry)
        breakdown["carry_over"] = use_carry
        duration -= use_carry

    if duration > remaining_current:
        raise LeaveError("Insufficient leave balance to approve the request")

    breakdown["current_year"] = duration
    return breakdown


def decide_leave(
    application_id: str,
    approver: str,
    decision: str,
    comment: str | None = None,
) -> Dict[str, Any]:
    decision = decision.lower()
    if decision not in {"approved", "rejected"}:
        raise LeaveError("decision must be either 'approved' or 'rejected'")

    state = load_state()
    application = _find_application(state, application_id)
    if application.get("status") != "pending":
        raise LeaveError("Only pending applications can be processed")

    employee = _ensure_employee(state, application["employee_id"])
    record = _get_or_create_year_record(state, employee, application["year"])

    history_entry = {
        "acted_by": approver,
        "decision": decision,
        "comment": comment,
        "acted_at": dt.datetime.utcnow().isoformat() + "Z",
    }

    if decision == "approved":
        leave_date = dt.datetime.strptime(application["date"], "%Y-%m-%d").date()
        breakdown = _allocate_for_date(record, leave_date, application["duration"])
        application["allocation_breakdown"] = breakdown
    else:
        application["allocation_breakdown"] = {"carry_over": 0.0, "current_year": 0.0}

    application["status"] = decision
    application.setdefault("history", []).append(history_entry)
    save_state(state)
    return application


def get_applications(
    employee_id: str | None = None,
    status: str | None = None,
) -> List[Dict[str, Any]]:
    state = load_state()
    applications = state.get("applications", {}).values()
    results = []
    for application in applications:
        if employee_id and application["employee_id"] != employee_id:
            continue
        if status and application["status"] != status:
            continue
        results.append(application)
    return sorted(results, key=lambda app: app["created_at"], reverse=True)


def get_balance(employee_id: str, year: int | None = None) -> Dict[str, Any]:
    state = load_state()
    employee = _ensure_employee(state, employee_id)
    year = year or _current_year()
    record = _get_or_create_year_record(state, employee, year)

    remaining_carry, remaining_current = _available_allocation(record)
    approved = [
        app
        for app in record.get("applications", [])
        if app.get("status") == "approved"
    ]
    used_carry = sum(app.get("allocation_breakdown", {}).get("carry_over", 0.0) for app in approved)
    used_current = sum(app.get("allocation_breakdown", {}).get("current_year", 0.0) for app in approved)

    return {
        "employee_id": employee_id,
        "employee_name": employee.get("name"),
        "year": year,
        "allocation": record.get("allocation", ANNUAL_ALLOCATION),
        "carry_over": record.get("carry_over", 0.0),
        "carry_over_expiry": record.get("carry_over_expiry"),
        "used_current_year": used_current,
        "used_carry_over": used_carry,
        "remaining_current_year": remaining_current,
        "remaining_carry_over": remaining_carry,
        "applications": record.get("applications", []),
    }


__all__ = [
    "apply_for_leave",
    "create_employee",
    "decide_leave",
    "get_applications",
    "get_balance",
    "get_employee",
    "LeaveError",
    "list_employees",
]
