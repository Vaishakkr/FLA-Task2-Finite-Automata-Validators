"""
Small finite-automata toolkit used by every validator in this repo.

Nothing here is specific to passwords, e-mails or PINs. A validator is just
a DFA (or an NFA that we convert) plus a function that maps each raw input
character to a symbol of the automaton's alphabet. Keeping the alphabet small
(character *classes* instead of all 95 printable ASCII characters) is what
keeps the diagrams readable.

Implemented:
  * DFA with a step-by-step trace of every run
  * NFA -> DFA subset construction
  * product construction (intersection) of two DFAs
  * complement
  * minimisation (table-filling / Myhill-Nerode)
  * export to Graphviz DOT
"""

from collections import deque
from itertools import product as cartesian

DEAD = "qD"   # name used for the implicit trap state


class DFA:
    def __init__(self, name, alphabet, delta, start, accepting, classify,
                 states=None, labels=None):
        """
        alphabet  : list of symbols (character classes), e.g. ["U", "L", "D"]
        delta     : dict {(state, symbol): next_state}; anything missing goes
                    to the dead state
        start     : start state
        accepting : set of accepting states
        classify  : function(char) -> symbol in alphabet
        labels    : optional dict state -> human readable meaning
        """
        self.name = name
        self.alphabet = list(alphabet)
        self.start = start
        self.accepting = set(accepting)
        self.classify = classify
        self.labels = labels or {}
        found = {start} | set(self.accepting)
        for (p, _a), q in delta.items():
            found.add(p)
            found.add(q)
        self.states = list(states) if states else sorted(found, key=_natural)
        # make the transition function total by adding the dead state
        self.delta = dict(delta)
        need_dead = False
        for p in self.states:
            for a in self.alphabet:
                if (p, a) not in self.delta:
                    self.delta[(p, a)] = DEAD
                    need_dead = True
        if need_dead or DEAD in self.states:
            if DEAD not in self.states:
                self.states.append(DEAD)
            for a in self.alphabet:
                self.delta[(DEAD, a)] = DEAD

    # ------------------------------------------------------------------ run
    def step(self, state, symbol):
        return self.delta.get((state, symbol), DEAD)

    def run(self, text):
        """Return (accepted, trace). trace = list of (state, char, symbol, next)."""
        state = self.start
        trace = []
        for ch in text:
            sym = self.classify(ch)
            nxt = self.step(state, sym) if sym in self.alphabet else DEAD
            trace.append((state, ch, sym, nxt))
            state = nxt
        return state in self.accepting, trace

    def accepts(self, text):
        return self.run(text)[0]

    def accepts_symbols(self, symbols):
        state = self.start
        for s in symbols:
            state = self.step(state, s)
        return state in self.accepting

    # ------------------------------------------------------------ algebra
    def reachable(self):
        seen = {self.start}
        todo = deque([self.start])
        while todo:
            p = todo.popleft()
            for a in self.alphabet:
                q = self.step(p, a)
                if q not in seen:
                    seen.add(q)
                    todo.append(q)
        return seen

    def complement(self, name=None):
        return DFA(name or "not " + self.name, self.alphabet,
                   {k: v for k, v in self.delta.items()}, self.start,
                   set(self.states) - self.accepting, self.classify,
                   states=self.states)

    def intersect(self, other, name=None):
        """Product construction. Both machines must share the alphabet."""
        assert self.alphabet == other.alphabet, "alphabets differ"
        start = (self.start, other.start)
        delta, seen, todo = {}, {start}, deque([start])
        while todo:
            p, q = todo.popleft()
            for a in self.alphabet:
                nxt = (self.step(p, a), other.step(q, a))
                delta[((p, q), a)] = nxt
                if nxt not in seen:
                    seen.add(nxt)
                    todo.append(nxt)
        acc = {s for s in seen if s[0] in self.accepting and s[1] in other.accepting}
        names = {s: f"{s[0]}|{s[1]}" for s in seen}
        return DFA(name or f"{self.name} AND {other.name}", self.alphabet,
                   {(names[p], a): names[q] for (p, a), q in delta.items()},
                   names[start], {names[s] for s in acc}, self.classify,
                   states=sorted(names.values(), key=_natural))

    def minimize(self, name=None):
        """Table-filling algorithm on the reachable part."""
        states = sorted(self.reachable(), key=_natural)
        idx = {s: i for i, s in enumerate(states)}
        n = len(states)
        marked = [[False] * n for _ in range(n)]
        for i in range(n):
            for j in range(i):
                if (states[i] in self.accepting) != (states[j] in self.accepting):
                    marked[i][j] = True
        changed = True
        while changed:
            changed = False
            for i in range(n):
                for j in range(i):
                    if marked[i][j]:
                        continue
                    for a in self.alphabet:
                        x = idx[self.step(states[i], a)]
                        y = idx[self.step(states[j], a)]
                        if x != y and marked[max(x, y)][min(x, y)]:
                            marked[i][j] = True
                            changed = True
                            break
        # union-find over unmarked pairs
        parent = list(range(n))

        def find(k):
            while parent[k] != k:
                parent[k] = parent[parent[k]]
                k = parent[k]
            return k
        for i in range(n):
            for j in range(i):
                if not marked[i][j]:
                    parent[find(i)] = find(j)
        groups = {}
        for i, s in enumerate(states):
            groups.setdefault(find(i), []).append(s)
        # name the blocks m0, m1, ... in BFS order from the start state
        block_of = {s: r for r, members in groups.items() for s in members}
        order, seen = [], set()
        todo = deque([block_of[self.start]])
        seen.add(block_of[self.start])
        while todo:
            b = todo.popleft()
            order.append(b)
            rep = groups[b][0]
            for a in self.alphabet:
                nb = block_of[self.step(rep, a)]
                if nb not in seen:
                    seen.add(nb)
                    todo.append(nb)
        dead_block = None
        for b in order:
            rep = groups[b][0]
            if rep not in self.accepting and all(block_of[self.step(rep, a)] == b for a in self.alphabet):
                dead_block = b
        newname = {}
        k = 0
        for b in order:
            if b == dead_block:
                newname[b] = DEAD
            else:
                newname[b] = f"m{k}"
                k += 1
        delta = {}
        for b in order:
            rep = groups[b][0]
            for a in self.alphabet:
                delta[(newname[b], a)] = newname[block_of[self.step(rep, a)]]
        acc = {newname[b] for b in order if groups[b][0] in self.accepting}
        return DFA(name or self.name + " (minimal)", self.alphabet, delta,
                   newname[block_of[self.start]], acc, self.classify,
                   states=[newname[b] for b in order])

    def live_states(self):
        """Number of states not counting the dead/trap state."""
        return len([s for s in self.reachable() if s != DEAD])

    # ------------------------------------------------------------- export
    def to_dot(self, show_dead=False, rankdir="LR", edge_names=None, size=None):
        edge_names = edge_names or {}
        out = [f'digraph "{self.name}" {{',
               f'  rankdir={rankdir}; bgcolor="white";',
               '  node [shape=circle fontname="Helvetica" fontsize=11];',
               '  edge [fontname="Helvetica" fontsize=10];',
               '  __start [shape=point width=0.08];']
        if size:
            out.append(f'  size="{size}";')
        shown = [s for s in self.states if show_dead or s != DEAD]
        for s in shown:
            shape = "doublecircle" if s in self.accepting else "circle"
            extra = ' style=filled fillcolor="#f2f2f2"' if s == DEAD else ""
            out.append(f'  "{s}" [shape={shape}{extra}];')
        out.append(f'  __start -> "{self.start}";')
        grouped = {}
        for (p, a), q in self.delta.items():
            if p not in shown or q not in shown:
                continue
            grouped.setdefault((p, q), []).append(edge_names.get(a, a))
        for (p, q), syms in grouped.items():
            out.append(f'  "{p}" -> "{q}" [label="{", ".join(syms)}"];')
        out.append("}")
        return "\n".join(out)

    def table(self):
        """Transition table as a list of rows (for README / report)."""
        rows = []
        for s in self.states:
            mark = ("->" if s == self.start else "") + ("*" if s in self.accepting else "")
            rows.append([mark + s] + [self.step(s, a) for a in self.alphabet])
        return rows


class NFA:
    """NFA without epsilon moves (we never needed them here)."""

    def __init__(self, name, alphabet, delta, start, accepting, classify):
        self.name = name
        self.alphabet = list(alphabet)
        self.delta = {k: set(v) for k, v in delta.items()}
        self.start = start
        self.accepting = set(accepting)
        self.classify = classify
        states = {start} | self.accepting
        for (p, _a), qs in self.delta.items():
            states.add(p)
            states |= qs
        self.states = sorted(states, key=_natural)

    def accepts(self, text):
        current = {self.start}
        for ch in text:
            a = self.classify(ch)
            current = set().union(*[self.delta.get((p, a), set()) for p in current]) if current else set()
        return bool(current & self.accepting)

    def to_dfa(self, name=None):
        """Subset construction. DFA states are named by the NFA subsets."""
        def nm(S):
            return "{" + ",".join(sorted(S, key=_natural)) + "}" if S else DEAD
        start = frozenset([self.start])
        seen, todo, delta = {start}, deque([start]), {}
        while todo:
            S = todo.popleft()
            for a in self.alphabet:
                T = frozenset(set().union(*[self.delta.get((p, a), set()) for p in S]))
                delta[(nm(S), a)] = nm(T)
                if T and T not in seen:
                    seen.add(T)
                    todo.append(T)
        acc = {nm(S) for S in seen if S & self.accepting}
        return DFA(name or self.name + " (subset construction)", self.alphabet,
                   delta, nm(start), acc, self.classify)

    def to_dot(self, rankdir="LR", edge_names=None):
        edge_names = edge_names or {}
        out = [f'digraph "{self.name}" {{', f'  rankdir={rankdir};',
               '  node [shape=circle fontname="Helvetica" fontsize=11];',
               '  edge [fontname="Helvetica" fontsize=10];',
               '  __start [shape=point width=0.08];']
        for s in self.states:
            out.append(f'  "{s}" [shape={"doublecircle" if s in self.accepting else "circle"}];')
        out.append(f'  __start -> "{self.start}";')
        grouped = {}
        for (p, a), qs in self.delta.items():
            for q in qs:
                grouped.setdefault((p, q), []).append(edge_names.get(a, a))
        for (p, q), syms in grouped.items():
            out.append(f'  "{p}" -> "{q}" [label="{", ".join(syms)}"];')
        out.append("}")
        return "\n".join(out)


def equivalent(d1, d2, max_len=None):
    """Decide L(d1) == L(d2) exactly by exploring the product machine.
    Returns (True, None) or (False, counterexample_symbols)."""
    start = (d1.start, d2.start)
    seen = {start: []}
    todo = deque([start])
    while todo:
        p, q = todo.popleft()
        if (p in d1.accepting) != (q in d2.accepting):
            return False, seen[(p, q)]
        for a in d1.alphabet:
            nxt = (d1.step(p, a), d2.step(q, a))
            if nxt not in seen:
                seen[nxt] = seen[(p, q)] + [a]
                todo.append(nxt)
    return True, None


def all_strings(alphabet, max_len):
    for n in range(max_len + 1):
        for t in cartesian(alphabet, repeat=n):
            yield "".join(t)


def _natural(s):
    import re
    s = str(s)
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", s)]
