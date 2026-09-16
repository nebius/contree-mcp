"""Helpers for adapting ``contree_client`` responses to tool output models.

``contree_client`` marks "field not included in this response" with
the ``...`` sentinel (see ``contree_client.types.EllipsisType``
fields) rather than ``None``, since ``None`` is itself a valid value
for many fields. Tool output models don't need that distinction —
:func:`resolved` collapses the sentinel to a plain default.
"""

from __future__ import annotations

from types import EllipsisType
from typing import TypeVar

FieldT = TypeVar("FieldT")


def resolved(value: FieldT | EllipsisType, default: FieldT) -> FieldT:
    return default if isinstance(value, EllipsisType) else value
