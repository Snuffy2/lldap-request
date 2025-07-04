"""Main lldap-request code."""

from __future__ import annotations

import logging
import os
from pathlib import Path
import sqlite3

from const import (
    DEFAULT_APPRISE_URL,
    DEFAULT_LLDAP_HTTPURL,
    DEFAULT_LOGLEVEL,
    DEFAULT_REQUIRE_APPROVAL,
    DEFAULT_RESET_TYPE,
    LOG_DATE_FORMAT,
    LOG_FORMAT,
    REQUIRED_VARS,
    RESET_TYPES,
    VERSION,
)
from flask import Flask, redirect, render_template, request
from flask_wtf.csrf import CSRFProtect
from lldap_wrapper import create_user
import requests

debug: str = os.getenv("DEBUG", "")
if debug.lower() in {"1", "true", "yes"}:
    LOGLEVEL = logging.DEBUG
else:
    LOGLEVEL = DEFAULT_LOGLEVEL

logging.basicConfig(
    format=LOG_FORMAT,
    datefmt=LOG_DATE_FORMAT,
    level=LOGLEVEL,
    handlers=[
        logging.StreamHandler(),
    ],
)
_LOGGER: logging.Logger = logging.getLogger(__name__)

_LOGGER.info("Starting lldap-request %s", VERSION)
app = Flask("lldap-request")
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "X6mMePk3TrgERzyi849E")
csrf = CSRFProtect(app)

if LOGLEVEL == logging.DEBUG:
    _LOGGER.debug("Debug mode is enabled")

for var in REQUIRED_VARS:
    if not os.getenv(var):
        raise OSError(f"Required environment variable {var} is not set")
_LOGGER.debug("LLDAP_USERNAME: %s", os.getenv("LLDAP_USERNAME"))

reset_type = os.getenv("RESET_TYPE", DEFAULT_RESET_TYPE)
if reset_type not in RESET_TYPES:
    raise ValueError(f"Invalid RESET_TYPE: {reset_type}. Must be one of: {RESET_TYPES}")
_LOGGER.debug("RESET_TYPE: %s", reset_type)

if reset_type == "lldap":
    if "LLDAP_URL" not in os.environ:
        raise OSError("LLDAP_URL must be set when RESET_TYPE is 'lldap'")
    _LOGGER.debug("LLDAP_URL: %s", os.getenv("LLDAP_URL"))
elif reset_type == "authelia":
    if "AUTHELIA_URL" not in os.environ:
        raise OSError("AUTHELIA_URL must be set when RESET_TYPE is 'authelia'")
    _LOGGER.debug("AUTHELIA_URL: %s", os.getenv("AUTHELIA_URL"))
_LOGGER.debug("LLDAP_HTTPURL: %s", os.getenv("LLDAP_HTTPURL", DEFAULT_LLDAP_HTTPURL))
_LOGGER.debug("APPRISE_URL: %s", os.getenv("APPRISE_URL", DEFAULT_APPRISE_URL))
if "APPRISE_NOTIFY_ADMIN_URL" in os.environ:
    _LOGGER.debug("APPRISE_NOTIFY_ADMIN_URL: %s", "Set")
else:
    _LOGGER.debug("APPRISE_NOTIFY_ADMIN_URL: %s", "Not set")

REQUIRE_APPROVAL: bool = os.getenv("REQUIRE_APPROVAL", DEFAULT_REQUIRE_APPROVAL).lower() in {
    "1",
    "true",
    "yes",
}
_LOGGER.debug("REQUIRE_APPROVAL: %s", REQUIRE_APPROVAL)


DB_DIR = Path("database")
DB_PATH: Path = DB_DIR / "requests.db"
DB_DIR.mkdir(parents=True, exist_ok=True)


def init_db() -> None:
    """Initialize the sqlite db if it doesn't exist."""
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT,
                email TEXT,
                displayname TEXT,
                firstname TEXT,
                lastname TEXT,
                status TEXT DEFAULT 'pending'
            )
        """)
        conn.commit()
        _LOGGER.info("Database initialized successfully at %s", DB_PATH)


init_db()
_LOGGER.info("Startup complete")


def apprise_notify_admin(message: str, title: str | None = None) -> None:
    """Send a notification to the admin using Apprise."""
    apprise_url: str = os.getenv("APPRISE_URL", DEFAULT_APPRISE_URL)
    notify_url: str | None = os.getenv("APPRISE_NOTIFY_ADMIN_URL")

    if not notify_url:
        return

    if not title:
        title = "New Account Request (lldap-request)"

    try:
        response: requests.Response = requests.post(
            f"{apprise_url}/notify",
            data={"urls": notify_url, "body": message, "title": title},
            timeout=5,
        )

        if response.status_code != 200:
            _LOGGER.error(
                "Apprise admin notification failed: %s - %s", response.status_code, response.text
            )
    except requests.RequestException as e:
        _LOGGER.error("Error sending apprise admin notification. %s: %s", type(e).__name__, e)
    else:
        _LOGGER.info("Apprise admin notification sent sucessfully")


@app.route("/", methods=["GET"])
def index():
    """Show the main request account form."""
    _LOGGER.info("Request account page accessed")
    return render_template("index.html", version=VERSION)


@app.route("/submit", methods=["POST"])
def submit() -> str:
    """Submit the new account request."""
    username: str = request.form["username"]
    email: str = request.form["email"]
    displayname: str = request.form.get("displayname", "")
    firstname: str = request.form.get("firstname", "")
    lastname: str = request.form.get("lastname", "")

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO requests (username, email, displayname, firstname, lastname)
            VALUES (?, ?, ?, ?, ?)
        """,
            (username, email, displayname, firstname, lastname),
        )
    _LOGGER.info("New account request submitted: %s (%s)", username, email)

    if REQUIRE_APPROVAL:
        message: str = "Your request has been submitted and is pending approval"
        apprise_notify_admin(f"New account request submitted by: {username} ({email})")
    else:
        success, msg = create_user(username, email, displayname, firstname, lastname)
        if success:
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute(
                    "UPDATE requests SET status = 'approved' WHERE username = ? AND email = ? AND status = 'pending'",
                    (username, email),
                )
                conn.commit()
            message = "Your account has been created"
            _LOGGER.info(msg)
            apprise_notify_admin(f"New account created for: {username} ({email})")
        else:
            message = f"Error creating account: {msg}"
            _LOGGER.error(msg)

    if reset_type == "lldap":
        redirect_url: str = os.getenv("LLDAP_URL", "/")
    elif reset_type == "authelia":
        redirect_url = os.getenv("AUTHELIA_URL", "/")
    else:
        redirect_url = "/"

    return render_template(
        "submitted.html",
        message=message,
        redirect_url=redirect_url,
        delay=10,
        version=VERSION,
    )


@app.route("/admin")
def admin():
    """Show the admin page."""
    _LOGGER.info("Admin page accessed")
    with sqlite3.connect(DB_PATH) as conn:
        requests = conn.execute("SELECT * FROM requests WHERE status = 'pending'").fetchall()
    return render_template("admin.html", requests=requests, version=VERSION)


@app.route("/approve/<int:req_id>", methods=["POST"])
def approve(req_id):
    """Approve a new account."""
    _LOGGER.info("Approving request ID %d", req_id)
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        req = c.execute(
            "SELECT username, email, displayname, firstname, lastname FROM requests WHERE id = ?",
            (req_id,),
        ).fetchone()
        if req:
            username, email, displayname, firstname, lastname = req
            success, message = create_user(username, email, displayname, firstname, lastname)
            if success:
                _LOGGER.info(message)
                c.execute("UPDATE requests SET status = 'approved' WHERE id = ?", (req_id,))
                conn.commit()
            else:
                _LOGGER.error("Failed to create account: %s", message)
                return f"Error: {message}"
    return redirect("/admin")


@app.route("/deny/<int:req_id>", methods=["POST"])
def deny(req_id):
    """Deny a new account."""
    _LOGGER.info("Denying request ID %d", req_id)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("UPDATE requests SET status = 'denied' WHERE id = ?", (req_id,))
        conn.commit()
    return redirect("/admin")
