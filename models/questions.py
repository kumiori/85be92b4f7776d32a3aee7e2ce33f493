from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

QuestionType = Literal["single", "multi", "text", "pre_signal"]
QuestionCategory = Literal["perception", "structure", "agency", "integration"]


@dataclass(frozen=True)
class Question:
    id: str
    category: QuestionCategory
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
