from __future__ import annotations

import streamlit as st

from infra.event_logger import log_event
from ui import apply_theme, heading, set_page


def _inject_css() -> None:
    st.markdown(
        """
<style>
.unesco-opening-shell {
  display: grid;
  gap: 2.75rem;
}
.unesco-opening-hero {
  padding: 2.2rem 1.5rem;
  border-radius: 18px;
  border: 1px solid rgba(20, 30, 60, 0.08);
  background:
    radial-gradient(circle at top right, rgba(120, 180, 220, 0.18), transparent 35%),
    linear-gradient(135deg, #eef5fb 0%, #f8fbfd 55%, #f3f8f2 100%);
}
.unesco-opening-hero h2 {
  margin: 0 0 0.65rem 0;
  font-size: 2.1rem;
  line-height: 1.08;
  letter-spacing: -0.02em;
}
.unesco-opening-hero p {
  margin: 0;
  font-size: 1.06rem;
  line-height: 1.6;
  max-width: 48rem;
}
.unesco-opening-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 1rem;
}
.unesco-opening-card {
  padding: 1.15rem 1rem;
  margin: 1.15rem 1rem;
  border-radius: 14px;
  border: 1px solid rgba(20, 30, 60, 0.08);
  background: rgba(255, 255, 255, 0.88);
}
.unesco-opening-label {
  display: inline-block;
  margin-bottom: 0.55rem;
  font-size: 0.76rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #546075;
}
.unesco-opening-card p {
  margin: 0;
  line-height: 1.6;
}
.unesco-opening-note {
  padding: 1.25rem 1.1rem;
  border-left: 3px solid rgba(36, 74, 120, 0.35);
  border-radius: 10px;
  background: rgba(245, 248, 252, 0.95);
}
.unesco-opening-links {
  margin-top: 0.35rem;
}
</style>
""",
        unsafe_allow_html=True,
    )


def main() -> None:
    set_page()
    apply_theme()
    _inject_css()

    st.markdown("<div class='unesco-opening-shell'>", unsafe_allow_html=True)

    st.markdown(
        """
<section class="unesco-opening-hero">
  <h2>This is #not-a-report. <br />
  This is where a collective process remains active.</h2>
  <p>
    This event is being shaped as an opening towards collaboration, understanding, and action.
  </p>
</section>
""",
        unsafe_allow_html=True,
    )

    st.markdown(
        """
<section class="unesco-opening-grid">
  <article class="unesco-opening-card">
    <span class="unesco-opening-label">Memory</span>
    <p>
      Voices, gestures, questions, and
      the first signals already present in the room.
    </p>
  </article>
  <article class="unesco-opening-card">
    <span class="unesco-opening-label">Location</span>
    <p>
      UNESCO Headquarters, Room XI. A point of departure for
      something that continues.
    </p>
  </article>
  <article class="unesco-opening-card">
    <span class="unesco-opening-label">Moment</span>
    <p>
      A live trace assembled in the immediate aftermath of the event.
    </p>
  </article>
</section>
""",
        unsafe_allow_html=True,
    )

    st.markdown(
        """
<section class="unesco-opening-note">
  <p>
    This page is being populated over these days. If it looks like a skeleton now, come and check again in a few days.
  </p>
</section>
""",
        unsafe_allow_html=True,
    )

    c1, c2 = st.columns(2)
    st.markdown("<div class='unesco-opening-links'>", unsafe_allow_html=True)
    # with c1:
    #     st.page_link(
    #         "pages/08_Overview.py",
    #         label="See the collective overview",
    #         icon=":material/travel_explore:",
    #     )
    # with c2:
    #     st.page_link(
    #         "pages/12_Report.py",
    #         label="Open the current trace page",
    #         icon=":material/article:",
    #     )
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)

    log_event(
        module="iceicebaby.sessions",
        event_type="page_view",
        page="UNESCO-opening",
        player_id=str(st.session_state.get("player_page_id", "")),
        session_id=str(st.session_state.get("session_id", "")),
        device_id=str(st.session_state.get("anon_token", "")),
        status="ok",
    )


if __name__ == "__main__":
    main()
