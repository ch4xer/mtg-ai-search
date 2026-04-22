"""Search log persistence boundary."""

from .sql.search_logs import get_ip_hourly_search_count, get_user_hourly_search_count, log_search

__all__ = ["get_ip_hourly_search_count", "get_user_hourly_search_count", "log_search"]
