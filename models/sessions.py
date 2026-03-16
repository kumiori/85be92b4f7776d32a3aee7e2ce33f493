from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SessionSpec:
    session_id: str
    session_name: str
    session_order: int
    session_title: str
    session_description: str
    session_visualisation: str = ""
    session_active: bool = True


SESSION_CATALOG: list[SessionSpec] = [
    SessionSpec(
        session_id="GLOBAL-SESSION",
        session_name="Global entry",
        session_order=0,
        session_title="Entry Signal",
        session_description="First collective signal before entering the lobby.",
        session_visualisation="globe_map",
        session_active=True,
    ),
    SessionSpec(
        session_id="SESSION-1",
        session_name="Listening",
        session_order=1,
        session_title="Listening to Glaciers",
        session_description="Observations, emotions, and interpretations of glaciers.",
        session_visualisation="emotion_cloud",
        session_active=True,
    ),
    SessionSpec(
        session_id="SESSION-2",
        session_name="Interpreting change",
        session_order=2,
        session_title="Interpreting Change",
        session_description="Conceptual framing of transitions and collective sense-making.",
        session_visualisation="metro_map",
        session_active=True,
    ),
]


def session_spec_by_id(session_id: str) -> SessionSpec | None:
    target = (session_id or "").strip().upper()
    for spec in SESSION_CATALOG:
        if spec.session_id.upper() == target:
            return spec
    return None
