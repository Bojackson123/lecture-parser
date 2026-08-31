import pytest
from pydantic import ValidationError

from lecturenotes.model import (
    BulletItem,
    BulletList,
    Callout,
    CalloutKind,
    CodeBlock,
    Definition,
    Equation,
    Figure,
    Prose,
    Quote,
    Table,
)


def test_each_node_type_instantiates_with_minimal_args() -> None:
    nodes = [
        Prose(text="p"),
        BulletList(items=[BulletItem(text="a")]),
        Definition(term="t", definition="d"),
        Equation(latex=r"e^{i\pi} + 1 = 0"),
        CodeBlock(code="print(1)"),
        Callout(kind=CalloutKind.EXAM, text="on the exam"),
        Figure(asset_id="img-1"),
        Table(header=["a", "b"], rows=[["1", "2"]]),
        Quote(text="q"),
    ]
    assert len(nodes) == 9
    assert {n.type for n in nodes} == {
        "prose",
        "bullet_list",
        "definition",
        "equation",
        "code_block",
        "callout",
        "figure",
        "table",
        "quote",
    }


def test_optional_fields_default_to_none() -> None:
    assert Equation(latex="x").label is None
    assert CodeBlock(code="x").language is None
    assert Figure(asset_id="a").caption is None
    assert Quote(text="q").attribution is None


def test_bullet_list_requires_at_least_one_item() -> None:
    with pytest.raises(ValidationError):
        BulletList(items=[])


def test_bullet_item_children_default_empty_and_nest() -> None:
    leaf = BulletItem(text="leaf")
    assert leaf.children == []
    parent = BulletItem(text="parent", children=[leaf])
    assert parent.children[0].text == "leaf"


def test_table_with_ragged_row_raises() -> None:
    with pytest.raises(ValidationError):
        Table(header=["a", "b"], rows=[["1", "2"], ["only-one"]])


def test_table_with_no_rows_is_fine() -> None:
    assert Table(header=["a"], rows=[]).rows == []


def test_callout_kind_from_string_and_unknown_raises() -> None:
    assert Callout.model_validate({"kind": "PITFALL", "text": "x"}).kind is CalloutKind.PITFALL
    with pytest.raises(ValidationError):
        Callout.model_validate({"kind": "WARNING", "text": "x"})


def test_callout_kind_values() -> None:
    assert {k.value for k in CalloutKind} == {"EXAM", "PITFALL", "UNCERTAIN", "ASIDE"}


def test_extra_field_raises() -> None:
    with pytest.raises(ValidationError):
        Prose.model_validate({"text": "p", "colour": "red"})


def test_wrong_discriminator_value_raises() -> None:
    with pytest.raises(ValidationError):
        Prose.model_validate({"type": "quote", "text": "p"})


def test_nodes_are_frozen_and_hashable() -> None:
    p = Prose(text="p")
    with pytest.raises(ValidationError):
        p.text = "q"  # type: ignore[misc]
    assert hash(p) == hash(Prose(text="p"))
    assert len({p, Prose(text="p"), Quote(text="p")}) == 2
