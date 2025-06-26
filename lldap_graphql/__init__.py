"""Class for interacting with lldap via GraphQL API."""

import logging
from typing import Any

import requests

from .const import (
    HTTP_AUTH_ENDPOINT,
    HTTP_GRAPHQL_ENDPOINT,
    HTTP_REFRESH_ENDPOINT,
    LLDAP_HTTPURL_DEFAULT,
)

_LOGGER: logging.Logger = logging.getLogger(__name__)


class lldap_graphql:
    """Class for interacting with lldap GraphQL API."""

    def __init__(self, username: str, password: str, base_url: str = LLDAP_HTTPURL_DEFAULT) -> None:
        """Initialize the lldap_graphql client."""
        self.base_url: str = base_url.rstrip("/")
        self.graphql_url: str = self.base_url + HTTP_GRAPHQL_ENDPOINT
        self.auth_url: str = self.base_url + HTTP_AUTH_ENDPOINT
        self.refresh_url: str = self.base_url + HTTP_REFRESH_ENDPOINT
        self.username: str = username
        self.password: str = password
        self.token: str | None = None
        self.refresh_token: str | None = None

    def get_token(self) -> None:
        """Get a token from the lldap GraphQL API."""
        payload: dict[str, str] = {"username": self.username, "password": self.password}
        response: requests.Response = requests.post(self.auth_url, json=payload)
        response.raise_for_status()
        data: dict[str, Any] = response.json()
        self.token = data.get("token")
        if not self.token:
            raise ValueError("No token received from auth endpoint")
        self.refresh_token = data.get("refreshToken")
        if not self.token:
            raise ValueError("No refresh token received from auth endpoint")

        _LOGGER.info("Token received successfully")

    def get_new_token(self, refresh_token: str | None = None) -> None:
        """Get a new token using the refresh token."""
        if not refresh_token:
            if not self.refresh_token:
                raise ValueError("No refresh token available")
            refresh_token = self.refresh_token

        cookies: dict[str, str] = {"refresh_token": refresh_token}

        response: requests.Response = requests.get(self.refresh_url, cookies=cookies)
        response.raise_for_status()
        data: dict[str, Any] = response.json()

        self.token = data.get("token")
        if not self.token:
            raise ValueError("No token received from refresh endpoint")

        _LOGGER.info("Token refreshed successfully")

    def run_query(self, query: str, variables: dict) -> dict[str, Any]:
        """Run a GraphQL query with the given variables, with auto token refresh."""
        if not self.token:
            self.get_token()

        headers: dict[str, str] = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.token}",
        }
        payload: dict[str, Any] = {"query": query, "variables": variables}

        def do_request() -> requests.Response:
            return requests.post(self.graphql_url, headers=headers, json=payload)

        response: requests.Response = do_request()

        if response.status_code == 401:
            _LOGGER.info("Token expired, attempting to refresh")
            self.get_new_token()
            headers["Authorization"] = f"Bearer {self.token}"
            response = do_request()

        response.raise_for_status()

        response_data: dict[str, Any] = response.json()
        if "errors" in response_data:
            messages: str = "; ".join(
                err.get("message", "Unknown error") for err in response_data["errors"]
            )
            raise APIResponseError(f"GraphQL error: {messages}", response_data=response_data)

        return response_data

    def create_user(
        self,
        user_id: str,
        email: str,
        display_name: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
    ) -> dict[str, Any]:
        """Create a new user in lldap."""
        query: str = """
        mutation createUser($user: CreateUserInput!) {
          createUser(user: $user) {
            id
            email
            displayName
            attributes {
              name
              value
            }
          }
        }
        """

        if not display_name:
            display_name = ""

        attributes: list[dict[str, Any]] = []

        if first_name:
            attributes.append({"name": "first_name", "value": [first_name]})

        if last_name:
            attributes.append({"name": "last_name", "value": [last_name]})

        variables: dict[str, Any] = {
            "user": {
                "id": user_id,
                "email": email,
                "displayName": display_name,
                "attributes": attributes,
            }
        }

        result: dict[str, Any] = self.run_query(query, variables)
        _LOGGER.info("Created user: %s", result["data"]["createUser"]["id"])
        return result["data"]["createUser"]

    def get_group_id(self, group_name: str) -> int:
        """Retrieve group ID by its Name."""
        query: str = """
        query {
          groups {
            id
            displayName
          }
        }
        """
        variables: dict[str, Any] = {}
        result: dict[str, Any] = self.run_query(query, variables)
        groups: list[dict[str, Any]] = result["data"]["groups"]

        for group in groups:
            if group.get("displayName") == group_name and group.get("id") is not None:
                _LOGGER.info("Found group '%s' with ID: %s", group_name, group["id"])
                return group["id"]

        raise ValueError(f"Failed to retrieve group ID for group: {group_name}")

    def add_user_to_group(
        self, user_id: str, group_name: str | None = None, group_id: int | None = None
    ) -> dict:
        """Add a user to a group by name or ID."""

        if group_id is None and group_name is None:
            raise ValueError("Either group_name or group_id must be provided.")

        if group_name and group_id is None:
            group_id = self.get_group_id(group_name)

        query: str = """
        mutation addUserToGroup($userId: String!, $groupId: Int!) {
          addUserToGroup(userId: $userId, groupId: $groupId) {
            ok
          }
        }
        """
        variables: dict[str, Any] = {"userId": user_id, "groupId": group_id}

        result: dict[str, Any] = self.run_query(query, variables)
        if result["data"]["addUserToGroup"]["ok"]:
            _LOGGER.info("Added user '%s' to group '%s' (ID: %s)", user_id, group_name, group_id)
        else:
            raise APIResponseError(
                f"Failed to add user '{user_id}' to group '{group_name}'",
                response_data=result,
            )
        return result["data"]["addUserToGroup"]


class APIResponseError(Exception):
    """Exception raised for errors in the API response data."""

    def __init__(self, message, response_data: dict[str, Any] | None = None) -> None:
        """Initialize APIResponseError Exception."""
        super().__init__(message)
        self.response_data: dict[str, Any] | None = response_data
