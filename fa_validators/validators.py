"""
The three applications required by the assignment, each written as a
finite automaton over a small alphabet of character classes.

  1. ATM PIN verification   (PIN syntax DFA, weak-PIN rule, session lock-out DFA)
  2. Password policy check  (product of five small DFAs)
  3. E-mail format check    (hand-written NFA -> subset construction -> minimal DFA)

Every automaton here recognises a *regular* language. Rules that are not
regular, or that need data the automaton does not have (the PIN stored for an
account, whether a mail domain exists), are listed in LIMITATIONS and are
handled outside the automaton.
"""

import string

from .automata import DFA, NFA, DEAD

# --------------------------------------------------------------------------
# 1. ATM PIN
# --------------------------------------------------------------------------
# Alphabet: D = any decimal digit, O = anything else (letters, space, '-', ...)


def pin_class(ch):
    return "D" if ch in string.digits else "O"


PIN_DFA = DFA(
    name="ATM PIN (exactly 4 digits)",
    alphabet=["D", "O"],
    delta={("q0", "D"): "q1", ("q1", "D"): "q2",
           ("q2", "D"): "q3", ("q3", "D"): "q4"},
    start="q0", accepting={"q4"}, classify=pin_class,
    labels={"q0": "no digit read", "q1": "1 digit", "q2": "2 digits",
            "q3": "3 digits", "q4": "4 digits - complete PIN",
            DEAD: "wrong length or non-digit"})

# Variant used by many banks: 4-digit OR 6-digit PIN
PIN46_DFA = DFA(
    name="ATM PIN (4 or 6 digits)",
    alphabet=["D", "O"],
    delta={("q0", "D"): "q1", ("q1", "D"): "q2", ("q2", "D"): "q3",
           ("q3", "D"): "q4", ("q4", "D"): "q5", ("q5", "D"): "q6"},
    start="q0", accepting={"q4", "q6"}, classify=pin_class)


def _weak_pin_dfa():
    """'All four digits identical' over the real digit alphabet 0-9.
    Used to show what a business rule costs when it is pushed into the FA."""
    digits = list(string.digits)
    delta = {}
    for d in digits:
        delta[("s", d)] = f"{d}1"
        for k in (1, 2, 3):
            delta[(f"{d}{k}", d)] = f"{d}{k + 1}"
    acc = {f"{d}4" for d in digits}
    return DFA("PIN with 4 identical digits", digits, delta, "s", acc,
               classify=lambda c: c)


def _four_digits_raw():
    digits = list(string.digits)
    delta = {}
    for k in range(4):
        for d in digits:
            delta[(f"p{k}", d)] = f"p{k + 1}"
    return DFA("4 digits (raw alphabet)", digits, delta, "p0", {"p4"},
               classify=lambda c: c)


WEAK_PIN = _weak_pin_dfa()
STRONG_PIN_DFA = _four_digits_raw().intersect(
    WEAK_PIN.complement(), "4-digit PIN, not all digits equal").minimize()


# ATM session: input events, not characters.
#   C = correct PIN entered, W = wrong PIN entered
# The card is locked after three consecutive wrong attempts. Comparing the
# PIN with the bank's record (the thing that decides whether an event is C
# or W) happens outside this automaton.
SESSION_DFA = DFA(
    name="ATM session (lock after 3 wrong PINs)",
    alphabet=["C", "W"],
    delta={("s0", "C"): "AUTH", ("s0", "W"): "s1",
           ("s1", "C"): "AUTH", ("s1", "W"): "s2",
           ("s2", "C"): "AUTH", ("s2", "W"): "LOCK",
           ("AUTH", "C"): "AUTH", ("AUTH", "W"): "AUTH",
           ("LOCK", "C"): "LOCK", ("LOCK", "W"): "LOCK"},
    start="s0", accepting={"AUTH"}, classify=lambda c: c,
    labels={"s0": "0 wrong attempts", "s1": "1 wrong attempt",
            "s2": "2 wrong attempts", "AUTH": "authenticated",
            "LOCK": "card blocked"})

# --------------------------------------------------------------------------
# 2. Password policy
# --------------------------------------------------------------------------
# Policy (typical of college / bank portals):
#   length 8..16, at least one upper-case letter, one lower-case letter,
#   one digit and one special symbol from SPECIALS; no spaces or other chars.
SPECIALS = "!@#$%^&*()-_=+[]{};:,.?/"
PW_MIN, PW_MAX = 8, 16


def pw_class(ch):
    if ch in string.ascii_uppercase:
        return "U"
    if ch in string.ascii_lowercase:
        return "L"
    if ch in string.digits:
        return "D"
    if ch in SPECIALS:
        return "S"
    return "O"


PW_ALPHA = ["U", "L", "D", "S", "O"]


def _contains(sym):
    """2-state DFA: 'the string contains at least one <sym>' (O always kills)."""
    delta = {}
    for a in PW_ALPHA:
        if a == "O":
            continue
        delta[("n", a)] = "y" if a == sym else "n"
        delta[("y", a)] = "y"
    return DFA(f"has {sym}", PW_ALPHA, delta, "n", {"y"}, pw_class)


def _length_dfa():
    delta = {}
    for k in range(PW_MAX):
        for a in PW_ALPHA:
            if a != "O":
                delta[(f"l{k}", a)] = f"l{k + 1}"
    acc = {f"l{k}" for k in range(PW_MIN, PW_MAX + 1)}
    return DFA(f"length {PW_MIN}..{PW_MAX}", PW_ALPHA, delta, "l0", acc, pw_class)


PW_PARTS = [_contains("U"), _contains("L"), _contains("D"), _contains("S"), _length_dfa()]


def _password_product():
    d = PW_PARTS[0]
    for part in PW_PARTS[1:]:
        d = d.intersect(part)
    d.name = "Password policy (product DFA)"
    return d


PASSWORD_PRODUCT = _password_product()
PASSWORD_DFA = PASSWORD_PRODUCT.minimize("Password policy (minimal DFA)")


def _coverage_dfa():
    """16-state DFA tracking which of {U,L,D,S} have been seen (length ignored).
    Small enough to draw; this is the 'shape' of the product machine."""
    import itertools
    letters = "ULDS"
    subsets = ["".join(c for c in letters if c in s) or "none"
               for r in range(5) for s in itertools.combinations(letters, r)]
    delta = {}
    for s in subsets:
        have = set() if s == "none" else set(s)
        for a in "ULDS":
            nh = have | {a}
            delta[(s, a)] = "".join(c for c in letters if c in nh)
    return DFA("Character-class coverage", PW_ALPHA, delta, "none", {"ULDS"}, pw_class,
               states=subsets)


PW_COVERAGE = _coverage_dfa()

# --------------------------------------------------------------------------
# 3. E-mail address format
# --------------------------------------------------------------------------
# A deliberately simplified, commonly used subset of RFC 5322:
#   local  = alnum+ ( [._-] alnum+ )*
#   domain = label ( "." label )* "." tld
#   label  = alnum+ ( "-"+ alnum+ )*      (no leading/trailing hyphen)
#   tld    = letter{2,}
# Alphabet classes: L letter, D digit, DOT ".", HY "-", US "_", AT "@", O other


def email_class(ch):
    if ch in string.ascii_letters:
        return "L"
    if ch in string.digits:
        return "D"
    return {".": "DOT", "-": "HY", "_": "US", "@": "AT"}.get(ch, "O")


EM_ALPHA = ["L", "D", "DOT", "HY", "US", "AT", "O"]
EM_EDGE = {"DOT": ".", "HY": "-", "US": "_", "AT": "@"}

_A = ["L", "D"]                 # alnum
_nfa = {}


def _add(p, syms, q):
    for s in syms:
        _nfa.setdefault((p, s), set()).add(q)


# local part
_add("n0", _A, "n1")
_add("n1", _A, "n1")
_add("n1", ["DOT", "HY", "US"], "n2")
_add("n2", _A, "n1")
_add("n1", ["AT"], "n3")
# domain labels
_add("n3", _A, "n4")
_add("n4", _A, "n4")
_add("n4", ["HY"], "n5")
_add("n5", ["HY"], "n5")
_add("n5", _A, "n4")
_add("n4", ["DOT"], "n3")       # guess: another label follows ...
_add("n4", ["DOT"], "n6")       # ... or: this dot starts the TLD
# top-level domain
_add("n6", ["L"], "n7")
_add("n7", ["L"], "n8")
_add("n8", ["L"], "n8")

EMAIL_NFA = NFA("E-mail format (NFA)", EM_ALPHA, _nfa, "n0", {"n8"}, email_class)
EMAIL_SUBSET = EMAIL_NFA.to_dfa("E-mail format (subset-construction DFA)")
EMAIL_DFA = EMAIL_SUBSET.minimize("E-mail format (minimal DFA)")

EMAIL_REFERENCE_REGEX = (r"^[A-Za-z0-9]+([._-][A-Za-z0-9]+)*@"
                         r"[A-Za-z0-9]+(-+[A-Za-z0-9]+)*"
                         r"(\.[A-Za-z0-9]+(-+[A-Za-z0-9]+)*)*\.[A-Za-z]{2,}$")

# --------------------------------------------------------------------------
# registry used by the CLI, tests and the web demo
# --------------------------------------------------------------------------
APPLICATIONS = {
    "pin": {
        "title": "ATM PIN verification",
        "dfa": PIN_DFA,
        "accept": ["4821", "0000", "9375", "1234", "0042", "7777"],
        "reject": ["482", "48211", "48a1", "12 34", "", "-123", "4,821"],
    },
    "session": {
        "title": "ATM session lock-out",
        "dfa": SESSION_DFA,
        "accept": ["C", "WC", "WWC", "CW", "WWCWW"],
        "reject": ["", "W", "WW", "WWW", "WWWC", "WWWWC"],
    },
    "password": {
        "title": "Password policy",
        "dfa": PASSWORD_DFA,
        "accept": ["Srm@2026", "Trichy#Aiml5", "aB3$efgh", "P@ssw0rdX", "Q1w2e3r4!T",
                   "Zz9_Zz9_Zz9_Zz9_"],
        "reject": ["srm@2026", "SRM@2026", "Srm@Trichy", "Srm20266", "Sr@1",
                   "Srm @2026", "Abcdefgh1!xyzABC9"],
    },
    "email": {
        "title": "E-mail format",
        "dfa": EMAIL_DFA,
        "accept": ["vaishak.kr@srmist.edu.in", "ra2411026050018@srmist.edu.in",
                   "deepak_vf@gmail.com", "a-b.c@my-site.co", "x@y.io",
                   "user@xn--p1ai-test.org"],
        "reject": ["vaishak@srmist", ".vaishak@gmail.com", "vaishak..kr@gmail.com",
                   "vaishak@-srm.in", "vaishak@srm.c0m", "vaishak@@gmail.com",
                   "vaishak kr@gmail.com", "vaishak@gmail.c"],
    },
}

LIMITATIONS = {
    "pin": [
        "Checks only the shape of the PIN. Whether 4821 is *this* card's PIN needs the bank's "
        "stored hash - a lookup, not a language property.",
        "Weak-PIN rules (all digits equal, 1234, birth years) are finite and so regular, but every "
        "rule multiplies states: the 'not all equal' rule alone takes the 4-digit DFA from 6 to "
        f"{STRONG_PIN_DFA.live_states() + 1} states.",
        "Rate limiting by time (e.g. 'lock for 24 hours') needs a clock; the session DFA only counts.",
    ],
    "session": [
        "Counts consecutive wrong attempts with a fixed bound (3). An unbounded counter "
        "('more failures than successes so far') is not regular.",
    ],
    "password": [
        "Length 8..16 and the four class rules are all regular. A rule like 'must not contain your "
        "register number' depends on the user, so each user would need a different DFA.",
        "Rules such as 'not one of the 10 000 leaked passwords' are regular (finite list) but the "
        "DFA would be huge; a hash-set lookup is the sensible engineering choice.",
        "A rule like 'equal number of letters and digits' is not regular (pumping lemma) and "
        "cannot be checked by any FA.",
    ],
    "email": [
        "Implements a practical subset of RFC 5322. Full RFC 5322 allows nested comments "
        "'(a(b)c)', and arbitrary nesting is not regular, so it needs a PDA/parser.",
        "Syntax only: whether the domain exists (DNS MX record) or the mailbox exists (SMTP) is a "
        "semantic check done after the FA accepts.",
        "Length limits (64 chars local part, 255 total) are regular but would add hundreds of states; "
        "a length counter beside the DFA is simpler.",
    ],
}
