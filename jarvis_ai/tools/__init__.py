"""Importing this package registers every tool with the shared registry."""

from . import apps, desktop, filesystem, memory, shell, system  # noqa: F401
from ..registry import REGISTRY

__all__ = ["REGISTRY"]
