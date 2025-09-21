# HolidayDashboard

A lightweight Flask application for managing annual leave allocations with support for carry-over balances and half-day requests. Every employee receives 25 days of annual leave (January through December). Up to five unused days can be carried into the following year, provided they are consumed by the end of March.

## Features

- Create and list employees.
- Submit leave applications for full days or half days (first or second half of the day).
- Approve or reject leave requests with automatic allocation tracking.
- Carry over up to five unused days into the next leave year, expiring on 31 March.
- Query the detailed leave balance for each employee.


## Getting started

1. **Install dependencies**

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Run the development server**

   ```bash
   flask --app app run --debug
   ```

   The API will be available at `http://127.0.0.1:5000` and the web dashboard at `http://127.0.0.1:5000/dashboard`.

## Using the web dashboard

The HTML experience provides friendly pages for common tasks:

- **Dashboard** (`/dashboard`) – overview of outstanding approvals, recent activity, and current year balances.
- **Employees** (`/dashboard/employees`) – add team members and drill into their annual balances.
- **Apply for leave** (`/dashboard/leave/apply`) – submit full-day, first-half, or second-half requests with optional context.
- **Approvals** (`/dashboard/leave/applications`) – filter applications and record approval or rejection decisions.

All HTML forms interact with the same underlying rules as the API endpoints, ensuring carry-over, half-day accounting, and approval tracking behave consistently whichever interface you prefer.


## Key API endpoints

### Health check

```http
GET /health
```

Returns `{ "status": "ok" }` when the service is ready.

### Create an employee

```http
POST /employees
Content-Type: application/json

{
  "name": "Aisha Khan",
  "employee_id": "EMP001"  // optional, generated if omitted
}
```

### List employees

```http
GET /employees
```

### Submit a leave application

```http
POST /leave/apply
Content-Type: application/json

{
  "employee_id": "EMP001",
  "date": "2024-02-14",
  "leave_type": "first_half",  // "full", "first_half", "second_half"
  "reason": "Medical appointment"
}
```

### Review pending applications

```http
GET /leave/applications?status=pending
```

### Approve or reject an application

```http
POST /leave/<application_id>/decision
Content-Type: application/json

{
  "approver": "Team Lead",
  "decision": "approved",  // or "rejected"
  "comment": "Enjoy your day off!"
}
```

The service automatically deducts approved leave from the carry-over bucket (when used before 31 March) before consuming the current year's allocation. Once carry-over days expire, only the 25-day annual balance remains available.

### View an employee's balance

```http
GET /employees/EMP001/balance?year=2024
```

The response contains the total allocation, carry-over, usage and remaining balances, alongside the employee's leave history.

## Data storage

Application data is stored in `data/state.json`. The file is created automatically when the service is first started and can be removed to reset the environment.
