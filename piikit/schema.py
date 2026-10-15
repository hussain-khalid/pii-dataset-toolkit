"""Shared definitions for the text dataset schema."""

LABELS = ("PERSON", "EMAIL", "PHONE", "ADDRESS", "ID_NUMBER", "DATE_OF_BIRTH")

REQUIRED_KEYS = ("id", "text", "spans", "source", "generator_version", "seed", "template_id")
REQUIRED_SPAN_KEYS = ("start", "end", "label", "text")