from __future__ import annotations

from dataclasses import dataclass

import streamlit as st

from conference.events import DALAMBERTIENNES_SESSION_CODE, UN_WG2_SESSION_CODE


@dataclass(frozen=True)
class PublicRouteConfig:
    path: str
    campaign_slug: str
    default_event_slug: str
    default_session_code: str
    default_question_set_id: str
    welcome_title: str
    welcome_body: str
    welcome_context: str
    welcome_note: str


_PUBLIC_ROUTES = (
    PublicRouteConfig(
        path="climate",
        campaign_slug="climate_research_labs",
        default_event_slug="dalembertiennes",
        default_session_code=DALAMBERTIENNES_SESSION_CODE,
        default_question_set_id="dalembertiennes_v1",
        welcome_title="Climate, resources, research",
        welcome_body="Can the laboratory formulate a problem?",
        welcome_context=(
            "It is difficult to formulate an actionable problem without assuming too much from "
            "the start: what the problem is, who should act, what should change, and what should "
            "be preserved."
        ),
        welcome_note=(
            "Anonymous and editable. "
            "You are answering the D’Alembertiennes version of a broader climate, resources, and research reflection."
        ),
    ),
    PublicRouteConfig(
        path="un-wg2-icebreaker",
        campaign_slug="un-cryosphere-decade",
        default_event_slug="un_wg2_first_iteration",
        default_session_code=UN_WG2_SESSION_CODE,
        default_question_set_id="un_wg2_v1",
        welcome_title="Working Group 2 — First Iteration",
        welcome_body="Actionable Cryosphere Projections",
        welcome_context=(
            "The questionnaire is the interface through which coordination begins. "
            "This first WG2 route is designed to make the group visible to itself."
        ),
        welcome_note=(
            "Anonymous and editable. "
            "This pilot is the first coordination layer of WG2, starting with the core group before a wider rollout."
        ),
    ),
)

_PUBLIC_ROUTE_BY_PATH = {item.path: item for item in _PUBLIC_ROUTES}


def public_route_config(path: str = "") -> PublicRouteConfig | None:
    token = str(path or st.query_params.get("public_route", "") or "").strip().lower()
    if not token:
        return None
    return _PUBLIC_ROUTE_BY_PATH.get(token)


def public_query_params() -> dict[str, str]:
    out: dict[str, str] = {}
    for key in ("key", "public_route", "campaign"):
        value = str(st.query_params.get(key, "") or "").strip()
        if value:
            out[key] = value
    return out


def ensure_public_route_query(path: str) -> PublicRouteConfig | None:
    config = public_route_config(path)
    if not config:
        return None
    current_route = str(st.query_params.get("public_route", "") or "").strip()
    current_campaign = str(st.query_params.get("campaign", "") or "").strip()
    current_event = str(st.query_params.get("event", "") or "").strip()
    if (
        current_route == config.path
        and current_campaign == config.campaign_slug
        and current_event == config.default_event_slug
    ):
        return config
    next_params = public_query_params()
    next_params["public_route"] = config.path
    next_params["campaign"] = config.campaign_slug
    next_params["event"] = config.default_event_slug
    st.query_params.clear()
    st.query_params.update(next_params)
    return config
