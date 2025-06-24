"""Main lldap-request code."""

import logging
import os
from pathlib import Path
import sqlite3

from flask import Flask, redirect, render_template, request

from const import DEFAULT_LOGLEVEL, LOG_DATE_FORMAT, LOG_FORMAT, VERSION
from lldap_cli_wrapper import create_user

DEBUG = os.getenv("DEBUG", "")
if DEBUG.lower() in {"1", "true", "yes"}:
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


init_db()


@app.route("/", methods=["GET"])
def index():
    """Show the main request account form."""
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
    return "Your request has been submitted."


@app.route("/admin")
def admin():
    """Show the admin page."""
    with sqlite3.connect(DB_PATH) as conn:
        requests = conn.execute("SELECT * FROM requests WHERE status = 'pending'").fetchall()
    return render_template("admin.html", requests=requests, version=VERSION)


@app.route("/approve/<int:req_id>")
def approve(req_id):
    """Approve a new account."""
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
                c.execute("UPDATE requests SET status = 'approved' WHERE id = ?", (req_id,))
                conn.commit()
            else:
                return f"Error: {message}"
    return redirect("/admin")


@app.route("/deny/<int:req_id>")
def deny(req_id):
    """Deny a new account."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("UPDATE requests SET status = 'denied' WHERE id = ?", (req_id,))
        conn.commit()
    return redirect("/admin")
