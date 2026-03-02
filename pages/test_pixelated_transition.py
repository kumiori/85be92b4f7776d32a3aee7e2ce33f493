from __future__ import annotations

import streamlit as st
import streamlit.components.v1 as components


HTML = """
<!doctype html>
<html lang="en" data-theme="system" data-transition="outIn" data-flipped="false">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Pixelated View Transitions</title>
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Reddit+Mono:wght@200..900&display=swap');
      @import url('https://unpkg.com/normalize.css') layer(normalize);

      @font-face {
        font-family: 'Departure Mono';
        src: url('https://assets.codepen.io/605876/DepartureMono-Regular.woff');
      }

      @layer normalize, base, demo, transition;

      @layer transition {
        :root {
          --speed: calc(var(--duration, 0.25) * 1s);
          --ms: calc(1vmax * var(--size));
        }
        ::view-transition {
          background: oklch(64.72% 0.3133 333.53);
        }
        ::view-transition-old(root),
        ::view-transition-new(root) {
          mask-image: var(--mi);
          mask-repeat: no-repeat;
          mask-size: calc(var(--ms) + 1px) calc(var(--ms) + 1px);
          mask-position: var(--mp, -100% -100%);
        }
        [data-transition='outIn']::view-transition-old(root) {
          animation: maskOut var(--speed) ease forwards reverse;
        }
        [data-transition='outIn']::view-transition-new(root) {
          animation: maskIn var(--speed) calc(var(--speed) * 1.25) ease forwards;
        }
        [data-transition='out']::view-transition-old(root) {
          animation: maskOut var(--speed) ease forwards reverse;
          z-index: 20;
        }
        [data-transition='out']::view-transition-new(root) {
          animation: none;
          mask: none;
          opacity: 1;
        }
      }

      @layer demo {
        h1 {
          --font-level: 6;
          font-family: 'Departure Mono', monospace;
          text-transform: uppercase;
          text-align: center;
          line-height: 1;
          width: 12ch;
          margin: 0;
        }
        p {
          --font-level: 2;
          font-family: 'Reddit Mono', monospace;
          text-transform: uppercase;
          text-align: center;
          line-height: 1;
          margin: 0;
          opacity: 0.5;
        }
        p + p {
          --font-level: 0.6;
          margin: 0;
          opacity: 0.25;
          translate: 0 -0.5lh;
          transition: opacity 0.26s ease-out;
        }
        p + p:hover {
          opacity: 1;
        }
        body {
          align-content: center;
          gap: 2rem;
        }
      }

      @layer base {
        :root {
          --font-size-min: 16;
          --font-size-max: 20;
          --font-ratio-min: 1.2;
          --font-ratio-max: 1.33;
          --font-width-min: 375;
          --font-width-max: 1500;
        }

        html {
          color-scheme: light dark;
        }

        [data-flipped='true'][data-theme='dark'],
        [data-theme='light'] {
          color-scheme: light only;
        }

        [data-flipped='true'][data-theme='light'],
        [data-theme='dark'] {
          color-scheme: dark only;
        }

        :where(.fluid) {
          --fluid-min: calc(
            var(--font-size-min) * pow(var(--font-ratio-min), var(--font-level, 0))
          );
          --fluid-max: calc(
            var(--font-size-max) * pow(var(--font-ratio-max), var(--font-level, 0))
          );
          --fluid-preferred: calc(
            (var(--fluid-max) - var(--fluid-min)) /
              (var(--font-width-max) - var(--font-width-min))
          );
          --fluid-type: clamp(
            (var(--fluid-min) / 16) * 1rem,
            ((var(--fluid-min) / 16) * 1rem) -
              (((var(--fluid-preferred) * var(--font-width-min)) / 16) * 1rem) +
              (var(--fluid-preferred) * var(--variable-unit, 100vi)),
            (var(--fluid-max) / 16) * 1rem
          );
          font-size: var(--fluid-type);
        }

        *,
        *:after,
        *:before {
          box-sizing: border-box;
        }

        body {
          display: grid;
          place-items: center;
          min-height: 100vh;
          font-family: 'SF Pro Text', 'SF Pro Icons', 'AOS Icons', 'Helvetica Neue',
            Helvetica, Arial, sans-serif, system-ui;
        }

        body::before {
          --size: 45px;
          --line: color-mix(in hsl, canvasText, transparent 70%);
          content: '';
          height: 100vh;
          width: 100vw;
          position: fixed;
          background: linear-gradient(
                90deg,
                var(--line) 1px,
                transparent 1px var(--size)
              )
              50% 50% / var(--size) var(--size),
            linear-gradient(var(--line) 1px, transparent 1px var(--size)) 50% 50% /
              var(--size) var(--size);
          mask: linear-gradient(-20deg, transparent 50%, white);
          top: 0;
          transform-style: flat;
          pointer-events: none;
          z-index: -1;
        }

        .bear-link {
          color: canvasText;
          position: fixed;
          top: 1rem;
          left: 1rem;
          width: 48px;
          aspect-ratio: 1;
          display: grid;
          place-items: center;
          opacity: 0.8;
        }
        .bear-link:hover {
          opacity: 1;
        }
        .bear-link svg {
          width: 75%;
        }
      }
    </style>
    <style id="vt"></style>
  </head>
  <body>
    <h1 class="fluid">Pixelated</h1>
    <p class="fluid">Subtitle</p>
    <p class="fluid"><a href="https://codepen.io/pen/debug/QwLdaQX" target="_blank">[open in debug]</a></p>
    <a class="bear-link" href="https://twitter.com/intent/follow?screen_name=jh3yy" target="_blank" rel="noreferrer noopener">
      <svg class="w-9" viewBox="0 0 969 955" fill="none" xmlns="http://www.w3.org/2000/svg">
        <circle cx="161.191" cy="320.191" r="133.191" stroke="currentColor" stroke-width="20"></circle>
        <circle cx="806.809" cy="320.191" r="133.191" stroke="currentColor" stroke-width="20"></circle>
        <circle cx="695.019" cy="587.733" r="31.4016" fill="currentColor"></circle>
        <circle cx="272.981" cy="587.733" r="31.4016" fill="currentColor"></circle>
        <path d="M564.388 712.083C564.388 743.994 526.035 779.911 483.372 779.911C440.709 779.911 402.356 743.994 402.356 712.083C402.356 680.173 440.709 664.353 483.372 664.353C526.035 664.353 564.388 680.173 564.388 712.083Z" fill="currentColor"></path>
        <rect x="310.42" y="448.31" width="343.468" height="51.4986" fill="#FF1E1E"></rect>
        <path fill-rule="evenodd" clip-rule="evenodd" d="M745.643 288.24C815.368 344.185 854.539 432.623 854.539 511.741H614.938V454.652C614.938 433.113 597.477 415.652 575.938 415.652H388.37C366.831 415.652 349.37 433.113 349.37 454.652V511.741L110.949 511.741C110.949 432.623 150.12 344.185 219.845 288.24C289.57 232.295 384.138 200.865 482.744 200.865C581.35 200.865 675.918 232.295 745.643 288.24Z" fill="currentColor"></path>
      </svg>
    </a>

    <script type="module">
      import { Pane } from 'https://cdn.skypack.dev/tweakpane@4.0.4'

      const config = { theme: 'system', type: 'outIn', flipped: false, cells: 9, speed: 0.3 }
      const ctrl = new Pane({ title: 'Config', expanded: true })
      let genStyles

      const update = () => {
        document.documentElement.dataset.theme = config.theme
        document.documentElement.dataset.transition = config.type
        document.documentElement.dataset.flipped = config.flipped
        document.documentElement.style.setProperty('--duration', config.speed)
        if (genStyles) genStyles()
      }

      const sync = (event) => {
        if (!document.startViewTransition || (event && event.target.controller.view.labelElement.innerText !== 'Theme')) {
          return update()
        }
        document.startViewTransition(() => update())
      }

      ctrl.addBinding(config, 'speed', { min: 0.2, max: 1, step: 0.01 })
      ctrl.addBinding(config, 'type', { label: 'Type', options: { Out: 'out', outIn: 'outIn' } })
      ctrl.addBinding(config, 'theme', { label: 'Theme', options: { System: 'system', Light: 'light', Dark: 'dark' } })
      ctrl.addBinding(config, 'cells', { label: 'per Row', min: 3, max: 21, step: 2 })
      ctrl.on('change', sync)
      ctrl.addButton({ title: 'Transition' }).on('click', () => { config.flipped = !config.flipped; sync() })

      const shuffleArray = (arr) => {
        for (let i = arr.length - 1; i > 0; i--) {
          const j = Math.floor(Math.random() * (i + 1))
          ;[arr[i], arr[j]] = [arr[j], arr[i]]
        }
        return arr
      }

      const getPositions = (frame, pos) => {
        const slices = []
        for (let i = 0; i < config.cells; i++) {
          if (i < frame) slices.push(pos.slice(i * config.cells, (i + 1) * config.cells))
          else slices.push(pos.slice(frame * config.cells, (frame + 1) * config.cells))
        }
        return slices.join(',')
      }

      const getFrames = (positions) => {
        let frames = ''
        const shuffled = shuffleArray(positions)
        for (let f = 1; f < config.cells; f++) {
          const sineFrame = Math.floor(Math.sin((f / config.cells) * (Math.PI / 2)) * 100)
          frames += `${sineFrame}% { --mp: ${getPositions(f, shuffled)}; }`
        }
        frames += `100% { --mp: ${positions.join(',')}; }`
        return frames
      }

      genStyles = () => {
        const sheet = document.querySelector('#vt')
        const positions = []
        const mid = Math.ceil(config.cells * 0.5)
        for (let p = 0; p < Math.pow(config.cells, 2); p++) {
          const x = p % config.cells
          const y = Math.floor(p / config.cells)
          const xm = x + 1 - mid
          const ym = y + 1 - mid
          positions.push(`calc(50% + (var(--ms) * ${xm})) calc(50% + (var(--ms) * ${ym}))`)
        }
        const maskIn = `@keyframes maskIn {${getFrames(positions)}}`
        const maskOut = `@keyframes maskOut {${getFrames(positions)}}`
        sheet.innerHTML = `
          :root {
            --mi: ${new Array(Math.pow(config.cells, 2)).fill('linear-gradient(#fff 0 0)').join(',')};
            --size: ${Math.ceil(100 / config.cells)};
          }
          ${maskIn}
          ${maskOut}
        `
      }

      genStyles()
      update()
    </script>
  </body>
</html>
"""


def main() -> None:
    st.set_page_config(page_title="Test · Pixel Transition", layout="wide")
    st.title("Test · Pixelated View Transition")
    components.html(HTML, height=980, scrolling=False)


if __name__ == "__main__":
    main()
