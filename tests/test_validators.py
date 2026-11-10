"""
Tests for the three applications.

Two kinds of check:
  * the hand-picked accepted / rejected strings from the assignment
    (at least five of each per application)
  * an independent cross-check: every string up to a fixed length over a small
    alphabet is fed both to our automaton and to a plain Python rule / regex
    written separately. Any disagreement fails the test.
"""
import random
import re
import string
import sys
from itertools import product
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fa_validators.automata import equivalent  # noqa: E402
from fa_validators.validators import (  # noqa: E402
    APPLICATIONS, EMAIL_DFA, EMAIL_NFA, EMAIL_REFERENCE_REGEX, EMAIL_SUBSET,
    PASSWORD_DFA, PASSWORD_PRODUCT, PIN46_DFA, PIN_DFA, SESSION_DFA,
    SPECIALS, STRONG_PIN_DFA)


@pytest.mark.parametrize("app", list(APPLICATIONS))
def test_minimum_five_examples_each(app):
    assert len(APPLICATIONS[app]["accept"]) >= 5
    assert len(APPLICATIONS[app]["reject"]) >= 5


CASES = [(k, s, True) for k, v in APPLICATIONS.items() for s in v["accept"]] + \
        [(k, s, False) for k, v in APPLICATIONS.items() for s in v["reject"]]


@pytest.mark.parametrize("app,text,expected", CASES)
def test_listed_examples(app, text, expected):
    assert APPLICATIONS[app]["dfa"].accepts(text) is expected


# ---------------------------------------------------------------- PIN
def test_pin_exhaustive_short_strings():
    for n in range(0, 7):
        for t in product("07a ", repeat=n):
            s = "".join(t)
            assert PIN_DFA.accepts(s) == (len(s) == 4 and s.isdigit())
            assert PIN46_DFA.accepts(s) == (len(s) in (4, 6) and s.isdigit())


def test_strong_pin_rule():
    for n in range(10000):
        pin = f"{n:04d}"
        assert STRONG_PIN_DFA.accepts(pin) == (len(set(pin)) > 1)
    assert not STRONG_PIN_DFA.accepts("123")


def test_session_lockout():
    def reference(events):
        wrong = 0
        for e in events:
            if e == "C":
                return True
            wrong += 1
            if wrong == 3:
                return False
        return False
    for n in range(0, 8):
        for t in product("CW", repeat=n):
            s = "".join(t)
            assert SESSION_DFA.accepts(s) == reference(s), s


# ----------------------------------------------------------- password
def password_reference(p):
    return (8 <= len(p) <= 16
            and any(c.isupper() for c in p) and any(c.islower() for c in p)
            and any(c.isdigit() for c in p) and any(c in SPECIALS for c in p)
            and all(c in string.ascii_letters + string.digits + SPECIALS for c in p))


def test_password_random_agreement():
    rnd = random.Random(2026)
    pool = "aZ5@ x"
    for _ in range(20000):
        s = "".join(rnd.choice(pool) for _ in range(rnd.randint(0, 19)))
        assert PASSWORD_DFA.accepts(s) == password_reference(s), s


def test_password_minimisation_preserves_language():
    same, cex = equivalent(PASSWORD_PRODUCT, PASSWORD_DFA)
    assert same, cex
    assert PASSWORD_DFA.live_states() < PASSWORD_PRODUCT.live_states()


# -------------------------------------------------------------- e-mail
def test_email_exhaustive_against_regex():
    rx = re.compile(EMAIL_REFERENCE_REGEX)
    alphabet = "a1.-_@"
    for n in range(0, 8):
        for t in product(alphabet, repeat=n):
            s = "".join(t)
            ref = bool(rx.match(s))
            assert EMAIL_DFA.accepts(s) == ref, s
            assert EMAIL_NFA.accepts(s) == ref, s


def test_email_nfa_dfa_minimal_all_equivalent():
    assert equivalent(EMAIL_SUBSET, EMAIL_DFA)[0]
    assert EMAIL_DFA.live_states() <= EMAIL_SUBSET.live_states()
