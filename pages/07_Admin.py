from __future__ import annotations

import json
from io import StringIO
from typing import Any, Dict, List

import streamlit as st
import yaml

from infra.app_context import get_notion_repo
from infra.app_state import ensure_session_state, require_login
from ui import apply_theme, heading, microcopy, set_page


def _is_admin(role: str) -> bool:
    st.write(f"Current role: {role}")
    return role.lower() in {"admin", "owner", "moderator"}


def _load_statements(payload: str) -> List[Dict[str, Any]]:
    if not payload:
        return []
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        data = yaml.safe_load(payload)
    if isinstance(data, dict):
        return data.get("statements", []) or data.get("items", []) or []
    if isinstance(data, list):
        return data
    return []


def main() -> None:
    set_page()
    apply_theme()
    ensure_session_state()
    require_login()

    role = st.session_state.get("player_role", "Contributor")
    if not _is_admin(role):
        st.error("Admin access only.")
        return

    repo = get_notion_repo()
    session_id = st.session_state.get("session_id")

    heading("Admin Console")
    microcopy("Manage sessions, statements, and exports.")

    if not repo or not session_id:
        st.error("Missing session context.")
        return

    st.subheader("Statements import")
    upload = st.file_uploader("Upload JSON or YAML", type=["json", "yaml", "yml"])
    if upload:
        content = StringIO(upload.getvalue().decode("utf-8")).read()
        items = _load_statements(content)
        if st.button("Import statements", type="primary"):
            for idx, item in enumerate(items, start=1):
                text = item.get("text") or item.get("statement") or ""
                theme = item.get("theme")
                order = item.get("order") or idx
                if text:
                    repo.create_statement(
                        session_id=session_id,
                        text=text,
                        theme=theme,
                        order=order,
                        active=True,
                    )
            st.success("Statements imported.")

    st.subheader("Export approved questions")
    approved = repo.list_questions(session_id, status="approved")
    if approved:
        csv_lines = ["text,domain,approve_count,park_count,rewrite_count"]
        for q in approved:
            row = [
                q["text"].replace(",", " "),
                q["domain"],
                str(q.get("approve_count", 0)),
                str(q.get("park_count", 0)),
                str(q.get("rewrite_count", 0)),
            ]
            csv_lines.append(",".join(row))
        csv_payload = "\n".join(csv_lines)
        st.download_button(
            "Download CSV snapshot",
            data=csv_payload,
            file_name="questions_snapshot.csv",
            mime="text/csv",
        )
    else:
        st.caption("No approved questions yet.")


if __name__ == "__main__":
    main()
