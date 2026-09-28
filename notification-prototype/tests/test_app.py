import os
import sqlite3
import pytest
from app import create_app, send_fake_notification


@pytest.fixture
def app_instance(tmp_path):
    """Create and configure a clean Flask application instance for each test."""
    test_db_path = str(tmp_path / "test_notifications.db")
    app = create_app(
        {
            "TESTING": True,
            "DATABASE": test_db_path,
            "SECRET_KEY": "test-secret-key",
        }
    )
    yield app


@pytest.fixture
def client(app_instance):
    """Test client for HTTP requests."""
    return app_instance.test_client()


@pytest.fixture
def db_conn(app_instance):
    """Direct SQLite connection to verify database contents."""
    conn = sqlite3.connect(app_instance.config["DATABASE"])
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


# -------------------------------------------------------------
# Required Tests
# -------------------------------------------------------------

def test_get_home_page_returns_200(client):
    """Requirement 1: GET / returns 200."""
    response = client.get("/")
    assert response.status_code == 200
    assert b"Notification Prototype" in response.data
    assert b"Send a Simulated Notification" in response.data


def test_notification_can_be_created(client):
    """Requirement 2: Notification can be created."""
    response = client.post(
        "/notifications",
        data={
            "recipient": "tester@example.com",
            "channel": "EMAIL",
            "subject": "Welcome",
            "body": "Your account is ready.",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"successfully SENT" in response.data
    assert b"tester@example.com" in response.data


def test_notification_is_stored_in_sqlite(client, db_conn):
    """Requirement 3: Notification is stored in SQLite."""
    client.post(
        "/notifications",
        data={
            "recipient": "+15551234567",
            "channel": "SMS",
            "subject": "Verification Code",
            "body": "Your code is 456789.",
        },
    )

    row = db_conn.execute(
        "SELECT * FROM notifications WHERE recipient = ?", ("+15551234567",)
    ).fetchone()

    assert row is not None
    assert row["channel"] == "SMS"
    assert row["subject"] == "Verification Code"
    assert row["body"] == "Your code is 456789."
    assert row["created_at"] is not None


def test_successful_fake_delivery_changes_status_to_sent(client, db_conn):
    """Requirement 4: Successful fake delivery changes status to SENT."""
    client.post(
        "/notifications",
        data={
            "recipient": "device_token_abc123",
            "channel": "PUSH",
            "subject": "New Alert",
            "body": "You have a new message.",
        },
    )

    row = db_conn.execute(
        "SELECT * FROM notifications WHERE recipient = ?", ("device_token_abc123",)
    ).fetchone()

    assert row is not None
    assert row["status"] == "SENT"
    assert row["sent_at"] is not None
    assert row["error_message"] is None


def test_invalid_channel_is_rejected(client, db_conn):
    """Requirement 5: Invalid channel is rejected."""
    response = client.post(
        "/notifications",
        data={
            "recipient": "user@example.com",
            "channel": "TELEPATHY",
            "subject": "Mind Reading",
            "body": "Can you hear this?",
        },
    )
    assert response.status_code == 400
    assert b"Invalid channel" in response.data

    count = db_conn.execute("SELECT COUNT(*) FROM notifications").fetchone()[0]
    assert count == 0


def test_empty_required_fields_are_rejected(client, db_conn):
    """Requirement 6: Empty required fields are rejected."""
    # Test all empty / whitespace fields
    response = client.post(
        "/notifications",
        data={
            "recipient": "   ",
            "channel": "EMAIL",
            "subject": " ",
            "body": "\n  \t",
        },
    )
    assert response.status_code == 400
    assert b"Recipient is required." in response.data
    assert b"Subject is required." in response.data
    assert b"Message body is required." in response.data

    count = db_conn.execute("SELECT COUNT(*) FROM notifications").fetchone()[0]
    assert count == 0


def test_get_notifications_returns_200(client):
    """Requirement 7: GET /notifications returns 200."""
    response = client.get("/notifications")
    assert response.status_code == 200
    assert b"Notification History" in response.data


def test_existing_notification_details_return_200(client, db_conn):
    """Requirement 8: Existing notification details return 200."""
    client.post(
        "/notifications",
        data={
            "recipient": "detail_test@example.com",
            "channel": "EMAIL",
            "subject": "Detailed Subject",
            "body": "Specific body content to inspect.",
        },
    )

    row = db_conn.execute(
        "SELECT id FROM notifications WHERE recipient = ?", ("detail_test@example.com",)
    ).fetchone()
    notification_id = row["id"]

    response = client.get(f"/notifications/{notification_id}")
    assert response.status_code == 200
    assert b"Notification #" in response.data
    assert b"detail_test@example.com" in response.data
    assert b"Specific body content to inspect." in response.data


def test_missing_notification_returns_404(client):
    """Requirement 9: Missing notification returns 404."""
    response = client.get("/notifications/999999")
    assert response.status_code == 404
    assert b"Notification Not Found" in response.data or b"was not found" in response.data


def test_failed_delivery_records_failed_status(app_instance, client, db_conn, monkeypatch):
    """Verify that simulated sender exception properly sets status to FAILED and stores error_message."""
    def mock_failing_sender(channel, recipient, subject, body):
        raise RuntimeError("Simulated transmission failure")

    monkeypatch.setattr("app.send_fake_notification", mock_failing_sender)

    response = client.post(
        "/notifications",
        data={
            "recipient": "fail_test@example.com",
            "channel": "EMAIL",
            "subject": "Will Fail",
            "body": "This delivery is expected to fail.",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"FAILED to deliver" in response.data

    row = db_conn.execute(
        "SELECT * FROM notifications WHERE recipient = ?", ("fail_test@example.com",)
    ).fetchone()
    assert row is not None
    assert row["status"] == "FAILED"
    assert "Simulated transmission failure" in row["error_message"]


def test_multi_source_notification_creation(client, db_conn):
    """Verify that multi-source notifications (YouTube, WhatsApp, etc.) are properly recorded."""
    response = client.post(
        "/notifications",
        data={
            "recipient": "creator@youtube.com",
            "channel": "PUSH",
            "app_source": "YouTube",
            "subject": "New Video Alert",
            "body": "Marques Brownlee just uploaded a video.",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"YouTube" in response.data

    row = db_conn.execute(
        "SELECT * FROM notifications WHERE recipient = ?", ("creator@youtube.com",)
    ).fetchone()
    assert row is not None
    assert row["app_source"] == "YouTube"
    assert row["is_read"] == 0


def test_toggle_read_status(client, db_conn):
    """Verify that notifications can toggle between read and unread states."""
    client.post(
        "/notifications",
        data={
            "recipient": "chat@whatsapp.com",
            "channel": "SMS",
            "app_source": "WhatsApp",
            "subject": "New Message",
            "body": "Hello there!",
        },
    )

    row = db_conn.execute(
        "SELECT id, is_read FROM notifications WHERE recipient = ?", ("chat@whatsapp.com",)
    ).fetchone()
    notif_id = row["id"]
    assert row["is_read"] == 0

    # Toggle to Read
    res = client.post(f"/notifications/{notif_id}/toggle-read")
    assert res.status_code in (200, 302)

    row = db_conn.execute("SELECT is_read FROM notifications WHERE id = ?", (notif_id,)).fetchone()
    assert row["is_read"] == 1

    # Toggle back to Unread
    res = client.post(f"/notifications/{notif_id}/toggle-read")
    assert res.status_code in (200, 302)

    row = db_conn.execute("SELECT is_read FROM notifications WHERE id = ?", (notif_id,)).fetchone()
    assert row["is_read"] == 0


def test_seed_demo_notifications(client, db_conn):
    """Verify that the seed-demo endpoint populates realistic mock notifications across all categories."""
    res = client.post("/notifications/seed-demo", follow_redirects=True)
    assert res.status_code == 200
    assert b"Sample notifications" in response_or_data(res)

    count = db_conn.execute("SELECT COUNT(*) FROM notifications").fetchone()[0]
    assert count >= 8


def response_or_data(res):
    return res.data

