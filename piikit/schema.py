"""Shared definitions for the text dataset schema."""

LABELS = ("PERSON", "EMAIL", "PHONE", "ADDRESS", "ID_NUMBER", "DATE_OF_BIRTH")

REQUIRED_KEYS = ("id", "text", "spans", "source", "generator_version", "seed", "template_id")
REQUIRED_SPAN_KEYS = ("start", "end", "label", "text")

# Document-image dataset (milestone 2)
DOC_REQUIRED_KEYS = (
    "id", "image", "width", "height", "doc_type", "fields",
    "source", "generator_version", "seed",
)
DOC_REQUIRED_FIELD_KEYS = ("label", "text", "bbox")
DOC_TYPES = ("invoice", "form", "id_card")