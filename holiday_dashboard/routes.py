"""HTTP routes for the leave management service."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from .leave_service import (
    LeaveError,
    apply_for_leave,
    create_employee,
    decide_leave,
    get_applications,
    get_balance,
    get_employee,
    list_employees,
)


bp = Blueprint("leave", __name__)


@bp.errorhandler(LeaveError)
def handle_leave_error(exc: LeaveError):
    response = {"error": str(exc)}
    return jsonify(response), 400


@bp.route("/health", methods=["GET"])
def health_check():
    return jsonify({"status": "ok"})


@bp.route("/employees", methods=["GET"])
def employees():
    return jsonify(sorted(list_employees(), key=lambda item: item["id"]))


@bp.route("/employees", methods=["POST"])
def add_employee():
    payload = request.get_json(force=True)
    name = payload.get("name")
    employee_id = payload.get("employee_id")
    if not name:
        raise LeaveError("'name' is required to create an employee")
    employee = create_employee(name=name, employee_id=employee_id)
    return jsonify(employee), 201


@bp.route("/employees/<employee_id>", methods=["GET"])
def employee_detail(employee_id: str):
    return jsonify(get_employee(employee_id))


@bp.route("/employees/<employee_id>/balance", methods=["GET"])
def employee_balance(employee_id: str):
    year = request.args.get("year", type=int)
    return jsonify(get_balance(employee_id, year=year))


@bp.route("/leave/apply", methods=["POST"])
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


@bp.route("/leave/applications", methods=["GET"])
def applications():
    employee_id = request.args.get("employee_id")
    status = request.args.get("status")
    return jsonify(get_applications(employee_id=employee_id, status=status))


@bp.route("/leave/<application_id>/decision", methods=["POST"])
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
