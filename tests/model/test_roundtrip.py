import json

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
)

ALL_TYPES = {
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


def build_lecture() -> NoteLecture:
    return NoteLecture(
        id="lec01",
        title="Eigenvalues",
        overview="What eigenvalues are and why we care.",
        objectives=["Define eigenvalue", "Compute for 2x2"],
        source=SourceRef(
            video_url="https://example.invalid/lec01.mp4",
            deck_path="week01/lec01.pdf",
            caption_path="week01/lec01.vtt",
        ),
        topics=[
            Topic(
                id="lec01:s1-3",
                heading="Definition",
                anchor=SourceAnchor(start_s=0.0, end_s=180.5, slides=SlideRange(start=1, end=3)),
                body=[
                    Prose(text="An eigenvector is scaled, not rotated."),
                    BulletList(
                        items=[
                            BulletItem(
                                text="Outer",
                                children=[
                                    BulletItem(text="Inner", children=[BulletItem(text="Leaf")])
                                ],
                            ),
                            BulletItem(text="Sibling"),
                        ]
                    ),
                    Definition(term="eigenvalue", definition="scalar lambda with Av = lambda v"),
                    Equation(latex=r"A v = \lambda v", label="eig"),
                    CodeBlock(code="import numpy as np\nnp.linalg.eig(A)", language="python"),
                    Callout(kind=CalloutKind.EXAM, text="Always on the exam."),
                    Figure(asset_id="fig-1", caption="Stretching along v"),
                    Table(header=["lambda", "v"], rows=[["2", "(1, 0)"], ["3", "(0, 1)"]]),
                    Quote(text="Nothing to see here.", attribution="Lecturer"),
                ],
                cards=[
                    CardSeed(
                        front="What is an eigenvalue?",
                        back="A scalar lambda with Av = lambda v",
                        tags=["linear-algebra"],
                    )
                ],
            ),
            Topic(
                id="lec01:t754",
                heading="Board work",
                anchor=SourceAnchor(start_s=754.2, end_s=900.0),
                body=[Prose(text="Worked example on the board.")],
            ),
        ],
        glossary=[Definition(term="spectrum", definition="set of eigenvalues")],
        open_questions=["Complex eigenvalues?"],
        assets=[
            MediaAsset(id="fig-1", media_type="image/png", source="week01/fig-1.png", alt="stretch")
        ],
    )


def test_lecture_round_trips_through_json() -> None:
    lecture = build_lecture()
    dumped = lecture.model_dump_json()
    assert NoteLecture.model_validate_json(dumped) == lecture


def test_dumped_json_contains_all_nine_discriminators() -> None:
    dumped = build_lecture().model_dump_json()
    data = json.loads(dumped)
    seen = {node["type"] for topic in data["topics"] for node in topic["body"]}
    assert seen == ALL_TYPES


def test_week_round_trips_via_json_and_dict() -> None:
    week = NoteWeek(id="w01", course="MATH201", week_number=1, lectures=[build_lecture()])
    assert NoteWeek.model_validate_json(week.model_dump_json()) == week
    assert NoteWeek.model_validate(week.model_dump()) == week


def test_nested_bullets_survive_round_trip() -> None:
    lecture = build_lecture()
    back = NoteLecture.model_validate_json(lecture.model_dump_json())
    bullet_list = back.topics[0].body[1]
    assert isinstance(bullet_list, BulletList)
    assert bullet_list.items[0].children[0].children[0].text == "Leaf"


def test_round_trip_preserves_node_classes_not_just_equality() -> None:
    back = NoteLecture.model_validate_json(build_lecture().model_dump_json())
    classes = [type(node).__name__ for node in back.topics[0].body]
    assert classes == [
        "Prose",
        "BulletList",
        "Definition",
        "Equation",
        "CodeBlock",
        "Callout",
        "Figure",
        "Table",
        "Quote",
    ]
