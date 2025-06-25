"""Main lldap-request code."""

from __future__ import annotations

import logging
import os
from pathlib import Path
import sqlite3

from flask import Flask, redirect, render_template, request

from const import (
    DEFAULT_LLDAP_CONFIG,
    DEFAULT_LLDAP_HTTPURL,
    DEFAULT_LOGLEVEL,
    DEFAULT_RESET_TYPE,
    LOG_DATE_FORMAT,
    LOG_FORMAT,
    REQUIRED_VARS,
    RESET_TYPES,
    VERSION,
)
from lldap_cli_wrapper import create_user

debug = os.getenv("DEBUG", "")
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

if reset_type == "lldap" and "LLDAP_URL" not in os.environ:
    raise OSError("LLDAP_URL must be set when RESET_TYPE is 'lldap'")
if reset_type == "authelia" and "AUTHELIA_URL" not in os.environ:
    raise OSError("AUTHELIA_URL must be set when RESET_TYPE is 'authelia'")
_LOGGER.debug("AUTHELIA_URL: %s", os.getenv("AUTHELIA_URL", "Not set"))
_LOGGER.debug("LLDAP_URL: %s", os.getenv("LLDAP_URL", "Not set"))

_LOGGER.debug("LLDAP_CONFIG: %s", os.getenv("LLDAP_CONFIG", DEFAULT_LLDAP_CONFIG))
_LOGGER.debug("LLDAP_HTTPURL: %s", os.getenv("LLDAP_HTTPURL", DEFAULT_LLDAP_HTTPURL))

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


@app.route("/", methods=["GET"])
def index():
    """Show the main request account form."""
    _LOGGER.info("Index page accessed")
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

    if reset_type == "lldap":
        redirect_url = os.getenv("LLDAP_URL", "/")
    elif reset_type == "authelia":
        redirect_url = os.getenv("AUTHELIA_URL", "/")
    else:
        redirect_url = "/"

    return render_template(
        "submitted.html",
        message="Your request has been submitted",
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


@app.route("/approve/<int:req_id>")
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


@app.route("/deny/<int:req_id>")
def deny(req_id):
    """Deny a new account."""
    _LOGGER.info("Denying request ID %d", req_id)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("UPDATE requests SET status = 'denied' WHERE id = ?", (req_id,))
        conn.commit()
    return redirect("/admin")
