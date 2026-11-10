"""
Command-line demo.

  python -m fa_validators.cli                 run every application's test table
  python -m fa_validators.cli email a@b.co    check one string with a full trace
  python -m fa_validators.cli --stats         state counts for every design
"""
import sys

from .automata import DEAD
from .validators import (APPLICATIONS, EMAIL_DFA, EMAIL_NFA, EMAIL_SUBSET,
                         LIMITATIONS, PASSWORD_DFA, PASSWORD_PRODUCT, PIN46_DFA,
                         PIN_DFA, PW_PARTS, STRONG_PIN_DFA)

GREEN, RED, DIM, BOLD, END = "\033[32m", "\033[31m", "\033[2m", "\033[1m", "\033[0m"
if not sys.stdout.isatty() and "--color" not in sys.argv:
    GREEN = RED = DIM = BOLD = END = ""


def show(s):
    return repr(s) if s == "" or " " in s else s


def table(app_key):
    app = APPLICATIONS[app_key]
    dfa = app["dfa"]
    print(f"\n{BOLD}{app['title']}{END}  [{dfa.name}, {dfa.live_states()} live states]")
    print(f"{'input':<24}{'expected':<10}{'result':<10}{'final state':<14}")
    ok = 0
    rows = [(s, True) for s in app["accept"]] + [(s, False) for s in app["reject"]]
    for s, exp in rows:
        acc, trace = dfa.run(s)
        final = trace[-1][3] if trace else dfa.start
        good = acc == exp
        ok += good
        res = f"{GREEN}ACCEPT{END}" if acc else f"{RED}REJECT{END}"
        pad = 10 + (len(res) - len("ACCEPT"))
        print(f"{show(s):<24}{('ACCEPT' if exp else 'REJECT'):<10}{res:<{pad}}{final:<14}"
              f"{'' if good else '  <-- MISMATCH'}")
    print(f"{DIM}{ok}/{len(rows)} as expected{END}")
    return ok == len(rows)


def trace(app_key, text):
    dfa = APPLICATIONS[app_key]["dfa"]
    acc, steps = dfa.run(text)
    print(f"{BOLD}{dfa.name}{END} on {show(text)}")
    for i, (p, ch, sym, q) in enumerate(steps, 1):
        note = "  (trap state - can never accept)" if q == DEAD and p != DEAD else ""
        print(f"  {i:>2}. δ({p}, '{ch}' -> {sym}) = {q}{note}")
    final = steps[-1][3] if steps else dfa.start
    verdict = f"{GREEN}ACCEPTED{END}" if acc else f"{RED}REJECTED{END}"
    print(f"  final state {final} -> {verdict}")


def stats():
    print(f"{BOLD}Design comparison (live states, trap state not counted){END}")
    rows = [
        ("PIN: exactly 4 digits", PIN_DFA.live_states()),
        ("PIN: 4 or 6 digits", PIN46_DFA.live_states()),
        ("PIN: 4 digits, not all equal (raw 0-9 alphabet)", STRONG_PIN_DFA.live_states()),
        ("Password: 5 separate DFAs run side by side", sum(p.live_states() for p in PW_PARTS)),
        ("Password: product of the 5 DFAs (reachable)", PASSWORD_PRODUCT.live_states()),
        ("Password: product after minimisation", PASSWORD_DFA.live_states()),
        ("E-mail: hand-written NFA", len(EMAIL_NFA.states)),
        ("E-mail: DFA by subset construction", EMAIL_SUBSET.live_states()),
        ("E-mail: minimal DFA", EMAIL_DFA.live_states()),
    ]
    for name, n in rows:
        print(f"  {name:<52}{n:>5}")


def limitations():
    for k, items in LIMITATIONS.items():
        print(f"\n{BOLD}Limitations - {APPLICATIONS[k]['title']}{END}")
        for it in items:
            print(f"  - {it}")


def main(argv):
    args = [a for a in argv if a != "--color"]
    if not args:
        all_ok = all([table(k) for k in APPLICATIONS])
        print(f"\n{BOLD}All examples behaved as expected: {all_ok}{END}")
        return 0 if all_ok else 1
    if args[0] == "--stats":
        stats()
        return 0
    if args[0] == "--limits":
        limitations()
        return 0
    if args[0] in APPLICATIONS and len(args) >= 2:
        trace(args[0], " ".join(args[1:]) if args[0] != "pin" else args[1])
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
