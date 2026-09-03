"""``degrade()`` and ``constructs_used()`` against the ``week01`` fixture (plan §2.3).

The all-64-subsets test pins the cascade order inside ``degrade()``: math-degradation
emits code blocks and table-degradation emits lists, so the subset property
``constructs_used(degrade(w, C)) <= C`` only holds if code- and nesting-degradation
run after them.
"""

from __future__ import annotations

import itertools

import pytest

from lecturenotes.model import (
    BulletList,
    Callout,
    CalloutKind,
    Capability,
    CodeBlock,
    Equation,
    Figure,
    NoteWeek,
    Prose,
    Table,
    constructs_used,
    degrade,
)
from tests.fixtures.notes.week01 import BELLMAN_LATEX

ALL = set(Capability)

SUBSETS = [
    set(combo)
    for r in range(len(ALL) + 1)
    for combo in itertools.combinations(sorted(ALL), r)
]


def _subset_id(caps: set[Capability]) -> str:
    return "+".join(sorted(c.value for c in caps)) or "none"


# --- the general properties -------------------------------------------------------------


def test_week01_uses_every_capability(week01: NoteWeek) -> None:
    """The fixture exercises the whole map, so the property tests below bite."""
    assert constructs_used(week01) == ALL


@pytest.mark.parametrize("removed", sorted(ALL))
def test_removing_one_capability_removes_its_construct(
    removed: Capability, week01: NoteWeek
) -> None:
    assert removed not in constructs_used(degrade(week01, ALL - {removed}))


@pytest.mark.parametrize("caps", SUBSETS, ids=_subset_id)
def test_result_uses_only_the_given_capabilities(
    caps: set[Capability], week01: NoteWeek
) -> None:
    assert constructs_used(degrade(week01, caps)) <= caps


@pytest.mark.parametrize("caps", SUBSETS, ids=_subset_id)
def test_result_is_a_valid_noteweek(caps: set[Capability], week01: NoteWeek) -> None:
    result = degrade(week01, caps)
    assert NoteWeek.model_validate_json(result.model_dump_json()) == result


def test_full_capability_set_is_identity(week01: NoteWeek) -> None:
    assert degrade(week01, ALL) == week01


@pytest.mark.parametrize(
    "caps",
    [set(), {Capability.NESTING}, ALL - {Capability.NATIVE_MATH, Capability.CODE}],
    ids=_subset_id,
)
def test_degrade_is_idempotent(caps: set[Capability], week01: NoteWeek) -> None:
    once = degrade(week01, caps)
    assert degrade(once, caps) == once


# --- per-rewrite spot checks on week01 --------------------------------------------------
# Lecture 1 topics: [0] MDPs, [1] board work, [2] the Bellman equation, [3] value iteration.


def test_no_native_math_turns_equations_into_latex_code_blocks(week01: NoteWeek) -> None:
    original = week01.lectures[0].topics[2].body[1]
    assert isinstance(original, Equation) and original.latex == BELLMAN_LATEX

    result = degrade(week01, ALL - {Capability.NATIVE_MATH})
    assert result.lectures[0].topics[2].body[1] == CodeBlock(
        language="latex", code=BELLMAN_LATEX
    )


def test_no_nesting_flattens_children_into_siblings(week01: NoteWeek) -> None:
    original = week01.lectures[0].topics[0].body[1]
    assert isinstance(original, BulletList)
    reward, discount = original.items[2], original.items[4]
    assert len(reward.children) == 1 and len(discount.children) == 2

    result = degrade(week01, ALL - {Capability.NESTING})
    flattened = result.lectures[0].topics[0].body[1]
    assert isinstance(flattened, BulletList)
    # Pre-order: parent, then its children, order preserved, no prefix decoration.
    assert [item.text for item in flattened.items] == [
        original.items[0].text,
        original.items[1].text,
        reward.text,
        reward.children[0].text,
        original.items[3].text,
        discount.text,
        discount.children[0].text,
        discount.children[1].text,
    ]
    assert all(not item.children for item in flattened.items)


def test_no_callouts_turns_callouts_into_prefixed_prose(week01: NoteWeek) -> None:
    original = week01.lectures[0].topics[2].body[3]
    assert isinstance(original, Callout) and original.kind is CalloutKind.EXAM

    result = degrade(week01, ALL - {Capability.CALLOUTS})
    assert result.lectures[0].topics[2].body[3] == Prose(text=f"EXAM: {original.text}")


def test_no_tables_turns_tables_into_bullet_lists(week01: NoteWeek) -> None:
    original = week01.lectures[0].topics[2].body[2]
    assert isinstance(original, Table)

    result = degrade(week01, ALL - {Capability.TABLES})
    degraded = result.lectures[0].topics[2].body[2]
    assert isinstance(degraded, BulletList)
    assert degraded.items[0].text == "Term | Meaning"
    assert [item.text for item in degraded.items[1:]] == [
        " | ".join(row) for row in original.rows
    ]


def test_no_images_turns_figures_into_placeholder_prose_and_keeps_assets(
    week01: NoteWeek,
) -> None:
    original = week01.lectures[0].topics[3].body[2]
    assert isinstance(original, Figure) and original.caption is not None
    assert original.caption.startswith("Maximum change between successive sweeps")

    result = degrade(week01, ALL - {Capability.IMAGES})
    assert result.lectures[0].topics[3].body[2] == Prose(
        text=f"[figure: {original.caption}]"
    )
    assert result.lectures[0].assets == week01.lectures[0].assets


def test_no_code_turns_code_blocks_into_verbatim_prose(week01: NoteWeek) -> None:
    original = week01.lectures[0].topics[3].body[1]
    assert isinstance(original, CodeBlock)

    result = degrade(week01, ALL - {Capability.CODE})
    assert result.lectures[0].topics[3].body[1] == Prose(text=original.code)


# --- what degradation must never touch --------------------------------------------------


@pytest.mark.parametrize("caps", SUBSETS, ids=_subset_id)
def test_metadata_anchors_and_ids_survive_every_degradation(
    caps: set[Capability], week01: NoteWeek
) -> None:
    result = degrade(week01, caps)
    for before, after in zip(week01.lectures, result.lectures, strict=True):
        assert after.glossary == before.glossary
        assert after.open_questions == before.open_questions
        for t_before, t_after in zip(before.topics, after.topics, strict=True):
            assert t_after.id == t_before.id
            assert t_after.anchor == t_before.anchor
            assert t_after.cards == t_before.cards
