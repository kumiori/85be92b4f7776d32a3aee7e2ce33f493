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

## Recent checkpoints

- 2026-03-XX: UNESCO flow produced response data and overview charts.
- 2026-03-XX: Event logger available in `infra/event_logger.py`.
- 2026-03-XX: Admin page available in `pages/07_Admin.py`.
- 2026-03-XX: Decade map prototype tested, needs guided trajectory redesign.
- 2026-03-XX: Architecture note adopted: event is the primary data boundary.
- 2026-03-XX: Next event codename selected: `dalembertiennes`.

## Immediate next step for coding agent

Bounded step:

Create the Dalembertiennes scaffold in draft state, map it to an explicit `session_code`, and route all writes through explicit session or event context.

Expected result:

`dalembertiennes` appears in admin, has its own question set id, and can be opened without showing or writing UNESCO data.

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
