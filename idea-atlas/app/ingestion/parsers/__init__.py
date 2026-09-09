"""Parsers turn retrieved bytes into plain text. They never execute content."""

from app.ingestion.parsers.base import ParsedDocument, Parser
from app.ingestion.parsers.registry import get_parser, register_parser

__all__ = ["ParsedDocument", "Parser", "get_parser", "register_parser"]
