"""Typed exceptions for expected mdship failures.

Adapters (CLI, MCP) should recognize conditions by exception type, never by
matching exception message text.

The placeholder errors also derive from ``ValueError`` so that existing callers
and tests that catch ``ValueError`` keep working during the migration.
"""

from __future__ import annotations


class MdshipError(Exception):
    """Base class for expected mdship operation failures."""


class FileOperationError(MdshipError):
    """A source or destination file could not be processed."""


class PlaceholderError(MdshipError, ValueError):
    """A placeholder was malformed or could not be processed."""


class PlaceholderNotFound(PlaceholderError):
    """The requested optional placeholder is not present in the document.

    Raised when a document contains no usable placeholder of the requested
    kind — either no opening marker at all, or only occurrences that are not
    valid placeholders (inside a fenced code block, or not at the start of a
    line). Workflows may treat this as "nothing to do" for optional
    placeholders such as TOC.
    """


class IntegrityError(PlaceholderError):
    """Managed content failed an integrity check."""


class ScriptError(PlaceholderError):
    """A user script could not be resolved, loaded, or executed."""


class TrustError(ScriptError):
    """Script execution is not enabled for this project.

    Raised when the ``trusted_projects`` allow-list is missing, writable, or does
    not list the project. mdship never edits that file — only the user can.
    """
