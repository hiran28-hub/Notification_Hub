# Notification System Prototype

A lightweight, beginner-friendly notification system prototype built with Python 3.12, Flask, and SQLite.

This project simulates multi-channel notification delivery (`EMAIL`, `SMS`, and `PUSH`) over a local area network without external third-party service dependencies, paid APIs, queues, or background workers.

---

## Table of Contents

- [Project Purpose](#project-purpose)
- [Architecture](#architecture)
- [Technologies Used](#technologies-used)
- [Technologies Intentionally Avoided](#technologies-intentionally-avoided)
- [Project Structure](#project-structure)
- [Database Schema](#database-schema)
- [How Fake Notification Delivery Works](#how-fake-notification-delivery-works)
- [Getting Started with Docker](#getting-started-with-docker)
  - [Prerequisites](#prerequisites)
  - [Start the Application](#start-the-application)
  - [View Real-Time Delivery Logs](#view-real-time-delivery-logs)
  - [Stop the Application](#stop-the-application)
- [Accessing the Application](#accessing-the-application)
  - [Local Machine Access](#local-machine-access)
  - [Local Network Access (Other Devices / Phones)](#local-network-access-other-devices--phones)
  - [How to Find Your Host IP Address](#how-to-find-your-host-ip-address)
  - [Important Security Notice](#important-security-notice)
- [Running Tests (Without Docker)](#running-tests-without-docker)
- [Current Limitations](#current-limitations)
- [Possible Future Improvements](#possible-future-improvements)

---

## Project Purpose

The purpose of this project is to provide a clean, educational, and functional prototype of a notification service. It demonstrates how incoming notification requests are validated, recorded in an SQLite database, logged for delivery simulation, and surfaced through a responsive web interface for history and detail inspection.

---

## Architecture

The architecture is kept as simple as possible:

```text
Browser / Client (Desktop or Mobile)
       |
       v
Flask Application (0.0.0.0:5000)
       |
       +----> SQLite Database (/app/data/notifications.db)
       |
       +----> Fake Notification Sender (stdout / Docker logs)
```

No message brokers, queues, background daemons, or microservices are used.

---

## Technologies Used

* **Python 3.12** — Modern, clean Python runtime.
* **Flask** — Minimal, lightweight WSGI web framework.
* **SQLite (`sqlite3`)** — Python's standard built-in relational database.
* **HTML5 & CSS3** — Vanilla, accessible, mobile-responsive user interface without heavy frontend frameworks.
* **Minimal JavaScript** — Lightweight script for trimming form input and enhancing usability.
* **Docker & Docker Compose** — Containerization for consistent setup across developer machines.
* **pytest** — Unit and integration test suite using Flask's test client.

---

## Technologies Intentionally Avoided

To keep the system simple, maintainable, and beginner-friendly, the following technologies were intentionally omitted:

* **Java / Spring Boot** — Avoided in favor of lightweight Python/Flask.
* **RabbitMQ / Redis / Celery** — Avoided message queues; delivery is synchronous simulation.
* **PostgreSQL / MySQL** — Avoided external database servers; SQLite requires zero configuration.
* **External Notification APIs (Twilio, SendGrid, Firebase)** — Avoided paid/cloud third-party APIs.
* **External Authentication / OAuth** — Avoided complex auth; open prototype for local network demonstration.
* **Microservices / Background Workers** — Avoided distributed architecture overhead.

---

## Project Structure

```text
notification-prototype/
├── app.py                  # Core Flask application, routes, models, and sender
├── requirements.txt        # Python package dependencies (Flask, pytest)
├── Dockerfile              # Docker container definition (Python 3.12-slim)
├── compose.yaml            # Docker Compose configuration (service, ports, volume)
├── .dockerignore           # Excluded files during Docker build
├── README.md               # Documentation and usage guide
├── data/                   # Persistent SQLite database directory (mounted in Docker)
├── templates/              # Jinja2 HTML templates
│   ├── base.html           # Base layout, header, navigation, and flash messages
│   ├── index.html          # Notification creation form
│   └── notifications.html  # Notification history table and individual detail view
├── static/
│   └── style.css           # Responsive, clean CSS stylesheet
└── tests/
    └── test_app.py         # Pytest test suite using temporary SQLite database
```

---

## Database Schema

SQLite database location inside the container:
```text
/app/data/notifications.db
```
Mounted to host:
```text
./data:/app/data
```

### 1. `users` Table
Stores basic user profiles for future user management.

| Column | Type | Description |
|---|---|---|
| `id` | `INTEGER PRIMARY KEY AUTOINCREMENT` | Unique user identifier |
| `name` | `TEXT NOT NULL` | Full name of the user |
| `email` | `TEXT` | Email address |
| `phone` | `TEXT` | Phone number |
| `created_at` | `TEXT NOT NULL` | Account creation timestamp (UTC) |

### 2. `notification_preferences` Table
Allows opt-in management per channel for future preference enforcement.

| Column | Type | Description |
|---|---|---|
| `id` | `INTEGER PRIMARY KEY AUTOINCREMENT` | Unique preference identifier |
| `user_id` | `INTEGER NOT NULL` | Foreign key referencing `users.id` |
| `channel` | `TEXT NOT NULL` | Delivery channel (`EMAIL`, `SMS`, `PUSH`) |
| `opt_in` | `INTEGER NOT NULL` | `1` for opted-in, `0` for opted-out |

*Constraint: `UNIQUE(user_id, channel)`*

### 3. `notifications` Table
Stores all submitted notifications and their delivery lifecycle.

| Column | Type | Description |
|---|---|---|
| `id` | `INTEGER PRIMARY KEY AUTOINCREMENT` | Unique notification ID |
| `user_id` | `INTEGER` | Optional user ID (foreign key referencing `users.id`) |
| `recipient` | `TEXT NOT NULL` | Recipient address, phone, or device ID |
| `channel` | `TEXT NOT NULL` | `EMAIL`, `SMS`, or `PUSH` |
| `subject` | `TEXT NOT NULL` | Subject or brief title |
| `body` | `TEXT NOT NULL` | Main message content |
| `status` | `TEXT NOT NULL` | `PENDING`, `SENT`, or `FAILED` |
| `retry_count` | `INTEGER DEFAULT 0` | Number of delivery attempts |
| `created_at` | `TEXT NOT NULL` | Submission timestamp (UTC) |
| `sent_at` | `TEXT` | Delivery timestamp (UTC), or NULL if not sent |
| `error_message` | `TEXT` | Failure explanation if status is `FAILED` |

All SQL operations use parameterized queries (`?`) to completely eliminate SQL injection risks.

---

## How Fake Notification Delivery Works

When a user submits the form:
1. Input is validated (trimmed values, required fields, allowed channels).
2. A record is inserted into SQLite with status `PENDING`.
3. The fake delivery function formats the message and prints it to standard output (`stdout`):
   ```text
   ----- FAKE NOTIFICATION -----
   Channel: EMAIL
   Recipient: example@example.com
   Subject: Welcome
   Body: Your account is ready.
   -----------------------------
   ```
4. Because `PYTHONUNBUFFERED=1` is set, Docker captures this output immediately in its container logs.
5. The notification status is updated to `SENT`, and `sent_at` is timestamped.
6. If any failure were to occur, the notification status would be updated to `FAILED`, and the error message recorded.

---

## Getting Started with Docker

### Prerequisites
* [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running.

### Start the Application
Open a terminal, navigate to the `notification-prototype` directory, and run:

```bash
docker compose up --build
```

To run in the background (detached mode):
```bash
docker compose up --build -d
```

### View Real-Time Delivery Logs
To monitor fake notifications being dispatched in real time:

```bash
docker compose logs -f
```

### Stop the Application
To stop and remove containers:

```bash
docker compose down
```

---

## Accessing the Application

### Local Machine Access
On the computer running Docker, open your browser and navigate to:
```text
http://localhost:5000
```

### Local Network Access (Other Devices / Phones)
Any phone, tablet, or laptop connected to the **same local Wi-Fi / network** can access the app:
```text
http://<HOST_IP>:5000
```
For example: `http://192.168.1.45:5000`

### How to Find Your Host IP Address

* **Windows:**
  1. Open PowerShell or Command Prompt.
  2. Run: `ipconfig`
  3. Look for **IPv4 Address** under your active Wi-Fi or Ethernet adapter (e.g., `192.168.1.X` or `10.0.0.X`).

* **macOS:**
  1. Open Terminal.
  2. Run: `ipconfig getifaddr en0` (or `en1` for secondary interface).

* **Linux:**
  1. Open Terminal.
  2. Run: `hostname -I` or `ip addr show`.

### Important Security Notice
* **No Authentication:** Anyone with network access can view notification history and submit notifications.
* **Shared History:** All users on the local network view the same notification history.
* **Local Use Only:** This prototype must **never** be exposed directly to the public internet or production environments.

---

## Running Tests (Without Docker)

Tests do not require Docker and run against a temporary in-memory/file-based SQLite database.

1. Create and activate a Python virtual environment (optional but recommended):
   ```bash
   python -m venv .venv
   # Windows PowerShell:
   .venv\Scripts\Activate.ps1
   # macOS / Linux:
   source .venv/bin/activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run pytest:
   ```bash
   pytest -v
   ```

All 10 tests verify:
* `GET /` returns 200
* Notification can be created
* Notification is stored in SQLite
* Fake delivery changes status to `SENT`
* Invalid channels are rejected with 400
* Empty required fields are rejected with 400
* `GET /notifications` returns 200
* Notification details page returns 200
* Missing notification returns 404
* Failed delivery error handling and `FAILED` status recording

---

## Current Limitations

1. **Simulated Delivery:** Notifications are printed to Docker logs rather than sent over actual telecommunication networks.
2. **No User Authentication:** No login system or password protection is included.
3. **Global Shared History:** Every user sees all submitted notifications.
4. **Synchronous Execution:** Submissions are processed synchronously in the request cycle.

---

## Possible Future Improvements

These features can be added in future iterations:

* **Authentication & Authorization:** Secure user login (e.g., session-based or token-based auth).
* **User-Specific History:** Filter notifications so users only view their own sent messages.
* **Preference Enforcement:** Check user opt-in preferences before sending.
* **Retry Mechanism:** Add a "Retry" button on failed notifications in the UI.
* **Real Notification Providers:** Integrate SendGrid (email), Twilio (SMS), and Firebase Cloud Messaging (push).
* **Production Database:** Migrate to PostgreSQL for high-concurrency workloads.
* **Queue / Worker Architecture:** Offload background sending to Celery or Redis Queue (RQ) with retry backoff.
