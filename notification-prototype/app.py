import os
import sqlite3
from datetime import datetime, timezone
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    g,
    abort,
    jsonify,
)

# Allowed configuration constants
ALLOWED_CHANNELS = {"EMAIL", "SMS", "PUSH"}
ALLOWED_STATUSES = {"PENDING", "SENT", "FAILED"}
ALLOWED_SOURCES = {
    "YouTube",
    "WhatsApp",
    "Gmail",
    "Instagram",
    "Discord",
    "GitHub",
    "Calendar",
    "System",
}

# Realistic mock notifications across all requested categories
SAMPLE_NOTIFICATIONS = [
    {
        "app_source": "YouTube",
        "recipient": "user@youtube.com",
        "channel": "PUSH",
        "subject": "Marques Brownlee uploaded: The Ultimate Smartphone Review",
        "body": "Check out the in-depth camera tests, battery benchmarks, and long-term durability breakdown.",
        "status": "SENT",
        "is_read": 0,
        "created_at": "10 mins ago",
        "sent_at": "10 mins ago",
    },
    {
        "app_source": "WhatsApp",
        "recipient": "+1 (555) 234-5678",
        "channel": "SMS",
        "subject": "Alex Johnson (+1 555-0192)",
        "body": "Hey! Are we still meeting for the project demo at 3 PM? Let me know if you need the slides.",
        "status": "SENT",
        "is_read": 0,
        "created_at": "25 mins ago",
        "sent_at": "25 mins ago",
    },
    {
        "app_source": "Gmail",
        "recipient": "alex.dev@gmail.com",
        "channel": "EMAIL",
        "subject": "Security alert: New login from Windows",
        "body": "Your Google Account was recently signed into from a new Windows device near San Francisco, CA.",
        "status": "SENT",
        "is_read": 0,
        "created_at": "1 hour ago",
        "sent_at": "1 hour ago",
    },
    {
        "app_source": "Instagram",
        "recipient": "@sarah_designs",
        "channel": "PUSH",
        "subject": "sarah_designs and 4 others liked your post",
        "body": "Your recent post 'Galaxy UI Exploration' is trending in the UI/UX Community.",
        "status": "SENT",
        "is_read": 1,
        "created_at": "2 hours ago",
        "sent_at": "2 hours ago",
    },
    {
        "app_source": "Discord",
        "recipient": "AlexDev#1337",
        "channel": "PUSH",
        "subject": "#dev-chat • DevCommunity Server",
        "body": "@alex: Has anyone tested the new Docker Compose build on Windows with Python 3.12?",
        "status": "SENT",
        "is_read": 0,
        "created_at": "3 hours ago",
        "sent_at": "3 hours ago",
    },
    {
        "app_source": "GitHub",
        "recipient": "developer@github.com",
        "channel": "EMAIL",
        "subject": "Pull Request #42 merged in notification-prototype",
        "body": "dependabot merged: Bump pytest from 8.3.4 to 9.1.1 in /tests with 10 passing tests.",
        "status": "SENT",
        "is_read": 1,
        "created_at": "5 hours ago",
        "sent_at": "5 hours ago",
    },
    {
        "app_source": "Calendar",
        "recipient": "team-calendar@company.com",
        "channel": "PUSH",
        "subject": "Upcoming: Product Design Review in 15 mins",
        "body": "Daily sync on prototype dashboard, visual hierarchy, and release milestones. Join via Meet.",
        "status": "SENT",
        "is_read": 0,
        "created_at": "Yesterday",
        "sent_at": "Yesterday",
    },
    {
        "app_source": "System",
        "recipient": "localhost:5000",
        "channel": "PUSH",
        "subject": "System Update Available (v2.4.0)",
        "body": "Galaxy aesthetic styling updates and contrast improvements are ready to apply.",
        "status": "SENT",
        "is_read": 1,
        "created_at": "Yesterday",
        "sent_at": "Yesterday",
    },
]


def get_default_db_path() -> str:
    """Return default SQLite database file path."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_dir, "data", "notifications.db")


def init_db(db_path: str, seed_samples: bool = False) -> None:
    """Initialize SQLite database, apply migrations, and optionally seed samples."""
    # Ensure parent directory exists (unless using in-memory DB)
    if db_path != ":memory:":
        os.makedirs(os.path.dirname(db_path), exist_ok=True)

    conn = sqlite3.connect(db_path)
    try:
        with conn:
            conn.execute("PRAGMA foreign_keys = ON;")

            # Table 1: users
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    email TEXT,
                    phone TEXT,
                    created_at TEXT NOT NULL
                );
                """
            )

            # Table 2: notification_preferences
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS notification_preferences (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    channel TEXT NOT NULL,
                    opt_in INTEGER NOT NULL,
                    UNIQUE (user_id, channel),
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                );
                """
            )

            # Table 3: notifications
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS notifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    recipient TEXT NOT NULL,
                    channel TEXT NOT NULL,
                    app_source TEXT DEFAULT 'General',
                    subject TEXT NOT NULL,
                    body TEXT NOT NULL,
                    status TEXT NOT NULL,
                    is_read INTEGER DEFAULT 0,
                    retry_count INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL,
                    sent_at TEXT,
                    error_message TEXT,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
                );
                """
            )

            # Safely check and add columns if upgrading an existing database
            cursor = conn.execute("PRAGMA table_info(notifications);")
            existing_cols = {row[1] for row in cursor.fetchall()}
            if "app_source" not in existing_cols:
                conn.execute("ALTER TABLE notifications ADD COLUMN app_source TEXT DEFAULT 'General';")
            if "is_read" not in existing_cols:
                conn.execute("ALTER TABLE notifications ADD COLUMN is_read INTEGER DEFAULT 0;")

            # Seed realistic mock notifications if requested and empty of sample data
            if seed_samples:
                existing_count = conn.execute("SELECT COUNT(*) FROM notifications;").fetchone()[0]
                if existing_count == 0:
                    for s in SAMPLE_NOTIFICATIONS:
                        conn.execute(
                            """
                            INSERT INTO notifications (
                                user_id, recipient, channel, app_source, subject,
                                body, status, is_read, retry_count, created_at, sent_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                None,
                                s["recipient"],
                                s["channel"],
                                s["app_source"],
                                s["subject"],
                                s["body"],
                                s["status"],
                                s["is_read"],
                                0,
                                s["created_at"],
                                s["sent_at"],
                            ),
                        )
    finally:
        conn.close()


def send_fake_notification(channel: str, recipient: str, subject: str, body: str) -> bool:
    """
    Simulate delivering a notification by printing formatted text to standard output.
    Docker logs capture stdout directly.
    """
    output = (
        "\n----- FAKE NOTIFICATION -----\n"
        f"Channel: {channel}\n"
        f"Recipient: {recipient}\n"
        f"Subject: {subject}\n"
        f"Body: {body}\n"
        "-----------------------------\n"
    )
    # flush=True ensures the log is written immediately to Docker logs
    print(output, flush=True)
    return True


def create_app(test_config=None) -> Flask:
    """Application factory for the notification service."""
    app = Flask(__name__)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-secret-key-change-in-prod"),
        DATABASE=os.environ.get("DATABASE_PATH", get_default_db_path()),
    )

    if test_config:
        app.config.update(test_config)

    # Seed samples when NOT in testing mode
    should_seed = not app.config.get("TESTING", False)
    init_db(app.config["DATABASE"], seed_samples=should_seed)

    def get_db() -> sqlite3.Connection:
        """Provide a request-scoped database connection."""
        if "db" not in g:
            g.db = sqlite3.connect(app.config["DATABASE"])
            g.db.row_factory = sqlite3.Row
            g.db.execute("PRAGMA foreign_keys = ON;")
        return g.db

    @app.teardown_appcontext
    def close_db(exception=None):
        """Close database connection at the end of the request."""
        db = g.pop("db", None)
        if db is not None:
            db.close()

    # ---------------------------------------------------------
    # Routes
    # ---------------------------------------------------------

    @app.route("/", methods=["GET"])
    def index():
        """Home page with notification submission form and navigation."""
        return render_template("index.html")

    @app.route("/notifications", methods=["POST"])
    def create_notification():
        """
        Process notification submission:
        1. Validate input
        2. Insert notification with PENDING
        3. Call fake notification sender
        4. Print notification to Docker logs
        5. Change status to SENT
        6. Set sent_at
        7. If delivery fails, change status to FAILED and store error
        8. Redirect back to home page with status feedback
        """
        recipient = request.form.get("recipient", "").strip()
        channel = request.form.get("channel", "").strip().upper()
        app_source = request.form.get("app_source", "").strip()
        subject = request.form.get("subject", "").strip()
        body = request.form.get("body", "").strip()

        # Validation
        errors = []
        if not recipient:
            errors.append("Recipient is required.")
        if not channel:
            errors.append("Channel is required.")
        elif channel not in ALLOWED_CHANNELS:
            errors.append(f"Invalid channel '{channel}'. Allowed channels are: {', '.join(sorted(ALLOWED_CHANNELS))}.")
        if not subject:
            errors.append("Subject is required.")
        if not body:
            errors.append("Message body is required.")

        # Default source if none or invalid provided
        if not app_source or app_source not in ALLOWED_SOURCES:
            if channel == "EMAIL":
                app_source = "Gmail"
            elif channel == "SMS":
                app_source = "WhatsApp"
            else:
                app_source = "System"

        if errors:
            for err in errors:
                flash(err, "error")
            return (
                render_template(
                    "index.html",
                    recipient=recipient,
                    channel=channel,
                    app_source=app_source,
                    subject=subject,
                    body=body,
                    form_errors=errors,
                ),
                400,
            )

        # 1. Insert notification with PENDING status
        created_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        db = get_db()
        cursor = db.execute(
            """
            INSERT INTO notifications (
                user_id, recipient, channel, app_source, subject,
                body, status, is_read, retry_count, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (None, recipient, channel, app_source, subject, body, "PENDING", 0, 0, created_at),
        )
        notification_id = cursor.lastrowid
        db.commit()

        # 2. Fake notification delivery
        try:
            send_fake_notification(channel, recipient, subject, body)
            sent_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            db.execute(
                """
                UPDATE notifications
                SET status = ?, sent_at = ?
                WHERE id = ?
                """,
                ("SENT", sent_at, notification_id),
            )
            db.commit()
            flash(
                f"Notification #{notification_id} was successfully SENT to '{recipient}' via {channel} ({app_source})!",
                "success",
            )
        except Exception as exc:
            db.execute(
                """
                UPDATE notifications
                SET status = ?, error_message = ?
                WHERE id = ?
                """,
                ("FAILED", str(exc), notification_id),
            )
            db.commit()
            flash(
                f"Notification #{notification_id} FAILED to deliver: {exc}",
                "error",
            )

        return redirect(url_for("index"))

    @app.route("/notifications", methods=["GET"])
    def list_notifications():
        """Show notification dashboard and history in reverse chronological order."""
        db = get_db()
        notifications = db.execute(
            """
            SELECT id, recipient, channel, app_source, subject, body, status, is_read, retry_count, created_at, sent_at
            FROM notifications
            ORDER BY id DESC
            """
        ).fetchall()
        return render_template("notifications.html", notifications=notifications)

    @app.route("/notifications/<int:notification_id>", methods=["GET"])
    def get_notification(notification_id: int):
        """Show full details of an individual notification."""
        db = get_db()
        notification = db.execute(
            """
            SELECT id, user_id, recipient, channel, app_source, subject, body, status, is_read, retry_count, created_at, sent_at, error_message
            FROM notifications
            WHERE id = ?
            """,
            (notification_id,),
        ).fetchone()

        if notification is None:
            return (
                render_template(
                    "notifications.html",
                    notification=None,
                    not_found_id=notification_id,
                ),
                404,
            )

        return render_template("notifications.html", notification=notification)

    @app.route("/notifications/<int:notification_id>/toggle-read", methods=["POST"])
    def toggle_read(notification_id: int):
        """Toggle read/unread state of a notification."""
        db = get_db()
        row = db.execute("SELECT is_read FROM notifications WHERE id = ?", (notification_id,)).fetchone()
        if row is None:
            if request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.is_json:
                return jsonify({"error": "Not found"}), 404
            abort(404)

        new_status = 0 if row["is_read"] else 1
        db.execute("UPDATE notifications SET is_read = ? WHERE id = ?", (new_status, notification_id))
        db.commit()

        if request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.is_json:
            return jsonify({"success": True, "id": notification_id, "is_read": new_status})

        return redirect(request.referrer or url_for("list_notifications"))

    @app.route("/notifications/seed-demo", methods=["POST"])
    def seed_demo():
        """Restore realistic sample notifications across all 8 apps."""
        db = get_db()
        for s in SAMPLE_NOTIFICATIONS:
            db.execute(
                """
                INSERT INTO notifications (
                    user_id, recipient, channel, app_source, subject,
                    body, status, is_read, retry_count, created_at, sent_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    None,
                    s["recipient"],
                    s["channel"],
                    s["app_source"],
                    s["subject"],
                    s["body"],
                    s["status"],
                    s["is_read"],
                    0,
                    s["created_at"],
                    s["sent_at"],
                ),
            )
        db.commit()
        flash("Sample notifications for all 8 platforms successfully loaded!", "success")
        return redirect(url_for("list_notifications"))

    # ---------------------------------------------------------
    # Error Handlers (Prevents raw stack traces from reaching users)
    # ---------------------------------------------------------

    @app.errorhandler(404)
    def handle_not_found(error):
        return (
            render_template(
                "base.html",
                custom_error_title="Page Not Found",
                custom_error_message="The requested page or notification does not exist.",
            ),
            404,
        )

    @app.errorhandler(500)
    def handle_server_error(error):
        return (
            render_template(
                "base.html",
                custom_error_title="Internal Server Error",
                custom_error_message="A server error occurred. Please try again later.",
            ),
            500,
        )

    return app


app = create_app()

if __name__ == "__main__":
    # Host on 0.0.0.0 for local network access; debug is disabled by default
    app.run(host="0.0.0.0", port=5000, debug=False)
