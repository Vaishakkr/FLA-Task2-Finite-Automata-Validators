"""Regenerate every diagram in docs/diagrams from the automata definitions.
Needs Graphviz (`dot`) on PATH."""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fa_validators.validators import (EM_EDGE, EMAIL_DFA, EMAIL_NFA, PIN46_DFA,  # noqa: E402
                                      PIN_DFA, PW_COVERAGE, PW_PARTS, SESSION_DFA,
                                      APPLICATIONS)

OUT = ROOT / "docs" / "diagrams"
OUT.mkdir(parents=True, exist_ok=True)

DIAGRAMS = {
    "pin_dfa": PIN_DFA.to_dot(),
    "pin46_dfa": PIN46_DFA.to_dot(),
    "session_dfa": SESSION_DFA.to_dot(),
    "password_coverage": PW_COVERAGE.to_dot(rankdir="LR"),
    "password_length": PW_PARTS[-1].to_dot(),
    "password_has_upper": PW_PARTS[0].to_dot(),
    "email_nfa": EMAIL_NFA.to_dot(edge_names=EM_EDGE),
    "email_dfa": EMAIL_DFA.to_dot(edge_names=EM_EDGE),
}

for name, dot in DIAGRAMS.items():
    (OUT / f"{name}.dot").write_text(dot)
    for fmt in ("svg", "png"):
        args = ["dot", f"-T{fmt}", "-o", str(OUT / f"{name}.{fmt}")]
        if fmt == "png":
            args.insert(1, "-Gdpi=170")
        subprocess.run(args, input=dot.encode(), check=True)
    print("wrote", name)

# JSON export for the browser demo (docs/index.html)
export = {}
for key, app in APPLICATIONS.items():
    d = app["dfa"]
    export[key] = {
        "title": app["title"], "name": d.name, "start": d.start,
        "accepting": sorted(d.accepting), "alphabet": d.alphabet,
        "delta": {f"{p}|{a}": q for (p, a), q in d.delta.items()},
        "examples": {"accept": app["accept"], "reject": app["reject"]},
        "states": d.live_states(),
    }
(ROOT / "docs" / "automata.json").write_text(json.dumps(export, indent=1))
print("wrote docs/automata.json")

# self-contained browser demo (works offline and on GitHub Pages)
svgs = {}
for key, fname in {"pin": "pin_dfa", "session": "session_dfa", "email": "email_dfa"}.items():
    txt = (OUT / f"{fname}.svg").read_text()
    svgs[key] = txt[txt.index("<svg"):]
tpl = (ROOT / "tools" / "demo_template.html").read_text()
html = tpl.replace("__JSON__", json.dumps(export)).replace("__SVG__", json.dumps(svgs))
(ROOT / "docs" / "index.html").write_text(html)
print("wrote docs/index.html")
