"""Send commands to lldap-cli."""

import logging
import os
import re
import subprocess

import requests

from const import DEFAULT_LLDAP_CONFIG, DEFAULT_LLDAP_HTTPURL, DEFAULT_RESET_TYPE, RESET_TYPES

_LOGGER: logging.Logger = logging.getLogger(__name__)


def lldap_login() -> bool:
    """Login to lldap."""
    _LOGGER.info("Logging in to lldap-cli")

    if "LLDAP_CONFIG" not in os.environ:
        os.environ["LLDAP_CONFIG"] = DEFAULT_LLDAP_CONFIG
    if "LLDAP_HTTPURL" not in os.environ:
        os.environ["LLDAP_HTTPURL"] = DEFAULT_LLDAP_HTTPURL

    result = subprocess.run(
        ["lldap-cli", "login"],
        check=False,
        capture_output=True,
        text=True,
        env=os.environ.copy(),
        timeout=30,
    )
    _LOGGER.debug("lldap-cli login output: %s", result.stdout)
    if result.returncode != 0:
        _LOGGER.error("lldap-cli login error: %s", result.stderr)
        raise RuntimeError(f"Login failed: {result.stderr}")
    for line in result.stdout.splitlines():
        match: re.Match[str] | None = re.match(r"^export LLDAP_TOKEN=(.+)$", line.strip())
        if match:
            os.environ["LLDAP_TOKEN"] = match.group(1)
            _LOGGER.info("Logged in to lldap-cli successfully")
            return True
    raise RuntimeError("Token not found in lldap-cli login output:\n" + result.stdout)


def create_user(uid, email, displayname=None, firstname=None, lastname=None):
    """Create a new user in lldap."""
    if "LLDAP_TOKEN" not in os.environ:
        lldap_login()

    group_name: str = os.getenv("LLDAP_USER_GROUP", "").strip()
    cmd: list[str] = ["lldap-cli", "user", "add", uid, email]
    if displayname:
        cmd += ["-d", displayname]
    if firstname:
        cmd += ["-f", firstname]
    if lastname:
        cmd += ["-l", lastname]

    _LOGGER.info("Creating user %s with email %s", uid, email)
    result = subprocess.run(
        cmd, check=False, capture_output=True, text=True, env=os.environ.copy(), timeout=30
    )
    _LOGGER.debug("lldap-cli user add output: %s", result.stdout)
    if result.returncode != 0:
        _LOGGER.error("lldap-cli user add error: %s", result.stderr)
        return False, result.stderr

    # Add to group if specified
    if group_name:
        _LOGGER.info("Adding user %s to group %s", uid, group_name)
        group_cmd: list[str] = ["lldap-cli", "user", "group", "add", uid, group_name]
        group_result = subprocess.run(
            group_cmd,
            check=False,
            capture_output=True,
            text=True,
            env=os.environ.copy(),
            timeout=30,
        )
        _LOGGER.debug("lldap-cli user group add output: %s", group_result.stdout)
        if group_result.returncode != 0:
            _LOGGER.error("lldap-cli user group add error: %s", group_result.stderr)
            return False, f"User created but failed to add to group: {group_result.stderr}"

    reset_type: str = os.getenv("RESET_TYPE", DEFAULT_RESET_TYPE)
    if reset_type not in RESET_TYPES:
        _LOGGER.error("Invalid RESET_TYPE: %s. Must be 'authelia' or 'lldap'", reset_type)
        return False, f"Invalid RESET_TYPE: {reset_type}. Must be 'authelia' or 'lldap'"

    _LOGGER.info("Sending reset request with %s", reset_type)
    if reset_type == "authelia":
        authelia_url: str = os.getenv("AUTHELIA_URL", "").rstrip("/")

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
    elif reset_type == "lldap":
        lldap_url: str = os.getenv("LLDAP_URL", "").rstrip("/")

        try:
            response = requests.post(
                f"{lldap_url}/auth/reset/step1/{uid}",
                headers={
                    "User-Agent": "Python lldap-request",
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "Origin": lldap_url,
                    "Referer": f"{lldap_url}/reset-password/step1",
                },
                timeout=10,
            )
            if response.status_code not in {200, 204}:
                return (
                    False,
                    f"User created but lldap reset failed: {response.status_code} - {response.text}",
                )

        except requests.RequestException as e:
            return False, f"User created but lldap reset failed (network error): {e!s}"
        except Exception as e:  # noqa: BLE001
            return False, f"User created but lldap reset failed (unexpected error): {e!s}"

    return (
        True,
        f"{uid} created {', group added,' if group_name else ''} and password reset triggered with {reset_type}",
    )
