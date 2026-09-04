"""Hand-written ``NoteWeek`` fixture: CS-RL-101, week 1 (P0-04).

The one note-side fixture every later phase shares: Phase 3 renders it, Phase 6 breaks
it. It exercises the entire IR — all nine ``Node`` types, all four ``CalloutKind``
values, nested bullets, a slide-less gap topic, cards, glossary and open questions —
and is written to read like real notes, since the plan's success criterion is "good
enough to revise from".

Lecture 1 follows the slide → time map in ``tests/fixtures/README.md`` exactly.
Lecture 2 is a second lecture in the same week (so renderers face the one-page-or-
several decision, plan §7.3); it reuses the P0-03 source files under a different id.

Regenerate the JSON snapshot deliberately, never automatically:

    uv run python -m tests.fixtures.notes.week01 --write
"""

from __future__ import annotations

import sys
from pathlib import Path

from lecturenotes.model import (
    BulletItem,
    BulletList,
    Callout,
    CalloutKind,
    CardSeed,
    CodeBlock,
    Definition,
    Equation,
    Figure,
    MediaAsset,
    NoteLecture,
    NoteWeek,
    Prose,
    Quote,
    SlideRange,
    SourceAnchor,
    SourceRef,
    Table,
    Topic,
    topic_id,
)

JSON_PATH = Path(__file__).with_suffix(".json")

# Paths are relative to the repo root (plan §2.2: assets are resolved by the emitter).
CAPTIONS = "tests/fixtures/captions/lecture01.vtt"
DECK = "tests/fixtures/decks/lecture01.pdf"
FIGURE_PNG = "tests/fixtures/decks/value_iteration.png"

LEC01 = "lec01"
LEC02 = "lec02"

BELLMAN_LATEX = r"V(s) = \max_a \Big[ R(s, a) + \gamma \sum_{s'} T(s, a, s')\, V(s') \Big]"

_Body = list[
    Prose | BulletList | Definition | Equation | CodeBlock | Callout | Figure | Table | Quote
]


def _topic(
    lecture_id: str,
    heading: str,
    start_s: float,
    end_s: float,
    slides: tuple[int, int] | None,
    body: _Body,
    cards: list[CardSeed] | None = None,
) -> Topic:
    slide_range = SlideRange(start=slides[0], end=slides[1]) if slides else None
    return Topic(
        id=topic_id(lecture_id, slide_range, start_s),
        heading=heading,
        anchor=SourceAnchor(start_s=start_s, end_s=end_s, slides=slide_range),
        body=body,
        cards=cards or [],
    )


# --- Lecture 1: MDPs and the Bellman Equation ------------------------------------------


def _lecture01() -> NoteLecture:
    mdp = _topic(
        LEC01,
        "Markov decision processes",
        1.0,
        149.0,
        (1, 1),
        [
            Prose(
                text=(
                    "Sequential decision making starts with a Markov decision process. "
                    "An MDP is fully specified by four ingredients; the Bellman equation "
                    "later in the lecture is nothing more than these four written down "
                    "recursively."
                )
            ),
            BulletList(
                items=[
                    BulletItem(
                        text=r"States $s \in S$ — everything the agent needs to know right now"
                    ),
                    BulletItem(text=r"Actions $a \in A$ — the choices available in each state"),
                    BulletItem(
                        text="Reward $R(s, a)$ — a number received for taking $a$ in $s$",
                        children=[
                            BulletItem(text="Immediate and given; not to be confused with value"),
                        ],
                    ),
                    BulletItem(
                        text="Transition function $T(s, a, s')$ — where you land after each action"
                    ),
                    BulletItem(
                        text=r"Discount factor $\gamma \in [0, 1)$ — how much later rewards count",
                        children=[
                            BulletItem(text=r"$\gamma \to 0$: myopic, only the next reward counts"),
                            BulletItem(text=r"$\gamma \to 1$: far-sighted, but sums may diverge"),
                        ],
                    ),
                ]
            ),
            Definition(
                term="Markov property",
                definition=(
                    "The next state depends only on the current state and action, not on "
                    "the history that led there."
                ),
            ),
            Callout(
                kind=CalloutKind.PITFALL,
                text=(
                    "Reward vs value: the reward is the number you get right now; the value "
                    "is the total discounted reward you expect from here on. Students mix "
                    "these up every year."
                ),
            ),
        ],
        cards=[
            CardSeed(
                front="What are the four ingredients of an MDP?",
                back="States, actions, rewards, and a transition function.",
                tags=["mdp"],
            ),
            CardSeed(
                front="What does the discount factor gamma control?",
                back="How much later rewards count relative to immediate ones.",
                tags=["mdp", "discounting"],
            ),
        ],
    )

    board_work = _topic(
        LEC01,
        "Board work: the reroll game",
        151.0,
        268.0,
        None,
        [
            Prose(
                text=(
                    "Away from the slides: roll a fair six-sided die and receive the face "
                    "value in dollars. The game is worth its expected payout, 3.5, so paying "
                    "anything less is a bargain."
                )
            ),
            Prose(
                text=(
                    "Now allow one reroll. The trick is to value the second roll first, because "
                    "its worth is already known: keep the first roll only if it beats 3.5, i.e. "
                    "a 4, 5 or 6."
                )
            ),
            Equation(
                latex=(
                    r"\mathbb{E}[\text{reroll game}] = \tfrac{1}{2}\cdot\tfrac{4+5+6}{3}"
                    r" + \tfrac{1}{2}\cdot 3.5 = 4.25"
                ),
                label="reroll-value",
            ),
            Callout(
                kind=CalloutKind.ASIDE,
                text=(
                    "This is dynamic programming in miniature: solve the last decision first, "
                    "then use its value to make the earlier one. The same idea drives value "
                    "iteration."
                ),
            ),
        ],
        cards=[
            CardSeed(
                front="With one optional reroll of a fair die, which first rolls do you keep?",
                back="4, 5 or 6 — anything that beats the 3.5 expected value of rerolling.",
                tags=["dynamic-programming"],
            ),
        ],
    )

    bellman = _topic(
        LEC01,
        "The Bellman equation",
        271.0,
        419.0,
        (2, 2),
        [
            Prose(
                text=(
                    "The value of a state is the immediate reward plus gamma times the expected "
                    "value of wherever you land next. The equation is recursive: the value on "
                    "the left shows up again on the right-hand side."
                )
            ),
            Equation(latex=BELLMAN_LATEX, label="bellman"),
            Table(
                header=["Term", "Meaning"],
                rows=[
                    ["$V(s)$", "value of state $s$"],
                    [r"$\max_a$", "best action available"],
                    [r"$\sum_{s'} T(s, a, s')$", "expectation over next states"],
                    [r"$\gamma$", "discount factor"],
                ],
            ),
            Callout(
                kind=CalloutKind.EXAM,
                text=(
                    "Write the Bellman equation down properly, with the max over actions and "
                    "the sum over next states. This will be on the exam."
                ),
            ),
            Quote(
                text=(
                    "Once you believe the Bellman equation has a unique fixed point, everything "
                    "else in this lecture follows."
                ),
                attribution="Lecturer, on the principle of optimality",
            ),
        ],
        cards=[
            CardSeed(
                front="State the Bellman optimality equation for $V(s)$.",
                back=f"${BELLMAN_LATEX}$",
                tags=["bellman", "exam"],
            ),
            CardSeed(
                front="Why is the Bellman equation called recursive?",
                back="The value function $V$ appears on both sides of the equation.",
                tags=["bellman"],
            ),
        ],
    )

    value_iteration = _topic(
        LEC01,
        "Value iteration",
        421.0,
        545.0,
        (3, 3),
        [
            Prose(
                text=(
                    "Value iteration turns the equation into an update rule: start with every "
                    "value at zero and sweep over all the states, applying the update once per "
                    "state."
                )
            ),
            CodeBlock(
                language="python",
                code=(
                    "def value_iteration(mdp, gamma, eps):\n"
                    "    V = {s: 0.0 for s in mdp.states}\n"
                    "    while True:\n"
                    "        delta = 0.0\n"
                    "        for s in mdp.states:\n"
                    "            best = max(\n"
                    "                mdp.R(s, a)\n"
                    "                + gamma * sum(p * V[s2] for s2, p in mdp.T(s, a))\n"
                    "                for a in mdp.actions(s)\n"
                    "            )\n"
                    "            delta = max(delta, abs(best - V[s]))\n"
                    "            V[s] = best\n"
                    "        if delta < eps:\n"
                    "            return V\n"
                ),
            ),
            Figure(
                asset_id="fig-value-iteration-convergence",
                caption=(
                    "Maximum change between successive sweeps on a small grid world; it "
                    "falls geometrically with rate gamma."
                ),
            ),
            Prose(
                text=(
                    "When the biggest change falls below the tolerance epsilon, stop and read "
                    "off the greedy policy by picking the best action in every state."
                )
            ),
            Callout(
                kind=CalloutKind.UNCERTAIN,
                text=(
                    "The lecturer said the error 'shrinks by a factor of gamma every time'. "
                    "That is the contraction bound; the observed per-sweep ratio can be smaller."
                ),
            ),
        ],
        cards=[
            CardSeed(
                front="When does value iteration stop, and what do you read off afterwards?",
                back=(
                    "When the biggest per-sweep change falls below the tolerance epsilon; "
                    "then pick the best action in every state to get the greedy policy."
                ),
                tags=["value-iteration"],
            ),
        ],
    )

    return NoteLecture(
        id=LEC01,
        title="MDPs and the Bellman Equation",
        overview=(
            "Introduces Markov decision processes, derives the Bellman optimality equation "
            "from their four ingredients, and turns it into the value iteration algorithm. "
            "A board-work detour on a dice game motivates solving the last decision first."
        ),
        objectives=[
            "Name the four ingredients of an MDP and the role of the discount factor.",
            "Write the Bellman optimality equation and explain why it is recursive.",
            "Run one sweep of value iteration by hand and state its stopping rule.",
        ],
        source=SourceRef(
            video_url="https://example.edu/cs-rl-101/week01/lecture01.mp4",
            deck_path=DECK,
            caption_path=CAPTIONS,
        ),
        topics=[mdp, board_work, bellman, value_iteration],
        glossary=[
            Definition(
                term="Discount factor",
                definition=r"$\gamma \in [0, 1)$; weights a reward $k$ steps ahead by $\gamma^k$.",
            ),
            Definition(
                term="Value function",
                definition=(
                    "$V(s)$: the expected total discounted reward starting from state $s$ and "
                    "acting optimally."
                ),
            ),
            Definition(
                term="Greedy policy",
                definition=(
                    "The policy that picks, in every state, the action maximising the Bellman "
                    "bracket."
                ),
            ),
        ],
        open_questions=[
            "Why does the Bellman equation have exactly one fixed point for gamma < 1?",
            "How many sweeps does value iteration need to reach a given epsilon?",
        ],
        assets=[
            MediaAsset(
                id="fig-value-iteration-convergence",
                media_type="image/png",
                source=FIGURE_PNG,
                alt="Line plot of maximum value change per sweep, decaying geometrically",
            ),
        ],
    )


# --- Lecture 2: Policies and Policy Iteration -------------------------------------------


def _lecture02() -> NoteLecture:
    policies = _topic(
        LEC02,
        "Policies and the state-value function",
        0.0,
        180.0,
        (1, 1),
        [
            Prose(
                text=(
                    r"A policy $\pi$ maps states to actions. Fixing a policy turns the MDP into "
                    "a Markov chain with rewards, and the value of a state under that policy "
                    "satisfies a linear version of last lecture's equation."
                )
            ),
            Equation(
                latex=(
                    r"V^{\pi}(s) = R(s, \pi(s)) + \gamma \sum_{s'} T(s, \pi(s), s')\, V^{\pi}(s')"
                ),
                label="bellman-expectation",
            ),
            BulletList(
                items=[
                    BulletItem(
                        text=r"No max: the action is chosen by $\pi$, so the system is linear"
                    ),
                    BulletItem(
                        text="Can be solved exactly by matrix inversion for small state spaces"
                    ),
                ]
            ),
        ],
        cards=[
            CardSeed(
                front=(
                    "What distinguishes the Bellman expectation equation from the optimality "
                    "equation?"
                ),
                back=(
                    "Expectation fixes the action via a policy and is linear; optimality has a "
                    "max over actions."
                ),
                tags=["bellman", "policy"],
            ),
        ],
    )

    policy_iteration = _topic(
        LEC02,
        "Policy iteration",
        180.0,
        420.0,
        (2, 3),
        [
            Prose(
                text=(
                    "Policy iteration alternates two steps until the policy stops changing: "
                    "evaluate the current policy, then improve it greedily."
                )
            ),
            Table(
                header=["Step", "What it does", "Cost"],
                rows=[
                    ["Evaluate", r"Solve $V^{\pi}$ for the current $\pi$", "One linear solve"],
                    ["Improve", r"Set $\pi(s) \leftarrow \arg\max_a [\cdot]$", "One sweep"],
                ],
            ),
            Callout(
                kind=CalloutKind.EXAM,
                text=(
                    "Be able to compare policy iteration with value iteration: few expensive "
                    "iterations versus many cheap ones."
                ),
            ),
        ],
        cards=[
            CardSeed(
                front="What are the two alternating steps of policy iteration?",
                back=(
                    "Evaluate the current policy exactly, then improve it greedily; stop "
                    "when the policy stops changing."
                ),
                tags=["policy-iteration"],
            ),
        ],
    )

    return NoteLecture(
        id=LEC02,
        title="Policies and Policy Iteration",
        overview=(
            "Defines policies, derives the Bellman expectation equation for a fixed policy, "
            "and introduces policy iteration as an alternative to value iteration."
        ),
        objectives=[
            "Define a policy and the state-value function under a policy.",
            "Explain the two steps of policy iteration and when it terminates.",
        ],
        source=SourceRef(deck_path=DECK, caption_path=CAPTIONS),
        topics=[policies, policy_iteration],
        glossary=[
            Definition(
                term="Policy", definition=r"A mapping $\pi: S \to A$ from states to actions."
            ),
        ],
        open_questions=["Does policy iteration always terminate in finitely many steps?"],
    )


def week01() -> NoteWeek:
    """The canonical week-1 fixture."""
    return NoteWeek(
        id="cs-rl-101-w01",
        course="CS-RL-101",
        week_number=1,
        lectures=[_lecture01(), _lecture02()],
    )


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    text = week01().model_dump_json(indent=2) + "\n"
    if "--write" in args:
        # LF on every platform so the snapshot never picks up CRLF on Windows.
        with JSON_PATH.open("w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        print(f"wrote {JSON_PATH}", file=sys.stderr)
    else:
        # Bytes, so neither the console code page nor newline translation touches it.
        sys.stdout.buffer.write(text.encode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
