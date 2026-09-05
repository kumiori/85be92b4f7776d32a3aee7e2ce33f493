from __future__ import annotations

import streamlit as st

from conference.ui import apply_conference_styles
from infra.event_logger import log_event
from ui import set_page


def _apply_page_styles() -> None:
    st.markdown(
        """
        <style>
        .wg2-info-kicker {
            margin: 0 0 .65rem 0;
            font-family: var(--type-font-serif);
            font-size: 1rem;
            font-weight: 600;
            color: var(--type-muted);
        }
        .wg2-info-title {
            max-width: 760px;
            margin: 0 0 1rem 0;
            font-family: var(--type-font-sans);
            font-size: clamp(3rem, 7vw, 5.2rem);
            line-height: 1;
            font-weight: 700;
            color: var(--type-ink);
            text-wrap: balance;
        }
        .wg2-info-lead {
            max-width: 720px;
            margin: 0 0 2.4rem 0;
            font-family: var(--type-font-sans);
            font-size: clamp(1.12rem, 1.8vw, 1.35rem);
            line-height: 1.55;
            color: var(--type-muted);
        }
        .wg2-info-section {
            margin: 2.8rem 0 1rem 0;
            padding-top: 1rem;
            border-top: 1px solid var(--type-border);
            font-family: var(--type-font-sans);
            font-size: clamp(1.55rem, 3vw, 2rem);
            line-height: 1.15;
            font-weight: 700;
            color: var(--type-ink);
        }
        .wg2-audience-card {
            min-height: 100%;
            padding: 1.2rem;
            border: 1px solid var(--type-border);
            border-radius: .5rem;
            background: rgba(255, 255, 255, .64);
        }
        .wg2-audience-label {
            margin-bottom: .45rem;
            font-family: var(--type-font-serif);
            font-size: .9rem;
            font-weight: 600;
            color: var(--type-muted);
            text-transform: uppercase;
        }
        .wg2-audience-title {
            margin-bottom: .45rem;
            font-family: var(--type-font-sans);
            font-size: 1.2rem;
            line-height: 1.25;
            font-weight: 700;
            color: var(--type-ink);
        }
        .wg2-audience-copy {
            font-family: var(--type-font-sans);
            font-size: 1rem;
            line-height: 1.55;
            color: var(--type-muted);
        }
        .wg2-module {
            margin: 1rem 0 1.5rem 0;
            padding: 1.25rem;
            border-left: 4px solid var(--type-accent);
            background: rgba(255, 255, 255, .58);
        }
        .wg2-module strong {
            color: var(--type-ink);
        }
        @media (max-width: 640px) {
            .wg2-info-title {
                font-size: clamp(2.8rem, 15vw, 4rem);
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    set_page()
    apply_conference_styles()
    _apply_page_styles()

    log_event(
        module="iceicebaby.un_wg2",
        event_type="wg2_info_viewed",
        page="un_wg2_info",
        metadata={
            "campaign_slug": "un-cryosphere-decade",
            "event_slug": "un_wg2_visibility",
            "session_code": "un_wg2_core_2026",
        },
    )

    st.markdown(
        '<div class="wg2-info-kicker">WG2 · Actionable Cryosphere Projections</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<h1 class="wg2-info-title">A shared view of the group.</h1>',
        unsafe_allow_html=True,
    )
    st.markdown(
        """
        <div class="wg2-info-lead">
        This space explains the current WG2 coordination work, makes its emerging
        collective picture visible, and gives participants a clear way to contribute.
        It is designed for people encountering WG2 from outside and for people already
        working inside it.
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="wg2-info-section">Two ways into the same picture</div>',
        unsafe_allow_html=True,
    )
    outside, inside = st.columns(2, gap="medium")
    with outside:
        st.markdown(
            """
            <div class="wg2-audience-card">
              <div class="wg2-audience-label">From outside WG2</div>
              <div class="wg2-audience-title">Understand the purpose and emerging signals.</div>
              <div class="wg2-audience-copy">
                See what the group is trying to make visible: expertise, regional
                perspectives, needs, decision interfaces, and places where coordination
                could create value.
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with inside:
        st.markdown(
            """
            <div class="wg2-audience-card">
              <div class="wg2-audience-label">From inside WG2</div>
              <div class="wg2-audience-title">Add your perspective and return to it later.</div>
              <div class="wg2-audience-copy">
                Contribute through the short visibility module, keep your personal access
                key, edit your answers, and see how individual signals form a collective map.
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown(
        '<div class="wg2-info-section">Current module</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        """
        <div class="wg2-module">
          <strong>Collective Visibility</strong><br>
          A first coordination layer for showing who is present, what people bring,
          what contexts matter, and where connection is needed. The current picture is
          an evolving participant signal, not a final WG2 assessment or official report.
        </div>
        """,
        unsafe_allow_html=True,
    )

    contribute, overview = st.columns(2)
    with contribute:
        if st.button(
            "Add your perspective",
            type="primary",
            use_container_width=True,
        ):
            st.switch_page("pages/25_UN_WG2_Icebreaker.py")
    with overview:
        if st.button(
            "View the collective picture",
            use_container_width=True,
        ):
            st.switch_page("pages/26_UN_WG2_Overview.py")

    st.caption(
        "Participant identities and credentials are not displayed on this public page."
    )


if __name__ == "__main__":
    main()
