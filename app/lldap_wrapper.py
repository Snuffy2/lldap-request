"""Send commands to lldap via GraphQL API."""

import json
import logging
import os
from typing import Any

import requests

from .const import DEFAULT_LLDAP_HTTPURL, DEFAULT_RESET_TYPE, RESET_TYPES
from .lldap_graphql import APIResponseError, lldap_graphql

_LOGGER: logging.Logger = logging.getLogger(__name__)


def create_user(uid, email, displayname=None, firstname=None, lastname=None) -> tuple[bool, str]:
    """Create a new user in lldap using the GraphQL API."""
    group_name: str = os.getenv("LLDAP_USER_GROUP", "").strip()
    lldap_httpurl: str = os.getenv("LLDAP_HTTPURL", DEFAULT_LLDAP_HTTPURL)
    admin_user: str = os.getenv("LLDAP_USERNAME", "").strip()
    admin_pass: str = os.getenv("LLDAP_PASSWORD", "")

    client = lldap_graphql(admin_user, admin_pass, base_url=lldap_httpurl)
    try:
        user: dict[str, Any] = client.create_user(
            user_id=uid,
            email=email,
            display_name=displayname,
            first_name=firstname,
            last_name=lastname,
        )
        _LOGGER.info("User created: %s", user["id"])
    except (APIResponseError, json.decoder.JSONDecodeError, requests.RequestException) as e:
        _LOGGER.error("Failed to create user. %s: %s", type(e).__name__, e)
        return False, f"User creation failed. {type(e).__name__}: {e}"

    if group_name:
        try:
            client.add_user_to_group(user_id=uid, group_name=group_name)
            _LOGGER.info("Added user '%s' to group '%s'", uid, group_name)
            group_msg: str = ", group added,"
        except (APIResponseError, json.decoder.JSONDecodeError, requests.RequestException) as e:
            _LOGGER.error("Failed to add user to group. %s: %s", type(e).__name__, e)
            return False, f"User created but failed to add to group. {type(e).__name__}: {e}"
    else:
        group_msg = ""

    reset_type = os.getenv("RESET_TYPE", DEFAULT_RESET_TYPE)
    success, message = trigger_password_reset(uid, reset_type)
    if not success:
        return False, f"User created{group_msg} but {message}"

    return (
        True,
        f"{uid} created{group_msg} and password reset triggered with {reset_type}",
    )


def trigger_password_reset(uid: str, reset_type: str) -> tuple[bool, str]:
    """Trigger password reset for a user via the configured reset type."""
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
                    f"Authelia reset failed: {response.status_code} - {response.text}",
                )
        except requests.RequestException as e:
            return (
                False,
                f"Authelia reset failed (network error). {type(e).__name__}: {e}",
            )
        except Exception as e:  # noqa: BLE001
            return (
                False,
                f"Authelia reset failed (unexpected error). {type(e).__name__}: {e}",
            )
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
                    f"lldap reset failed: {response.status_code} - {response.text}",
                )
        except requests.RequestException as e:
            return (
                False,
                f"lldap reset failed (network error). {type(e).__name__}: {e}",
            )
        except Exception as e:  # noqa: BLE001
            return (
                False,
                f"lldap reset failed (unexpected error). {type(e).__name__}: {e}",
            )

    return True, f"Password reset triggered successfully with {reset_type}"
