# Spirit University – Smart Classroom Booking System

## Run in VS Code
1. Install Python 3.10 or later.
2. Open this folder in VS Code.
3. In the terminal run:
   ```bash
   python -m venv venv
   ```
4. Activate the environment:
   - Windows PowerShell: `venv\Scripts\Activate.ps1`
   - macOS/Linux: `source venv/bin/activate`
5. Install dependencies: `pip install -r requirements.txt`
6. Start the application: `python app.py`
7. Open `http://127.0.0.1:5000`

The SQLite database is created automatically in `instance/spirit_university.db`.

## Initial accounts
All supplied initial accounts are created on first startup. Every account is required to change its initial password on first login.

- Super Admin: `SUPER001`
- Dean: `DEAN001`
- Administrator: `ADMIN001`
- Faculty: `FAC001` through `FAC005`
- Students: `2024BTAM001` through `2024BTAM010`

Initial passwords are the values supplied by the project owner in the setup conversation. Do not deploy this demo with these passwords. Change them immediately, set a strong `SECRET_KEY`, and use HTTPS in production.

## Bulk student import
Only Dean and Super Admin can open **Members → Bulk Import**.
Upload a CSV with these exact headers:

`name,prn,dob`

DOB must be a real date in `DDMMYYYY` format. Each new student's PRN is the username; DOB is the initial password and must be changed at first login. Duplicate PRNs and invalid rows are skipped and reported.

## Included functionality
- Role-based login and personalized name/role in the top-right menu
- Super Admin, Dean, Administrator, Faculty and Student roles
- Bulk student import for Dean and Super Admin
- Password hashing and forced first-login password change
- Room catalogue with supplied image assets
- Booking overlap checks protected by a SQLite write transaction
- Restricted room approval workflow
- My bookings and shared booking calendar

This is a student-project starter implementation. Before production deployment, add CSRF protection, rate limiting, email verification, audit logs, backups, and stronger operational security.

## Faculty-opened classes and seat booking
- Faculty, Administrator, Dean and Super Admin can open a classroom for a date/time and seat limit.
- Students book only classes that faculty have opened.
- Students see available seat counts, never other students' names or PRNs.
- A student may have only one active booking at a time.
- SQLite write transactions prevent simultaneous requests from exceeding the seat limit.
- Students can cancel their own booking; the seat becomes available again.
- Logout is available in the top navigation.
- Existing databases are migrated automatically when the app starts.

Run with `python app.py`, then visit `/classes`. Faculty can use `/classes/open`.
