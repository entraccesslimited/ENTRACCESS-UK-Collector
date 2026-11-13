"""Comparing people's names as nurseries write them.

The same person turns up as "Grace Smith", "grace  smith", "Smith, Grace" and
"Grace A. Smith" across a parent's form, a register and a court order. These
helpers treat those as one person, and nothing looser: two names match when
their words are the same, or when every word of one (at least two of them)
appears in the other. "Grace" alone never matches "Grace Smith" here, because
first names are shared by too many people to stop or flag a collection on.
"""

from __future__ import annotations

import re
import unicodedata

_NOT_LETTERS = re.compile(r"[^\w\s]|_|\d")


def words(name: str) -> frozenset[str]:
    """The words of a name, lower-cased, without accents, punctuation or initials."""
    plain = unicodedata.normalize("NFKD", name)
    plain = "".join(ch for ch in plain if not unicodedata.combining(ch))
    # O'Brien and OBrien are one name; Smith-Jones and Smith Jones are two words.
    plain = plain.casefold().replace("'", "").replace("\u2019", "")
    plain = _NOT_LETTERS.sub(" ", plain)
    return frozenset(word for word in plain.split() if len(word) > 1)


def same_person(a: str, b: str) -> bool:
    first, second = words(a), words(b)
    if not first or not second:
        return False
    if first == second:
        return True
    shorter, longer = sorted((first, second), key=len)
    return len(shorter) >= 2 and shorter <= longer


def normalised(name: str) -> str:
    """One spelling per name, for matching a register's child to ours."""
    return " ".join(sorted(words(name)))
