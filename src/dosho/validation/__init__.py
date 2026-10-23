"""Optional, framework-independent cab validation and argv formatting."""

from .compiled import CabSpec, CompiledCab
from .compiler import compile_cab, parse_document
from .modelgen import TypeBinding, build_model, dtype_to_type, sanitize, sanitize_unique
from .policies import build_argv
from .schema import ParamMeta, ParamPattern, ParamSegment, Policies

__all__ = [
    "FORMATTER_CONTRACT_VERSION",
    "SCHEMA_CONTRACT_VERSION",
    "CabSpec",
    "CompiledCab",
    "ParamMeta",
    "ParamPattern",
    "ParamSegment",
    "Policies",
    "TypeBinding",
    "build_argv",
    "build_model",
    "compile_cab",
    "dtype_to_type",
    "parse_document",
    "sanitize",
    "sanitize_unique",
]

SCHEMA_CONTRACT_VERSION = 1
FORMATTER_CONTRACT_VERSION = 1
