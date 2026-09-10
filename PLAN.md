# PLAN.md

## Goal

Operate Ice Ice Baby as a multi-event questionnaire engine with explicit,
isolated participation and response scope. The current event is the CISM course
in Udine, codename `prediction`.

## 2026-09-08 checkpoint — CISM / PREDICTION infrastructure

- Added declarative `prediction` and `prediction_debug` event definitions backed by distinct persisted session codes.
- Added a generic `/event?event=<slug>` entry surface plus generic overview and host recovery surfaces.
- Added an identified-event policy with required name/email and optional institution/base location.
- Made player session membership union-preserving so joining another event cannot remove earlier relations.
- Added an explicit participation contract and durable checkpoints in the shared interaction-response store.
- Added normalised-email collision detection and host-only, signed, one-time recovery links.
- Added submission, revision, supersession, and write-idempotency metadata while preserving append-only writes.
- Added an infrastructure-only `prediction_v0` question-set shell; scientific questions remain intentionally absent.
- Added an explicit bootstrap script for production/debug sessions and additive player-profile properties. Page rendering never creates sessions.
- Verification: `139 passed` under `./.venv/bin/pytest -q tests`; repository-wide collection still includes two pre-existing Streamlit page-test collection failures outside `tests/`.

The explicit Notion bootstrap and generic production/debug route verification
are complete. Stop at the infrastructure boundary until the CISM scientific
questionnaire content is supplied.

The immediate objective is to preserve the verified PREDICTION vertical slice
while adding its scientific question schema/content in the next pass. The
existing `session`-based persistence boundary remains authoritative.

## 2026-09-08 checkpoint — platform cleanup before scientific questions

- Replaced CISM implementation-language copy with concise participant language.
- Made Flag and Skip default capabilities of the shared scientific-question
  contract, with explicit answered/unanswered/skipped/flagged checkpoint state.
- Made `?event=prediction&test=1` resolve the debug event/session before reads
  and writes; added repository rejection for mixed PREDICTION scopes.
- Replaced the identified-profile base-location text field with the shared
  semantic location lookup and structured place value.
- Split missing-email guidance from malformed-email feedback without implying
  communication consent.
- Rebuilt displayed event navigation from declarative family metadata:
  Complexity, Young, Prediction, and D'Alembertiennes.
- Simplified the identified-event review/dashboard language and retained the
  access-key screenshot dialog at submission.
- Scientific PREDICTION questions remain intentionally absent.

## 2026-09-08 checkpoint — pre-questionnaire blocker closure

- Diagnosed the missing Flag/Skip display: the generic renderer already owned
  both controls, but the intentionally empty `prediction_v0` set never entered
  a scientific question step; no CISM-specific wrapper was bypassing them.
- Added a temporary debug-only controls fixture with single-choice, scale, and
  free-text questions. It is selected only by
  `/event?event=prediction&test=1&fixture=controls` and is not production or
  scientific questionnaire content.
- Canonicalised generic event URLs to `event`, `test`, `recovery`, `key`, and
  the explicit QA-only `fixture` parameter. `public_route` remains a readable
  compatibility alias; `campaign` remains metadata only. Neither is emitted by
  the generic route.
- Removed duplicate identified-profile introduction copy and changed the
  participant label to `Where are you based? (optional)` without changing the
  durable `base_location` field.
- Reworded the access-key modal around return and assisted recovery, and made
  its confirmation action `I saved a screenshot`.
- Made completion participant-facing: it shows the full access key and hides
  implementation hashes/identifiers in production. Test-only diagnostics remain
  available in a collapsed debug section.
- Fixed the generic event host page to construct its authenticator with the
  configured repository; unauthenticated access now reaches the normal login
  boundary instead of raising a constructor error.
- Browser QA exercised answer, flag, skip, review, submission, and completion
  against the persisted debug session only. Scientific PREDICTION questions
  remain intentionally absent.

## 2026-09-08 checkpoint — universal Flag / Skip grammar

- Added one shared `StepInteractions` capability contract exposing
  `can_flag`, `can_skip`, and disabled-reason copy for every rendered step.
- Moved identity, profile, scientific-question, review, welcome, and completion
  action rendering through the same Flag/Skip helpers; neither control is
  conditionally omitted.
- Required identity keeps Flag active and Skip disabled with the required
  restriction message. Optional profile and scientific fixture steps enable
  both. Review keeps both visible and disabled with guidance to return to an
  editable step.
- Added an optional-profile step to the existing debug-only controls fixture so
  all capability states can be verified without creating CISM questionnaire
  content.
- Browser QA verified stable native-button order, enabled/disabled semantics,
  visible disabled-state help, and the four required visual states in the
  isolated PREDICTION debug session.
- Scientific PREDICTION questions remain intentionally absent.

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

## 2026-09-08 checkpoint — YAML-first questionnaires

- Added the simplified questionnaire metadata model: stable `id`, integer
  `revision`, optional grammar `format`, lifecycle `status`, and lightweight
  review provenance.
- Added stable question IDs, integer question revisions, optional revision
  lineage, explicit retirement, shared dimensions, and legacy-ID aliases.
- Added declarative shared-question references backed by
  `shared_questions.yaml`, with controlled presentation overrides and justified
  option overrides.
- Migrated Complexity to canonical `complexity.yaml`; the existing
  `complexity_v2.py` remains as an equivalence oracle and is no longer the
  runtime registry definition.
- Added the review-state `prediction.yaml` skeleton without scientific
  questions.
- Added clean response provenance alongside legacy `question_set_id`,
  `questionnaire_version`, `schema_id`, and `text_id` compatibility fields.
- Added generic revision/re-ask recognition and retired-question filtering.
  Earlier answers remain in append-only response rows.
- Documented the final grammar, compatibility map, cross-session dimensions,
  and migration risks in `docs/questionnaire_yaml.md`.

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
- Static routes are declared in `app.py`; generic event pages resolve
  `?event=<slug>` without creating a dynamic `/event/:slug` router.
- Player schema already has concrete columns such as `access_key`, `role`, `last_seen`, `phrase`, `emoji_suffix_4`, and `emoji_suffix_6`.
- Current event line is `prediction`; production and debug use distinct
  persisted sessions.

## Current event

### Codename

`prediction`

### Working title

CISM-EUROMECH Advanced Course — PREDICTION

### Purpose

Identified scientific-event questionnaire for “Damage and Fracture Mechanics
of Fluid-Infiltrated Geomaterials”, Udine, 7–11 September 2026.

The event has its own production/debug session pair, participation checkpoints,
responses, overview, host recovery surface, and aggregate scope.

### Primary risk to avoid

Data mingling with IceIceBaby production records or with PREDICTION debug data.

## Next action

Add the supplied CISM scientific questionnaire schema/content to
`prediction_v0` (or create its explicit next version), preserving the verified
identity, participation, recovery, idempotency, and session-isolation contracts.

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

- 2026-09-07: Added reusable persisted test-session isolation and applied it to WG2. `conference/test_sessions.py` now defines an idempotent debug-session primitive that refuses to reuse a production session code plus a durable host-control reducer that is closed by default. WG2 test mode resolves `?test=1` to the dedicated `un_wg2_debug_2026` session only while the authenticated host toggle is enabled; it reuses the `un_wg2_v1` question set while payloads and events carry the debug event slug, `test_mode = true`, `data_classification = debug`, and `response_scope = debug_session`. The participant route displays a persistent `TEST MODE` notice, disables production-credential reuse, resets browser draft/cache/device state when crossing production and debug sessions, and normal event selectors hide test events. The funding mixer shares the deliberate host gate and debug session, but remains separated by interaction/text id. Production/debug scope cross-pairing is rejected. The same primitive and isolation rules are now part of `AGENTS.md` for future event implementations. The idempotent bootstrap script created the live Notion debug session; live read-only verification found 12 production WG2 submissions and 0 debug submissions. Verification: all 132 tests in `tests/` pass and `git diff --check` passes; broad pytest discovery remains polluted by unrelated experimental `pages/test_*.py` files that are excluded from this delivery.
- 2026-09-05: Corrected and completed the WG2 member-claim operator path after live QA. Live read-only verification found 12 WG2-scoped response trajectories: 9 identified and 3 anonymous. The member directory now includes all 12, marks anonymous contributors as included/non-claimable, and links pending claims directly to `WG2 Host → Member recovery`. A host-controlled `Allow public claiming` switch opens or closes logged-out claiming; its state is session-scoped, closed by default, and derived from append-only enable/disable events rather than browser state. The host surface also explains and exposes claim approval, one-time-link preparation, and append-only `Revoke and allow retry`; revocation resets the recovery workflow without deleting responses or silently removing an approved email. The event reader now resolves the configured Notion database to its data-source id and tolerates null date/relation values. Event writes return their persistence result, and claim/reminder/revoke/link UI no longer reports success or exposes a token when its ledger event failed. Live verification found no stored recovery event for the claim made before this correction, so that claim must be resubmitted. Verification: focused tests and `git diff --check` pass.
- 2026-09-05: Completed WG2 schema evolution and participant-alignment workstream. Files changed: `conference/question_sets/__init__.py`, `conference/question_sets/yaml_loader.py`, `conference/question_sets/un_wg2_v1.yaml`, `conference/wg2_schema.py`, `conference/flow.py`, `conference/questionnaire.py`, `conference/registry.py`, `conference/events.py`, `conference/repo.py`, `docs/routes/un_wg2_route_icebreaker.md`, `tests/test_wg2_schema_evolution.py`, `tests/test_wg2_response_field.py`, `PLAN.md`. Result: the stable `un_wg2_v1` catalogue now declares schema `questionnaire_v2`; the answered `UN_WG2_ROLE_LENS` definition remains immutable in `legacy_questions`; active question `UN_WG2_ROLE_LENS_V2` splits core group from leadership with explicit revision metadata; response payloads persist question-set, schema, and questionnaire version; the alignment service classifies current, refinement, new, and legacy-only answers; and a clarification produces an append-only response bundle retaining the old answer, response id, revision reason, new answer, and timestamp. Verification: focused schema, YAML, registry, flow, repository, overview, and UX tests pass.
- 2026-09-05: Completed WG2 existing-participant recovery and claiming workstream. Files changed: `app.py`, `conference/questionnaire.py`, `conference/wg2_members.py`, `pages/27_UN_WG2_Host.py`, `pages/32_UN_WG2_Member.py`, `tests/test_wg2_member_recovery.py`, `PLAN.md`. Result: `/un-wg2-member` derives its candidates from WG2-scoped responses outward, protects the pilot list, masks stored email, creates pending claims when email is absent, and resolves signed one-time links to the existing player without minting a new identity. The host panel shows response count, schema, alignment, email/recovery status, response inspection, and claim approval/rejection without displaying raw credentials. Recovery delivery is explicitly host-assisted through a prepared email because this repository has no configured transactional email transport. Verification: focused recovery tests cover scoping, cross-event isolation, latest append-only bundle selection, masking, pending claims, existing-player updates, signed expiry/session checks, route wiring, and refinement UI.
- 2026-09-05: Corrected WG2 member routing after admin-login QA. A generic authenticated `player_page_id` was incorrectly treated as the trajectory being recovered, so an administrator without a WG2 response saw a terminal participant-mismatch warning. Route selection now distinguishes host/admin directory access, explicit one-time-link recovery, matching WG2 participants, and unrelated participant logins. The superseded credential-reveal renderer was removed from the host page rather than retaining two recovery systems. Verification: the exact admin regression test failed before the correction and passes afterward; 79 focused tests pass.
- 2026-07-31: Completed the WG2 review and orientation UX follow-up without changing questionnaire content. Files changed: `app.py`, `conference/questionnaire.py`, `conference/ui.py`, `conference/wg2_ux.py`, `pages/27_UN_WG2_Host.py`, `pages/28_UN_WG2_Info.py`, `tests/test_wg2_ux.py`, `PLAN.md`. Result: each review answer now has a compact tertiary `Edit` control aligned at the right of its row; the redundant pre-submission `Back to questions` action was removed; `/un-wg2` now provides a simple public orientation page for people outside and inside WG2; and the host-only access panel is now named `Access help`, states its credential-recovery purpose, distinguishes an empty questionnaire from an unresolved participant record, and can recover only WG2-scoped participant records whose access-key hashes appear in WG2 submissions. Questionnaire IDs, wording, fields, ordering, and response semantics were not changed. Verification: Python compilation passed; 49 focused tests passed; `git diff --check` passed; the new public page was inspected at desktop and narrow viewport widths. The review card itself was not forced through the live route because that would require creating participant data; its structure and absence of the old action are covered by focused tests.
- 2026-07-31: Completed the tester-driven WG2 UX sprint, explicitly separate from questionnaire-content work. Files changed: `conference/wg2_ux.py`, `conference/flow.py`, `conference/questionnaire.py`, `pages/27_UN_WG2_Host.py`, `tests/test_wg2_ux.py`, `PLAN.md`. Result: WG2 location entry now performs a debounced automatic approximate lookup, preserves raw and resolved location fields, supports confirmation, correction, and non-blocking failure fallback, and logs the lookup lifecycle. Review cards now open one prepopulated answer in a dialog and return directly to review; pre-submission edits update only the draft, while post-submission edits append a scoped revision row. The WG2 host route now requires an authenticated host/admin role and includes participant access support with credentials hidden by default, deliberate reveal, reminder preparation, manual sent/resend status, event logging, and CSV export that excludes full credentials unless explicitly requested. Questionnaire IDs, wording, field names, response semantics, and ordering were not changed. Verification: Python compilation passed; 46 focused tests passed across WG2 UX, flow, registry, YAML loading, and repository contracts; `git diff --check` passed. The broader `pytest` collection remains blocked by pre-existing page-test import errors, and `pytest tests` has one pre-existing failure in the dirty `conference/events.py` path. Next action: run a deliberate browser QA pass for the timed lookup, answer-edit dialog, and protected host panel with test credentials before live WG2 use.
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

## Checkpoint — 2026-08-31 · WG2 funding mixer

- Files changed: `app.py`, `conference/wg2_funding_mixer.py`, `pages/29_WG2_Funding_Mixer.py`, `tests/test_wg2_funding_mixer.py`, `PLAN.md`.
- Result: added the dedicated `/wg2-funding-mixer` interaction with six scarcity-coupled channels totalling exactly 100, existing access-key entry, append-only revisioned writes to the explicitly resolved `?session=` Notion session, and a live `?results=1` aggregate showing median, range, anonymous traces, and participant count. The response identity is `seed_funding_allocation` / `wg2_funding_mixer_v1`; the default session code is `wg2-meeting-3`, but writes fail closed if that session does not resolve.
- Event logged: `page_view`, `allocation_committed`, and `allocation_write_failed` through `infra/event_logger.py` under `iceicebaby.wg2_funding_mixer`.
- Visualisation impact: participant mode is a stripped-back mixing console; reveal mode refreshes every five seconds and uses only the latest revision per anonymous participant while retaining every revision in storage.
- Next action: create or confirm the `wg2-meeting-3` persisted session, then test participant and reveal URLs inside the actual HackMD slide view, including mobile height and framing headers.

### Correction — Philoui and persisted session

- The first route pass styled native Streamlit sliders; the intended control is Philoui's `CustomStreamlitSurvey.equaliser`, backed by `streamlit-vertical-slider`. The route now imports that package API and the application pins Philoui commit `eed2e5e` with its Streamlit 1.62 runtime requirement.
- Added `scripts/bootstrap_wg2_funding_mixer_session.py`, an idempotent bootstrap for the missing `wg2-meeting-3` Notion session. It preserves `session` as the durable boundary and does not reuse or contaminate `un_wg2_core_2026`.

### UX finish pass — six-scientist milestone

- Files changed: `conference/wg2_funding_mixer.py`, `pages/29_WG2_Funding_Mixer.py`, `tests/test_wg2_funding_mixer.py`, `PLAN.md`.
- Identity entry now shows the emoji key directly and links to existing recovery/login and onboarding routes.
- The mixer now has seven full-title channels with one-sentence definitions, including a conditional `Other` note. Philoui equaliser values are the source of truth: the headline reports allocated and remaining tokens live, allocations may remain partial while editing, peer channels contract proportionally on overflow, and commit remains disabled until the sum is exactly 100.
- Successful writes remain append-only and revisioned. A successful revision produces one transient canvas-confetti burst, a persistent confirmation, and a separate `Revise allocation` action before another revision can be committed.
- Visual treatment uses softer page-matched framing so the fader tracks remain dominant.
- Verification: focused allocation and interaction-repository tests pass; fresh Streamlit browser check confirms the unmasked emoji entry and both identity actions. A real participant-linked commit was intentionally not created during visual QA.

### Celebration and privacy correction

- Renormalisation to the 100-token ceiling now produces a one-shot toast on the stable rerun.
- Persistent commit confirmations no longer expose even the shortened access key.
- Confetti moved out of the custom-component iframe and into a fixed, full-viewport CSS layer in the main page, with reduced-motion support; it still triggers only once for each successfully written revision.

### Backup and dedicated aggregate results

- A committed mix now exposes a downloadable `wg2-funding-mix-<session>-revision-<n>.json` backup. The portable document contains session, revision, phase, timestamp, allocation, total, and the optional Other note, while deliberately excluding the access key, participant hash, player id, and device id. Downloads emit `allocation_backup_downloaded` in the event log.
- Added `/wg2-funding-mixer-results?session=wg2-meeting-3`, a read-only live page showing participant count, total committed revisions, median and observed range per channel, and faint anonymous latest-revision traces. It refreshes every five seconds and remains explicitly scoped to the resolved persisted session.

## Immediate next step for coding agent

## Checkpoint — 2026-09-09 · Canonical Prediction and sessions routing

- Files changed: `app.py`, `conference/events.py`, `conference/public_routes.py`, `conference/session_routes.py`, `conference/questionnaire.py`, `pages/33_Event.py`, `pages/34_Event_Overview.py`, `pages/35_Event_Host.py`, `pages/36_Prediction.py`, `pages/37_Sessions.py`, `tests/test_session_routes.py`, `tests/test_platform_requirements.py`, `README.md`, `AGENTS.md`, `PLAN.md`.
- Result: `/prediction` is the canonical Prediction dispatcher. The explicit `view=results` and `view=host` values select subviews; absent or unknown values safely render Join. `test=1` composes with all views. The public top navigation contains only Join and Results; Host and Test are developer-sidebar links and are not rendered in the deployed production interface. Recovery links return to the canonical route, and `/sessions` lists production session entry points without test flags.
- Compatibility: `/event`, `/event-overview`, and `/event-host` remain registered as hidden aliases. Canonical UI links do not emit the legacy `event=prediction` parameter or bare query flags.
- Verification: pure route-contract tests cover direct URL generation, unknown-view fallback, production/test composition, test preservation across subviews, and the production sessions index. No browser or screenshot testing was used, per deployment instruction.
- Next action: deploy the canonical route and generate the public QR from `/prediction` only.

## Checkpoint — 2026-09-09 · Prediction editorial results portrait

- Files changed: `conference/events.py`, `conference/editorial_results_ui.py`, `conference/prediction_results.py`, `conference/repo.py`, `pages/34_Event_Overview.py`, `tests/test_prediction_results.py`, `tests/test_conference_repo.py`, `tests/test_platform_requirements.py`, `PLAN.md`.
- Result: `/event-overview?event=prediction` now renders a long-form scientific portrait using the UNESCO Opening visual language. Opening copy and interpretation prompts live in the event result configuration; all 13 question titles, contexts, option labels, types, and order resolve from `prediction.yaml`. Reusable renderers cover categorical bars with explicit answered denominators and restrained anonymous text excerpts.
- Event scope: the page resolves the same persisted production/debug session pair as the questionnaire. `?event=prediction&test=1` reads only `prediction_debug_2026`, while the production URL reads only `prediction_2026`. Flag and Skip metadata are counted separately and excluded from scientific distributions.
- Verification: focused aggregation, repository-normalisation, event-resolution, and navigation tests pass. Live browser QA against the debug route verified the opening, first and middle categorical sections, contribution text section, final challenge section, all 13 YAML-derived questions, alternating editorial rhythm, and debug-only signal totals.
- Next action: deploy and perform a hosted read-only smoke check of the debug results URL; defer authored interpretation and cross-question analysis until real CISM data is available.

## Checkpoint — 2026-09-09 · Prediction flag/skip semantics and live debug QA

- Files changed: `conference/question_sets/prediction.yaml`, `conference/question_sets/yaml_loader.py`, `conference/question_flags.py`, `conference/question_skips.py`, `conference/flow.py`, `conference/questionnaire.py`, `pages/19_Pisa_Experiment.py`, `tests/test_question_interaction_semantics.py`, `tests/test_yaml_first_questionnaires.py`, `tests/test_questionnaire_performance.py`, `PLAN.md`.
- Result: Flag is now independent question feedback with positive and critical reasons; Skip is an optional response-state reason with its own taxonomy. Both states coexist, Other-detail reveal is generic, and the shared-question override grammar accepts an explicitly justified `free_text` override without changing `shared.role` globally. Prediction uses the revised identity and Q1–Q13 copy.
- Event scope: browser QA created one synthetic participant and one submission only in `prediction_debug_2026`. A fresh browser session recovered the debug-scoped saved record by access key; production was not opened or written.
- Verification: live `event=prediction&test=1` QA covered Q1/Q2/Q3 Other reveal, positive and critical flags, skip with and without a reason, answered+flagged, skipped+flagged, skip after choosing an answer, revised Q8/Q10/Q11 wording, review, submission, and fresh-browser recovery. The complete suite passes with `180 passed`.
- Next action: deploy this bounded change and repeat only a read-only smoke check on the hosted debug URL before authoring further scientific content.

## Checkpoint — 2026-09-09 · Questionnaire transition performance

- Files changed: `conference/questionnaire.py`, `conference/repo.py`, `repositories/interaction_repo.py`, `infra/event_logger.py`, `tests/test_questionnaire_performance.py`, `tests/test_platform_requirements.py`, `tests/test_event_logger_data_source.py`, `PLAN.md`.
- Result: ordinary `Continue` transitions now reuse the participant resolved by the first durable identity checkpoint, append the next recovery checkpoint without a redundant read of all prior checkpoints, skip irrelevant scientific-question lookup for checkpoint records, and keep `page_view` / `question_answered` / blocked-navigation telemetry in application logs without synchronous Notion event writes. The required durable checkpoint write remains synchronous before advancing.
- Event scope: cached participant bindings include the persisted session id and an access-key hash and are cleared whenever the production/debug session scope changes.
- Observability: application logs now report `perf.checkpoint_player_resolve_ms` and `perf.checkpoint_write_ms`, including whether the participant binding was reused.
- Verification: performance regression tests constrain repeat navigation to one participant upsert per browser scope, one checkpoint write per completed step, zero checkpoint-history reads, and zero Questions-database lookups for checkpoint records. Full-suite verification passed with 174 tests.
- Next action: deploy and compare Cloud logs for the first identity transition versus later scientific-question transitions; later transitions should be dominated by the single `checkpoint_write` measurement.

## Checkpoint — 2026-09-09 · Graceful Notion throttling

- Files changed: `infra/notion_repo.py`, `conference/questionnaire.py`, `tests/test_notion_rate_limit_handling.py`, `PLAN.md`.
- Result: Notion 429 retries now honour `Retry-After`; public session-resolution and checkpoint throttling show a calm retry message rather than exposing a Streamlit traceback. The current per-tab draft is retained for retry, while durable recovery continues from the last successful checkpoint.
- Event scope: shared questionnaire infrastructure; no event data, response schema, or questionnaire content changed.
- Verification: focused retry, checkpoint, platform, and Prediction tests pass (`36 passed`); compile check passes. Full suite reports `194 passed` and the same two unrelated failures from the existing dirty questionnaire YAML/revision work.
- Next action: deploy and confirm a forced/transient Notion 429 presents the retry state without losing the open-tab draft.

## Checkpoint — 2026-09-09 · Prediction one-go persistence

- Files changed: `conference/events.py`, `conference/questionnaire.py`, `tests/test_questionnaire_performance.py`, `tests/test_prediction_vertical_slice.py`, `PLAN.md`.
- Result: Prediction production and test sessions now declare `integration_only` persistence. Their event session is resolved once per open browser flow; answer, flag, skip, and structural-step navigation remain in browser session state without Notion checkpoint or telemetry writes. Final Integration remains idempotent and writes the completed response; a temporary throttle leaves the participant on Review for retry.
- Event scope: only `prediction` and `prediction_debug`; checkpointed persistence remains the default for every other event.
- Verification: focused questionnaire, rate-limit, interaction, and Prediction tests pass (`43 passed`). Full suite reports `197 passed` with the same two unrelated failures from existing dirty questionnaire YAML/revision work.
- Operational limitation: one-go drafts survive Streamlit reruns in the open tab, but deliberately do not promise recovery after tab closure or server restart before Integration.
- Next action: deploy and complete one test-mode Prediction run, verifying no Notion writes occur between About You and Review and Integration can be retried idempotently.

## Checkpoint — 2026-09-09 · Stabilise Prediction results layout

- Files changed: `pages/36_Prediction.py`, `tests/test_prediction_route_page.py`, `PLAN.md`.
- Result: the canonical `/prediction` dispatcher now establishes the Streamlit page shell before rendering shared route navigation, preventing the Results navigation from inheriting the oversized default top inset and appearing clipped.
- Event scope: presentation-only; no questionnaire, response, session, or aggregate data changed.
- Verification: focused Prediction route/results tests pass (`9 passed`). The full suite has `191 passed`, with two pre-existing failures caused by the unrelated dirty questionnaire YAML/revision edits.
- Next action: refresh the running local `/prediction?view=results` page; Streamlit hot reload should show the corrected top spacing.

## Checkpoint — 2026-09-09 · Activate PREDICTION YAML questionnaire

- Files changed: `conference/question_sets/prediction.yaml`, `tests/test_conference_registry.py`, `tests/test_yaml_first_questionnaires.py`, `README.md`, `PLAN.md`.
- Result: the production PREDICTION route now accepts the reviewed YAML questionnaire as active and resolves all 13 scientific questions in the configured standard flow. The durable `prediction_v0` identifier remains unchanged for compatibility with existing sessions and stored responses.
- Event scope: both `prediction_2026` and `prediction_debug_2026` reuse the same YAML question catalogue while retaining their separate persisted session boundaries.
- Verification: the focused activation regression test passed and the complete repository suite passed with 170 tests.
- Next action: deploy the change and confirm the production `/event?event=prediction` identity step advances to the first scientific question against the persisted `prediction_2026` session.

## Checkpoint — 2026-09-10 · Generic session Host cockpit

- Files changed: `app.py`, `conference/events.py`, `conference/host.py`, `conference/host_ui.py`, `pages/16_Pisa_Meeting_Host.py`, `pages/23_Dalembertiennes_Host.py`, `pages/27_UN_WG2_Host.py`, `pages/35_Event_Host.py`, `pages/38_Host.py`, `tests/test_generic_host.py`, `tests/test_wg2_member_recovery.py`, `tests/test_wg2_ux.py`, `PLAN.md`.
- Result: `/host` is the single visible session-operator cockpit. It selects questionnaire-backed production/debug sessions from the existing registry, acquires one normalized `HostSnapshot`, and derives summary metrics, masked participant rows, Response Field, cumulative Response Timeline, spatial context, question-set inspection, submissions, and event-log views locally. Results pages remain separate scientific portraits.
- Compatibility: `pisa-meeting-host`, `dalembertiennes-host`, `un-wg2-host`, and `event-host` remain hidden thin wrappers that preselect the corresponding session; `test=1` resolves the paired debug session before loading data.
- Remote-read budget: one snapshot acquisition performs one session resolution, one scoped response read, one scoped participant read, and one scoped event-log read. Session choices and questionnaire definitions are local. Tab, sort, and filter reruns reuse the session-state snapshot until the operator selects Refresh data.
- Verification: generic host tests pass (`8 passed`), compile and diff checks pass. The repository test directory reports `205 passed`, with two unrelated failures from pre-existing dirty Prediction revision metadata and Complexity YAML/Python content drift. No browser or screenshots were used.
- Next action: resolve the separate Prediction questionnaire revision-validation edits, then deploy and perform an operator-led read-only smoke check of `/host`.

Bounded step:

## Checkpoint — 2026-09-10 · Prediction profile persistence and Host join repair

- Files changed: `conference/questionnaire.py`, `conference/repo.py`, `conference/host.py`, `infra/notion_repo.py`, `scripts/bootstrap_prediction_sessions.py`, `scripts/migrate_player_profile_schema.py`, `tests/test_questionnaire_performance.py`, `tests/test_generic_host.py`, `tests/test_player_profile_schema.py`, `PLAN.md`.
- Result: Integration emits presence-only `integration.pre_persist.*` diagnostics immediately before identified-player persistence. Supplied canonical profile fields now fail loudly when unmapped. Structured base location survives as label, place id, latitude, and longitude; Host joins the selected session's Players in one batch and includes participant base locations independently of questionnaire geography.
- Live schema: added `email`, `institution`, `base_location`, `base_location_label`, `base_location_place_id`, `base_location_lat`, `base_location_lon`, and the canonical `session` relation. The existing `events` relation was preserved after direct inspection showed that it targets the event-log database, not Sessions.
- Isolated debug acceptance: a fresh post-migration Prediction debug Integration created Player `3d754516-e9e1-8158-b964-d626d8eef94a` and response `3d754516-e9e1-81e8-a26d-fd3b21b23c8b`. All four pre-persist flags were true; email, institution, structured Udine location, automatic session membership, batch retrieval, masked Host email, and spatial point were verified. No production or legacy profile values were backfilled.
- Remote-read budget: Host participant acquisition remains one filtered Players query for the selected session; there is no per-participant lookup loop.
- Verification: focused profile/Host/Prediction/platform suite passes (`68 passed`); full repository tests report `213 passed` and the same two unrelated dirty questionnaire failures. Compile and diff checks pass. No browser or screenshots were used.
- Next action: refresh the Host snapshot explicitly after deployment; existing lost profile values remain absent until their participant submits an update.

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
