"""
Passport Automation System
A full-stack demo web application for passport applications, document upload,
appointment scheduling, application tracking, and an admin back-office.

Run with: python app.py
Then visit http://127.0.0.1:5000
"""

import os
import sqlite3
import random
import io

from datetime import datetime, timedelta
from functools import wraps

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    jsonify,
    g,
    flash,
    send_file,
)

from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DB_PATH = os.path.join(
    BASE_DIR,
    "database.db"
)

UPLOAD_DIR = os.path.join(
    BASE_DIR,
    "static",
    "uploads"
)

os.makedirs(
    UPLOAD_DIR,
    exist_ok=True
)

app = Flask(__name__)

app.secret_key = os.environ.get(
    "SECRET_KEY",
    "passport-automation-system-demo-secret-key"
)

app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024


# --------------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------------

TRACKING_STAGES = [
    "Application Submitted",
    "Documents Uploaded",
    "Document Verification",
    "Appointment Scheduled",
    "Police Verification",
    "Passport Printing",
    "Passport Dispatched",
    "Completed",
]


DOCUMENT_TYPES = [
    ("identity_proof", "Identity Proof"),
    ("address_proof", "Address Proof"),
    ("dob_proof", "Date of Birth Proof"),
    ("photograph", "Photograph"),
    ("signature", "Signature"),
]


PASSPORT_OFFICES = [
    "Regional Passport Office - Central",
    "Regional Passport Office - North",
    "Regional Passport Office - East",
    "Regional Passport Office - West",
]


TIME_SLOTS = [
    "09:00 AM",
    "09:30 AM",
    "10:00 AM",
    "10:30 AM",
    "11:00 AM",
    "11:30 AM",
    "12:00 PM",
    "02:00 PM",
    "02:30 PM",
    "03:00 PM",
    "03:30 PM",
    "04:00 PM",
]


# --------------------------------------------------------------------------
# Database helpers
# --------------------------------------------------------------------------

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(
            DB_PATH,
            timeout=30
        )

        g.db.row_factory = sqlite3.Row

        g.db.execute(
            "PRAGMA foreign_keys = ON"
        )

    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop(
        "db",
        None
    )

    if db is not None:
        db.close()


def init_db(reset=False):

    # Delete old database when reset is requested
    if reset and os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    first_run = not os.path.exists(DB_PATH)

    db = sqlite3.connect(
        DB_PATH,
        timeout=30
    )

    db.execute(
        "PRAGMA foreign_keys = ON"
    )

    # ----------------------------------------------------------------------
    # Create tables
    # ----------------------------------------------------------------------

    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            phone TEXT,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            application_id TEXT UNIQUE NOT NULL,
            user_id INTEGER NOT NULL,
            full_name TEXT,
            dob TEXT,
            gender TEXT,
            email TEXT,
            mobile TEXT,
            address TEXT,
            city TEXT,
            state TEXT,
            pincode TEXT,
            passport_type TEXT,
            status TEXT NOT NULL DEFAULT 'Application Submitted',
            progress INTEGER NOT NULL DEFAULT 12,
            payment_status TEXT NOT NULL DEFAULT 'Pending',
            step_completed INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (user_id)
                REFERENCES users (id)
        );

        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            application_id TEXT NOT NULL,
            doc_type TEXT NOT NULL,
            filename TEXT NOT NULL,
            original_name TEXT NOT NULL,
            verified INTEGER NOT NULL DEFAULT 0,
            uploaded_at TEXT NOT NULL,
            FOREIGN KEY (application_id)
                REFERENCES applications (application_id)
        );

        CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            application_id TEXT NOT NULL,
            office TEXT,
            appt_date TEXT,
            appt_time TEXT,
            status TEXT NOT NULL DEFAULT 'Confirmed',
            created_at TEXT NOT NULL,
            FOREIGN KEY (application_id)
                REFERENCES applications (application_id)
        );

        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            is_read INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id)
                REFERENCES users (id)
        );
        """
    )

    db.commit()

    # ----------------------------------------------------------------------
    # IMPORTANT:
    # Render may have a database file that exists but contains no users.
    # Seed demo data only when the database is empty.
    # ----------------------------------------------------------------------

    user_count = db.execute(
        "SELECT COUNT(*) FROM users"
    ).fetchone()[0]

    if first_run or reset or user_count == 0:

        seed_demo_data(db)

    else:

        # Make sure admin account exists
        admin_exists = db.execute(
            """
            SELECT id
            FROM users
            WHERE email = ?
            AND role = 'admin'
            """,
            ("admin@passport.gov",)
        ).fetchone()

        if not admin_exists:

            db.execute(
                """
                INSERT INTO users
                (
                    full_name,
                    email,
                    phone,
                    password_hash,
                    role,
                    created_at
                )
                VALUES (?, ?, ?, ?, 'admin', ?)
                """,
                (
                    "System Administrator",
                    "admin@passport.gov",
                    "9999999999",
                    generate_password_hash("admin1234"),
                    now_iso(),
                ),
            )

            db.commit()

    db.close()


def gen_application_id(db):

    while True:

        candidate = (
            f"PAS-2026-"
            f"{random.randint(100000, 999999)}"
        )

        exists = db.execute(
            """
            SELECT 1
            FROM applications
            WHERE application_id = ?
            """,
            (candidate,)
        ).fetchone()

        if not exists:
            return candidate


def now_iso():
    return datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )


def add_notification(
    db,
    user_id,
    title,
    message
):

    db.execute(
        """
        INSERT INTO notifications
        (
            user_id,
            title,
            message,
            created_at
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            user_id,
            title,
            message,
            now_iso()
        ),
    )


def seed_demo_data(db):

    # ----------------------------------------------------------------------
    # Demo user
    # ----------------------------------------------------------------------

    pw = generate_password_hash(
        "demo1234"
    )

    cur = db.execute(
        """
        INSERT INTO users
        (
            full_name,
            email,
            phone,
            password_hash,
            role,
            created_at
        )
        VALUES (?, ?, ?, ?, 'user', ?)
        """,
        (
            "Aditya Sharma",
            "demo@passport.gov",
            "9876543210",
            pw,
            now_iso(),
        ),
    )

    user_id = cur.lastrowid

    # ----------------------------------------------------------------------
    # Demo admin
    # ----------------------------------------------------------------------

    admin_pw = generate_password_hash(
        "admin1234"
    )

    db.execute(
        """
        INSERT INTO users
        (
            full_name,
            email,
            phone,
            password_hash,
            role,
            created_at
        )
        VALUES (?, ?, ?, ?, 'admin', ?)
        """,
        (
            "System Administrator",
            "admin@passport.gov",
            "9999999999",
            admin_pw,
            now_iso(),
        ),
    )

    # ----------------------------------------------------------------------
    # Demo application
    # ----------------------------------------------------------------------

    app_id = "PAS-2026-001245"

    db.execute(
        """
        INSERT INTO applications
        (
            application_id,
            user_id,
            full_name,
            dob,
            gender,
            email,
            mobile,
            address,
            city,
            state,
            pincode,
            passport_type,
            status,
            progress,
            payment_status,
            step_completed,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            app_id,
            user_id,
            "Aditya Sharma",
            "1996-04-12",
            "Male",
            "demo@passport.gov",
            "9876543210",
            "221B, Lake View Residency",
            "Kolkata",
            "West Bengal",
            "700019",
            "New Passport",
            "Document Verification",
            65,
            "Paid",
            5,
            now_iso(),
            now_iso(),
        ),
    )

    # ----------------------------------------------------------------------
    # Demo documents
    # ----------------------------------------------------------------------

    for doc_type, _ in DOCUMENT_TYPES:

        db.execute(
            """
            INSERT INTO documents
            (
                application_id,
                doc_type,
                filename,
                original_name,
                verified,
                uploaded_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                app_id,
                doc_type,
                f"sample_{doc_type}.pdf",
                f"{doc_type}.pdf",
                1 if doc_type != "signature" else 0,
                now_iso(),
            ),
        )

    # ----------------------------------------------------------------------
    # Demo appointment
    # ----------------------------------------------------------------------

    db.execute(
        """
        INSERT INTO appointments
        (
            application_id,
            office,
            appt_date,
            appt_time,
            status,
            created_at
        )
        VALUES (?, ?, ?, ?, 'Confirmed', ?)
        """,
        (
            app_id,
            PASSPORT_OFFICES[0],
            (
                datetime.now()
                + timedelta(days=5)
            ).strftime("%Y-%m-%d"),
            "11:00 AM",
            now_iso(),
        ),
    )

    # ----------------------------------------------------------------------
    # Demo notifications
    # ----------------------------------------------------------------------

    add_notification(
        db,
        user_id,
        "Application submitted",
        (
            f"Your application {app_id} "
            "has been submitted successfully."
        ),
    )

    add_notification(
        db,
        user_id,
        "Documents uploaded",
        (
            "All required documents were received "
            "and are under review."
        ),
    )

    add_notification(
        db,
        user_id,
        "Appointment confirmed",
        (
            "Your passport office appointment "
            "has been confirmed for next week."
        ),
    )

    # ----------------------------------------------------------------------
    # Extra demo applications
    # ----------------------------------------------------------------------

    sample_names = [
        ("Priya Nair", "Kochi", "Kerala"),
        ("Rohan Mehta", "Pune", "Maharashtra"),
        ("Sara Khan", "Lucknow", "Uttar Pradesh"),
        ("Ibrahim Ali", "Hyderabad", "Telangana"),
        ("Ananya Das", "Kolkata", "West Bengal"),
        ("Vikram Singh", "Jaipur", "Rajasthan"),
        ("Neha Verma", "Indore", "Madhya Pradesh"),
        ("Karan Kapoor", "Chandigarh", "Punjab"),
    ]

    statuses = [
        "Application Submitted",
        "Document Verification",
        "Police Verification",
        "Passport Printing",
        "Passport Dispatched",
        "Completed",
        "Document Verification",
    ]

    for i, (name, city, state) in enumerate(
        sample_names
    ):

        email = (
            name.lower()
            .replace(" ", ".")
            + "@example.com"
        )

        pw2 = generate_password_hash(
            "demo1234"
        )

        cur2 = db.execute(
            """
            INSERT INTO users
            (
                full_name,
                email,
                phone,
                password_hash,
                role,
                created_at
            )
            VALUES (?, ?, ?, ?, 'user', ?)
            """,
            (
                name,
                email,
                "90000000" + str(i).zfill(2),
                pw2,
                now_iso(),
            ),
        )

        uid = cur2.lastrowid

        aid = gen_application_id(db)

        status = statuses[
            i % len(statuses)
        ]

        progress = {
            "Application Submitted": 12,
            "Document Verification": 45,
            "Police Verification": 65,
            "Passport Printing": 85,
            "Passport Dispatched": 95,
            "Completed": 100,
        }[status]

        created = (
            datetime.now()
            - timedelta(
                days=random.randint(1, 60)
            )
        ).strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        db.execute(
            """
            INSERT INTO applications
            (
                application_id,
                user_id,
                full_name,
                dob,
                gender,
                email,
                mobile,
                address,
                city,
                state,
                pincode,
                passport_type,
                status,
                progress,
                payment_status,
                step_completed,
                created_at,
                updated_at
            )
            VALUES
            (
                ?, ?, ?, '1998-01-01', 'Other', ?, ?,
                'Sample Address', ?, ?, '500001',
                ?, ?, ?, 'Paid', 5, ?, ?
            )
            """,
            (
                aid,
                uid,
                name,
                email,
                "9000000000",
                city,
                state,
                random.choice(
                    [
                        "New Passport",
                        "Renewal",
                        "Reissue",
                    ]
                ),
                status,
                progress,
                created,
                created,
            ),
        )

    db.commit()


# --------------------------------------------------------------------------
# Auth helpers
# --------------------------------------------------------------------------

def login_required(view):

    @wraps(view)
    def wrapped(*args, **kwargs):

        if not session.get("user_id"):

            return redirect(
                url_for(
                    "login",
                    next=request.path
                )
            )

        return view(
            *args,
            **kwargs
        )

    return wrapped


def admin_required(view):

    @wraps(view)
    def wrapped(*args, **kwargs):

        if not session.get("user_id"):

            return redirect(
                url_for(
                    "login",
                    next=request.path
                )
            )

        if session.get("role") != "admin":

            return redirect(
                url_for("dashboard")
            )

        return view(
            *args,
            **kwargs
        )

    return wrapped


def current_user():

    if not session.get("user_id"):
        return None

    db = get_db()

    return db.execute(
        """
        SELECT *
        FROM users
        WHERE id = ?
        """,
        (session["user_id"],)
    ).fetchone()


@app.context_processor
def inject_globals():

    return {
        "current_user": current_user(),
        "current_year": datetime.now().year
    }


# --------------------------------------------------------------------------
# Public pages
# --------------------------------------------------------------------------

@app.route("/")
def index():

    return render_template(
        "index.html"
    )


@app.route("/faq")
def faq():

    return render_template(
        "index.html",
        scroll_to="faq"
    )


@app.route(
    "/register",
    methods=["GET", "POST"]
)
def register():

    if request.method == "POST":

        db = get_db()

        full_name = request.form.get(
            "full_name",
            ""
        ).strip()

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        phone = request.form.get(
            "phone",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        )

        if (
            not full_name
            or not email
            or not password
        ):

            flash(
                "Please fill in all required fields.",
                "error"
            )

            return render_template(
                "register.html"
            )

        existing = db.execute(
            """
            SELECT id
            FROM users
            WHERE email = ?
            """,
            (email,)
        ).fetchone()

        if existing:

            flash(
                "An account with this email already exists. Please log in.",
                "error"
            )

            return render_template(
                "register.html"
            )

        pw_hash = generate_password_hash(
            password
        )

        cur = db.execute(
            """
            INSERT INTO users
            (
                full_name,
                email,
                phone,
                password_hash,
                role,
                created_at
            )
            VALUES (?, ?, ?, ?, 'user', ?)
            """,
            (
                full_name,
                email,
                phone,
                pw_hash,
                now_iso(),
            ),
        )

        db.commit()

        session["user_id"] = cur.lastrowid
        session["role"] = "user"
        session["full_name"] = full_name

        flash(
            "Account created successfully. Welcome!",
            "success"
        )

        return redirect(
            url_for("dashboard")
        )

    return render_template(
        "register.html"
    )


@app.route(
    "/login",
    methods=["GET", "POST"]
)
def login():

    if request.method == "POST":

        db = get_db()

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        password = request.form.get(
            "password",
            ""
        )

        user = db.execute(
            """
            SELECT *
            FROM users
            WHERE email = ?
            """,
            (email,)
        ).fetchone()

        if user and check_password_hash(
            user["password_hash"],
            password
        ):

            session["user_id"] = user["id"]
            session["role"] = user["role"]
            session["full_name"] = user["full_name"]

            if user["role"] == "admin":

                return redirect(
                    url_for(
                        "admin_dashboard"
                    )
                )

            return redirect(
                request.args.get("next")
                or url_for("dashboard")
            )

        flash(
            "Invalid email or password.",
            "error"
        )

    return render_template(
        "login.html"
    )


@app.route("/logout")
def logout():

    session.clear()

    return redirect(
        url_for("index")
    )


# --------------------------------------------------------------------------
# Official / Admin Login
# --------------------------------------------------------------------------

@app.route(
    "/official-login",
    methods=["GET", "POST"]
)
def official_login():

    if request.method == "POST":

        db = get_db()

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        password = request.form.get(
            "password",
            ""
        )

        if not email or not password:

            flash(
                "Please enter official email and password.",
                "error"
            )

            return render_template(
                "official_login.html"
            )

        user = db.execute(
            """
            SELECT *
            FROM users
            WHERE email = ?
            """,
            (email,)
        ).fetchone()

        if not user or not check_password_hash(
            user["password_hash"],
            password
        ):

            flash(
                "Invalid official email or password.",
                "error"
            )

            return render_template(
                "official_login.html"
            )

        if user["role"] != "admin":

            flash(
                "Access denied. This portal is only for authorized officials.",
                "error"
            )

            return render_template(
                "official_login.html"
            )

        session["user_id"] = user["id"]
        session["role"] = user["role"]
        session["full_name"] = user["full_name"]

        flash(
            "Official login successful.",
            "success"
        )

        return redirect(
            url_for(
                "admin_dashboard"
            )
        )

    return render_template(
        "official_login.html"
    )


# --------------------------------------------------------------------------
# User dashboard
# --------------------------------------------------------------------------

@app.route("/dashboard")
@login_required
def dashboard():

    db = get_db()

    user = current_user()

    application = db.execute(
        """
        SELECT *
        FROM applications
        WHERE user_id = ?
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (user["id"],),
    ).fetchone()

    documents = []

    appointment = None

    if application:

        documents = db.execute(
            """
            SELECT *
            FROM documents
            WHERE application_id = ?
            """,
            (
                application["application_id"],
            ),
        ).fetchall()

        appointment = db.execute(
            """
            SELECT *
            FROM appointments
            WHERE application_id = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (
                application["application_id"],
            ),
        ).fetchone()

    notifications = db.execute(
        """
        SELECT *
        FROM notifications
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT 6
        """,
        (user["id"],)
    ).fetchall()

    docs_verified = sum(
        1
        for d in documents
        if d["verified"]
    )

    return render_template(
        "dashboard.html",
        application=application,
        documents=documents,
        docs_total=len(DOCUMENT_TYPES),
        docs_verified=docs_verified,
        appointment=appointment,
        notifications=notifications,
    )


# --------------------------------------------------------------------------
# Application
# --------------------------------------------------------------------------

@app.route(
    "/application",
    methods=["GET"]
)
@login_required
def application_form():

    db = get_db()

    user = current_user()

    application = db.execute(
        """
        SELECT *
        FROM applications
        WHERE user_id = ?
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (user["id"],),
    ).fetchone()

    documents = {}

    if application:

        for d in db.execute(
            """
            SELECT *
            FROM documents
            WHERE application_id = ?
            """,
            (
                application["application_id"],
            )
        ).fetchall():

            documents[d["doc_type"]] = d

    return render_template(
        "application.html",
        application=application,
        documents=documents,
        document_types=DOCUMENT_TYPES,
    )


@app.route(
    "/api/application/save-step",
    methods=["POST"]
)
@login_required
def api_save_step():

    db = get_db()

    user = current_user()

    data = request.get_json(
        force=True
    )

    step = int(
        data.get(
            "step",
            1
        )
    )

    application = db.execute(
        """
        SELECT *
        FROM applications
        WHERE user_id = ?
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (user["id"],),
    ).fetchone()

    if not application:

        app_id = gen_application_id(
            db
        )

        db.execute(
            """
            INSERT INTO applications
            (
                application_id,
                user_id,
                status,
                progress,
                step_completed,
                created_at,
                updated_at
            )
            VALUES
            (
                ?,
                ?,
                'Application Submitted',
                12,
                1,
                ?,
                ?
            )
            """,
            (
                app_id,
                user["id"],
                now_iso(),
                now_iso(),
            ),
        )

        db.commit()

        application = db.execute(
            """
            SELECT *
            FROM applications
            WHERE application_id = ?
            """,
            (app_id,)
        ).fetchone()

    app_id = application[
        "application_id"
    ]

    fields = {}

    if step == 1:

        fields = {
            k: data.get(k, "")
            for k in [
                "full_name",
                "dob",
                "gender",
                "email",
                "mobile"
            ]
        }

    elif step == 2:

        fields = {
            k: data.get(k, "")
            for k in [
                "address",
                "city",
                "state",
                "pincode"
            ]
        }

    elif step == 3:

        fields = {
            "passport_type":
                data.get(
                    "passport_type",
                    "New Passport"
                )
        }

    if fields:

        set_clause = ", ".join(
            f"{k} = ?"
            for k in fields
        )

        db.execute(
            f"""
            UPDATE applications
            SET {set_clause},
                step_completed = MAX(step_completed, ?),
                updated_at = ?
            WHERE application_id = ?
            """,
            (
                *fields.values(),
                step + 1,
                now_iso(),
                app_id,
            ),
        )

        db.commit()

    return jsonify(
        {
            "ok": True,
            "application_id": app_id
        }
    )


@app.route(
    "/api/application/upload-document",
    methods=["POST"]
)
@login_required
def api_upload_document():

    db = get_db()

    user = current_user()

    doc_type = request.form.get(
        "doc_type"
    )

    application = db.execute(
        """
        SELECT *
        FROM applications
        WHERE user_id = ?
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (user["id"],),
    ).fetchone()

    if (
        not application
        or doc_type not in dict(DOCUMENT_TYPES)
    ):

        return jsonify(
            {
                "ok": False,
                "error": "Invalid request."
            }
        ), 400

    file = request.files.get(
        "file"
    )

    if (
        not file
        or file.filename == ""
    ):

        return jsonify(
            {
                "ok": False,
                "error": "No file selected."
            }
        ), 400

    app_id = application[
        "application_id"
    ]

    ext = (
        os.path.splitext(
            secure_filename(
                file.filename
            )
        )[1]
        or ".dat"
    )

    stored_name = (
        f"{app_id}_{doc_type}_"
        f"{int(datetime.now().timestamp())}"
        f"{ext}"
    )

    file.save(
        os.path.join(
            UPLOAD_DIR,
            stored_name
        )
    )

    db.execute(
        """
        DELETE FROM documents
        WHERE application_id = ?
        AND doc_type = ?
        """,
        (
            app_id,
            doc_type
        ),
    )

    db.execute(
        """
        INSERT INTO documents
        (
            application_id,
            doc_type,
            filename,
            original_name,
            verified,
            uploaded_at
        )
        VALUES (?, ?, ?, ?, 0, ?)
        """,
        (
            app_id,
            doc_type,
            stored_name,
            file.filename,
            now_iso(),
        ),
    )

    db.execute(
        """
        UPDATE applications
        SET updated_at = ?
        WHERE application_id = ?
        """,
        (
            now_iso(),
            app_id
        ),
    )

    db.commit()

    return jsonify(
        {
            "ok": True,
            "filename": stored_name,
            "original_name": file.filename
        }
    )


@app.route(
    "/api/application/remove-document",
    methods=["POST"]
)
@login_required
def api_remove_document():

    db = get_db()

    user = current_user()

    doc_type = request.get_json(
        force=True
    ).get("doc_type")

    application = db.execute(
        """
        SELECT *
        FROM applications
        WHERE user_id = ?
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (user["id"],),
    ).fetchone()

    if application:

        db.execute(
            """
            DELETE FROM documents
            WHERE application_id = ?
            AND doc_type = ?
            """,
            (
                application[
                    "application_id"
                ],
                doc_type,
            ),
        )

        db.commit()

    return jsonify(
        {
            "ok": True
        }
    )


@app.route(
    "/api/application/submit",
    methods=["POST"]
)
@login_required
def api_submit_application():

    db = get_db()

    user = current_user()

    application = db.execute(
        """
        SELECT *
        FROM applications
        WHERE user_id = ?
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (user["id"],),
    ).fetchone()

    if not application:

        return jsonify(
            {
                "ok": False,
                "error": "No application found."
            }
        ), 400

    app_id = application[
        "application_id"
    ]

    db.execute(
        """
        UPDATE applications
        SET status = 'Documents Uploaded',
            progress = 30,
            payment_status = 'Paid',
            step_completed = 5,
            updated_at = ?
        WHERE application_id = ?
        """,
        (
            now_iso(),
            app_id
        ),
    )

    add_notification(
        db,
        user["id"],
        "Application submitted",
        (
            f"Your application {app_id} "
            "has been submitted and is now under review."
        ),
    )

    db.commit()

    return jsonify(
        {
            "ok": True,
            "application_id": app_id
        }
    )


# --------------------------------------------------------------------------
# Receipt
# --------------------------------------------------------------------------

@app.route(
    "/api/application/<application_id>/receipt"
)
@login_required
def download_application_receipt(
    application_id
):

    db = get_db()

    application_id = (
        application_id
        .strip()
        .upper()
    )

    application = db.execute(
        """
        SELECT *
        FROM applications
        WHERE application_id = ?
        AND user_id = ?
        """,
        (
            application_id,
            session["user_id"]
        )
    ).fetchone()

    if not application:

        return jsonify(
            {
                "ok": False,
                "error": "Application not found."
            }
        ), 404

    buffer = io.BytesIO()

    pdf = canvas.Canvas(
        buffer,
        pagesize=A4
    )

    width, height = A4

    left = 50

    y = height - 60

    pdf.setTitle(
        f"Passport Receipt - "
        f"{application['application_id']}"
    )

    pdf.setFont(
        "Helvetica-Bold",
        20
    )

    pdf.drawString(
        left,
        y,
        "PASSPORT AUTOMATION SYSTEM"
    )

    y -= 24

    pdf.setFont(
        "Helvetica",
        10
    )

    pdf.drawString(
        left,
        y,
        "Official Application Receipt"
    )

    y -= 18

    pdf.line(
        left,
        y,
        width - left,
        y
    )

    y -= 40

    pdf.setFont(
        "Helvetica-Bold",
        13
    )

    pdf.drawString(
        left,
        y,
        "Application Details"
    )

    y -= 30

    details = [
        (
            "Application ID",
            application[
                "application_id"
            ]
        ),
        (
            "Applicant Name",
            application[
                "full_name"
            ]
        ),
        (
            "Email",
            application[
                "email"
            ]
        ),
        (
            "Mobile",
            application[
                "mobile"
            ]
        ),
        (
            "Passport Type",
            application[
                "passport_type"
            ] or "New Passport"
        ),
        (
            "Application Status",
            application[
                "status"
            ]
        ),
        (
            "Payment Status",
            application[
                "payment_status"
            ] or "Pending"
        ),
        (
            "Application Date",
            application[
                "created_at"
            ]
        ),
        (
            "Last Updated",
            application[
                "updated_at"
            ]
        ),
    ]

    for label, value in details:

        pdf.setFont(
            "Helvetica-Bold",
            10
        )

        pdf.drawString(
            left,
            y,
            f"{label}:"
        )

        pdf.setFont(
            "Helvetica",
            10
        )

        pdf.drawString(
            175,
            y,
            str(value or "-")
        )

        y -= 23

    y -= 10

    pdf.line(
        left,
        y,
        width - left,
        y
    )

    y -= 30

    payment_status = (
        application[
            "payment_status"
        ]
        or "Pending"
    )

    pdf.setFont(
        "Helvetica-Bold",
        12
    )

    pdf.drawString(
        left,
        y,
        f"Payment Status: {payment_status}"
    )

    y -= 45

    pdf.setFont(
        "Helvetica",
        9
    )

    pdf.drawString(
        left,
        y,
        "This is a system-generated application receipt."
    )

    y -= 16

    pdf.drawString(
        left,
        y,
        "Please keep this receipt for your records."
    )

    y -= 35

    pdf.setFont(
        "Helvetica-Oblique",
        8
    )

    pdf.drawString(
        left,
        y,
        "Passport Automation System - Demo Application"
    )

    pdf.save()

    buffer.seek(0)

    return send_file(
        buffer,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=(
            f"Passport_Receipt_"
            f"{application['application_id']}.pdf"
        )
    )


# --------------------------------------------------------------------------
# Tracking
# --------------------------------------------------------------------------

@app.route("/track")
def track_page():

    return render_template(
        "tracking.html"
    )


@app.route(
    "/api/track/<application_id>"
)
def api_track(application_id):

    db = get_db()

    application_id = (
        application_id
        .strip()
        .upper()
    )

    if application_id.startswith(
        "2026-"
    ):

        application_id = (
            "PAS-" + application_id
        )

    application = db.execute(
        """
        SELECT *
        FROM applications
        WHERE application_id = ?
        """,
        (application_id,)
    ).fetchone()

    if not application:

        return jsonify(
            {
                "ok": False,
                "error": "No application found with that ID."
            }
        ), 404

    if application["status"] in TRACKING_STAGES:

        current_index = (
            TRACKING_STAGES.index(
                application["status"]
            )
        )

    else:

        current_index = 0

    stages = [
        {
            "name": stage,
            "done": i < current_index,
            "current": i == current_index
        }
        for i, stage in enumerate(
            TRACKING_STAGES
        )
    ]

    return jsonify(
        {
            "ok": True,
            "application_id":
                application[
                    "application_id"
                ],
            "full_name":
                application[
                    "full_name"
                ],
            "status":
                application[
                    "status"
                ],
            "progress":
                application[
                    "progress"
                ],
            "passport_type":
                application[
                    "passport_type"
                ],
            "updated_at":
                application[
                    "updated_at"
                ],
            "stages":
                stages,
        }
    )


# --------------------------------------------------------------------------
# Appointments
# --------------------------------------------------------------------------

@app.route("/appointment")
@login_required
def appointment_page():

    db = get_db()

    user = current_user()

    application = db.execute(
        """
        SELECT *
        FROM applications
        WHERE user_id = ?
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (user["id"],),
    ).fetchone()

    existing = None

    if application:

        existing = db.execute(
            """
            SELECT *
            FROM appointments
            WHERE application_id = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (
                application[
                    "application_id"
                ],
            ),
        ).fetchone()

    dates = [
        {
            "value": (
                datetime.now()
                + timedelta(days=i)
            ).strftime("%Y-%m-%d"),

            "dow": (
                datetime.now()
                + timedelta(days=i)
            ).strftime("%a"),

            "dom": (
                datetime.now()
                + timedelta(days=i)
            ).strftime("%d"),
        }

        for i in range(1, 15)
    ]

    return render_template(
        "appointment.html",
        application=application,
        existing=existing,
        offices=PASSPORT_OFFICES,
        dates=dates,
        slots=TIME_SLOTS,
    )


@app.route(
    "/api/appointment/book",
    methods=["POST"]
)
@login_required
def api_book_appointment():

    db = get_db()

    user = current_user()

    data = request.get_json(
        force=True
    )

    application = db.execute(
        """
        SELECT *
        FROM applications
        WHERE user_id = ?
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (user["id"],),
    ).fetchone()

    if not application:

        return jsonify(
            {
                "ok": False,
                "error":
                    "Please complete your application first."
            }
        ), 400

    app_id = application[
        "application_id"
    ]

    office = data.get(
        "office"
    )

    date = data.get(
        "date"
    )

    time_slot = data.get(
        "time"
    )

    if not (
        office
        and date
        and time_slot
    ):

        return jsonify(
            {
                "ok": False,
                "error":
                    "Please choose office, date and time."
            }
        ), 400

    db.execute(
        """
        DELETE FROM appointments
        WHERE application_id = ?
        """,
        (app_id,)
    )

    db.execute(
        """
        INSERT INTO appointments
        (
            application_id,
            office,
            appt_date,
            appt_time,
            status,
            created_at
        )
        VALUES (?, ?, ?, ?, 'Confirmed', ?)
        """,
        (
            app_id,
            office,
            date,
            time_slot,
            now_iso(),
        ),
    )

    db.execute(
        """
        UPDATE applications
        SET status = 'Appointment Scheduled',
            progress = MAX(progress, 55),
            updated_at = ?
        WHERE application_id = ?
        """,
        (
            now_iso(),
            app_id
        ),
    )

    add_notification(
        db,
        user["id"],
        "Appointment confirmed",
        (
            f"Your appointment at {office} "
            f"on {date} at {time_slot} is confirmed."
        ),
    )

    db.commit()

    return jsonify(
        {
            "ok": True
        }
    )


# --------------------------------------------------------------------------
# Notifications
# --------------------------------------------------------------------------

@app.route(
    "/api/notifications/mark-read",
    methods=["POST"]
)
@login_required
def api_notifications_mark_read():

    db = get_db()

    db.execute(
        """
        UPDATE notifications
        SET is_read = 1
        WHERE user_id = ?
        """,
        (session["user_id"],)
    )

    db.commit()

    return jsonify(
        {
            "ok": True
        }
    )


# --------------------------------------------------------------------------
# Admin Dashboard
# --------------------------------------------------------------------------

@app.route("/admin")
@admin_required
def admin_dashboard():

    db = get_db()

    total = db.execute(
        """
        SELECT COUNT(*) c
        FROM applications
        """
    ).fetchone()["c"]

    pending = db.execute(
        """
        SELECT COUNT(*) c
        FROM applications
        WHERE status NOT IN ('Completed')
        """
    ).fetchone()["c"]

    approved = db.execute(
        """
        SELECT COUNT(*) c
        FROM applications
        WHERE status = 'Completed'
        """
    ).fetchone()["c"]

    today = datetime.now().strftime(
        "%Y-%m-%d"
    )

    appts_today = db.execute(
        """
        SELECT COUNT(*) c
        FROM appointments
        WHERE appt_date = ?
        """,
        (today,)
    ).fetchone()["c"]

    rejected = db.execute(
        """
        SELECT COUNT(*) c
        FROM applications
        WHERE status = 'Rejected'
        """
    ).fetchone()["c"]

    by_status = db.execute(
        """
        SELECT status, COUNT(*) c
        FROM applications
        GROUP BY status
        """
    ).fetchall()

    monthly = db.execute(
        """
        SELECT
            strftime('%Y-%m', created_at) ym,
            COUNT(*) c
        FROM applications
        GROUP BY ym
        ORDER BY ym
        """
    ).fetchall()

    recent = db.execute(
        """
        SELECT *
        FROM applications
        ORDER BY created_at DESC
        LIMIT 6
        """
    ).fetchall()

    return render_template(
        "admin/dashboard.html",
        total=total,
        pending=pending,
        approved=approved,
        rejected=rejected,
        appts_today=appts_today,
        by_status=by_status,
        monthly=monthly,
        recent=recent,
        active="dashboard",
    )


@app.route(
    "/admin/applications"
)
@admin_required
def admin_applications():

    db = get_db()

    q = request.args.get(
        "q",
        ""
    ).strip()

    status_filter = request.args.get(
        "status",
        ""
    )

    query = """
        SELECT *
        FROM applications
        WHERE 1=1
    """

    params = []

    if q:

        query += """
            AND (
                application_id LIKE ?
                OR full_name LIKE ?
                OR email LIKE ?
            )
        """

        params += [
            f"%{q}%",
            f"%{q}%",
            f"%{q}%"
        ]

    if status_filter:

        query += """
            AND status = ?
        """

        params.append(
            status_filter
        )

    query += """
        ORDER BY created_at DESC
    """

    applications = db.execute(
        query,
        params
    ).fetchall()

    return render_template(
        "admin/applications.html",
        applications=applications,
        stages=TRACKING_STAGES,
        q=q,
        status_filter=status_filter,
        active="applications",
    )


@app.route(
    "/admin/applications/<application_id>"
)
@admin_required
def admin_application_detail(
    application_id
):

    db = get_db()

    application = db.execute(
        """
        SELECT *
        FROM applications
        WHERE application_id = ?
        """,
        (application_id,)
    ).fetchone()

    if not application:

        return redirect(
            url_for(
                "admin_applications"
            )
        )

    documents = db.execute(
        """
        SELECT *
        FROM documents
        WHERE application_id = ?
        """,
        (application_id,)
    ).fetchall()

    appt = db.execute(
        """
        SELECT *
        FROM appointments
        WHERE application_id = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (application_id,)
    ).fetchone()

    return render_template(
        "admin/application_detail.html",
        application=application,
        documents=documents,
        appointment=appt,
        stages=TRACKING_STAGES,
        active="applications",
    )


@app.route(
    "/api/admin/application/<application_id>/status",
    methods=["POST"]
)
@admin_required
def api_admin_update_status(
    application_id
):

    db = get_db()

    new_status = request.get_json(
        force=True
    ).get("status")

    if new_status not in (
        TRACKING_STAGES + ["Rejected"]
    ):

        return jsonify(
            {
                "ok": False,
                "error": "Invalid status."
            }
        ), 400

    progress_map = {
        "Application Submitted": 12,
        "Documents Uploaded": 25,
        "Document Verification": 45,
        "Appointment Scheduled": 55,
        "Police Verification": 70,
        "Passport Printing": 85,
        "Passport Dispatched": 95,
        "Completed": 100,
        "Rejected": 100,
    }

    application = db.execute(
        """
        SELECT *
        FROM applications
        WHERE application_id = ?
        """,
        (application_id,)
    ).fetchone()

    if not application:

        return jsonify(
            {
                "ok": False,
                "error": "Not found."
            }
        ), 404

    db.execute(
        """
        UPDATE applications
        SET status = ?,
            progress = ?,
            updated_at = ?
        WHERE application_id = ?
        """,
        (
            new_status,
            progress_map.get(
                new_status,
                application["progress"]
            ),
            now_iso(),
            application_id,
        ),
    )

    add_notification(
        db,
        application["user_id"],
        "Application status updated",
        (
            f"Your application {application_id} "
            f"status changed to '{new_status}'."
        ),
    )

    db.commit()

    return jsonify(
        {
            "ok": True
        }
    )


@app.route(
    "/api/admin/document/<int:doc_id>/verify",
    methods=["POST"]
)
@admin_required
def api_admin_verify_document(
    doc_id
):

    db = get_db()

    verified = 1 if request.get_json(
        force=True
    ).get("verified") else 0

    db.execute(
        """
        UPDATE documents
        SET verified = ?
        WHERE id = ?
        """,
        (
            verified,
            doc_id
        )
    )

    db.commit()

    return jsonify(
        {
            "ok": True
        }
    )


@app.route(
    "/admin/appointments"
)
@admin_required
def admin_appointments():

    db = get_db()

    appts = db.execute(
        """
        SELECT
            appointments.*,
            applications.full_name,
            applications.email
        FROM appointments
        JOIN applications
            ON appointments.application_id =
               applications.application_id
        ORDER BY appt_date ASC
        """
    ).fetchall()

    return render_template(
        "admin/appointments.html",
        appointments=appts,
        active="appointments"
    )


@app.route(
    "/admin/users"
)
@admin_required
def admin_users():

    db = get_db()

    users = db.execute(
        """
        SELECT
            users.*,
            (
                SELECT COUNT(*)
                FROM applications
                WHERE applications.user_id = users.id
            ) AS application_count
        FROM users
        ORDER BY created_at DESC
        """
    ).fetchall()

    return render_template(
        "admin/users.html",
        users=users,
        active="users"
    )


@app.route(
    "/admin/documents"
)
@admin_required
def admin_documents():

    db = get_db()

    docs = db.execute(
        """
        SELECT
            documents.*,
            applications.full_name
        FROM documents
        JOIN applications
            ON documents.application_id =
               applications.application_id
        ORDER BY documents.uploaded_at DESC
        """
    ).fetchall()

    return render_template(
        "admin/documents.html",
        documents=docs,
        active="documents"
    )


@app.route(
    "/admin/reports"
)
@admin_required
def admin_reports():

    db = get_db()

    by_status = db.execute(
        """
        SELECT status, COUNT(*) c
        FROM applications
        GROUP BY status
        """
    ).fetchall()

    by_type = db.execute(
        """
        SELECT passport_type, COUNT(*) c
        FROM applications
        GROUP BY passport_type
        """
    ).fetchall()

    by_state = db.execute(
        """
        SELECT state, COUNT(*) c
        FROM applications
        WHERE state IS NOT NULL
        GROUP BY state
        ORDER BY c DESC
        LIMIT 8
        """
    ).fetchall()

    return render_template(
        "admin/reports.html",
        by_status=by_status,
        by_type=by_type,
        by_state=by_state,
        active="reports",
    )


@app.route(
    "/admin/settings"
)
@admin_required
def admin_settings():

    return render_template(
        "admin/settings.html",
        active="settings"
    )


# --------------------------------------------------------------------------
# Reset demo data
# --------------------------------------------------------------------------

@app.route(
    "/api/reset-demo-data",
    methods=["POST"]
)
@admin_required
def api_reset_demo_data():

    """
    Reset the SQLite demo database.
    Admin only.
    """

    init_db(
        reset=True
    )

    session.clear()

    return jsonify(
        {
            "ok": True
        }
    )


# --------------------------------------------------------------------------
# IMPORTANT FOR RENDER / GUNICORN
# --------------------------------------------------------------------------

# Initialize the database when the module is imported.
# Gunicorn uses: gunicorn app:app
# Therefore this code MUST run during import.
init_db(reset=False)


# --------------------------------------------------------------------------
# Local development
# --------------------------------------------------------------------------

if __name__ == "__main__":

    app.run(
        debug=True,
        port=5000
    )