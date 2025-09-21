
"""HTTP and HTML routes for the leave management service."""

from __future__ import annotations

import datetime as dt
from typing import Any, Dict, List, Optional

from flask import (
    Blueprint,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)

from .leave_service import (
    LEAVE_TYPES,

    LeaveError,
    apply_for_leave,
    create_employee,
    decide_leave,
    get_applications,
    get_balance,
    get_employee,
    list_employees,
)


api_bp = Blueprint("leave_api", __name__)
ui_bp = Blueprint("ui", __name__, template_folder="templates", static_folder="static")


LEAVE_TYPE_LABELS = {
    "full": "Full day",
    "first_half": "First half-day",
    "second_half": "Second half-day",
}


def _sorted_employees() -> List[Dict[str, Any]]:
    employees = list(list_employees())
    return sorted(employees, key=lambda emp: emp["name"].lower())


def _find_application(application_id: str) -> Optional[Dict[str, Any]]:
    for application in get_applications():
        if application["id"] == application_id:
            return application
    return None


@api_bp.errorhandler(LeaveError)

def handle_leave_error(exc: LeaveError):
    response = {"error": str(exc)}
    return jsonify(response), 400



@api_bp.route("/health", methods=["GET"])

def health_check():
    return jsonify({"status": "ok"})



@api_bp.route("/employees", methods=["GET"])

def employees():
    return jsonify(sorted(list_employees(), key=lambda item: item["id"]))



@api_bp.route("/employees", methods=["POST"])

def add_employee():
    payload = request.get_json(force=True)
    name = payload.get("name")
    employee_id = payload.get("employee_id")
    if not name:
        raise LeaveError("'name' is required to create an employee")
    employee = create_employee(name=name, employee_id=employee_id)
    return jsonify(employee), 201



@api_bp.route("/employees/<employee_id>", methods=["GET"])

def employee_detail(employee_id: str):
    return jsonify(get_employee(employee_id))



@api_bp.route("/employees/<employee_id>/balance", methods=["GET"])

def employee_balance(employee_id: str):
    year = request.args.get("year", type=int)
    return jsonify(get_balance(employee_id, year=year))



@api_bp.route("/leave/apply", methods=["POST"])

def apply_leave():
    payload = request.get_json(force=True)
    employee_id = payload.get("employee_id")
    leave_type = payload.get("leave_type")
    date = payload.get("date")
    reason = payload.get("reason")
    requested_by = payload.get("requested_by")

    if not employee_id:
        raise LeaveError("'employee_id' is required")
    if not date:
        raise LeaveError("'date' is required in YYYY-MM-DD format")
    if not leave_type:
        raise LeaveError("'leave_type' is required")

    application = apply_for_leave(
        employee_id=employee_id,
        date=date,
        leave_type=leave_type,
        reason=reason,
        requested_by=requested_by,
    )
    return jsonify(application), 201



@api_bp.route("/leave/applications", methods=["GET"])

def applications():
    employee_id = request.args.get("employee_id")
    status = request.args.get("status")
    return jsonify(get_applications(employee_id=employee_id, status=status))



@api_bp.route("/leave/<application_id>/decision", methods=["POST"])

def leave_decision(application_id: str):
    payload = request.get_json(force=True)
    decision = payload.get("decision")
    approver = payload.get("approver")
    comment = payload.get("comment")

    if not approver:
        raise LeaveError("'approver' is required to record a decision")
    if not decision:
        raise LeaveError("'decision' must be 'approved' or 'rejected'")

    application = decide_leave(
        application_id=application_id,
        approver=approver,
        decision=decision,
        comment=comment,
    )
    return jsonify(application)



@ui_bp.route("/")
def landing():
    return redirect(url_for("ui.dashboard"))


@ui_bp.route("/dashboard")
def dashboard():
    current_year = dt.date.today().year
    employees = _sorted_employees()
    employee_lookup = {employee["id"]: employee for employee in employees}
    balances = []
    for employee in employees:
        try:
            balances.append(get_balance(employee["id"], year=current_year))
        except LeaveError:
            continue

    pending = get_applications(status="pending")
    recent_activity = get_applications()
    return render_template(
        "index.html",
        employees=employees,
        employee_lookup=employee_lookup,
        balances=balances,
        pending=pending,
        recent_activity=recent_activity[:10],
        current_year=current_year,
        leave_type_labels=LEAVE_TYPE_LABELS,
    )


@ui_bp.route("/dashboard/employees", methods=["GET", "POST"])
def manage_employees():
    error: Optional[str] = None
    success: Optional[str] = None

    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        employee_id = (request.form.get("employee_id") or "").strip() or None
        if not name:
            error = "Employee name is required."
        else:
            try:
                employee = create_employee(name=name, employee_id=employee_id)
            except LeaveError as exc:
                error = str(exc)
            else:
                return redirect(url_for("ui.manage_employees", created=employee["id"]))

    created_id = request.args.get("created")
    if created_id:
        try:
            employee = get_employee(created_id)
        except LeaveError:
            success = "Employee created successfully."
        else:
            success = f"Employee '{employee['name']}' ({employee['id']}) was created successfully."

    employees = _sorted_employees()
    return render_template(
        "employees.html",
        employees=employees,
        error=error,
        success=success,
    )


@ui_bp.route("/dashboard/employees/<employee_id>")
def employee_profile(employee_id: str):
    year = request.args.get("year", type=int)
    try:
        employee = get_employee(employee_id)
        balance = get_balance(employee_id, year=year)
    except LeaveError as exc:
        return render_template("employee_detail.html", error=str(exc), employee=None, balance=None), 404

    available_years = sorted({int(year_key) for year_key in employee.get("yearly_records", {}).keys()})
    if balance["year"] not in available_years:
        available_years.append(balance["year"])
        available_years.sort()

    return render_template(
        "employee_detail.html",
        employee=employee,
        balance=balance,
        available_years=available_years,
        leave_type_labels=LEAVE_TYPE_LABELS,
        error=None,
    )


@ui_bp.route("/dashboard/leave/apply", methods=["GET", "POST"])
def apply_leave_form():
    error: Optional[str] = None
    success: Optional[str] = None
    application: Optional[Dict[str, str]] = None

    if request.method == "POST":
        employee_id = (request.form.get("employee_id") or "").strip()
        leave_type = (request.form.get("leave_type") or "").strip()
        date = (request.form.get("date") or "").strip()
        reason = (request.form.get("reason") or "").strip() or None
        requested_by = (request.form.get("requested_by") or "").strip() or None

        if not employee_id:
            error = "Please select an employee."
        elif not date:
            error = "A leave date is required."
        elif leave_type not in LEAVE_TYPES:
            error = "Choose a valid leave type."
        else:
            try:
                application = apply_for_leave(
                    employee_id=employee_id,
                    date=date,
                    leave_type=leave_type,
                    reason=reason,
                    requested_by=requested_by,
                )
            except LeaveError as exc:
                error = str(exc)
            else:
                return redirect(url_for("ui.apply_leave_form", success=application["id"]))

    success_id = request.args.get("success")
    if success_id:
        application = _find_application(success_id)
        if application:
            success = (
                f"Leave request {application['id']} submitted for {application['date']} "
                f"({LEAVE_TYPE_LABELS.get(application['leave_type'], application['leave_type'])})."
            )
        else:
            success = "Leave request submitted successfully."

    return render_template(
        "apply_leave.html",
        employees=_sorted_employees(),
        leave_types=LEAVE_TYPES,
        leave_type_labels=LEAVE_TYPE_LABELS,
        error=error,
        success=success,
        application=application,
    )


@ui_bp.route("/dashboard/leave/applications", methods=["GET", "POST"])
def review_applications():
    error: Optional[str] = None
    success: Optional[str] = None

    if request.method == "POST":
        application_id = (request.form.get("application_id") or "").strip()
        decision = (request.form.get("decision") or "").strip().lower()
        approver = (request.form.get("approver") or "").strip()
        comment = (request.form.get("comment") or "").strip() or None

        if not application_id:
            error = "Missing application identifier."
        elif decision not in {"approved", "rejected"}:
            error = "Choose approve or reject to record a decision."
        elif not approver:
            error = "Approver name is required."
        else:
            try:
                decide_leave(
                    application_id=application_id,
                    approver=approver,
                    decision=decision,
                    comment=comment,
                )
            except LeaveError as exc:
                error = str(exc)
            else:
                return redirect(
                    url_for(
                        "ui.review_applications",
                        success=decision,
                        application_id=application_id,
                        status=request.args.get("status", "pending"),
                        employee_id=request.args.get("employee_id") or None,
                    )
                )

    success_decision = request.args.get("success")
    success_id = request.args.get("application_id")
    if success_decision and success_id:
        application = _find_application(success_id)
        if application:
            status_text = "approved" if success_decision == "approved" else "rejected"
            success = f"Application {application['id']} has been {status_text}."
        else:
            success = "Application decision recorded."

    status_filter = request.args.get("status", "pending")
    if status_filter == "all":
        status = None
    else:
        status = status_filter

    employee_filter = request.args.get("employee_id") or None
    applications = get_applications(employee_id=employee_filter, status=status)
    employees = _sorted_employees()
    employee_lookup = {employee["id"]: employee for employee in employees}

    return render_template(
        "applications.html",
        applications=applications,
        employees=employees,
        employee_lookup=employee_lookup,
        selected_employee=employee_filter,
        status_filter=status_filter,
        error=error,
        success=success,
        leave_type_labels=LEAVE_TYPE_LABELS,
    )


__all__ = ["api_bp", "ui_bp"]

