import os, csv, io, sqlite3, secrets, string
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file, abort
from werkzeug.security import generate_password_hash, check_password_hash

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "instance", "spirit_university.db")
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-key-before-deployment")
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024

ROLES = ("Super Admin", "Dean", "Administrator", "Faculty", "Student")

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with db() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL,
            must_change_password INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS rooms(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            room_type TEXT NOT NULL,
            capacity INTEGER NOT NULL,
            building TEXT NOT NULL DEFAULT 'Main Block',
            facilities TEXT NOT NULL DEFAULT '',
            image TEXT NOT NULL DEFAULT '',
            restricted INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS bookings(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id),
            room_id INTEGER NOT NULL REFERENCES rooms(id),
            booking_date TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            purpose TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Confirmed',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
                CREATE TABLE IF NOT EXISTS class_sessions(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_id INTEGER NOT NULL REFERENCES rooms(id),
            faculty_id INTEGER NOT NULL REFERENCES users(id),
            class_date TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            purpose TEXT NOT NULL,
            seat_limit INTEGER NOT NULL CHECK(seat_limit > 0),
            is_open INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(room_id,class_date,start_time,end_time)
        );
        """)
        booking_columns = {row["name"] for row in con.execute("PRAGMA table_info(bookings)").fetchall()}
        if "session_id" not in booking_columns:
            con.execute("ALTER TABLE bookings ADD COLUMN session_id INTEGER REFERENCES class_sessions(id)")
        if con.execute("SELECT COUNT(*) FROM rooms").fetchone()[0] == 0:
            rooms = [
                ("Lecture Hall A","Classroom",60,"Academic Block","Projector, Smart Board, Wi-Fi","images/classroom_warm.jpg",0),
                ("Classroom B","Classroom",45,"Academic Block","Projector, Whiteboard, Wi-Fi","images/classroom_modern.jpg",0),
                ("Smart Classroom C","Classroom",50,"Academic Block","Smart Board, Projector, Wi-Fi","images/spirit_classroom.png",0),
                ("Computer Lab 1","Computer Lab",40,"Technology Block","40 Computers, Internet, Projector","images/computer_lab.jpg",0),
                ("Science Lab 1","Laboratory",30,"Science Block","Lab benches, Safety equipment","images/science_lab.jpg",1),
                ("Main Auditorium","Auditorium",300,"Admin Block","Stage, Sound System, Projector","images/auditorium.jpg",1),
            ]
            con.executemany("INSERT INTO rooms(name,room_type,capacity,building,facilities,image,restricted) VALUES(?,?,?,?,?,?,?)", rooms)

def seed_accounts():
    # Initial demo credentials supplied by the project owner. Change them after first login.
    students = [
        ("Dinesh","2024BTAM001","12032006"),
        ("Jaswanth","2024BTAM002","11032006"),
        ("Anil","2024BTAM003","13032006"),
        ("Lithin","2024BTAM004","14032006"),
        ("Jaideep","2024BTAM005","15032006"),
        ("Prakash","2024BTAM006","16042005"),
        ("Prajwal","2024BTAM007","17032005"),
        ("Bharath","2024BTAM008","18032005"),
        ("Shankar","2024BTAM009","19032005"),
        ("Hari","2024BTAM010","20032005"),
    ]
    staff = [
        ("Murali","SUPER001","3333335","Super Admin"),
        ("Krishna","DEAN001","2055739","Dean"),
        ("Deva","ADMIN001","5412092","Administrator"),
        ("Siva","FAC001","7386509","Faculty"),
        ("Shankar","FAC002","0590012","Faculty"),
        ("Ganesh","FAC003","6281752","Faculty"),
        ("Suriya","FAC004","1750021","Faculty"),
        ("Deepak","FAC005","8247084","Faculty"),
    ]
    with db() as con:
        for name, username, password in students:
            con.execute("""INSERT OR IGNORE INTO users(name,username,password_hash,role,must_change_password)
                           VALUES(?,?,?,?,1)""",
                        (name, username, generate_password_hash(password), "Student"))
        for name, username, password, role in staff:
            con.execute("""INSERT OR IGNORE INTO users(name,username,password_hash,role,must_change_password)
                           VALUES(?,?,?,?,1)""",
                        (name, username, generate_password_hash(password), role))

def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper

def roles_required(*roles):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not session.get("user_id"):
                return redirect(url_for("login"))
            if session.get("role") not in roles:
                abort(403)
            return fn(*args, **kwargs)
        return wrapper
    return decorator

@app.context_processor
def common_context():
    return {"current_user": session, "roles": ROLES}

@app.route("/")
def index():
    return redirect(url_for("dashboard") if session.get("user_id") else url_for("login"))

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username","").strip()
        password = request.form.get("password","")
        with db() as con:
            user = con.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session.update(user_id=user["id"], name=user["name"], username=user["username"], role=user["role"])
            if user["must_change_password"]:
                return redirect(url_for("change_password"))
            return redirect(url_for("dashboard"))
        flash("Invalid username or password.", "error")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("login"))

@app.route("/change-password", methods=["GET","POST"])
@login_required
def change_password():
    if request.method == "POST":
        new = request.form.get("new_password","")
        confirm = request.form.get("confirm_password","")
        if len(new) < 8:
            flash("Use at least 8 characters for your new password.", "error")
        elif new != confirm:
            flash("Passwords do not match.", "error")
        else:
            with db() as con:
                con.execute("UPDATE users SET password_hash=?, must_change_password=0 WHERE id=?",
                            (generate_password_hash(new), session["user_id"]))
            flash("Password updated successfully.", "success")
            return redirect(url_for("dashboard"))
    return render_template("change_password.html")

@app.route("/dashboard")
@login_required
def dashboard():
    with db() as con:
        room_count = con.execute("SELECT COUNT(*) FROM rooms").fetchone()[0]
        booking_count = con.execute("SELECT COUNT(*) FROM bookings").fetchone()[0]
        my_count = con.execute("SELECT COUNT(*) FROM bookings WHERE user_id=?", (session["user_id"],)).fetchone()[0]
        pending = con.execute("SELECT COUNT(*) FROM bookings WHERE status='Pending'").fetchone()[0]
        rooms = con.execute("SELECT * FROM rooms ORDER BY id LIMIT 3").fetchall()
        recent = []
        if session.get("role") != "Student":
            recent = con.execute("""SELECT b.*,r.name room_name,u.name user_name FROM bookings b
                JOIN rooms r ON r.id=b.room_id JOIN users u ON u.id=b.user_id
                ORDER BY b.id DESC LIMIT 5""").fetchall()
    return render_template("dashboard.html", room_count=room_count, booking_count=booking_count,
                           my_count=my_count, pending=pending, rooms=rooms, recent=recent)

@app.route("/rooms")
@login_required
def rooms():
    q = request.args.get("q","").strip()
    with db() as con:
        rows = con.execute("SELECT * FROM rooms WHERE name LIKE ? OR room_type LIKE ? ORDER BY name",
                           (f"%{q}%",f"%{q}%")).fetchall()
    return render_template("rooms.html", rooms=rows, q=q)

@app.route("/book/<int:room_id>", methods=["GET","POST"])
@login_required
def book(room_id):
    if session.get("role") == "Student":
        return redirect(url_for("classes"))
    with db() as con:
        room = con.execute("SELECT * FROM rooms WHERE id=?", (room_id,)).fetchone()
    if not room: abort(404)
    if request.method == "POST":
        date = request.form.get("booking_date","")
        start = request.form.get("start_time","")
        end = request.form.get("end_time","")
        purpose = request.form.get("purpose","").strip()
        try:
            datetime.strptime(date, "%Y-%m-%d")
            valid = bool(start and end and start < end and purpose)
        except ValueError:
            valid = False
        if not valid:
            flash("Enter a valid date, time range and purpose.", "error")
        else:
            with db() as con:
                con.execute("BEGIN IMMEDIATE")
                overlap = con.execute("""SELECT COUNT(*) FROM bookings
                    WHERE room_id=? AND booking_date=? AND status IN ('Pending','Confirmed')
                    AND start_time < ? AND end_time > ?""", (room_id,date,end,start)).fetchone()[0]
                if overlap:
                    flash("This room is already booked during that time. Choose another slot.", "error")
                else:
                    status = "Pending" if room["restricted"] else "Confirmed"
                    con.execute("""INSERT INTO bookings(user_id,room_id,booking_date,start_time,end_time,purpose,status)
                        VALUES(?,?,?,?,?,?,?)""",
                        (session["user_id"],room_id,date,start,end,purpose,status))
                    flash("Booking request submitted." if status=="Pending" else "Room booked successfully.", "success")
                    return redirect(url_for("my_bookings"))
    return render_template("book.html", room=room)

@app.route("/my-bookings")
@login_required
def my_bookings():
    with db() as con:
        rows = con.execute("""SELECT b.*,r.name room_name FROM bookings b JOIN rooms r ON r.id=b.room_id
            WHERE b.user_id=? ORDER BY b.booking_date DESC,b.start_time""",(session["user_id"],)).fetchall()
    return render_template("my_bookings.html", bookings=rows)

@app.route("/approvals")
@roles_required("Administrator","Dean","Super Admin")
def approvals():
    with db() as con:
        rows = con.execute("""SELECT b.*,r.name room_name,u.name user_name,u.role FROM bookings b
            JOIN rooms r ON r.id=b.room_id JOIN users u ON u.id=b.user_id
            WHERE b.status='Pending' ORDER BY b.booking_date,b.start_time""").fetchall()
    return render_template("approvals.html", bookings=rows)

@app.route("/booking/<int:booking_id>/<action>", methods=["POST"])
@roles_required("Administrator","Dean","Super Admin")
def booking_action(booking_id, action):
    if action not in ("approve","reject"): abort(404)
    with db() as con:
        row = con.execute("SELECT * FROM bookings WHERE id=? AND status='Pending'",(booking_id,)).fetchone()
        if row:
            status = "Confirmed" if action=="approve" else "Rejected"
            con.execute("UPDATE bookings SET status=? WHERE id=?", (status,booking_id))
            flash(f"Booking {status.lower()}.", "success")
    return redirect(url_for("approvals"))

@app.route("/members")
@roles_required("Dean","Super Admin")
def members():
    with db() as con:
        rows = con.execute("SELECT id,name,username,role,created_at FROM users ORDER BY role,name").fetchall()
    return render_template("members.html", users=rows)

@app.route("/bulk-import", methods=["GET","POST"])
@roles_required("Dean","Super Admin")
def bulk_import():
    if request.method == "POST":
        f = request.files.get("file")
        if not f or not f.filename.lower().endswith(".csv"):
            flash("Please upload a CSV file using the provided template.", "error")
            return redirect(url_for("bulk_import"))
        try:
            stream = io.StringIO(f.stream.read().decode("utf-8-sig"))
            reader = csv.DictReader(stream)
            required = {"name","prn","dob"}
            if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
                raise ValueError("CSV headers must be: name,prn,dob")
            added, skipped = 0, []
            with db() as con:
                for line, row in enumerate(reader, start=2):
                    name = (row.get("name") or "").strip()
                    prn = (row.get("prn") or "").strip()
                    dob = (row.get("dob") or "").strip()
                    if not name or not prn or not (len(dob)==8 and dob.isdigit()):
                        skipped.append(f"Row {line}: missing or invalid name, PRN or DOB")
                        continue
                    try:
                        datetime.strptime(dob,"%d%m%Y")
                    except ValueError:
                        skipped.append(f"Row {line}: DOB must be a real date in DDMMYYYY format")
                        continue
                    exists = con.execute("SELECT 1 FROM users WHERE username=?",(prn,)).fetchone()
                    if exists:
                        skipped.append(f"Row {line}: PRN {prn} already exists")
                        continue
                    con.execute("""INSERT INTO users(name,username,password_hash,role,must_change_password)
                        VALUES(?,?,?,?,1)""",(name,prn,generate_password_hash(dob),"Student"))
                    added += 1
            flash(f"Import complete: {added} student(s) added; {len(skipped)} row(s) skipped.", "success")
            for msg in skipped[:8]: flash(msg, "error")
        except Exception as exc:
            flash(str(exc), "error")
        return redirect(url_for("members"))
    return render_template("bulk_import.html")

@app.route("/download-template")
@roles_required("Dean","Super Admin")
def download_template():
    data = "name,prn,dob\nExample Student,2024BTAM011,01012006\n"
    return send_file(io.BytesIO(data.encode()), mimetype="text/csv", as_attachment=True,
                     download_name="spirit_student_import_template.csv")

@app.route("/calendar")
@login_required
def calendar_view():
    with db() as con:
        rows = con.execute("""SELECT b.*,r.name room_name,u.name user_name FROM bookings b
            JOIN rooms r ON r.id=b.room_id JOIN users u ON u.id=b.user_id
            WHERE b.status IN ('Pending','Confirmed') ORDER BY b.booking_date,b.start_time""").fetchall()
    if session.get("role") == "Student":
        rows = [dict(row) for row in rows]
        for row in rows:
            row["user_name"] = "Private"
    return render_template("calendar.html", bookings=rows)


@app.route("/classes")
@login_required
def classes():
    with db() as con:
        rows = con.execute("""
            SELECT s.*, r.name room_name, r.room_type, r.building, r.image,
                   u.name faculty_name,
                   (SELECT COUNT(*) FROM bookings b
                    WHERE b.session_id=s.id AND b.status IN ('Pending','Confirmed')) booked_count
            FROM class_sessions s JOIN rooms r ON r.id=s.room_id
            JOIN users u ON u.id=s.faculty_id
            WHERE s.is_open=1 AND s.class_date >= date('now','localtime')
            ORDER BY s.class_date,s.start_time
        """).fetchall()
        rows = [dict(row) | {"available_seats": max(0,row["seat_limit"]-row["booked_count"])} for row in rows]
    return render_template("classes.html", classes=rows)

@app.route("/classes/open", methods=["GET","POST"])
@roles_required("Faculty","Administrator","Dean","Super Admin")
def open_class():
    with db() as con:
        rooms = con.execute("SELECT * FROM rooms ORDER BY name").fetchall()
    if request.method == "POST":
        room_id=request.form.get("room_id",type=int)
        class_date=request.form.get("class_date","")
        start=request.form.get("start_time","")
        end=request.form.get("end_time","")
        purpose=request.form.get("purpose","").strip()
        seat_limit=request.form.get("seat_limit",type=int)
        try:
            datetime.strptime(class_date,"%Y-%m-%d")
            valid=bool(room_id and start and end and start<end and purpose and seat_limit and seat_limit>0)
        except ValueError:
            valid=False
        if not valid:
            flash("Please enter a valid room, date, time, purpose and positive seat count.","error")
        else:
            with db() as con:
                room=con.execute("SELECT capacity FROM rooms WHERE id=?",(room_id,)).fetchone()
                if not room:
                    flash("Selected classroom was not found.","error")
                elif seat_limit>room["capacity"]:
                    flash(f"Seat limit cannot exceed room capacity ({room['capacity']}).","error")
                else:
                    try:
                        con.execute("""INSERT INTO class_sessions
                            (room_id,faculty_id,class_date,start_time,end_time,purpose,seat_limit)
                            VALUES(?,?,?,?,?,?,?)""",
                            (room_id,session["user_id"],class_date,start,end,purpose,seat_limit))
                        flash("Classroom opened for student booking.","success")
                        return redirect(url_for("classes"))
                    except sqlite3.IntegrityError:
                        flash("A class opening already exists for this room and time.","error")
    return render_template("open_class.html",rooms=rooms)

@app.route("/classes/<int:class_id>/book",methods=["POST"])
@roles_required("Student")
def book_class(class_id):
    with db() as con:
        con.execute("BEGIN IMMEDIATE")
        slot=con.execute("""SELECT * FROM class_sessions
            WHERE id=? AND is_open=1 AND class_date>=date('now','localtime')""",(class_id,)).fetchone()
        if not slot:
            flash("This class is no longer open for booking.","error")
            return redirect(url_for("classes"))
        active=con.execute("""SELECT COUNT(*) FROM bookings
            WHERE user_id=? AND status IN ('Pending','Confirmed')""",(session["user_id"],)).fetchone()[0]
        if active:
            flash("You already have an active classroom booking. Cancel it before booking another class.","error")
            return redirect(url_for("classes"))
        booked=con.execute("""SELECT COUNT(*) FROM bookings
            WHERE session_id=? AND status IN ('Pending','Confirmed')""",(class_id,)).fetchone()[0]
        if booked>=slot["seat_limit"]:
            flash("Sorry, this class is fully booked.","error")
            return redirect(url_for("classes"))
        con.execute("""INSERT INTO bookings
            (user_id,room_id,booking_date,start_time,end_time,purpose,status,session_id)
            VALUES(?,?,?,?,?,?,?,?)""",
            (session["user_id"],slot["room_id"],slot["class_date"],slot["start_time"],
             slot["end_time"],slot["purpose"],"Confirmed",class_id))
        flash("Your class seat is confirmed.","success")
    return redirect(url_for("my_bookings"))

@app.route("/classes/<int:class_id>/close",methods=["POST"])
@roles_required("Faculty","Administrator","Dean","Super Admin")
def close_class(class_id):
    with db() as con:
        slot=con.execute("SELECT * FROM class_sessions WHERE id=?",(class_id,)).fetchone()
        if not slot: abort(404)
        if session.get("role")=="Faculty" and slot["faculty_id"]!=session["user_id"]:
            abort(403)
        con.execute("UPDATE class_sessions SET is_open=0 WHERE id=?",(class_id,))
        flash("Class booking has been closed.","success")
    return redirect(url_for("classes"))

@app.route("/booking/<int:booking_id>/cancel",methods=["POST"])
@login_required
def cancel_booking(booking_id):
    with db() as con:
        row=con.execute("""SELECT * FROM bookings WHERE id=? AND user_id=?
            AND status IN ('Pending','Confirmed')""",(booking_id,session["user_id"])).fetchone()
        if not row:
            flash("Active booking not found.","error")
        else:
            con.execute("UPDATE bookings SET status='Cancelled' WHERE id=?",(booking_id,))
            flash("Booking cancelled. The seat is available again.","success")
    return redirect(url_for("my_bookings"))

@app.errorhandler(403)
def forbidden(_):
    return render_template("error.html", code=403, message="You do not have permission to access this page."),403

@app.errorhandler(404)
def not_found(_):
    return render_template("error.html", code=404, message="The page or record could not be found."),404

if __name__ == "__main__":
    init_db()
    seed_accounts()
    app.run(debug=True)
