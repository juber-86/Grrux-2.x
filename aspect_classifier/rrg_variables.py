"""Contrato único de variables argumentales de GRR.

Las letras expresan posiciones en la EL, no ordinales de tokens.  Por eso
este módulo valida, ordena y detecta legado, pero deliberadamente no convierte
``xN`` a una letra.
"""

from __future__ import annotations

import re
from collections.abc import Mapping


RRG_VARIABLES = ("x", "y", "z")
RRG_VARIABLE_SET = frozenset(RRG_VARIABLES)
_LEGACY_RE = re.compile(r"(?<![\w])x\d+(?![\w])", re.IGNORECASE)


class LegacyRRGNotationError(ValueError):
    """Una entrada usa la notación ordinal anterior de GRRux."""


def legacy_variables(text: str | None) -> tuple[str, ...]:
    """Devuelve variables ``xN`` completas encontradas, sin duplicados."""
    return tuple(dict.fromkeys(m.group(0) for m in _LEGACY_RE.finditer(text or "")))


def reject_legacy_notation(text: str | None, *, context: str = "entrada") -> None:
    found = legacy_variables(text)
    if found:
        joined = ", ".join(found)
        raise LegacyRRGNotationError(
            f"{context} usa la notación anterior ({joined}); "
            "debe regenerarse con la versión actual, que usa x/y/z"
        )


def validate_variable(value: str, *, field: str = "variable") -> str:
    reject_legacy_notation(value, context=field)
    if value not in RRG_VARIABLE_SET:
        raise ValueError(
            f"{field} inválida {value!r}; se esperaba una de: "
            f"{', '.join(RRG_VARIABLES)}"
        )
    return value


def validate_mapping_values(mapping: Mapping, *, field: str) -> None:
    for value in mapping.values():
        validate_variable(value, field=field)


def canonical_variables(mapping: Mapping[str, str]) -> dict[str, str]:
    """Valida y devuelve un dict en el orden canónico x, y, z."""
    for key in mapping:
        validate_variable(key, field="variables")
    return {key: mapping[key] for key in RRG_VARIABLES if key in mapping}
