"""Send commands to lldap-cli."""

import os
import re
import subprocess

import requests


def lldap_login() -> bool:
    """Login to lldap."""
    result = subprocess.run(
        ["lldap-cli", "login"],
        check=False,
        capture_output=True,
        text=True,
        env=os.environ.copy(),
        timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Login failed: {result.stderr}")
    for line in result.stdout.splitlines():
        match: re.Match[str] | None = re.match(r"^export LLDAP_TOKEN=(.+)$", line.strip())
        if match:
            os.environ["LLDAP_TOKEN"] = match.group(1)
            return True
    raise RuntimeError("Token not found in lldap-cli login output:\n" + result.stdout)


def create_user(uid, email, displayname=None, firstname=None, lastname=None):
    """Create a new user in lldap."""
    if "LLDAP_TOKEN" not in os.environ:
        lldap_login()

    authelia_url: str = os.getenv("AUTHELIA_URL", "").rstrip("/")
    group_name: str = os.getenv("LLDAP_USER_GROUP", "").strip()
    cmd: list[str] = ["lldap-cli", "user", "add", uid, email]
    if displayname:
        cmd += ["-d", displayname]
    if firstname:
        cmd += ["-f", firstname]
    if lastname:
        cmd += ["-l", lastname]

    result = subprocess.run(
        cmd, check=False, capture_output=True, text=True, env=os.environ.copy(), timeout=30
    )
    if result.returncode != 0:
        return False, result.stderr

    # Add to group if specified
    if group_name:
        group_cmd: list[str] = ["lldap-cli", "user", "group", "add", uid, group_name]
        group_result = subprocess.run(
            group_cmd,
            check=False,
            capture_output=True,
            text=True,
            env=os.environ.copy(),
            timeout=30,
        )
        if group_result.returncode != 0:
            return False, f"User created but failed to add to group: {group_result.stderr}"

    # Trigger password reset via Authelia
    try:
        response: requests.Response = requests.post(
            f"{authelia_url}/api/reset-password/identity/start",
            json={"username": uid},
            headers={
                "User-Agent": "Python lldap-request",
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Origin": authelia_url,
                "Referer": f"{authelia_url}/reset-password/step1",
            },
            timeout=10,
        )
        if response.status_code not in {200, 204}:
            return (
                False,
                f"User created but Authelia reset failed: {response.status_code} - {response.text}",
            )

    except requests.RequestException as e:
        return False, f"User created but Authelia reset failed (network error): {e!s}"
    except Exception as e:  # noqa: BLE001
        return False, f"User created but Authelia reset failed (unexpected error): {e!s}"

    return True, "User created" + (
        ", group added," if group_name else ""
    ) + " and password reset triggered"
