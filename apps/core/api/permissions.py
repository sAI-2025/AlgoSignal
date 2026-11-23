"""Permissions for the API layer (ARCHITECTURE §14)."""

from __future__ import annotations

from rest_framework.permissions import IsAdminUser, IsAuthenticated


class IsStaff(IsAdminUser):
    """Staff users only (superuser or is_staff=True)."""

    message = "Staff access required."


class IsAuthenticatedOrReadOnly(IsAuthenticated):
    """Authenticated users may read; writes require staff via per-view checks."""


__all__ = ["IsAuthenticated", "IsAdminUser", "IsStaff", "IsAuthenticatedOrReadOnly"]
