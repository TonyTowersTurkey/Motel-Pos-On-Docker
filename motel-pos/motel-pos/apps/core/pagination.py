"""Shared pagination classes for DRF."""

from rest_framework.pagination import PageNumberPagination


class StandardPagination(PageNumberPagination):
    """Standard page-based pagination for all API endpoints.

    Attributes:
        page_size: Default number of items per page.
        page_size_query_param: Query parameter to control page size.
        max_page_size: Maximum allowed page size.
    """

    page_size: int = 20
    page_size_query_param: str | None = "page_size"
    max_page_size: int = 100


class LargePagination(PageNumberPagination):
    """Larger pagination for list endpoints with many records."""

    page_size: int = 50
    page_size_query_param: str | None = "page_size"
    max_page_size: int = 200
