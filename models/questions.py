from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Optional

QuestionType = Literal[
    "single",
    "multi",
    "text",
    "pre_signal",
    "choice",
    "tags",
    "keywords",
    "signal",
]
QuestionCategory = Literal["perception", "structure", "agency", "integration"]


@dataclass(frozen=True)
class Question:
    id: str
    session_id: str
    category: QuestionCategory
    context: str
    prompt: str
    qtype: QuestionType
    options: Optional[list[str]] = None
    max_select: Optional[int] = None
    short_description: str = ""
    depth: int = 1
    required: bool = False
    visible_before_lobby: bool = False
    show_text_field: bool = False
    placeholder: str = ""
    order: int = 0
    active: bool = True
    response_mode: Optional[str] = None
    response_structure: Optional[Any] = None
    is_collective_signal: bool = False

    @property
    def response_type(self) -> QuestionType:
        if self.response_mode:
            return self.response_mode  # type: ignore[return-value]
        if self.qtype == "single":
            return "choice"
        if self.qtype == "multi":
            return "tags"
        if self.qtype == "pre_signal":
            return "signal"
        return "text"

    @property
    def response_options(self) -> list[str]:
        return list(self.options or [])

    @property
    def question_id(self) -> str:
        return self.id

    @property
    def question_text(self) -> str:
        return self.prompt

    @property
    def question_order(self) -> int:
        return self.order

    @property
    def question_active(self) -> bool:
        return self.active

    @property
    def canonical_response_structure(self) -> Any:
        if self.response_structure is not None:
            return self.response_structure
        if self.qtype in {"single", "multi", "pre_signal"}:
            return list(self.options or [])
        if self.qtype == "text":
            return {"max_length": 200}
        return {}
