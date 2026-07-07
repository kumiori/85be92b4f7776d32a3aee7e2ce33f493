from __future__ import annotations

import streamlit as st

from ui import set_page


def _css() -> None:
    st.markdown(
        """
<style>
:root {
  --tw-bg: #ded4d6;
  --tw-ink: #6f5055;
  --tw-ink-strong: #67484e;
  --tw-ink-soft: rgba(103, 72, 78, 0.72);
  --tw-white: #ffffff;
  --tw-rule: rgba(103, 72, 78, 0.58);
  --tw-card-rule: rgba(103, 72, 78, 0.10);
  --tw-navy: #000719;
  --tw-red: #ee2e27;
  --tw-yellow: #f9b826;
  --tw-grey: #d5dada;
}

html,
body,
[data-testid="stAppViewContainer"] {
  background: var(--tw-bg);
}

[data-testid="stHeader"] {
  background: transparent;
}

.block-container {
  max-width: 1284px !important;
  padding-top: 4.4rem !important;
  padding-bottom: 5rem !important;
}

.tw-page {
  color: var(--tw-ink);
  font-family: Arial, Helvetica, sans-serif;
}

.tw-masthead {
  text-align: center;
  margin: 0 auto;
}

.tw-logo {
  margin: 0;
  color: var(--tw-white) !important;
  font-family: Georgia, "Times New Roman", serif !important;
  font-size: clamp(5.4rem, 9vw, 7.45rem) !important;
  font-weight: 700 !important;
  line-height: 0.86 !important;
  letter-spacing: -0.055em !important;
}

.tw-tagline {
  margin: 1.1rem 0 2.7rem 0;
  color: var(--tw-ink) !important;
  font-family: Georgia, "Times New Roman", serif !important;
  font-size: 1.7rem !important;
  line-height: 1.2 !important;
}

.tw-rule {
  height: 1px;
  max-width: 1080px;
  margin: 0 auto;
  background: var(--tw-rule);
}

.tw-nav {
  display: flex;
  justify-content: center;
  gap: clamp(2rem, 4vw, 3.25rem);
  margin: 1.3rem 0 4.1rem 0;
  color: var(--tw-ink-strong);
  font-size: 0.86rem;
  font-weight: 800;
  letter-spacing: 0.075em;
  text-transform: uppercase;
}

.tw-feature {
  text-align: center;
  margin-bottom: 3rem;
}

.tw-feature-title {
  margin: 0;
  color: var(--tw-ink-strong) !important;
  font-family: Georgia, "Times New Roman", serif !important;
  font-size: clamp(3.4rem, 5.3vw, 4.1rem) !important;
  font-weight: 700 !important;
  line-height: 0.98 !important;
  letter-spacing: -0.055em !important;
}

.tw-feature-meta {
  margin: 1.25rem 0 0 0;
  color: var(--tw-ink-strong);
  font-size: 1.05rem;
  font-weight: 800;
  letter-spacing: 0.012em;
}

.tw-font-meta {
  margin: 0.75rem 0 0 0;
  color: var(--tw-ink-strong);
  font-family: Georgia, "Times New Roman", serif;
  font-size: 1rem;
  line-height: 1.2;
}

.tw-font-meta strong {
  font-family: Arial, Helvetica, sans-serif;
  font-size: 0.84rem;
  letter-spacing: 0.085em;
  text-transform: uppercase;
}

.tw-font-meta span {
  border-bottom: 1px solid currentColor;
}

.tw-card {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 386px;
  max-width: 1284px;
  min-height: 360px;
  margin: 0 auto;
  padding: 12px;
  background: var(--tw-white);
  box-shadow: 0 1px 0 rgba(103, 72, 78, 0.05);
}

.tw-poster {
  position: relative;
  min-height: 360px;
  overflow: hidden;
  background: var(--tw-grey);
}

.tw-red-block {
  position: absolute;
  inset: 45px 42px 28px 42px;
  background: var(--tw-red);
  clip-path: polygon(0 0, 100% 0, 100% 67%, 92% 56%, 77% 60%, 64% 80%, 50% 57%, 32% 78%, 16% 61%, 0 70%);
}

.tw-yellow-block {
  position: absolute;
  top: 45px;
  left: 42px;
  width: 278px;
  height: 238px;
  background: var(--tw-yellow);
  clip-path: polygon(0 0, 76% 0, 100% 53%, 47% 86%, 0 100%);
}

.tw-letter {
  position: absolute;
  color: var(--tw-navy);
  font-family: Arial Black, Arial, Helvetica, sans-serif;
  font-size: 15rem;
  font-weight: 900;
  line-height: 0.8;
  letter-spacing: -0.1em;
}

.tw-letter-o-left {
  left: 52px;
  bottom: -92px;
}

.tw-letter-i {
  left: 382px;
  bottom: -78px;
}

.tw-letter-o-right {
  right: 48px;
  bottom: -92px;
}

.tw-side {
  padding: 24px 28px;
  background: #fff;
  color: var(--tw-navy);
  font-family: Arial, Helvetica, sans-serif;
}

.tw-season {
  display: grid;
  grid-template-columns: 28px 1fr 50px;
  gap: 10px;
  align-items: start;
}

.tw-dot {
  width: 27px;
  height: 27px;
  margin-top: 5px;
  border-radius: 999px;
  background: var(--tw-navy);
}

.tw-season-title {
  margin: 0;
  color: var(--tw-navy) !important;
  font-family: Arial, Helvetica, sans-serif !important;
  font-size: clamp(2rem, 3.1vw, 2.5rem) !important;
  font-weight: 400 !important;
  line-height: 0.95 !important;
  letter-spacing: -0.08em !important;
}

.tw-season-copy {
  margin: 0.5rem 0 0 0;
  color: var(--tw-navy) !important;
  font-family: Arial, Helvetica, sans-serif !important;
  font-size: 1.75rem !important;
  font-weight: 400 !important;
  line-height: 0.92 !important;
  letter-spacing: -0.08em !important;
}

.tw-info {
  display: grid;
  place-items: center;
  width: 50px;
  height: 50px;
  border-radius: 999px;
  background: var(--tw-navy);
  color: #fff;
  font-size: 0.82rem;
  font-weight: 800;
}

@media (max-width: 900px) {
  .block-container {
    padding-top: 2.6rem !important;
  }

  .tw-nav {
    flex-wrap: wrap;
    row-gap: 0.85rem;
    margin-bottom: 3rem;
  }

  .tw-card {
    grid-template-columns: 1fr;
  }

  .tw-side {
    min-height: 220px;
  }
}

@media (max-width: 520px) {
  .tw-logo {
    font-size: clamp(4.2rem, 18vw, 5.4rem);
  }

  .tw-tagline {
    font-size: 1.35rem;
  }

  .tw-feature-title {
    font-size: clamp(2.65rem, 13vw, 3.4rem);
  }

  .tw-card {
    padding: 8px;
  }

  .tw-poster {
    min-height: 300px;
  }

  .tw-side {
    padding: 22px 18px;
  }

  .tw-season {
    grid-template-columns: 24px 1fr;
  }

  .tw-info {
    grid-column: 1 / -1;
  }
}
</style>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    set_page()
    _css()
    st.markdown(
        """
<main class="tw-page">
  <header class="tw-masthead">
    <h1 class="tw-logo">Typewolf</h1>
    <p class="tw-tagline">What’s Trending in Type</p>
  </header>

  <div class="tw-rule"></div>
  <nav class="tw-nav" aria-label="Typography reference sections">
    <span>Font Lists</span>
    <span>Lookbooks</span>
    <span>Checklist</span>
    <span>Free Fonts</span>
    <span>Learning Resources</span>
  </nav>

  <section class="tw-feature">
    <h2 class="tw-feature-title">Theatre Dijon Bourgogne</h2>
    <p class="tw-feature-meta">Site of the Day · August 4, 2019</p>
    <p class="tw-font-meta"><strong>Fonts</strong> — <span>Neue Haas Grotesk</span></p>
  </section>

  <section class="tw-card" aria-label="Editorial preview">
    <div class="tw-poster">
      <div class="tw-red-block"></div>
      <div class="tw-yellow-block"></div>
      <div class="tw-letter tw-letter-o-left">O</div>
      <div class="tw-letter tw-letter-i">I</div>
      <div class="tw-letter tw-letter-o-right">O</div>
    </div>
    <aside class="tw-side">
      <div class="tw-season">
        <div class="tw-dot"></div>
        <div>
          <h3 class="tw-season-title">Saison 19 | 20</h3>
          <p class="tw-season-copy">Voici un aperçu de la nouvelle saison 19—20. Plus d’infos et ouverture de la billetterie à la rentrée. Bonnes vacances !</p>
        </div>
        <div class="tw-info">info+</div>
      </div>
    </aside>
  </section>
</main>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
