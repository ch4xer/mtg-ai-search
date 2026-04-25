"""User persistence boundary."""

from .sql.user_accounts import (
    create_user,
    get_user_by_email,
    get_user_by_id,
    get_user_by_username,
    update_last_active,
    update_user_password,
)
from .sql.user_admin import delete_user, search_users, update_user_role
from .sql.user_api_keys import get_api_key_status, get_user_by_api_key_hash, set_user_api_key
from .sql.user_verification import set_verification_code, verify_user_email

__all__ = [
    "create_user",
    "delete_user",
    "get_api_key_status",
    "get_user_by_api_key_hash",
    "get_user_by_email",
    "get_user_by_id",
    "get_user_by_username",
    "search_users",
    "set_verification_code",
    "set_user_api_key",
    "update_last_active",
    "update_user_password",
    "update_user_role",
    "verify_user_email",
]
