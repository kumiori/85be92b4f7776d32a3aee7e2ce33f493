from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, Iterable, List

import altair as alt
import pandas as pd
import streamlit as st

from infra.app_context import get_authenticator, get_notion_repo
from infra.app_state import (
    ensure_auth,
    ensure_session_context,
    ensure_session_state,
    remember_access,
    require_login,
)
from services.decade_map import (
    CONTRIBUTION_FIRMNESS,
    CONTRIBUTION_SCOPES,
    CONTRIBUTION_STATUSES,
    CONTRIBUTION_THEMES,
    CONTRIBUTION_TYPES,
    DECADE_CONTRIBUTION_TYPE,
    DECADE_DELETE_TYPE,
    DECADE_REACTION_TYPE,
    DECADE_REVISION_TYPE,
    build_delete_payload,
    REACTION_OPTIONS,
    TIME_GRANULARITIES,
    build_contribution_payload,
    build_reaction_payload,
    can_place_contributions,
    coordination_lens,
    filter_contributions,
    list_decade_contributions,
    my_contributions,
)
from ui import apply_theme, heading, microcopy, set_page, sidebar_debug_state


def _normalise_month(value: date) -> str:
    return value.replace(day=1).isoformat()


def _time_input_block(
    *,
    key_prefix: str,
    defaults: Dict[str, Any] | None = None,
) -> tuple[str, str, str]:
    defaults = defaults or {}
    granularity = st.selectbox(
        "Time precision",
        TIME_GRANULARITIES,
        index=TIME_GRANULARITIES.index(defaults.get("time_granularity", "Month")),
        key=f"{key_prefix}-granularity",
    )
    if granularity == "Month":
        start_default = defaults.get("month_start") or date.today().replace(day=1)
        end_default = defaults.get("month_end") or start_default
        col1, col2 = st.columns(2)
        with col1:
            start_value = st.date_input("Start month", value=start_default, key=f"{key_prefix}-month-start")
        with col2:
            end_value = st.date_input("End month (optional)", value=end_default, key=f"{key_prefix}-month-end")
        return granularity, _normalise_month(start_value), _normalise_month(end_value)

    if granularity == "Season":
        seasons = ["Winter", "Spring", "Summer", "Autumn"]
        start_year = st.number_input(
            "Start year",
            min_value=2024,
            max_value=2035,
            value=int(defaults.get("season_start_year", 2026)),
            step=1,
            key=f"{key_prefix}-season-start-year",
        )
        start_season = st.selectbox(
            "Start season",
            seasons,
            index=seasons.index(defaults.get("season_start_name", "Spring")),
            key=f"{key_prefix}-season-start-name",
        )
        end_year = st.number_input(
            "End year (optional)",
            min_value=2024,
            max_value=2035,
            value=int(defaults.get("season_end_year", start_year)),
            step=1,
            key=f"{key_prefix}-season-end-year",
        )
        end_season = st.selectbox(
            "End season",
            seasons,
            index=seasons.index(defaults.get("season_end_name", start_season)),
            key=f"{key_prefix}-season-end-name",
        )
        return granularity, f"{int(start_year)}-{start_season}", f"{int(end_year)}-{end_season}"

    start_year = st.number_input(
        "Start year",
        min_value=2024,
        max_value=2035,
        value=int(defaults.get("year_start", 2026)),
        step=1,
        key=f"{key_prefix}-year-start",
    )
    end_year = st.number_input(
        "End year (optional)",
        min_value=2024,
        max_value=2035,
        value=int(defaults.get("year_end", start_year)),
        step=1,
        key=f"{key_prefix}-year-end",
    )
    return granularity, str(int(start_year)), str(int(end_year))


def _time_defaults(row: Dict[str, Any]) -> Dict[str, Any]:
    granularity = str(row.get("time_granularity") or "Month")
    start_label = str(row.get("start_label") or "")
    end_label = str(row.get("end_label") or start_label)
    defaults: Dict[str, Any] = {"time_granularity": granularity}
    if granularity == "Month":
        try:
            defaults["month_start"] = datetime.strptime(start_label, "%Y-%m-%d").date()
            defaults["month_end"] = datetime.strptime(end_label, "%Y-%m-%d").date()
        except ValueError:
            defaults["month_start"] = date.today().replace(day=1)
            defaults["month_end"] = defaults["month_start"]
    elif granularity == "Season":
        start_parts = start_label.split("-")
        end_parts = end_label.split("-")
        defaults["season_start_year"] = int(start_parts[0]) if start_parts and start_parts[0].isdigit() else 2026
        defaults["season_end_year"] = int(end_parts[0]) if end_parts and end_parts[0].isdigit() else defaults["season_start_year"]
        defaults["season_start_name"] = start_parts[1].title() if len(start_parts) > 1 else "Spring"
        defaults["season_end_name"] = end_parts[1].title() if len(end_parts) > 1 else defaults["season_start_name"]
    else:
        defaults["year_start"] = int(start_label) if start_label.isdigit() else 2026
        defaults["year_end"] = int(end_label) if end_label.isdigit() else defaults["year_start"]
    return defaults


def _timeline_dataframe(rows: List[Dict[str, Any]]) -> pd.DataFrame:
    chart_rows = []
    for row in rows:
        start = str(row.get("timeline_start") or "")
        end = str(row.get("timeline_end") or start)
        if not start or not end:
            continue
        try:
            start_dt = datetime.fromisoformat(start)
            end_dt = datetime.fromisoformat(end)
        except ValueError:
            continue
        chart_rows.append(
            {
                "title": str(row.get("title") or "Untitled"),
                "owner": str(row.get("owner_label") or "Contributor"),
                "status": str(row.get("status") or "Unknown"),
                "firmness": str(row.get("firmness") or "Unknown"),
                "scope": str(row.get("scope") or "Unknown"),
                "start": start_dt,
                "end": end_dt,
                "themes": ", ".join(row.get("themes", [])),
            }
        )
    return pd.DataFrame(chart_rows)


def _render_timeline(rows: List[Dict[str, Any]], *, title: str, color_field: str) -> None:
    df = _timeline_dataframe(rows)
    if df.empty:
        st.caption(f"{title}: no placed contributions yet.")
        return
    chart = (
        alt.Chart(df)
        .mark_bar(size=18, cornerRadiusEnd=4)
        .encode(
            x=alt.X("start:T", title="Time"),
            x2="end:T",
            y=alt.Y("title:N", sort=alt.SortField("start"), title=None),
            color=alt.Color(f"{color_field}:N", title=color_field.title()),
            tooltip=[
                "title:N",
                "owner:N",
                "status:N",
                "firmness:N",
                "scope:N",
                "themes:N",
                alt.Tooltip("start:T", title="Start"),
                alt.Tooltip("end:T", title="End"),
            ],
        )
        .properties(title=title, height=max(240, min(680, 28 * len(df))))
    )
    st.altair_chart(chart, use_container_width=True)


def _render_counter_bar(title: str, counts: Dict[str, int]) -> None:
    if not counts:
        st.caption(f"{title}: no data yet.")
        return
    df = pd.DataFrame(
        [{"label": str(key), "value": int(value)} for key, value in counts.items()]
    ).sort_values("value", ascending=False)
    chart = (
        alt.Chart(df)
        .mark_bar()
        .encode(
            x=alt.X("value:Q", title="Count"),
            y=alt.Y("label:N", sort="-x", title=None),
            tooltip=["label:N", "value:Q"],
        )
        .properties(title=title, height=max(180, 32 * len(df)))
    )
    st.altair_chart(chart, use_container_width=True)


def _format_window(row: Dict[str, Any]) -> str:
    start_display = str(row.get("start_display") or "—")
    end_display = str(row.get("end_display") or "—")
    if start_display == end_display:
        return start_display
    return f"{start_display} → {end_display}"


def _submit_reaction(
    *,
    repo,
    session_id: str,
    player_id: str,
    player_name: str,
    contribution_id: str,
    reaction: str,
) -> None:
    repo.create_decision(
        session_id=session_id,
        player_id=player_id,
        decision_type=DECADE_REACTION_TYPE,
        payload=build_reaction_payload(
            contribution_id=contribution_id,
            reaction=reaction,
            player_id=player_id,
            player_label=player_name,
        ),
    )


def _render_reaction_row(
    *,
    repo,
    session_id: str,
    player_id: str,
    player_name: str,
    row: Dict[str, Any],
    key_prefix: str,
) -> None:
    counts = row.get("reaction_counts", {})
    st.caption(
        f"Signals: resonates {int(counts.get('resonates', 0))} · builds on {int(counts.get('builds on', 0))} · unclear {int(counts.get('unclear', 0))}"
    )
    cols = st.columns(len(REACTION_OPTIONS))
    for idx, reaction in enumerate(REACTION_OPTIONS):
        if cols[idx].button(
            reaction.title(),
            key=f"{key_prefix}-reaction-{row.get('contribution_id')}-{reaction}",
        ):
            _submit_reaction(
                repo=repo,
                session_id=session_id,
                player_id=player_id,
                player_name=player_name,
                contribution_id=str(row.get("contribution_id") or ""),
                reaction=reaction,
            )
            st.toast(f"Signal saved: {reaction}")
            st.rerun()


def _render_revision_form(
    *,
    repo,
    session_id: str,
    player_id: str,
    player_name: str,
    row: Dict[str, Any],
    key_prefix: str,
) -> None:
    widget_prefix = f"{key_prefix}-{row.get('contribution_id')}"
    with st.expander("Revise this contribution", expanded=False):
        defaults = _time_defaults(row)
        with st.form(f"{key_prefix}-revise-{row.get('contribution_id')}"):
            title = st.text_input("Title", value=str(row.get("title") or ""), key=f"{widget_prefix}-title")
            contribution_type = st.selectbox(
                "Type",
                CONTRIBUTION_TYPES,
                index=CONTRIBUTION_TYPES.index(str(row.get("type") or CONTRIBUTION_TYPES[0])),
                key=f"{widget_prefix}-type",
            )
            status = st.selectbox(
                "Status",
                CONTRIBUTION_STATUSES,
                index=CONTRIBUTION_STATUSES.index(str(row.get("status") or CONTRIBUTION_STATUSES[0])),
                key=f"{widget_prefix}-status",
            )
            scope = st.selectbox(
                "Scope",
                CONTRIBUTION_SCOPES,
                index=CONTRIBUTION_SCOPES.index(str(row.get("scope") or CONTRIBUTION_SCOPES[0])),
                key=f"{widget_prefix}-scope",
            )
            firmness = st.selectbox(
                "How firm is this?",
                CONTRIBUTION_FIRMNESS,
                index=CONTRIBUTION_FIRMNESS.index(str(row.get("firmness") or CONTRIBUTION_FIRMNESS[0])),
                key=f"{widget_prefix}-firmness",
            )
            granularity, start_label, end_label = _time_input_block(
                key_prefix=f"{widget_prefix}-revise",
                defaults=defaults,
            )
            themes = st.multiselect(
                "Themes",
                CONTRIBUTION_THEMES,
                default=[theme for theme in row.get("themes", []) if theme in CONTRIBUTION_THEMES],
                key=f"{widget_prefix}-themes",
            )
            description = st.text_area(
                "Description",
                value=str(row.get("description") or ""),
                height=120,
                key=f"{widget_prefix}-description",
            )
            revision_note = st.text_input(
                "Why are you revising this?",
                value="",
                key=f"{widget_prefix}-revision-note",
            )
            submitted = st.form_submit_button("Save revision")
        if submitted:
            repo.create_decision(
                session_id=session_id,
                player_id=player_id,
                decision_type=DECADE_REVISION_TYPE,
                payload=build_contribution_payload(
                    title=title,
                    contribution_type=contribution_type,
                    status=status,
                    scope=scope,
                    firmness=firmness,
                    time_granularity=granularity,
                    start_label=start_label,
                    end_label=end_label,
                    themes=themes,
                    description=description,
                    owner_id=player_id,
                    owner_label=player_name,
                    contribution_id=str(row.get("contribution_id") or ""),
                    revision_note=revision_note,
                ),
            )
            st.toast("Revision saved.")
            st.rerun()


def _render_delete_action(
    *,
    repo,
    session_id: str,
    player_id: str,
    player_name: str,
    row: Dict[str, Any],
    key_prefix: str,
) -> None:
    contribution_id = str(row.get("contribution_id") or "")
    delete_key = f"{key_prefix}-{contribution_id}-confirm-delete"
    if st.button("Delete", type="secondary", key=f"{delete_key}-button"):
        st.session_state[delete_key] = True
    if st.session_state.get(delete_key):
        st.warning("Delete this placed contribution from the decade map?")
        confirm_col, cancel_col = st.columns(2)
        if confirm_col.button("Confirm delete", type="primary", key=f"{delete_key}-confirm"):
            repo.create_decision(
                session_id=session_id,
                player_id=player_id,
                decision_type=DECADE_DELETE_TYPE,
                payload=build_delete_payload(
                    contribution_id=contribution_id,
                    owner_id=player_id,
                    owner_label=player_name,
                ),
            )
            st.session_state.pop(delete_key, None)
            st.toast("Contribution deleted.")
            st.rerun()
        if cancel_col.button("Cancel", key=f"{delete_key}-cancel"):
            st.session_state.pop(delete_key, None)
            st.rerun()


def _render_contribution_card(
    *,
    repo,
    session_id: str,
    player_id: str,
    player_name: str,
    row: Dict[str, Any],
    allow_revision: bool,
    allow_delete: bool,
    key_prefix: str,
) -> None:
    title = str(row.get("title") or "Untitled")
    owner = str(row.get("owner_label") or "Contributor")
    status = str(row.get("status") or "Unknown")
    firmness = str(row.get("firmness") or "Unknown")
    theme_label = ", ".join(row.get("themes", [])) or "No themes yet"
    with st.container(border=True):
        st.markdown(f"**{title}**")
        st.caption(f"{owner} · {_format_window(row)} · {status} · {firmness}")
        st.write(str(row.get("description") or ""))
        st.caption(f"Type: {row.get('type') or '—'} · Scope: {row.get('scope') or '—'} · Themes: {theme_label}")
        if str(row.get("revision_note") or "").strip():
            st.caption(f"Latest revision note: {row.get('revision_note')}")
        _render_reaction_row(
            repo=repo,
            session_id=session_id,
            player_id=player_id,
            player_name=player_name,
            row=row,
            key_prefix=key_prefix,
        )
        history = row.get("history") or []
        if history:
            with st.expander("Trace", expanded=False):
                for item in reversed(history):
                    created_at = str(item.get("created_at") or "—")
                    note = str(item.get("revision_note") or "").strip()
                    summary = f"{created_at} · {item.get('status') or '—'} · {item.get('firmness') or '—'}"
                    if note:
                        summary = f"{summary} · {note}"
                    st.caption(summary)
        if allow_revision:
            _render_revision_form(
                repo=repo,
                session_id=session_id,
                player_id=player_id,
                player_name=player_name,
                row=row,
                key_prefix=key_prefix,
            )
        if allow_delete:
            _render_delete_action(
                repo=repo,
                session_id=session_id,
                player_id=player_id,
                player_name=player_name,
                row=row,
                key_prefix=key_prefix,
            )


def _render_place_form(repo, session_id: str, player_id: str, player_name: str) -> None:
    st.markdown("**Place a contribution in the decade**")
    st.caption("This is not only for finished work. Place emerging intent, partial commitments, or work already underway.")
    with st.form("place-contribution"):
        title = st.text_input("Title")
        contribution_type = st.selectbox("Type", CONTRIBUTION_TYPES)
        status = st.selectbox("Status", CONTRIBUTION_STATUSES)
        scope = st.selectbox("Scope", CONTRIBUTION_SCOPES)
        firmness = st.selectbox("How firm is this?", CONTRIBUTION_FIRMNESS)
        granularity, start_label, end_label = _time_input_block(key_prefix="new")
        themes = st.multiselect("Themes", CONTRIBUTION_THEMES)
        description = st.text_area("Description", height=140)
        submitted = st.form_submit_button("Place contribution")
    if submitted:
        if not title.strip():
            st.error("Title is required.")
            return
        repo.create_decision(
            session_id=session_id,
            player_id=player_id,
            decision_type=DECADE_CONTRIBUTION_TYPE,
            payload=build_contribution_payload(
                title=title,
                contribution_type=contribution_type,
                status=status,
                scope=scope,
                firmness=firmness,
                time_granularity=granularity,
                start_label=start_label,
                end_label=end_label,
                themes=themes,
                description=description,
                owner_id=player_id,
                owner_label=player_name,
            ),
        )
        st.success("Contribution placed in the decade.")
        st.rerun()


def main() -> None:
    set_page()
    apply_theme()
    ensure_session_state()
    repo = get_notion_repo()
    authenticator = get_authenticator(repo)
    ensure_auth(authenticator, callback=remember_access, key="decade-map-login")
    ensure_session_context(repo)
    require_login()
    sidebar_debug_state()

    if st.session_state.get("authentication_status"):
        authenticator.logout(button_name="Logout", location="sidebar")

    session_id = st.session_state.get("session_id")
    player_id = str(st.session_state.get("player_page_id") or "")
    player_name = str(st.session_state.get("player_name") or "Contributor")
    player_role = str(st.session_state.get("player_role") or "")

    heading("Decade Coordination Map")
    microcopy("A surface where intentions become visible, interact, and evolve over time.")
    st.caption(
        "Place a contribution in the decade, see it in relation to others, and revise it as the collective field becomes legible."
    )

    if not repo or not session_id or not player_id:
        st.error("Missing repository, session, or player context.")
        return

    payload = list_decade_contributions(repo, session_id)
    contributions = payload.get("contributions", [])
    mine = my_contributions(contributions, player_id)
    lens = coordination_lens(contributions)
    can_place = can_place_contributions(player_role)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Placed contributions", str(len(contributions)))
    c2.metric("Your trajectory", str(len(mine)))
    c3.metric("Revisions", str(sum(int(row.get("revision_count", 0)) for row in contributions)))
    c4.metric("Signals", str(sum(payload.get("counts", {}).get("reaction", {}).values())))

    overview_tab, place_tab, my_tab, collective_tab = st.tabs(
        ["Overview", "Place", "My Trajectory", "Collective Map"]
    )

    with overview_tab:
        st.subheader("Coordination lens")
        for insight in lens:
            st.write(f"- {insight}")
        _render_timeline(contributions, title="Collective decade field", color_field="status")
        left, right = st.columns(2)
        with left:
            _render_counter_bar("Themes", payload.get("counts", {}).get("theme", {}))
        with right:
            _render_counter_bar("How firm is this?", payload.get("counts", {}).get("firmness", {}))

    with place_tab:
        if can_place:
            _render_place_form(repo, session_id, player_id, player_name)
        else:
            st.warning("Your account is authenticated but cannot yet place contributions because no contributor role is assigned.")

    with my_tab:
        st.subheader("My trajectory")
        st.caption("Personal placement first, then collective revision.")
        _render_timeline(mine, title="Your placed contributions", color_field="firmness")
        if not mine:
            st.caption("You have not placed a contribution yet.")
        for row in mine:
            _render_contribution_card(
                repo=repo,
                session_id=session_id,
                player_id=player_id,
                player_name=player_name,
                row=row,
                allow_revision=can_place,
                allow_delete=can_place,
                key_prefix="mine",
            )

    with collective_tab:
        st.subheader("Collective field")
        filter_col1, filter_col2, filter_col3 = st.columns(3)
        with filter_col1:
            selected_themes = st.multiselect("Themes", CONTRIBUTION_THEMES)
            selected_statuses = st.multiselect("Status", CONTRIBUTION_STATUSES)
        with filter_col2:
            selected_scopes = st.multiselect("Scope", CONTRIBUTION_SCOPES)
            selected_types = st.multiselect("Type", CONTRIBUTION_TYPES)
        with filter_col3:
            owners = sorted({str(row.get("owner_label") or "Contributor") for row in contributions})
            selected_owners = st.multiselect("Actor", owners)
        filtered = filter_contributions(
            contributions,
            themes=selected_themes,
            scopes=selected_scopes,
            statuses=selected_statuses,
            owners=selected_owners,
            types=selected_types,
        )
        _render_timeline(filtered, title="Filtered collective map", color_field="firmness")
        if not filtered:
            st.caption("No contributions match the current filters.")
        for row in filtered:
            _render_contribution_card(
                repo=repo,
                session_id=session_id,
                player_id=player_id,
                player_name=player_name,
                row=row,
                allow_revision=bool(can_place and str(row.get("owner_id") or "") == player_id),
                allow_delete=bool(can_place and str(row.get("owner_id") or "") == player_id),
                key_prefix="collective",
            )


if __name__ == "__main__":
    main()
