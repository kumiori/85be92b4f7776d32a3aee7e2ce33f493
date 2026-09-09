from __future__ import annotations

from html import escape
from typing import Any, Callable, Sequence

import streamlit as st

from ui import stylable_container


PAPER_CSS = """
background: rgba(255,255,255,0.72);
border: 1px solid rgba(19,36,52,0.09);
border-radius: 22px;
padding: 30px 32px;
box-shadow: 0 12px 26px rgba(19,36,52,0.05);
height: 100%;
"""

INTERPRETATION_CSS = """
background: rgba(255,255,255,0.58);
border-left: 4px solid rgba(44,111,163,0.45);
border-radius: 18px;
padding: 30px 32px;
height: 100%;
"""


def apply_editorial_results_theme() -> None:
    st.markdown(
        """
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght,SOFT@9..144,300..700,0..100&family=Space+Grotesk:wght@400;500;700&display=swap');
:root { --portrait-ink:#132434; --portrait-muted:#607384; --portrait-accent:#2c6fa3; }
html, body, [data-testid="stAppViewContainer"] { background:radial-gradient(circle at top,rgba(255,255,255,.7),transparent 26%),linear-gradient(180deg,#eef5fb 0%,#dde9f2 100%); }
.block-container { max-width:1220px!important; padding-top:2.4rem!important; padding-bottom:5rem!important; }
[data-testid="stHeadingWithActionElements"] h1,[data-testid="stHeadingWithActionElements"] h2 { font-family:"Fraunces",serif!important; color:var(--portrait-ink)!important; letter-spacing:-.035em!important; }
p,li,[data-testid="stCaptionContainer"] { font-family:"Space Grotesk",sans-serif!important; }
.portrait-kicker { color:var(--portrait-accent); font:700 .72rem/1.2 "Space Grotesk",sans-serif; letter-spacing:.17em; text-transform:uppercase; margin-bottom:.7rem; }
.portrait-copy { color:var(--portrait-ink); font:400 1.08rem/1.68 "Space Grotesk",sans-serif; max-width:66ch; margin:0 0 1.15rem; }
.portrait-metric { border-top:1px solid rgba(19,36,52,.12); padding:.9rem 0; }
.portrait-metric strong { display:block; color:var(--portrait-ink); font:500 2.35rem/1 "Fraunces",serif; }
.portrait-metric span { color:var(--portrait-muted); font:500 .76rem/1.35 "Space Grotesk",sans-serif; text-transform:uppercase; letter-spacing:.08em; }
.portrait-bar-row { margin:.85rem 0 1.1rem; }
.portrait-bar-label { display:flex; justify-content:space-between; gap:1rem; color:var(--portrait-ink); font:500 .86rem/1.35 "Space Grotesk",sans-serif; }
.portrait-bar-track { background:rgba(44,111,163,.09); border-radius:999px; height:9px; margin-top:.42rem; overflow:hidden; }
.portrait-bar-fill { background:linear-gradient(90deg,#6f8ea4,#2c6fa3); border-radius:999px; height:100%; min-width:0; }
.portrait-meta { color:var(--portrait-muted); font:500 .76rem/1.4 "Space Grotesk",sans-serif; margin-top:1.35rem; }
.portrait-quote { border-top:1px solid rgba(19,36,52,.1); color:var(--portrait-ink); font:400 1rem/1.6 "Space Grotesk",sans-serif; padding:1rem 0; }
@media(max-width:700px){.block-container{padding-top:1.3rem!important}.portrait-copy{font-size:1rem}.portrait-metric strong{font-size:2rem}}
</style>
""",
        unsafe_allow_html=True,
    )


def render_metric(value: Any, label: str) -> None:
    st.markdown(
        f'<div class="portrait-metric"><strong>{escape(str(value))}</strong><span>{escape(label)}</span></div>',
        unsafe_allow_html=True,
    )


def render_prose(paragraphs: Sequence[str]) -> None:
    for paragraph in paragraphs:
        st.markdown(
            f'<p class="portrait-copy">{escape(str(paragraph))}</p>',
            unsafe_allow_html=True,
        )


def render_bars(counts: Sequence[tuple[str, int]], denominator: int) -> None:
    for label, count in counts:
        percentage = (100.0 * count / denominator) if denominator else 0.0
        st.markdown(
            '<div class="portrait-bar-row">'
            f'<div class="portrait-bar-label"><span>{escape(label)}</span><span>{count} · {percentage:.0f}%</span></div>'
            f'<div class="portrait-bar-track"><div class="portrait-bar-fill" style="width:{percentage:.2f}%"></div></div>'
            '</div>',
            unsafe_allow_html=True,
        )
    st.caption(f"Percentages among the {denominator} participant{'s' if denominator != 1 else ''} who answered this question.")


def render_excerpts(excerpts: Sequence[str], answered: int) -> None:
    st.markdown(f"**{answered} response{'s' if answered != 1 else ''}**")
    if not excerpts:
        st.caption("No responses yet.")
        return
    for excerpt in excerpts:
        st.markdown(
            f'<div class="portrait-quote">{escape(str(excerpt))}</div>',
            unsafe_allow_html=True,
        )


def render_two_column_section(
    *,
    key: str,
    interpretation: Callable[[], None],
    data: Callable[[], None],
    data_left: bool,
) -> None:
    left, right = st.columns([1, 1.18], vertical_alignment="top")
    text_column, data_column = (right, left) if data_left else (left, right)
    with text_column:
        with stylable_container(key=f"{key}-interpretation", css_styles=INTERPRETATION_CSS):
            interpretation()
    with data_column:
        with stylable_container(key=f"{key}-figure", css_styles=PAPER_CSS):
            data()
    st.markdown("<div style='height:3rem'></div>", unsafe_allow_html=True)
