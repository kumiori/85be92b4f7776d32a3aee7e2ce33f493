# PLAN.md

## Goal

Refactor Ice Ice Baby so that every questionnaire belongs to a clearly isolated event, then add the next event questionnaire for the D’Alembert laboratory, codename `dalembertiennes`.

The immediate objective is not to create another ad hoc questionnaire. The objective is to make `dalembertiennes` the first clean test of an event-scoped architecture that still respects the current `session`-based implementation.

## Current architectural decision

At the product level, the event is the target boundary.

At the implementation level today, the system is still organized around `session`, `session_code`, and `session_id`.

So the migration rule is:

- treat `event` as a resolver or alias over the current session model first;
- add event-specific metadata and scope incrementally;
- do not force a big-bang rename of every `session_*` path in the code.

Everything must still become scoped, explicitly, to one real gathering:

- questions
- responses
- participants’ participation traces
- logs
- overviews
- exports
- reports

Responses from UNESCO, Dalembertiennes, or any future workshop must never be mixed or double-counted unless a cross-event comparison explicitly requests it.

## Participant flow practice

- A participant must not advance past a normal question step accidentally.
- Every normal question step must render the same action structure: dominant `Continue`, secondary `Flag`, and secondary `Skip`.
- `Continue` requires a response for the current question.
- If the participant does not want to respond, they must use `Skip` and provide a reason.
- Skip reasons must be stored with the question feedback/flag trail and remain visible in review, overview, host, or export surfaces where appropriate.
- Optionality means “may skip with stated reason”, not “blank continue”.
- Built-in structural steps such as `welcome`, `identity`, `review`, and `done` may have their own controls, but they must not be used to host ordinary question prompts.

## Current status

- Streamlit app is functional.
- Notion backend stores players, responses, sessions, decisions, and events.
- UNESCO event flow exists and has produced usable data.
- Overview and report logic exist in prototype form.
- `pages/07_Admin.py` serves as the operator/admin surface.
- `infra/event_logger.py` provides logging, timing, and event infrastructure.
- A Notion `ice_Events` database exists.
- The current codebase still uses `session` as the durable boundary in repositories and query paths.
- Static routes are declared in `app.py`; there is no generic `/event/:slug` router.
- Player schema already has concrete columns such as `access_key`, `role`, `last_seen`, `phrase`, `emoji_suffix_4`, and `emoji_suffix_6`.
- Next event line is `dalembertiennes`.

## Next event

### Codename

`dalembertiennes`

### Working title

D’Alembertiennes Lab Questionnaire

### Purpose

Internal laboratory questionnaire / participatory session connected to the D’Alembert lab days.

The event should be treated as a new event instance with its own question set, own responses, own overview, and own exports.

### Primary risk to avoid

Data mingling with UNESCO or previous `GLOBAL-SESSION` data.

## Next action

Implement a `dalembertiennes` session or event resolver scaffold without breaking the current session-based write paths.

This must be done before finalising the question wording.

## Sprint 0 — Event architecture hardening

### Objective

Make it impossible, or at least difficult, to write responses without explicit session or event scope.

### Tasks

- [ ] Audit the current session schema and usage before introducing any new event abstraction.
- [ ] Formalise an event resolver that maps one event slug to one current `session_code`.
- [ ] Keep current session fields first-class:
    - `session_code`
    - `session_name`
    - `session_title`
    - `session_description`
    - `session_order`
    - `session_visualisation`
    - `status`
    - `mode`
    - `round_index`
    - `active`
- [ ] Add event metadata only as an additive layer:
    - `event_slug`
    - `event_title`
    - `event_location`
    - `event_visibility`
    - `question_set_id`
    - `questionnaire_version`

- [ ] Add event lifecycle states:
    - `draft`
    - `open`
    - `closed`
    - `archived`

- [ ] Ensure closed and archived event states translate into read-only response behavior.

- [ ] Rename internal mental model:
    - real-world gathering = `Event`
    - persisted grouping record = `Session`
    - participant filling flow = `Participation`
    - browser context = `Browser session`

- [ ] Audit code for ambiguous `session_id` usage in:
    - `infra/notion_repo.py`
    - `conference/context.py`
    - `conference/repo.py`
    - `models/catalog.py`
    - `pages/*`

- [ ] Add migration notes where legacy session terms remain for valid reasons.

## Next action

Finish the typography verification pass before final copy polish.

Tasks:

- Create a central typography/style helper. Done for conference routes through `conference/ui.py`.
- Replace route-local ad hoc heading styles with shared classes. Done for WG2 landing, question, review, and done surfaces in `conference/questionnaire.py`.
- Apply the system to the WG2 route first. Done.
- Check mobile readability. Landing and first question checked; review/done still need a completed test trajectory or fixture route for direct screenshots.
- Then return to final copy edits.

Acceptance criteria:
- Landing, question, review, and done screens use the same type ramp.
- Headings are visually strong but not oversized on mobile.
- Body text has readable line height and limited width.
- Helper/context text is clearly secondary.
- Buttons are consistent across the flow.

### Definition of done

- Event can be resolved from slug into one current `session_code`.
- Every questionnaire page has explicit session or event context.
- Event status controls write permissions.
- Response save path requires at least session context plus question identity.

## Sprint 1 — Dalembertiennes scaffold

### Objective

Create the `dalembertiennes` event or session scaffold without duplicating UNESCO code or data.

### Tasks

- [ ] Create or identify a session-backed event record:
    - resolver slug: `dalembertiennes`
    - title: `D’Alembertiennes Lab Questionnaire`
    - status: `draft`
    - visibility: internal or private
    - question_set_id: `dalembertiennes_v0`
    - backing `session_code`: explicit and unique

- [ ] Create question set record or code object:
    - id: `dalembertiennes_v0`
    - title: `D’Alembertiennes questionnaire v0`
    - version: `0`
    - language: `fr/en` if bilingual, otherwise specify one language

- [ ] Add route resolver compatible with current Streamlit navigation:
    - either a new `url_path`
    - or an existing page plus query params
    - or a session selector that resolves `dalembertiennes`

- [ ] Check all existing route entry points in `app.py` before adding a new page:
    - `unesco-opening`
    - `complexity`
    - `pisa`
    - `young-overview`
    - `complexity-overview`
    - `pisa-opening`
    - `pisa-meeting-host`

- [ ] Ensure welcome copy reads from resolved event or session metadata.

- [ ] Ensure questionnaire reads from event question set.

- [ ] Ensure overview filters by resolved session or event id.

- [ ] Ensure exports filter by resolved session or event id.

### Definition of done

- Opening the Dalembertiennes entry point does not show UNESCO content.
- Submitting a response writes the Dalembertiennes session or event scope explicitly.
- Overview for `dalembertiennes` shows only Dalembertiennes responses.
- UNESCO overview remains unchanged.

## Sprint 2 — Response schema enforcement

### Objective

Guarantee that response rows are self-sufficient and auditable.

### Required response fields

Each response should preserve current schema fields and add event-facing ones only where justified.

Current persisted fields already used by the write path include:

- `session`
- `player`
- `question`
- `question_id`
- `item_id`
- `value_json`
- `value_label`
- `question_type`
- `timestamp`
- `submitted_at`
- `text_id`
- optional `response_value`
- optional `score`
- optional `page_index`
- optional `depth`
- optional `optional_text`
- optional `device_id`
- optional `access_key`

Additive fields that can be introduced carefully:

- optional `event_slug`
- optional `question_set_id`
- optional `participation_id`

### Tasks

- [ ] Patch response writer to require session scope or resolved event scope.
- [ ] Patch response writer to keep `text_id` explicit.
- [ ] Patch response writer to add `question_set_id` only if it can be sourced reliably.
- [ ] Patch response writer to require `question_id`.
- [ ] Fail loudly if session or event scope is missing.
- [ ] Log failure through `infra/event_logger.py`.
- [ ] Add admin visibility for failed response writes.

### Definition of done

No response can be saved without explicit session or event scope, `question_id`, and `text_id`.

## Sprint 3 — Admin event cockpit

### Objective

Use `pages/07_Admin.py` as the operator view for multi-event management.

### Tasks

- [ ] Add event selector.
- [ ] Show event lifecycle status.
- [ ] Show question set attached to event.
- [ ] Show response count by event.
- [ ] Show participant count by event.
- [ ] Show latest events/logs by event.
- [ ] Show backing `session_code` for each event resolver.
- [ ] Add button to open event overview.
- [ ] Add button to export event responses.
- [ ] Add lifecycle controls for admin:
    - draft → open
    - open → closed
    - closed → archived

### Guardrails

- Lifecycle changes must log an admin event.
- Closing an event must prevent new response writes.
- Archiving must be treated as immutable.

### Definition of done

Admin can see and manage `dalembertiennes` without touching UNESCO data.

## Sprint 4 — Question catalogue for Dalembertiennes

### Objective

Prepare the questionnaire structure while allowing wording to remain flexible until final copy is approved.

### Minimal structure

Each question needs:

- stable `id`
- `question_set_id = dalembertiennes_v0`
- section
- order
- prompt
- context
- qtype
- response structure
- active flag

### Proposed sections

- entry / identity light
- lab perception
- climate reflection
- collective decision
- open question
- follow-up / willingness to continue

### Tasks

- [ ] Draft initial `dalembertiennes_v0` question list.
- [ ] Add placeholder questions with stable ids.
- [ ] Make question wording editable before event opens.
- [ ] Freeze question set when event status becomes `open`.
- [ ] If wording changes after opening, create `dalembertiennes_v1` instead of overwriting.

### Definition of done

Questionnaire can run with placeholder or final questions and still write event-scoped responses.

## Sprint 5 — Overview and aggregation

### Objective

Produce event-scoped aggregate views.

### Tasks

- [ ] Add aggregation scope argument: `event_id`.
- [ ] Ensure all aggregation calls require event scope.
- [ ] Build `dalembertiennes` overview from its own responses.
- [ ] Keep raw debug JSON in admin only.
- [ ] Render public overview as interpreted signals, not raw database dumps.

### First visualisations

- response count
- participant count
- distribution by question
- collective decision signal if present
- open-text excerpt list if moderated

### Definition of done

Overview answers the question: what happened in this event, and only this event?

## Sprint 6 — Event logs and long-running loop

### Objective

Prepare for multi-loop, long-running agentic operation.

### Tasks

- [ ] Log event access:
    - `event_page_view`
    - `questionnaire_started`
    - `response_submit`
    - `questionnaire_completed`
    - `overview_loaded`
    - `export_created`
    - `event_status_changed`

- [ ] Store logs through `infra/event_logger.py`.
- [ ] Add event id to every log.
- [ ] Preserve `session_id` in logs while event mapping is transitional.
- [ ] Add participation id where available.
- [ ] Add admin panel for recent event logs.

### Later tasks

- [ ] Add persisted job queue in SQLite or Notion.
- [ ] Add runner script for bounded agent tasks.
- [ ] Add checkpoint loop:
    - read durable state
    - choose next action
    - execute one step
    - log
    - checkpoint
    - stop

### Definition of done

Every important action leaves an append-only event trace.

## Open blockers

- Define exact Dalembertiennes date, location, and organisers.
- Define whether event is internal-only or accessible to guests.
- Define language strategy: French, English, or bilingual.
- Define first question set.
- Define whether existing participants can reuse access keys across sessions or events.
- Define whether event welcome page should mention UNESCO lineage or stand alone.
- Define final overview visual style.

## Design decisions pending

### Participant identity across events

Options:

1. Same participant key can join multiple events.
2. Each event mints event-specific keys.
3. Hybrid: global participant, event-specific participation.

Preferred direction:

Global participant, event-specific participation.

This preserves continuity without mixing responses and fits the current players table better than event-specific reminting.

### Question reuse

Options:

1. Reuse UNESCO questions.
2. Create Dalembertiennes-specific question set.
3. Use shared core questions plus event-specific extensions.

Preferred direction:

Shared core questions plus event-specific extensions.

### Aggregation

Default must always be event-scoped.
Cross-event comparisons are a later explicit feature.

### Verification constraint

No event-scoped write is considered complete just because the questionnaire shows success.

For every new event flow, the same checkpoint must pass end to end:

1. open the event entry point
2. submit one known answer
3. read it back through the event-specific overview/export path
4. confirm other events remain unchanged

If the scoped overview cannot read the scoped write, the task is not done.

### Naming isolation constraint

Event-specific persistence names must not leak another event lineage.

Examples:

- Dalembertiennes rows must not be saved under `COMPLEXITY_BUNDLE`.
- UNESCO rows must not reuse Dalembertiennes identifiers.
- Export labels, bundle ids, and event-facing item names must stay event-specific or neutral.

If an event write succeeds but its persisted identifiers still reference another event family, the task is not done.

### Event-local anonymity constraint

Anonymous fallback markers are part of the event-facing identity layer and must also stay scoped.

Examples:

- Dalembertiennes must not default to the Complexity anonymous symbol.
- Event-specific player nicknames created during anonymous-first flows must be derived from the resolved event context.
- If a fallback anonymous label is reused, it must be intentionally shared, not inherited accidentally from another event path.

If the write path stores the right response but still assigns another event's anonymous identity marker, the task is not done.

### Bundle routing constraint

Bundle routing must be explicit and fail closed.

Required rule:

- `event_slug`
- `session_code`
- `text_id`
- `question_set_id`
- `response_scope`

must agree before any event-scoped write is accepted.

In particular:

- unknown `text_id` must be rejected, never routed to `COMPLEXITY_BUNDLE`
- if outer `text_id` and payload `session.text_id` disagree, the write must fail
- the saved `text_id` must be the canonical event text id used for bundle routing
- combinations like `COMPLEXITY_BUNDLE · dalembertiennes_v0` must be impossible after validation

## Recent checkpoints

- 2026-06-30: Dalembertiennes route and write guardrails added. Files changed: `app.py`, `conference/events.py`, `conference/page_loader.py`, `conference/repo.py`, `models/sessions.py`, `pages/07_Admin.py`, `pages/15_Pisa_Meeting.py`, `pages/16_Pisa_Meeting_Host.py`, `pages/20_Complexity_Overview.py`, `pages/21_Dalembertiennes.py`, `pages/22_Dalembertiennes_Overview.py`, `pages/23_Dalembertiennes_Host.py`, `scripts/bootstrap_dalembertiennes_session.py`. Result: `dalembertiennes` now resolves through explicit event/session metadata, has first-class Streamlit entry points, overview and host aliases, read-only lifecycle gating for closed or archived events, and response writes now fail loudly when session or event scope is incomplete.
- 2026-06-30: Dalembertiennes questionnaire isolated from Complexity copy. Files changed: `conference/dalembertiennes.py`, `pages/21_Dalembertiennes.py`, `pages/22_Dalembertiennes_Overview.py`, `pages/23_Dalembertiennes_Host.py`. Result: Dalembertiennes now starts from a blank placeholder flow with dedicated state, writes a session-scoped placeholder response, and exposes a dedicated overview/export path that does not reuse the Complexity questionnaire UI.
- 2026-07-01: Dalembertiennes scoped read path bug identified and patched. Files changed: `repositories/interaction_repo.py`. Result: when the interaction database lacks a physical `text_id` column, the reader now derives `text_id` from `value_json`, so event-specific overviews can read back conference bundle rows instead of silently dropping them.
- 2026-07-01: Dalembertiennes persistence naming separated from Complexity. Files changed: `conference/repo.py`, `pages/20_Complexity_Overview.py`, `tests/test_conference_repo.py`. Result: Dalembertiennes writes now use an event-specific bundle id instead of falling into Complexity, the shared debug reader no longer assumes all non-Pisa conference bundles are Complexity, and the repository contract now guards against this naming leak.
- 2026-07-01: Dalembertiennes anonymous fallback separated from Complexity. Files changed: `conference/repo.py`, `tests/test_conference_repo.py`, `PLAN.md`. Result: anonymous-first player upserts now derive their fallback nickname from event metadata, so Dalembertiennes uses its own marker instead of inheriting the Complexity spiral.
- 2026-07-01: Dalembertiennes bundle routing made fail-closed. Files changed: `conference/repo.py`, `tests/test_conference_repo.py`, `scripts/migrate_dalembertiennes_bundle_ids.py`, `PLAN.md`. Result: event writes now derive a canonical `text_id`, reject text-id mismatches instead of silently falling back to Complexity, and route Dalembertiennes rows to `DALEMBERTIENNES_BUNDLE`.
- 2026-03-XX: UNESCO flow produced response data and overview charts.
- 2026-03-XX: Event logger available in `infra/event_logger.py`.
- 2026-03-XX: Admin page available in `pages/07_Admin.py`.
- 2026-03-XX: Decade map prototype tested, needs guided trajectory redesign.
- 2026-03-XX: Architecture note adopted: event is the primary data boundary.
- 2026-03-XX: Next event codename selected: `dalembertiennes`.
- 2026-07-06: Added YAML question-set authoring support. Files changed: `conference/question_sets/yaml_loader.py`, `conference/question_sets/un_wg2_v1.py`, `tests/test_question_set_yaml_loader.py`. Result: WG2 keeps `un_wg2_v1` and now loads `conference/question_sets/specs/un_wg2_v1.yaml` when present, otherwise it falls back to the current Python scaffold. Verification: `./.venv/bin/python -m pytest tests/test_question_set_yaml_loader.py tests/test_conference_registry.py` passed. Next action: author the WG2 YAML spec and place it at `conference/question_sets/specs/un_wg2_v1.yaml`.
- 2026-07-07: Added question-set source diagnostics and fixed WG2 YAML loading. Files changed: `conference/question_sets/__init__.py`, `conference/question_sets/yaml_loader.py`, `conference/question_sets/un_wg2_v1.py`, `conference/registry.py`, `conference/questionnaire.py`, `pages/26_UN_WG2_Overview.py`, `pages/27_UN_WG2_Host.py`, `ui.py`, `conference/question_sets/un_wg2_v1.yaml`. Result: WG2 now loads `conference/question_sets/un_wg2_v1.yaml` directly, reports source kind/path/question counts in the sidebar and host page, preserves `yes`/`no` option values as strings, and validates the YAML question set. Verification: `./.venv/bin/python -m pytest tests/test_question_set_yaml_loader.py tests/test_conference_registry.py` passed; registry reports `source_kind = yaml`, `question_count = 13`, and no validation errors.
- 2026-07-07: Hardened WG2 participant flow. Files changed: `conference/questionnaire.py`, `conference/flow.py`, `conference/question_sets/un_wg2_v1.yaml`, `conference/question_sets/__init__.py`, `tests/test_conference_registry.py`, `tests/test_conference_flow.py`, `PLAN.md`. Result: normal question steps now block `Continue` unless answered; participants must use `Skip` with a reason for blank questions; route logging is null-safe for built-in steps; WG2 no longer asks a redundant stay-in-touch question; the built-in identity step shows optional contact for WG2; WG2 now asks where participants are mainly based through the geography context field. Verification: `./.venv/bin/python -m pytest tests/test_question_set_yaml_loader.py tests/test_conference_registry.py tests/test_conference_flow.py` passed.
- 2026-07-07: Consolidated question action structure rule. Result: the plan now states that every normal question step must expose `Continue`, `Flag`, and `Skip`; WG2 registry tests verify each active YAML step resolves to a concrete question definition so it receives the standard action row.
- 2026-07-07: Added explicit location-to-coordinate lookup for geography questions. Files changed: `conference/questionnaire.py`, `conference/flow.py`, `tests/test_conference_flow.py`. Result: participants can click `Look up approximate coordinates` after entering a place; the app uses OpenCage via `st.secrets["opencage"]["OPENCAGE_KEY"]`, stores coordinates plus `geocode_query`, `geocode_label`, `geocode_source`, and marks `coordinates_consent = lookup`. No IP inference is used. Verification: `./.venv/bin/python -m pytest tests/test_question_set_yaml_loader.py tests/test_conference_registry.py tests/test_conference_flow.py` passed.
- 2026-07-07: Added shared participant typography layer for WG2. Files changed: `conference/ui.py`, `conference/questionnaire.py`, `PLAN.md`. Result: `apply_typography_theme()` now centralizes the participant type ramp and shared classes `.page-title`, `.page-kicker`, `.page-subtitle`, `.section-title`, `.question-title`, `.question-context`, `.helper-text`, `.caption`, `.primary-action`, and `.secondary-action`; WG2 landing, question, review, and done surfaces now use the shared classes without data logic, Notion schema, or question ID changes. Verification: `./.venv/bin/python -m py_compile conference/ui.py conference/questionnaire.py pages/25_UN_WG2_Icebreaker.py` passed; `./.venv/bin/python -m pytest tests/test_question_set_yaml_loader.py tests/test_conference_registry.py tests/test_conference_flow.py` passed. Screenshots checked: `/private/tmp/ice_typography_pdf/wg2-entry-desktop-final.png`, `/private/tmp/ice_typography_pdf/wg2-entry-mobile-final.png`, `/private/tmp/ice_typography_pdf/wg2-question-desktop.png`, `/private/tmp/ice_typography_pdf/wg2-question-mobile.png`. Remaining typography issues: capture review and done screens through a completed non-production test trajectory; Streamlit button markup cannot directly attach `.primary-action` and `.secondary-action`, so those classes are available for custom markup while the current button styling targets Streamlit primary/secondary button selectors.
- 2026-07-07: Corrected WG2 landing typographic composition. Files changed: `conference/ui.py`, `conference/questionnaire.py`, `conference/public_routes.py`, `PLAN.md`. Result: the WG2 entry now reads as one editorial sequence: `Working Group 2` display, `Actionable Cryosphere Projections` headline, `Module 1 · Collective visibility` kicker, lead paragraph, quieter privacy note, then immediate action. The artificial narrow title column was removed, the type ramp was reduced toward four roles, the background was flattened, and button/card radii were tightened. Verification: `./.venv/bin/python -m py_compile conference/ui.py conference/questionnaire.py conference/public_routes.py pages/25_UN_WG2_Icebreaker.py` passed; `./.venv/bin/python -m pytest tests/test_question_set_yaml_loader.py tests/test_conference_registry.py tests/test_conference_flow.py` passed. Screenshots checked: `/private/tmp/ice_typography_pdf/wg2-entry-composition-desktop.png`, `/private/tmp/ice_typography_pdf/wg2-entry-composition-mobile.png`, `/private/tmp/ice_typography_pdf/wg2-question-composition-desktop.png`, `/private/tmp/ice_typography_pdf/wg2-question-composition-mobile.png`. Remaining typography issues: review and done still need direct screenshots through a completed non-production trajectory.
- 2026-07-07: Reframed WG2 landing and questionnaire order around coordinates. Files changed: `conference/public_routes.py`, `conference/questionnaire.py`, `conference/question_sets/un_wg2_v1.yaml`, `conference/ui.py`, `tests/test_conference_registry.py`, `PLAN.md`. Result: landing begins with `Collective Visibility`, treats `WG2 • Actionable Cryosphere Projections` as report-style metadata, and presents explicit `Purpose`, `This pilot`, and participation blocks. The active WG2 flow now starts with `Who is speaking?`, merges participant base and relevant regions into one `Spatial context` screen, then moves into cryosphere domain, collective needs, perspective, and shared coordination/contribution questions. Existing question IDs and storage fields are preserved; `UN_WG2_REGION` remains in the catalogue but is rendered on the `main_location` step instead of as a separate page. Verification: `./.venv/bin/python -m py_compile conference/ui.py conference/questionnaire.py conference/public_routes.py pages/25_UN_WG2_Icebreaker.py` passed; `./.venv/bin/python -m pytest tests/test_question_set_yaml_loader.py tests/test_conference_registry.py tests/test_conference_flow.py` passed with 19 tests. Screenshots checked: `/private/tmp/ice_typography_pdf/wg2-landing-purpose-desktop.png`, `/private/tmp/ice_typography_pdf/wg2-spatial-context-desktop.png`.
- 2026-07-07: Added Typewolf-style typography reference page. Files changed: `app.py`, `pages/test_typewolf_reference.py`, `PLAN.md`. Result: Lab navigation now includes `Test · Typewolf reference`, a self-contained page reproducing the attached screenshot's dusty background, large white serif masthead, uppercase nav, centered editorial title, metadata, and image/text preview card using static CSS only. Verification: `./.venv/bin/python -m py_compile app.py pages/test_typewolf_reference.py` passed. Screenshot checked: `/private/tmp/ice_typography_pdf/typewolf-reference-page.png`.
- 2026-07-07: Added native-typography questionnaire landing reference page. Files changed: `app.py`, `pages/test_questionnaire_landing_native.py`, `PLAN.md`. Result: Lab navigation now includes `Test · Questionnaire landing`, a Streamlit-native questionnaire landing prototype based on `Test · Typography native` tokens and structure: native title, Fraunces accent voice, measured body copy, translucent rounded containers, metrics, flow preview, and native primary/secondary/tertiary buttons. Verification: `./.venv/bin/python -m py_compile app.py pages/test_questionnaire_landing_native.py` passed. Screenshot checked: `/private/tmp/ice_typography_pdf/questionnaire-landing-native.png`.
- 2026-07-07: Moved WG2 to the native questionnaire typography system. Files changed: `conference/ui.py`, `PLAN.md`. Result: the WG2 participant route now uses the cleaner native prototype tokens: glacier background, Space Grotesk body text, Fraunces accent text, translucent panels, pill-shaped native buttons, quieter helper text, and tighter form controls. Pipeline note: spawning Streamlit and capturing screenshots is relatively token/time expensive, so routine verification is compile/tests only for now; live server and screenshots should be run only when explicitly requested for visual QA. Verification target for this pass: `py_compile` plus focused questionnaire tests; screenshots intentionally skipped.
- 2026-07-07: Tightened WG2 landing information blocks. Files changed: `conference/questionnaire.py`, `conference/ui.py`, `PLAN.md`. Result: `Purpose` and `This pilot` now render as a responsive two-column grid when horizontal space is available and collapse to stacked blocks on mobile; the pilot bullet list uses tighter line height and item spacing to remove unnecessary whitespace. Verification target for this pass: compile/tests only; screenshots intentionally skipped under the lightweight pipeline.
- 2026-07-07: Aligned WG2 landing actions and question page template. Files changed: `conference/questionnaire.py`, `conference/ui.py`, `PLAN.md`. Result: the public landing now uses one keyed Streamlit card containing both the hero content and entry buttons, removing the button/card misalignment. Normal question pages now render as `{progress row} · {section}`, then context paragraph, then main question, then answers/details, then a stable navigation row. Blocked `Continue` writes a reserved validation message above the navigation row while keeping `Continue`, `Flag`, and `Skip` visible. Verification: `./.venv/bin/python -m py_compile conference/ui.py conference/questionnaire.py conference/public_routes.py pages/25_UN_WG2_Icebreaker.py app.py` passed; `./.venv/bin/python -m pytest tests/test_question_set_yaml_loader.py tests/test_conference_registry.py tests/test_conference_flow.py` passed with 19 tests. Screenshots intentionally skipped under the lightweight pipeline.
- 2026-07-07: Tuned WG2 question context hierarchy. Files changed: `conference/questionnaire.py`, `conference/ui.py`, `PLAN.md`. Result: question context now starts with a monospace `Context:` label, uses a slightly larger type size, and has tighter spacing to the main question than the progress row has to the context. Verification: `./.venv/bin/python -m py_compile conference/ui.py conference/questionnaire.py` passed; focused questionnaire tests passed with 19 tests.
- 2026-07-07: Expanded WG2 YAML questionnaire to 15 proposed questions. Files changed: `conference/question_sets/un_wg2_v1.yaml`, `conference/questionnaire.py`, `pages/27_UN_WG2_Host.py`, `tests/test_conference_registry.py`, `tests/test_conference_flow.py`, `PLAN.md`. Result: WG2 now includes active participant-profile questions for expertise, support needs, and work style; the active flow is organized as `I. Who is speaking?`, `II. Spatial context`, `III. Needs`, and `IV. Action`; region is now a separate active question instead of being merged into location; profile fields are stored under participant profile payload; the host page shows proposed questions by the four groups and a YAML-only/disabled section for questions present in YAML but not active. Verification: registry reports YAML source with 15 questions and the requested order; `./.venv/bin/python -m py_compile conference/questionnaire.py pages/27_UN_WG2_Host.py conference/question_sets/yaml_loader.py` passed; focused questionnaire tests passed with 20 tests.
- 2026-07-07: Updated WG2 question context copy. Files changed: `conference/question_sets/un_wg2_v1.yaml`, `PLAN.md`. Result: all 15 active WG2 question context descriptions now use the refined participant-facing copy while preserving IDs, fields, order, options, and grouping. Verification: YAML loader and registry tests passed with 13 tests; registry reports YAML source with 15 questions.
- 2026-07-07: Updated WG2 time-horizon options and accessibility label. Files changed: `conference/question_sets/un_wg2_v1.yaml`, `conference/questionnaire.py`, `PLAN.md`. Result: time horizon options now run from immediate next week through 3 months, seasonal/annual, 3 years, SDG 2030, decade, event-based, century, beyond century, and not sure; hidden text areas now receive non-empty accessible labels to avoid Streamlit label warnings. Verification: `py_compile` passed and focused questionnaire tests passed with 20 tests.
- 2026-07-20: Reworked WG2 overview into a collective mirror. Files changed: `pages/26_UN_WG2_Overview.py`, `PLAN.md`. Result: the public overview no longer starts with technical identifiers; it opens with `Collective Visibility`, early-signal framing, participant/submission/question/last-contribution indicators, and four analytical sections: `Who is speaking?`, `Spatial context`, `Collective needs`, and `Projection-to-decision interfaces`. The page now renders grouped dot-field views for roles, expertise, work styles, regions, domains, needs, support needs, policy interfaces, stakeholders, and uncertainty guidance; time horizons render on an ordered temporal axis with aliases for earlier submitted values; base locations parse consented coordinate payloads and show map points when available; CSV export and technical scope moved into an operator expander. Verification: `./.venv/bin/python -m py_compile pages/26_UN_WG2_Overview.py` passed; focused questionnaire tests passed with 20 tests; direct module import passed. Screenshots intentionally skipped under the lightweight pipeline.
- 2026-07-20: Added WG2 overview question-density diagnostics. Files changed: `pages/26_UN_WG2_Overview.py`, `PLAN.md`. Result: the overview now includes a read-only `Question Density` widget after the opening metrics. It follows the active YAML question order and reports per-question completion, explicit skip events when available, stored flag/skip-note counts, and multi-select response density as average selections per participant plus population standard deviation. Remaining caveat: older skip reasons stored only in `question_flags` appear under flag/skip notes rather than the explicit skip-event column.
- 2026-07-20: Added WG2 Response Field matrix. Files changed: `pages/26_UN_WG2_Overview.py`, `tests/test_wg2_response_field.py`, `PLAN.md`. Result: the overview now renders a participant-by-question response-density matrix after the headline metrics. Rows are anonymous participant labels, columns follow active YAML question order, cell intensity is normalized response extent, and overlays distinguish skipped, flagged, viewed-unanswered, and not-reached states. The widget includes sorting, row focus controls, bottom question summaries, per-participant summaries, privacy-preserving tooltips, and an unobtrusive math note explaining the normalization. Verification: `./.venv/bin/python -m py_compile pages/26_UN_WG2_Overview.py tests/test_wg2_response_field.py` passed; focused overview/questionnaire tests passed with 28 tests. Screenshots intentionally skipped under the lightweight pipeline.
- 2026-07-20: Replaced WG2 flat base-location map with the shared 3D globe. Files changed: `pages/26_UN_WG2_Overview.py`, `ui.py`, `tests/test_wg2_response_field.py`, `PLAN.md`. Result: consented WG2 base-location coordinates now render as aggregated pins on the same Globe.gl component used by `pages/test_geo.py`; duplicate coordinates are combined into one pin with participant count, and the shared helper now supports participant-oriented tooltip labels and route-specific pin color. Verification: `./.venv/bin/python -m py_compile pages/26_UN_WG2_Overview.py tests/test_wg2_response_field.py ui.py` passed; focused overview/questionnaire tests passed with 29 tests. Screenshots intentionally skipped under the lightweight pipeline.
- 2026-07-20: Added WG2 cumulative response timeline. Files changed: `pages/26_UN_WG2_Overview.py`, `tests/test_wg2_response_field.py`, `PLAN.md`. Result: the overview now shows a WG2-scoped `Response Timeline` after the Response Field. It plots cumulative submitted response bundles over time, uses weekly guide lines and month labels rather than day labels, and includes a small math note explaining that the y-axis is running submission count within the filtered WG2 session scope. Verification: `./.venv/bin/python -m py_compile pages/26_UN_WG2_Overview.py tests/test_wg2_response_field.py` passed; focused overview/questionnaire tests passed with 31 tests. Screenshots intentionally skipped under the lightweight pipeline.

## Immediate next step for coding agent

Bounded step:

Run the live checkpoint: open Dalembertiennes, submit one placeholder answer, confirm it appears only in Dalembertiennes overview/export, then add explicit lifecycle controls in admin for draft/open/closed/archived.

Expected result:

Dalembertiennes accepts one placeholder response, the response appears only in Dalembertiennes overview/export, and UNESCO, Complexity, and Pisa remain unchanged.

After completing this step, update this file with:

- timestamp
- files changed
- result
- next action

## Backlog

- [ ] Add `dalembertiennes` event scaffold.
- [ ] Add event-specific question set.
- [ ] Add event lifecycle controls.
- [ ] Add event-specific routes.
- [ ] Add event-scoped response writer enforcement.
- [ ] Add admin event selector.
- [ ] Add event-specific overview.
- [ ] Add event-specific exports.
- [ ] Add duplicate-player review panel.
- [ ] Add player trajectory page.
- [ ] Add persisted job queue in SQLite or Notion.
- [ ] Add runner script for bounded agent tasks.
- [ ] Add scheduler-compatible checkpoint loop.
- [ ] Refactor Decade Map into guided paths.
- [ ] Add report page for Art for the Cryosphere.
