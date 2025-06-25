"""Constants for lldap-request."""

import logging

# Will auto-update based on GitHub release
VERSION = "v0.0.3"

LOG_FORMAT = "%(asctime)-20s %(levelname)-9s [%(name)s] %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
DEFAULT_LOGLEVEL = logging.INFO

REQUIRED_VARS: list[str] = ["LLDAP_USERNAME", "LLDAP_PASSWORD"]
RESET_TYPES: list[str] = ["lldap", "authelia"]

DEFAULT_RESET_TYPE = "lldap"
DEFAULT_LLDAP_CONFIG = "/app/data/lldap_config.toml"
DEFAULT_LLDAP_HTTPURL = "http://lldap:17170"
