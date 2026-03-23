from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Literal, Optional
import os

import json
import time

import streamlit as st

from config import settings

EVENT_DATE = "19 March 2026"
EVENT_TIME = "16:00-17:30 (CET)"
EVENT_ROOM = "Room XI, UNESCO Headquarters"
EVENT_ORGANISERS = " Leopold Bouzard, Véronique Dansereau, Jean-François Delhom, Bruno Doucey,  Andrés León Baldelli, Ignacio Palomo"
MARGINS = {
    "top": "2.875rem",
    "bottom": "0",
}
STICKY_CONTAINER_HTML = """
<style>
div[data-testid="stVerticalBlock"] div:has(div.fixed-header-{i}) {{
    position: sticky;
    {position}: {margin};
    background-color: white;
    z-index: 999;
}}
</style>
<div class='fixed-header-{i}'/>
""".strip()
_sticky_count = 0


def _initial_sidebar_state() -> str:
    if _is_production_runtime():
        return "collapsed"
    ui_cfg = st.secrets.get("ui", {})
    explicit = str(ui_cfg.get("sidebar_state", "")).strip().lower()
    if explicit in {"expanded", "collapsed", "auto"}:
        return explicit
    visible_raw = ui_cfg.get("sidebar_visible")
    if visible_raw is None:
        return "expanded"
    if isinstance(visible_raw, bool):
        return "expanded" if visible_raw else "collapsed"
    visible_txt = str(visible_raw).strip().lower()
    if visible_txt in {"1", "true", "yes", "on"}:
        return "expanded"
    if visible_txt in {"0", "false", "no", "off"}:
        return "collapsed"
    return "expanded"


def _is_production_runtime() -> bool:
    env_raw = (
        str(os.getenv("APP_ENV") or os.getenv("ENV") or os.getenv("ENVIRONMENT") or "")
        .strip()
        .lower()
    )
    if env_raw in {"prod", "production", "live"}:
        return True

    # Streamlit Community Cloud / hosted runtime heuristic.
    cwd = os.getcwd()
    home = str(os.getenv("HOME", ""))
    if cwd.startswith("/mount/src/") or home == "/home/adminuser":
        return True
    return False


def is_production_runtime() -> bool:
    return _is_production_runtime()


def _apply_production_shell_css() -> None:
    st.markdown(
        """
<style>
div[data-testid="stSidebarNav"] { display: none !important; }
[data-testid="collapsedControl"] { display: none !important; }
[data-testid="stHeader"] { display: none !important; }
</style>
""",
        unsafe_allow_html=True,
    )


def set_page() -> None:
    st.set_page_config(
        page_title=settings.app_title,
        page_icon="🪶",
        layout="centered",
        initial_sidebar_state=_initial_sidebar_state(),
    )
    if _is_production_runtime():
        _apply_production_shell_css()


def apply_theme() -> None:
    css_path = Path("assets/styles.css")
    if css_path.exists():
        css = css_path.read_text(encoding="utf-8")
        # accent_override = f":root {{ --accent: {settings.accent_color}; }}"
        # st.markdown(f"<style>{css}{accent_override}</style>", unsafe_allow_html=True)


def heading(text: str) -> None:
    st.markdown(f"<h1 class='heading'>{text}</h1>", unsafe_allow_html=True)


def microcopy(text: str) -> None:
    st.markdown(f"<p class='microcopy'>{text}</p>", unsafe_allow_html=True)


def render_event_details() -> None:
    st.markdown(
        f"""
Date: {EVENT_DATE} {EVENT_ROOM}    
Panel (alphabetical): {EVENT_ORGANISERS}.
"""
    )


def apply_auth_input_form_styles(
    main_font_rem: float = 3.0, input_height_em: float | None = None
) -> None:
    if input_height_em is None:
        main_min_height = f"calc({main_font_rem}rem * 1.8)"
    else:
        main_min_height = f"{input_height_em}em"
    st.markdown(
        f"""
<style>
section.main [data-testid="stTextInput"] input {{
  font-size: {main_font_rem}rem !important;
  line-height: 1.15 !important;
  min-height: {main_min_height} !important;
  padding-top: 0.45rem !important;
  padding-bottom: 0.45rem !important;
}}
section.main [data-testid="stTextInput"] label p {{
  font-size: 1.05rem !important;
}}
div[data-testid="stSidebar"] [data-testid="stTextInput"] input {{
  font-size: 1rem !important;
  line-height: 1.3 !important;
  min-height: 2.4rem !important;
}}
div[data-testid="stSidebar"] [data-testid="stTextInput"] label p {{
  font-size: 0.95rem !important;
}}
</style>
""",
        unsafe_allow_html=True,
    )


def sticky_container(
    *,
    height: int | None = None,
    border: bool | None = None,
    mode: Literal["top", "bottom"] = "top",
    margin: str | None = None,
):
    global _sticky_count
    if margin is None:
        margin = MARGINS[mode]
    html_code = STICKY_CONTAINER_HTML.format(
        position=mode,
        margin=margin,
        i=_sticky_count,
    )
    _sticky_count += 1

    if height is None:
        container = st.container(border=border)
    else:
        container = st.container(height=height, border=border)
    container.markdown(html_code, unsafe_allow_html=True)
    return container


def primary_button(
    label: str, key: Optional[str] = None, disabled: bool = False
) -> bool:
    return st.button(label, key=key, type="primary", disabled=disabled, width="stretch")


def small_button(label: str, key: Optional[str] = None, disabled: bool = False) -> bool:
    return st.button(label, key=key, disabled=disabled, width="stretch")


def card_block(
    image_url: Optional[str], concept_line: Optional[str], symbol: Optional[str]
) -> None:
    with st.container():
        if image_url:
            st.image(image_url, caption=None)
        if symbol:
            microcopy(symbol)
        if concept_line:
            st.markdown(
                f"<p class='concept'>{concept_line}</p>", unsafe_allow_html=True
            )


@contextmanager
def fade_container():
    container = st.container()
    container.markdown("<div class='fade-in app-shell'>", unsafe_allow_html=True)
    with container:
        yield
    container.markdown("</div>", unsafe_allow_html=True)


def viz_block(
    kind: Literal["cube", "sphere"], size_px: int = 220, opacity: float = 0.22
) -> None:
    """Embed a lightweight canvas viz."""
    canvas_id = f"viz-{kind}"
    html = f"""
    <style>
    .viz-wrap {{
      width: {size_px}px;
      height: {size_px}px;
      margin: 0 auto;
      opacity: {opacity};
      filter: saturate(0.9);
    }}
    .viz-wrap canvas {{
      width: 100%;
      height: 100%;
      display: block;
    }}
    </style>
    <div class="viz-wrap">
      <canvas id="{canvas_id}" aria-label="{kind} signal"></canvas>
    </div>
    <script>
    class WavyBase {{
      constructor(sel, isSphere) {{
        this.canvas = document.getElementById(sel);
        this.ctx = this.canvas?.getContext("2d");
        this.isSphere = isSphere;
        this.size = isSphere ? 260 : 220;
        this.radius = 140;
        this.edgeFadeWidth = 14;
        this.lineCount = 14;
        this.lineSpacing = 28;
        this.lineWidth = 1.5;
        this.maxAmplitude = 18;
        this.rotationSpeed = 0.02;
        this.waveFrequency = 0.55;
        this.width = 0;
        this.height = 0;
        this.rotX = 0.4;
        this.rotY = 0.4;
        this.time = 0;
      }}
      get lineColor() {{ return "hsl(0, 0%, 0%)"; }}
      init() {{
        this.resize();
        this.draw();
        window.addEventListener("resize", this.resize.bind(this));
      }}
      applyMatrix(v, m) {{
        return [
          v[0] * m[0] + v[1] * m[1] + v[2] * m[2],
          v[0] * m[3] + v[1] * m[4] + v[2] * m[5],
          v[0] * m[6] + v[1] * m[7] + v[2] * m[8]
        ];
      }}
      dot(a, b) {{ return a[0]*b[0] + a[1]*b[1] + a[2]*b[2]; }}
      clamp(x,a,b) {{ return Math.max(a, Math.min(b, x)); }}
      lightDirOrbit(ts) {{
        const w = 0.35;
        const w2 = 0.17;
        const az = ts * w;
        const el = 0.35 + 0.22 * Math.sin(ts * w2);
        return this.normalize([
          Math.cos(el) * Math.cos(az),
          Math.sin(el),
          Math.cos(el) * Math.sin(az)
        ]);
      }}
      normalize(v) {{
        const len = Math.hypot(v[0], v[1], v[2]) || 1;
        return [v[0]/len, v[1]/len, v[2]/len];
      }}
      draw() {{
        if (!this.ctx) return;
        this.ctx.clearRect(0, 0, this.width, this.height);
        this.ctx.strokeStyle = this.lineColor;
        this.ctx.lineWidth = this.lineWidth;
        this.ctx.lineCap = "round";
        this.rotX = (this.rotX + this.rotationSpeed) % (2*Math.PI);
        this.rotY = (this.rotY + this.rotationSpeed) % (2*Math.PI);
        this.time += 0.09;
        const rotMat = this.getRotationMatrix(this.rotX, this.rotY);
        const invRot = this.transpose(rotMat);
        const totalH = (this.lineCount - 1) * this.lineSpacing;
        const startY = (this.height/2) - (totalH/2);
        const r = this.isSphere ? this.radius : this.size/2;
        const L1 = this.lightDirOrbit(this.time);
        const L2 = this.normalize([-L1[0], 0.25, -L1[2]]);
        for (let i=0; i<this.lineCount; i++) {{
          const screenY = startY + i*this.lineSpacing;
          this.ctx.beginPath();
          for (let x=0; x<this.width; x++) {{
            const cx = x - this.width/2;
            const cy = screenY - this.height/2;
            const rayOrigin = [cx, cy, 400];
            const rayDir = [0,0,-1];
            const localOrigin = this.applyMatrix(rayOrigin, invRot);
            const localDir = this.applyMatrix(rayDir, invRot);
            let yOffset = 0;
            if (this.isSphere) {{
              const hit = this.intersectSphere(localOrigin, localDir, r);
              if (hit) {{
                const hp = [
                  localOrigin[0] + localDir[0] * hit.t,
                  localOrigin[1] + localDir[1] * hit.t,
                  localOrigin[2] + localDir[2] * hit.t
                ];
                const normLen = Math.hypot(hp[0], hp[1], hp[2]) || 1;
                const normal = [hp[0]/normLen, hp[1]/normLen, hp[2]/normLen];
                const diff1 = this.clamp(this.dot(normal, L1), 0, 1);
                const diff2 = this.clamp(this.dot(normal, L2), 0, 1) * 0.25;
                const diff = this.clamp(diff1 + diff2, 0, 1);
                const facing = Math.max(0, this.dot(normal, [0,0,1])) ** 0.4;
                let amp = (0.5 - diff * 0.4) + 0.08;
                amp = this.clamp(amp, 0, 1);
                const wave = Math.sin((x * this.waveFrequency) + this.time);
                yOffset = wave * this.maxAmplitude * amp * facing;
              }}
            }} else {{
              const hit = this.intersectBox(localOrigin, localDir, r);
              if (hit) {{
                const hp = [
                  localOrigin[0] + localDir[0] * hit.t,
                  localOrigin[1] + localDir[1] * hit.t,
                  localOrigin[2] + localDir[2] * hit.t
                ];
                const distances = [r - Math.abs(hp[0]), r - Math.abs(hp[1]), r - Math.abs(hp[2])];
                distances.sort((a,b)=>a-b);
                let edgeFactor = distances[1] / this.edgeFadeWidth;
                edgeFactor = Math.max(0, Math.min(1, edgeFactor));
                edgeFactor = edgeFactor * (2 - edgeFactor);
                const sceneNormal = this.applyMatrix(hit.normal, rotMat);
                const diff1 = this.clamp(this.dot(sceneNormal, L1), 0, 1);
                const diff2 = this.clamp(this.dot(sceneNormal, L2), 0, 1) * 0.25;
                const diff = this.clamp(diff1 + diff2, 0, 1);
                let amp = (0.5 - diff * 0.4) + 0.1;
                amp = this.clamp(amp, 0, 1);
                const wave = Math.sin((x * this.waveFrequency) + this.time);
                yOffset = wave * this.maxAmplitude * amp * edgeFactor;
              }}
            }}
            if (x===0) this.ctx.moveTo(x, screenY + yOffset);
            else this.ctx.lineTo(x, screenY + yOffset);
          }}
          this.ctx.stroke();
        }}
        requestAnimationFrame(this.draw.bind(this));
      }}
      getRotationMatrix(rx, ry) {{
        const cx = Math.cos(rx), sx = Math.sin(rx), cy = Math.cos(ry), sy = Math.sin(ry);
        return [cy, sx*sy, cx*sy, 0, cx, -sx, -sy, sx*cy, cx*cy];
      }}
      intersectBox(origin, dir, size) {{
        const tMin={{t:-Infinity, normal:[0,0,0]}}, tMax={{t:Infinity}};
        if(!this.intersectSlab(origin[0], dir[0], size, 0, tMin, tMax)) return null;
        if(!this.intersectSlab(origin[1], dir[1], size, 1, tMin, tMax)) return null;
        if(!this.intersectSlab(origin[2], dir[2], size, 2, tMin, tMax)) return null;
        if (tMin.t < 0 || tMin.t > tMax.t) return null;
        return {{t: tMin.t, normal: tMin.normal}};
      }}
      intersectSlab(originAxis, dirAxis, size, axisIndex, tMin, tMax) {{
        if (Math.abs(dirAxis) < 1e-5) {{
          if (Math.abs(originAxis) > size) return false;
        }} else {{
          const inv = 1/dirAxis;
          let t1 = (-size - originAxis) * inv;
          let t2 = (size - originAxis) * inv;
          let n1=[0,0,0], n2=[0,0,0];
          n1[axisIndex] = -1; n2[axisIndex] = 1;
          if (t1 > t2) {{ [t1,t2]=[t2,t1]; n1=n2; }}
          if (t1 > tMin.t) {{ tMin.t = t1; tMin.normal = n1; }}
          if (t2 < tMax.t) {{ tMax.t = t2; }}
        }}
        return tMin.t <= tMax.t;
      }}
      intersectSphere(origin, dir, radius) {{
        const a = this.dot(dir, dir);
        const b = 2 * this.dot(origin, dir);
        const c = this.dot(origin, origin) - radius*radius;
        const disc = b*b - 4*a*c;
        if (disc < 0) return null;
        const t = (-b - Math.sqrt(disc)) / (2*a);
        if (t < 0) return null;
        return {{ t, normal: [origin[0]+dir[0]*t, origin[1]+dir[1]*t, origin[2]+dir[2]*t] }};
      }}
      resize() {{
        if (!this.canvas || !this.ctx) return;
        const ratio = window.devicePixelRatio || 1;
        this.width = {size_px};
        this.height = {size_px};
        this.canvas.width = this.width * ratio;
        this.canvas.height = this.height * ratio;
        this.canvas.style.width = this.width + "px";
        this.canvas.style.height = this.height + "px";
        this.ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
      }}
      transpose(m) {{ return [m[0],m[3],m[6], m[1],m[4],m[7], m[2],m[5],m[8]]; }}
    }}
    function start() {{
      const viz = new WavyBase("{canvas_id}", {str(kind == "sphere").lower()});
      viz.init();
    }}
    function boot() {{
      const canvas = document.getElementById("{canvas_id}");
      if (!canvas) return;
      start();
    }}
    if (document.readyState === "complete" || document.readyState === "interactive") {{
      setTimeout(boot, 0);
    }} else {{
      window.addEventListener("DOMContentLoaded", boot);
    }}
    </script>
    """


def sidebar_debug_state() -> None:
    from infra.app_context import reset_notion_repo_cache

    if not settings.show_debug:
        return
    with st.sidebar.expander("Debug · Session state", expanded=False):
        st.json({key: str(val) for key, val in st.session_state.items()})
        if st.button("Reset Notion cache"):
            reset_notion_repo_cache()
            st.toast("Notion cache cleared. Reload the page.")
    # st.components.v1.html(html, height=size_px + 20, scrolling=False)


def _now_hhmmss() -> str:
    return datetime.now().strftime("%H:%M:%S")


def update_sidebar_task(task: str, *, done: bool = False) -> None:
    title = str(task or "").strip() or "Idle"
    st.session_state["sidebar_current_task"] = title
    if done:
        st.session_state["sidebar_last_task"] = title
        st.session_state["sidebar_last_task_at"] = _now_hhmmss()


def push_sidebar_timing(label: str, elapsed_ms: float) -> None:
    try:
        ms = float(elapsed_ms)
    except Exception:
        return
    timings = st.session_state.get("sidebar_timings")
    if not isinstance(timings, list):
        timings = []
    timings.append(
        {
            "label": str(label or "task"),
            "ms": round(ms, 1),
            "at": _now_hhmmss(),
        }
    )
    # Keep the latest 12 timings only.
    st.session_state["sidebar_timings"] = timings[-12:]


def begin_sidebar_timing(label: str) -> float:
    st.session_state["sidebar_current_timing_label"] = str(label or "task")
    return time.perf_counter()


def end_sidebar_timing(started_at: float, label: str | None = None) -> None:
    elapsed_ms = (time.perf_counter() - float(started_at)) * 1000.0
    push_sidebar_timing(label or st.session_state.get("sidebar_current_timing_label") or "task", elapsed_ms)


def _short_access_key_label(access_key: str) -> str:
    key = str(access_key or "").strip()
    if not key:
        return "—"
    try:
        from infra.key_codec import hex_to_emoji, split_emoji_symbols

        emoji = hex_to_emoji(key)
        symbols = split_emoji_symbols(emoji)
        if len(symbols) >= 4:
            return "".join(symbols[-4:])
        return emoji
    except Exception:
        return key[-8:] if len(key) > 8 else key


def render_orientation_sidebar(
    *,
    session_name: str = "",
    session_description: str = (
        "This session explores how individual signals form collective decisions."
    ),
    question_index: int | None = None,
    question_total: int | None = None,
    responses_submitted: int | None = None,
    sessions_participated: int | None = None,
) -> None:
    with st.sidebar:
        st.markdown("#### Session")
        st.caption(session_name or "GLOBAL SESSION")
        if session_description:
            st.caption(session_description)
        if question_index is not None and question_total:
            st.caption(f"Question {question_index} / {question_total}")

        st.divider()
        st.markdown("#### You")
        st.caption(f"Key: {_short_access_key_label(st.session_state.get('player_access_key', ''))}")
        st.caption(f"Name: {st.session_state.get('player_name') or '—'}")
        if responses_submitted is None:
            responses_submitted = int(
                st.session_state.get("sidebar_responses_submitted", 0) or 0
            )
        if sessions_participated is None:
            sessions_participated = int(
                st.session_state.get("sidebar_sessions_participated", 1) or 1
            )
        st.caption(f"Responses: {responses_submitted}")
        st.caption(f"Sessions: {sessions_participated}")

        st.divider()
        st.markdown("#### System")
        st.caption("Your responses are anonymous and linked only to your key.")
        st.caption("You can return later to continue your trajectory.")
        status = "connected" if st.session_state.get("authentication_status") else "offline"
        st.caption(f"Status: {status}")
        st.caption(f"Last activity: {st.session_state.get('sidebar_last_task_at') or '—'}")

        current_task = str(st.session_state.get("sidebar_current_task") or "Idle")
        with st.expander(f"Task · {current_task}", expanded=False):
            st.caption(f"Current: {current_task}")
            st.caption(f"Last: {st.session_state.get('sidebar_last_task') or '—'}")
            st.caption(f"Last at: {st.session_state.get('sidebar_last_task_at') or '—'}")
            timings = st.session_state.get("sidebar_timings")
            if isinstance(timings, list) and timings:
                st.caption("Timings (latest)")
                for row in reversed(timings[-6:]):
                    st.caption(
                        f"{row.get('label', 'task')}: {row.get('ms', '—')} ms ({row.get('at', '—')})"
                    )


def morph3_defaults() -> dict:
    return {
        "canvas_width": 900,
        "canvas_height": 520,
        "bg_alpha": 0.06,
        "bg_gap": 46,
        "bg_wave_amp": 0.0,
        "bg_wave_freq": 0.0,
        "bg_wave_time": 0.0,
        "bg_x_step": 6,
        "flow_u": 1.0,
        "flow_radius": 1.05,
        "flow_x_span": 2.6,
        "flow_iter": 6,
        "line_gap": 7,
        "x_step": 5,
        "wave_freq": 0.020,
        "wave_base": 2.0,
        "wave_shadow": 10.0,
        "wave_noise_factor": 0.35,
        "wave_time_freq": 1.2,
        "morph_p_max": 40.0,
        "morph_power": 2.2,
        "noise_amp": 0.08,
        "noise_freq": 3.0,
        "noise_crawl": 0.07,
        "normal_epsilon": 0.003,
        "ray_steps": 80,
        "hit_eps": 0.001,
        "max_dist": 6.0,
        "march_relax": 0.8,
        "cam_dist": 3.0,
        "cam_elev_deg": 20.0,
        "fov": 1.0,
        "auto_rotate_speed": 0.4,
        "light_radius": 3.2,
        "light_az_speed": 0.8,
        "light_el_amp": 0.55,
        "light_el_speed": 0.23,
        "fill_weight": 0.18,
        "fill_y_bias": 0.25,
        "diff_boost": 0.65,
        "atten_k": 0.15,
        "spec_power": 56.0,
        "spec_scale": 0.35,
        "spec_noise_boost": 0.25,
        "alpha_base": 0.08,
        "alpha_shade": 0.80,
        "width_base": 0.9,
        "width_shadow": 3.0,
        "width_spec": 1.2,
        "enable_light_orbit": True,
        "enable_rim": True,
        "quant_levels": 4,
    }


def morph3_block(
    params: Optional[dict] = None,
    t: float = 1.0,
    noise: float = 2.0,
    auto_rotate: bool = True,
    azimuth: float = 25.0,
    height_pad: int = 0,
) -> None:
    """Embed the morph3 flow-line visualization used in test_splash."""
    params = params or morph3_defaults()
    params_json = json.dumps(params)
    html = f"""
<style>
  .morph-wrap {{
    width: 100%;
    display: grid;
    place-items: center;
    padding: 18px;
    border-radius: 16px;
  }}
  canvas {{
    width: 100%;
    height: auto;
    max-width: 100%;
    aspect-ratio: {params["canvas_width"]} / {params["canvas_height"]};
    display: block;
  }}
</style>
  <div class="morph-wrap">
    <canvas id="morph3-canvas" width="{params["canvas_width"]}" height="{params["canvas_height"]}"></canvas>
  </div>
<script>
(() => {{
  const canvas = document.getElementById("morph3-canvas");
  const ctx = canvas.getContext("2d");
  const W = canvas.width;
  const H = canvas.height;
  const t = {t};
  const noiseLevel = {noise};
  const autoRotate = {str(auto_rotate).lower()};
  let azim = {azimuth};
  const P = {params_json};
  const p = 2 + Math.pow(1 - t, P.morph_power) * (P.morph_p_max - 2);
  let time = performance.now() / 1000;

  function clamp(x, a, b) {{ return Math.max(a, Math.min(b, x)); }}
  function normalize(v) {{ const len = Math.hypot(v[0], v[1], v[2]) || 1; return [v[0]/len, v[1]/len, v[2]/len]; }}
  function dot(a,b) {{ return a[0]*b[0] + a[1]*b[1] + a[2]*b[2]; }}
  function mulAdd(o, d, tv) {{ return [o[0]+d[0]*tv, o[1]+d[1]*tv, o[2]+d[2]*tv]; }}
  function sub(a,b) {{ return [a[0]-b[0], a[1]-b[1], a[2]-b[2]]; }}
  function cross(a,b) {{ return [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]]; }}
  function length(v) {{ return Math.hypot(v[0], v[1], v[2]); }}
  function lengthP(v, pp) {{ return Math.pow(Math.pow(Math.abs(v[0]), pp) + Math.pow(Math.abs(v[1]), pp) + Math.pow(Math.abs(v[2]), pp), 1/pp); }}
  function fract(x) {{ return x - Math.floor(x); }}
  function hash3(x,y,z) {{ return fract(Math.sin(x*127.1 + y*311.7 + z*74.7) * 43758.5453123); }}
  function smoothstep(tv) {{ return tv*tv*(3-2*tv); }}
  function noise3(pnt) {{
    const x=pnt[0], y=pnt[1], z=pnt[2];
    const ix=Math.floor(x), iy=Math.floor(y), iz=Math.floor(z);
    const fx=x-ix, fy=y-iy, fz=z-iz;
    const ux=smoothstep(fx), uy=smoothstep(fy), uz=smoothstep(fz);
    function h(dx,dy,dz) {{ return hash3(ix+dx, iy+dy, iz+dz); }}
    const c000=h(0,0,0), c100=h(1,0,0), c010=h(0,1,0), c110=h(1,1,0);
    const c001=h(0,0,1), c101=h(1,0,1), c011=h(0,1,1), c111=h(1,1,1);
    const x00=c000*(1-ux)+c100*ux, x10=c010*(1-ux)+c110*ux;
    const x01=c001*(1-ux)+c101*ux, x11=c011*(1-ux)+c111*ux;
    const y0=x00*(1-uy)+x10*uy, y1=x01*(1-uy)+x11*uy;
    return (y0*(1-uz)+y1*uz)*2.0-1.0;
  }}
  function sdfSphere(pnt) {{ return Math.hypot(pnt[0], pnt[1], pnt[2]) - 1.0; }}
  function sdfBox(pnt, b) {{
    const qx = Math.abs(pnt[0]) - b[0];
    const qy = Math.abs(pnt[1]) - b[1];
    const qz = Math.abs(pnt[2]) - b[2];
    const ox = Math.max(qx, 0), oy = Math.max(qy, 0), oz = Math.max(qz, 0);
    const outside = Math.hypot(ox, oy, oz);
    const inside = Math.min(Math.max(qx, Math.max(qy, qz)), 0);
    return outside + inside;
  }}
  function lerp(a,b,tv){{ return a + (b-a)*tv; }}
  function mixSdf(d1, d2, tv){{ return lerp(d1, d2, tv); }}
  function sdfBase(pos) {{
    const dBox = sdfBox(pos, [1.0, 1.0, 1.0]);
    const dSph = sdfSphere(pos);
    return mixSdf(dBox, dSph, t);
  }}
  function sdf(pos) {{
    const base = sdfBase(pos);
    const amp = P.noise_amp * noiseLevel;
    const freq = P.noise_freq;
    const n = noise3([pos[0]*freq + time*P.noise_crawl, pos[1]*freq, pos[2]*freq]);
    return base + amp * n;
  }}
  function normalAt(pos) {{
    const e = P.normal_epsilon;
    const dx = sdf([pos[0]+e, pos[1], pos[2]]) - sdf([pos[0]-e, pos[1], pos[2]]);
    const dy = sdf([pos[0], pos[1]+e, pos[2]]) - sdf([pos[0], pos[1]-e, pos[2]]);
    const dz = sdf([pos[0], pos[1], pos[2]+e]) - sdf([pos[0], pos[1], pos[2]-e]);
    return normalize([dx, dy, dz]);
  }}
  function axisFaceNormal(pos) {{
    const ax = Math.abs(pos[0]), ay = Math.abs(pos[1]), az = Math.abs(pos[2]);
    if (ax > ay && ax > az) return [Math.sign(pos[0]), 0, 0];
    if (ay > ax && ay > az) return [0, Math.sign(pos[1]), 0];
    return [0, 0, Math.sign(pos[2])];
  }}
  function quantize(x, levels) {{ return Math.round(x * levels) / levels; }}

  function raymarch(ro, rd) {{
    let tMarch = 0.0;
    for (let i=0; i<P.ray_steps; i++) {{
      const pos = mulAdd(ro, rd, tMarch);
      const dist = sdf(pos);
      if (dist < P.hit_eps) {{
        return {{ hit: true, pos, normal: normalAt(pos), t: tMarch }};
      }}
      tMarch += dist * P.march_relax;
      if (tMarch > P.max_dist) break;
    }}
    return {{ hit: false }};
  }}

  function shadowAt(pos, L) {{
    let tS = 0.02;
    for (let i = 0; i < 40; i++) {{
      const p = mulAdd(pos, L, tS);
      const d = sdf(p);
      if (d < 0.001) return 0.0;
      tS += d * 0.9;
      if (tS > 3.5) break;
    }}
    return 1.0;
  }}

  function renderScanlines() {{
    time = performance.now() / 1000;
    ctx.clearRect(0, 0, W, H);

    ctx.globalAlpha = 1.0;
    ctx.lineWidth = 2;
    ctx.strokeStyle = `rgba(255,255,255,${{P.bg_alpha}})`;
    const flowU = P.flow_u;
    const flowA = P.flow_radius;
    const flowSpan = P.flow_x_span;
    const flowIter = P.flow_iter;
    const flowScale = W / (flowSpan * 2);
    const yOffset = H * 0.5;
    for (let y0 = -flowSpan; y0 <= flowSpan; y0 += (P.bg_gap / flowScale)) {{
      const psi0 = flowU * y0;
      ctx.beginPath();
      let prev = null;
      for (let x = -flowSpan; x <= flowSpan; x += (P.bg_x_step / flowScale)) {{
        let y = prev ? prev : y0;
        for (let i = 0; i < flowIter; i++) {{
          const r2 = x*x + y*y;
          const denom = Math.max(r2, 1e-4);
          const f = flowU * y * (1 - (flowA*flowA) / denom) - psi0;
          const df = flowU * (1 - (flowA*flowA)/denom) + flowU * y * (2 * flowA*flowA * y) / (denom*denom);
          y -= f / (df || 1e-4);
        }}
        const sx = x * flowScale + W * 0.5;
        const sy = -y * flowScale + yOffset + Math.sin((x * flowScale) * P.bg_wave_freq + time * P.bg_wave_time) * P.bg_wave_amp;
        if (prev === null) {{
          ctx.moveTo(sx, sy);
        }} else {{
          ctx.lineTo(sx, sy);
        }}
        prev = y;
      }}
      ctx.stroke();
    }}

    const lineGap = P.line_gap;
    const xStep = P.x_step;
    const waveFreq = P.wave_freq;
    const elev = P.cam_elev_deg * Math.PI / 180;

    const az = azim * Math.PI / 180;
    const camPos = [
      P.cam_dist * Math.cos(elev) * Math.cos(az),
      P.cam_dist * Math.sin(elev),
      P.cam_dist * Math.cos(elev) * Math.sin(az)
    ];
    const target = [0,0,0];
    const forward = normalize(sub(target, camPos));
    const right = normalize(cross(forward, [0,1,0]));
    const up = cross(right, forward);

    function rayDirForPixel(px, py) {{
      const aspect = W / H;
      const nx = (2 * (px + 0.5) / W - 1) * aspect;
      const ny = (1 - 2 * (py + 0.5) / H);
      const fov = P.fov;
      return normalize([
        forward[0] + right[0]*nx*fov + up[0]*ny*fov,
        forward[1] + right[1]*nx*fov + up[1]*ny*fov,
        forward[2] + right[2]*nx*fov + up[2]*ny*fov
      ]);
    }}

    function lightPosOrbit(ts) {{
      const R = P.light_radius;
      const az = ts * P.light_az_speed;
      const el = P.light_el_amp * Math.sin(ts * P.light_el_speed);
      return [
        R * Math.cos(el) * Math.cos(az),
        R * Math.sin(el),
        R * Math.cos(el) * Math.sin(az)
      ];
    }}

    const lightPos = P.enable_light_orbit ? lightPosOrbit(time) : [P.light_radius, P.fill_y_bias, P.light_radius];
    const Lfill = normalize([-lightPos[0], P.fill_y_bias, -lightPos[2]]);
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';

    for (let y = 0; y < H; y += lineGap) {{
      let prev = null;
      for (let x = 0; x < W; x += xStep) {{
        const dir = rayDirForPixel(x, y);
        const hit = raymarch(camPos, dir);
        if (!hit.hit) {{
          prev = null;
          continue;
        }}

        const Nfd = normalize(hit.normal);
        const Nh = axisFaceNormal(hit.pos);
        const k = (1.0 - t) * 0.95;
        const N = normalize([
          (1-k)*Nfd[0] + k*Nh[0],
          (1-k)*Nfd[1] + k*Nh[1],
          (1-k)*Nfd[2] + k*Nh[2],
        ]);
        const L = normalize(sub(lightPos, hit.pos));
        const vis = shadowAt(hit.pos, L);
        let diff = clamp(dot(N, L), 0, 1) * vis;
        diff = quantize(diff, P.quant_levels);
        const diff2 = clamp(dot(N, Lfill), 0, 1) * P.fill_weight;
        diff = clamp(diff + diff2, 0, 1);
        const diffBoost = Math.pow(diff, P.diff_boost);
        const distLight = length(sub(lightPos, hit.pos));
        const atten = 1.0 / (1.0 + P.atten_k * distLight * distLight);
        const shade = clamp(diffBoost * atten, 0, 1);
        const V = normalize(sub(camPos, hit.pos));
        const R = normalize([
          2*dot(N,L)*N[0] - L[0],
          2*dot(N,L)*N[1] - L[1],
          2*dot(N,L)*N[2] - L[2]
        ]);
        const nVal = noise3([hit.pos[0]*P.noise_freq + time*P.noise_crawl, hit.pos[1]*P.noise_freq, hit.pos[2]*P.noise_freq]);
        let spec = Math.pow(clamp(dot(R, V), 0, 1), P.spec_power) * P.spec_scale;
        spec *= 1.0 + P.spec_noise_boost * noiseLevel * Math.abs(nVal);
        const shadow = 1.0 - shade;
        const waveAmp = (P.wave_base + P.wave_shadow * shadow) * (1.0 + P.wave_noise_factor * noiseLevel);
        const yOff = Math.sin(x * waveFreq + time * P.wave_time_freq) * waveAmp;
        const rim = P.enable_rim ? Math.pow(1.0 - clamp(dot(N, V), 0, 1), 2.0) * 0.35 : 0.0;
        const alpha = clamp(P.alpha_base + P.alpha_shade * shade + rim + spec, 0, 1);
        const width = P.width_base + P.width_shadow * shadow + P.width_spec * spec;
        const yy = y + yOff;

        if (prev) {{
          ctx.beginPath();
          ctx.strokeStyle = `rgba(255,255,255,${{clamp(alpha,0,1)}})`;
          ctx.lineWidth = width;
          ctx.moveTo(prev.x, prev.y);
          ctx.lineTo(x, yy);
          ctx.stroke();
        }}
        prev = {{ x, y: yy }};
      }}
    }}
  }}

  function setFrameHeight() {{
    const wrap = document.querySelector(".morph-wrap");
    if (!wrap || !window.parent) return;
    const height = Math.ceil(wrap.getBoundingClientRect().height);
    window.parent.postMessage({{ type: "streamlit:setFrameHeight", height }}, "*");
  }}

  let resizeTimer = null;
  window.addEventListener("resize", () => {{
    if (resizeTimer) clearTimeout(resizeTimer);
    resizeTimer = setTimeout(setFrameHeight, 100);
  }});

  function tick() {{
    if (autoRotate) {{
      azim = (azim + P.auto_rotate_speed) % 360;
    }}
    renderScanlines();
    if ((Math.floor(time * 10) % 10) === 0) {{
      setFrameHeight();
    }}
    requestAnimationFrame(tick);
  }}

  setFrameHeight();
  tick();
}})();
</script>
    """
    st.components.v1.html(
        html, height=params["canvas_height"] + height_pad, scrolling=False
    )


def cracks_globe_block(
    points: list[dict[str, float | str]],
    *,
    height: int = 520,
    key: str = "cracks-globe",
    auto_rotate_speed: float = 2.6,
    camera_lat: float = 0.0,
    camera_lng: float = 0.0,
    camera_altitude: float = 1.2,
) -> None:
    safe_key = "".join(ch if ch.isalnum() else "-" for ch in key).strip("-") or "cracks"
    globe_id = f"globe-{safe_key}"
    tooltip_id = f"tooltip-{safe_key}"
    points_json = json.dumps(points)
    html = f"""
<head>
<style>
  html, body {{
    margin: 0;
    padding: 0;
    width: 100%;
    height: 100%;
    overflow: hidden;
    background: white;
  }}
  #{globe_id} {{
    width: 100%;
    height: 100%;
    margin: 0 auto;
  }}
  #{tooltip_id} {{
    position: absolute;
    background: rgba(255, 255, 255, 0.94);
    color: #111;
    padding: 6px 8px;
    border: 1px solid #d0d0d0;
    border-radius: 4px;
    display: none;
    pointer-events: none;
    font-size: 12px;
    z-index: 5;
  }}
</style>
<script src="https://unpkg.com/globe.gl"></script>
<script src="https://unpkg.com/three"></script>
<script src="https://unpkg.com/solar-calculator"></script>
</head>
<body>
<div id="{globe_id}"></div>
<div id="{tooltip_id}"></div>
<script>
  const cryosphereCracksData = {points_json};
  const globeContainer = document.getElementById("{globe_id}");
  const tooltip = document.getElementById("{tooltip_id}");

  const globe = Globe()(globeContainer)
    .globeImageUrl("https://unpkg.com/three-globe/example/img/earth-night.jpg")
    .backgroundColor("rgb(255, 255, 255)")
    .heatmapPointLat("lat")
    .heatmapPointLng("lng")
    .heatmapPointWeight("energy")
    .heatmapBandwidth(1.9)
    .heatmapColorSaturation(1.8)
    .enablePointerInteraction(true)
    .pointsData(cryosphereCracksData)
    .pointLat(d => d.lat)
    .pointLng(d => d.lng)
    .pointAltitude(d => d.energy * 0.001)
    .pointColor(() => "orange")
    .pointRadius(0.5)
    .onPointHover(d => {{
      if (!tooltip) return;
      if (d) {{
        tooltip.style.display = "block";
        tooltip.innerHTML = `<b>${{d.name}}</b><br>Energy: ${{d.energy}}`;
      }} else {{
        tooltip.style.display = "none";
      }}
    }});

  globe.heatmapsData([cryosphereCracksData]);
  globe.pointOfView({{
    lat: {camera_lat},
    lng: {camera_lng},
    altitude: {camera_altitude}
  }}, 0);

  const resizeGlobe = () => {{
    globe.width(globeContainer.clientWidth);
    globe.height(globeContainer.clientHeight);
  }};
  resizeGlobe();

  window.addEventListener("resize", resizeGlobe);
  window.addEventListener("mousemove", (e) => {{
    if (!tooltip || tooltip.style.display === "none") return;
    tooltip.style.left = (e.clientX + 12) + "px";
    tooltip.style.top = (e.clientY + 12) + "px";
  }});

  globe.controls().autoRotate = true;
  globe.controls().autoRotateSpeed = {auto_rotate_speed};
</script>
</body>
    """
    st.components.v1.html(html, height=height, scrolling=False)


def render_info_block(left_title: str, left_subtitle: str, right_content: str):
    """
    Displays a two-column section with:
    - a left title and subtitle (Markdown),
    - a right column with arbitrary Markdown content.
    """
    col_left, col_right = st.columns([1, 2], vertical_alignment="top")

    with col_left:
        st.markdown(f"# {left_title}")
        if left_subtitle:
            st.write(f"##### `{left_subtitle}`")

    with col_right:
        st.markdown(right_content)

    st.divider()


def display_centered_prompt(prompt: str = "What would you like to see?"):
    st.markdown(
        f""" 
        <div style="display: flex; align-items: center; justify-content: center; margin: 2em 0;">
        <hr style="flex: 1; border: none; height: 1px; background-color: #000;">
        <span style="margin: 0 1rem; font-family: 'Georgia', serif; font-size: 2.5rem;">{prompt}</span>
        <hr style="flex: 1; border: none; height: 1px; background-color: #000;">
        </div>
        """,
        unsafe_allow_html=True,
    )
