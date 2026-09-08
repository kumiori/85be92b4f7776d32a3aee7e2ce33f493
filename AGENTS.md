# AGENTS.md

## Project

Ice Ice Baby / Decade Coordination Map is a Streamlit + Notion app for participatory climate, cryosphere, laboratory, and collective-decision experiments.

## Purpose

Support long-running participatory events where users create access keys, respond to questionnaires, place contributions, and generate collective traces over time.

The system must now support multiple real-world events without mixing responses, questions, participants, or aggregated results.

The current multi-event implementation target is the CISM-EUROMECH course in Udine, codename `prediction`. Its production/debug infrastructure is implemented; scientific questionnaire content is the next bounded pass.

## Main subsystems

- Streamlit frontend.
- Notion backend.
- Event registry and lifecycle management.
- Question sets and versioned question catalogues.
- Participant and access-key management.
- Response storage with explicit event scope.
- Admin/operator interface in `pages/07_Admin.py`.
- Append-only event logging through `infra/event_logger.py`.
- Live overview, analytics, exports, and report pages.
- Future durable job state in SQLite or Notion.

## Core architecture principle

In the current codebase, the durable boundary is still `session`, not `event`.

- `session_code` and `session_id` drive resolution in `infra/notion_repo.py`, `conference/context.py`, `conference/repo.py`, and `models/catalog.py`.
- player rows relate to `session`.
- interaction responses are queried by `session_id`.
- page routing is static Streamlit navigation, not a dynamic `/event/...` router.

So the correct implementation strategy is:

1. Preserve `session` as the persisted boundary for now.
2. Introduce `event` as an application-level label or resolver on top of `session`.
3. Add explicit mappings only where needed, instead of renaming the whole system in one pass.

This is the rule that prevents data mingling without breaking the existing app.

## Core entities

### Event

Represents one real-world gathering at the product level.

In the current implementation, this should usually resolve to one existing session record plus optional metadata rather than a fully separate persistence model on day one.

Examples:

- `unesco-opening`
- `prediction`
- `prediction_debug`
- `dalembertiennes`
- `cop31-side-event`
- `wg2-workshop`
- `student-pilot`

Suggested fields:

- `id`
- `slug`
- `title`
- `description`
- `location`
- `organisers`
- `start_datetime`
- `end_datetime`
- `visibility`
- `status`
- `questionnaire_version`
- `question_set_id`
- `created_at`

### Session

This is the current persisted boundary already used throughout the codebase and Notion schema.

Observed or normalized fields in code:

- `id`
- `session_code`
- `session_id`
- `session_name`
- `session_title`
- `session_description`
- `session_order`
- `session_visualisation`
- `status`
- `mode`
- `round_index`
- `session_active`
- `start`
- `end`

Implementation rule:

- if a new `Event` abstraction is introduced, it must resolve to one `session_code` explicitly;
- do not silently replace `session` with `event` in repositories, page state, or Notion relations.

### Event lifecycle

Every event has a lifecycle:

- `draft`: questions and settings are being prepared; invisible to participants.
- `open`: participants can access and respond.
- `closed`: no more responses; results remain visible.
- `archived`: immutable historical record.

Once an event is closed or archived, its responses must be treated as read-only.

### Question Set

An event points to exactly one question set.

A question set is reusable and versioned. Different events may reuse the same question set or use different versions.

Fields:

- `id`
- `title`
- `version`
- `language`
- `questions[]`

### Question

Each question belongs to a question set.

Fields:

- `id`
- `question_set_id`
- `section`
- `order`
- `type`
- `wording`
- `options`
- `metadata`

Question IDs should be stable. Changing wording should create a new version rather than rewriting historical questions.

### Participant

Participants already exist in the codebase as player rows in the players database.

Use the current database column names and current normalized keys before inventing new ones.

Observed database columns from code and attached table:

- `Name`
- `access_key`
- `decisions`
- `emoji`
- `emoji_suffix_4`
- `emoji_suffix_6`
- `moderation_votes`
- `phrase`
- `questions_submitted`
- `responses`
- `status`
- `last_seen`
- `role`
- `events`

Additional columns used by the repo when present:

- `session`
- `nickname`
- `nickname_title`
- `consented`
- `consent_research`
- `joined_at`
- `last_joined_on`
- `preferred_mode`
- `email`
- `intent`
- `motivation`

Normalized player keys in code should remain:

- `id`
- `access_key`
- `nickname`
- `role`
- `session_ids`
- `status`
- `consent_play`
- `consent_research`
- `created_at`
- `joined_at`
- `last_joined_on`
- `email`
- `intent`
- `preferred_mode`

If `Participant` is introduced as a richer domain term, map it onto these fields rather than replacing them all at once.

### Participation

A participation is one participant’s trajectory through one persisted `session` or product-level `event`.

This is an additive concept, not a replacement for current session links. The
current implementation checkpoints participation through the shared
interaction-response store so it works without a destructive historical-data
migration.

Suggested fields:

- `participation_id`
- `participant_id`
- `session_id`
- optional `event_slug`
- `started_at`
- `last_seen_at`
- `status`
- `device_id`
- `current_position`
- `progress`
- `completion_state`
- `created_at`
- `updated_at`

For identified events, profile fields such as name, normalised email,
institution, and base location belong to the participant profile and must not
be encoded as scientific answers. Email is a recovery lookup handle, not an
authentication factor; the access key remains the participant credential.

### Response

The current response writer already targets a richer schema than this draft describes.

Current response properties written or resolved in `repositories/interaction_repo.py` include:

- `session`
- `player`
- `question`
- `question_id`
- `item_id`
- `value_json`
- `response_value`
- `value_label`
- `question_type`
- `score`
- `timestamp`
- `submitted_at`
- `created_at`
- `page_index`
- `depth`
- `optional_text`
- `text_id`
- `device_id`
- `access_key`

Implementation rule:

- additive fields like `event_slug` or `question_set_id` are acceptable;
- do not propose a response contract that ignores the existing `session` and `text_id` write path.

## Naming convention

Avoid ambiguous use of `session`, but do not erase the term where it already means something concrete in code and data.

Use:

- `Event` for the product-level real-world gathering.
- `Session` for the current persisted Notion object and current repository boundary.
- `Participation` for a participant’s interaction within a session or event.
- `Browser session` only for temporary Streamlit/session-state context.

Migration rule:

- when the code says `session_id`, check whether it means persisted session, browser state, or event-like grouping before renaming anything.

## Navigation model

The app currently uses static `st.Page(...)` declarations in `app.py` plus a few `url_path=` aliases and `st.switch_page(...)` calls.

Current top-level routes/pages:

- `pages/Splash.py`
- `pages/011_Intro.py`
- `pages/01_Login.py`
- `pages/02_Home.py`
- `pages/03_Resonance.py`
- `pages/04_Questions.py`
- `pages/05_Decisions.py`
- `pages/06_Coordination.py`
- `pages/08_Overview.py`
- `pages/09_Player.py`
- `pages/12_Report.py`
- `pages/13_UNESCO_Opening.py` with `url_path="unesco-opening"`
- `pages/15_Pisa_Meeting.py` with `url_path="complexity"`
- `pages/16_Pisa_Meeting_Host.py` with `url_path="pisa-meeting-host"`
- `pages/17_Young_Overview.py` via `YOUNG_OVERVIEW_PAGE` with `url_path="young-overview"`
- `pages/18_Pisa_Opening.py` with `url_path="pisa-opening"`
- `pages/19_Pisa_Experiment.py` with `url_path="pisa"`
- `pages/20_Complexity_Overview.py` via `COMPLEXITY_OVERVIEW_PAGE` with `url_path="complexity-overview"`
- `pages/33_Event.py` with `url_path="event"` and `?event=<slug>`
- `pages/34_Event_Overview.py` with `url_path="event-overview"` and `?event=<slug>`
- `pages/35_Event_Host.py` with `url_path="event-host"` and `?event=<slug>`
- `pages/14_Decade_Map.py`
- `pages/07_Admin.py`

The generic event entry point is query-param based (`/event?event=<slug>`), not
a dynamic path such as `/event/dalembertiennes`. Event resolution must not
create persisted sessions while rendering a page.

Preferred implementation choices:

1. resolve an event/session slug in page logic or query params;
2. reuse existing pages where possible;
3. only add new `url_path` aliases when a new public entry point is truly needed.

Every page that writes or aggregates data must know which `session_code` or resolved `event_slug` it belongs to.

## Back office model

Each event should expose, at minimum:

- Overview.
- Questions.
- Participants.
- Responses.
- Analytics.
- Settings.
- Exports.

Event creation flow:

1. Admin clicks `New Event`.
2. Provides title, slug, date, location, question set.
3. Publishes event.
4. Landing page or page resolver is generated.
5. Questionnaire resolves to one `session_code`.
6. Responses are isolated automatically.
7. Results and report pages point to the session or event resolver explicitly.

## Core principles

- Mobile-first.
- One screen = one action.
- Main area is for action.
- Sidebar is for extended info, orientation, and operator context.
- No expanders in question flows.
- Preserve trajectories. Do not overwrite historical responses.
- Prefer append-only event logging, blockchain-like.
- Data must be interpretable as collective signals, not only dashboard metrics.
- Never trust `st.session_state` for durable work.
- Never aggregate without explicit session or event scope.
- Never allow a response write without session context, question identity, and text bundle identity.
- Persist completed steps incrementally; never treat browser state as a checkpoint.
- Keep participant identity separate from session-scoped participation.
- Make retries idempotent and intentional revisions append-only with explicit supersession metadata.
- Never use email alone to grant participant access; recovery remains host-assisted and access-key based.
- Check `app.py` and `st.switch_page(...)` calls before proposing new routes.

## YAML-first questionnaire contract

- Canonical questionnaire files use stable semantic filenames and IDs without
  revision suffixes. Content evolution uses integer `revision`; YAML grammar
  compatibility uses `format`; publication uses `status`.
- New questions use stable semantic IDs plus integer revisions and optional
  `supersedes_revision`/`change` lineage. Historical IDs remain aliases and
  historical response rows are never rewritten.
- Shared definitions live in `shared_questions.yaml` and are referenced with
  `use: shared.<name>`. Presentation overrides are controlled; shared option
  overrides require an explicit reason.
- Retired questions remain historically resolvable but are excluded from active
  participant flow.
- New response bundles store `questionnaire_id`, questionnaire revision, and
  per-question revision provenance. Keep `text_id`, `question_set_id`,
  `questionnaire_version`, and `schema_id` as internal compatibility fields
  while current Notion records and readers depend on them.
- A production route serves only an `active` questionnaire. Review definitions
  may be exercised through an explicitly isolated test session.

## Platform interaction invariants

- Every rendered questionnaire step exposes `can_flag`, `can_skip`, and
  optional disabled-reason copy through the shared step-interaction contract.
- Flag and Skip are always rendered in a stable action row. Availability may
  change, visibility may not: unsupported actions are disabled native buttons
  with concise keyboard-accessible help and visible explanatory copy.
- Required identity enables Flag and disables Skip. Optional profile and normal
  scientific steps enable both. Review displays both as inactive and directs
  the participant back to an editable step.
- Every scientific `QuestionDefinition` exposes Flag and Skip by default.
- Skip means intentionally unanswered. It is distinct from unanswered/not yet
  visited, lost browser state, and validation failure.
- Flag may coexist with answered or skipped. Both skip and flag state must be
  included in durable checkpoints and restored on resume/recovery.
- A question may disable Skip only through explicit structural configuration
  (`skippable=False`). This is for genuinely non-skippable structural steps,
  not ordinary scientific questions.
- Review surfaces show the actual question, answer or `Skipped` state, and flag
  indicator in participant language.
- A controls fixture may exist for debug-only platform QA, but it must require
  an explicit test-session selector, remain unreachable from production, and
  never be presented as scientific event content.

## Public URL and completion invariants

- Generic event links emit the smallest sufficient query contract: `event`,
  plus `test=1` for deliberate debug use. Recovery credentials and explicit
  debug fixtures are additive only when that flow requires them.
- `public_route` may be read as a legacy compatibility alias but is not emitted
  by the generic event flow. `campaign` is metadata, not a routing requirement.
- Identified-event copy must describe the access key as the return credential
  and email only as a host-assisted recovery handle.
- Production completion surfaces show participant-facing confirmation and the
  full access key. Internal hashes, ASCII encodings, response identifiers, and
  similar diagnostics must not be shown in production; test diagnostics may be
  available in a collapsed, explicitly labelled debug surface.

## Semantic field invariants

- Every field with semantic type `location` uses the shared lookup component;
  arbitrary raw text is not a valid stored location value.
- Store the lookup display label, locality/city, region, country, country code,
  stable provider/place identifier, and coordinates only when naturally
  returned by the lookup.
- Do not request precise coordinates from a participant.
- This applies to base locations, institution locations, field sites,
  participant-entered event locations, and future geographic answers.

## Identity and profile boundary

- PREDICTION requires name and email; institution and base location are optional.
- Email supports access-key issuance and host-assisted recovery. Email is not
  authentication and does not imply mailing-list or other communication consent.
- Required email validation distinguishes a missing value (explain recovery
  purpose) from a malformed supplied address (ask the participant to check it).
- Durable profile information remains separate from event/session scientific
  responses.

## Session-family navigation

Participant-facing sessions are grouped by current conceptual family:

- Complexity (formerly B-Complex);
- Young (formerly Pisa);
- Prediction (CISM / Udine);
- D'Alembertiennes (Climate).

Use declarative `navigation_families()` metadata for these groups. Preserve old
URL paths where compatibility requires them, but do not expose historical
implementation labels such as `Scientific Event` in navigation. This metadata
is the precursor to a future Sessions index; do not build that dashboard yet.

## Test-mode isolation primitive

Every participant-facing event flow should support deliberate testing without mixing test records into production participation.

Implementation rule:

- `?event=<production-slug>&test=1` resolves to the configured debug event and
  persisted debug session before any participant lookup, checkpoint, response,
  revision, aggregate, analytics, or recovery operation;
- a test run must resolve to a dedicated persisted session with its own `session_code` and `session_id`;
- never reuse the production session id and never rely on browser state alone to mark a run as test data;
- reuse the production question set when the purpose is route QA, but record `test_mode = true`, a debug event slug, and an explicit debug response scope in every response bundle and event;
- display a persistent, unmistakable `TEST MODE` notice throughout the participant flow;
- production overviews, member lists, exports, reports, recovery tools, and aggregates must remain scoped to the production session and therefore exclude the debug session by construction;
- creating or opening a debug session must be an explicit host/operator action, never an automatic side effect of loading a public route;
- test sessions should be reusable and inactive by default so repeated QA does not mint a new event scope each time;
- a test participant remains a real database record associated with the debug session. Do not delete only its player row: any later cleanup must resolve and handle its debug-scoped responses and events as one guarded operation;
- if a test session is reset or archived, keep a minimal operator audit record and never touch production-scoped records.

This is a general event-system primitive, not a WG2-specific exception. New event implementations should define their production/test session pair and test entry path as part of the user flow, data-written contract, logging, analytics scope, and Definition of Done.

Current CISM pair:

- production: event slug `prediction`, session code `prediction_2026`;
- test/debug: event slug `prediction_debug`, session code `prediction_debug_2026`;
- both are created only by `scripts/bootstrap_prediction_sessions.py` or an
  equivalent explicit operator action.

## Loop contract for long-running agents

Each agentic loop must:

1. Read durable state.
2. Choose one bounded next action.
3. Execute only that step.
4. Log events and timings.
5. Checkpoint result.
6. Stop.

No unbounded background work inside Streamlit request cycles.

## Runtime pattern

- `PLAN.md` stores the current plan and checkpoints.
- SQLite or Notion stores persisted job state.
- A runner script executes one bounded task.
- An outer scheduler re-triggers the runner later.
- `pages/07_Admin.py` exposes operator view: queue, status, retries, recent checkpoints.
- `infra/event_logger.py` records step logs, timings, and failures.

## Coding rules

- Keep changes small and testable.
- Do not break existing Notion schemas without migration notes.
- Do not rename existing fields without migration notes.
- Add logging with `iceicebaby.<module>`.
- Every new feature should define:
    - user flow
    - data written
    - event logged
    - visualization impact
    - event scope

## UX rules

- Avoid abstract language in user-facing copy.
- Internal concepts: trajectory, bifurcation, irreversibility.
- User-facing concepts: place, continue, map, signal, contribution, event.
- Complexity should be sequenced, not exposed all at once.
- During question flows, show only the current question, answer inputs, and navigation buttons.
- No expanders, debug panels, dashboards, or side explanations inside question pages.

## Typography and visual hierarchy rules

- Typography is part of the interaction design, not decoration.
- Every route must use a consistent type ramp, spacing scale, and layout width.
- Avoid raw Streamlit default typography when building participant-facing flows.
- Define page-level CSS tokens for:
    - font family
    - heading sizes
    - body size
    - line height
    - paragraph spacing
    - max text width
    - button text size
    - caption/note size
- Prioritise readability:
    - generous line height
    - limited line length
    - strong hierarchy between title, question, context, and controls
    - clear contrast between primary and secondary text
- One screen = one typographic hierarchy.
- Question pages must show only:
    - progress
    - title
    - question
    - context/helper text
    - input
    - navigation controls
- No visual clutter, no nested expanders, no dense debug text in participant flows.
- Mobile typography must be tested explicitly.

## Aggregation rules

Every aggregation must specify scope.

Examples:

- Arrival emotions for `unesco-opening`.
- Laboratory expectations for `dalembertiennes`.
- Decision signal for `wg2-workshop`.

Later cross-event comparison is allowed, but it must be explicit:

- `unesco-opening` vs `dalembertiennes`.
- `event_group = cryosphere-public-events`.

No default global aggregation unless intentionally marked as global.

## Escalation rules

Escalate instead of acting when:

- Notion schema is missing or ambiguous.
- An event id cannot be resolved.
- A migration could destroy or overwrite data.
- A response would be written without explicit event scope.
- Duplicate player merging is requested without consent or admin confirmation.
- External emails or public communications would be sent.
- A task requires credentials not present in secrets.

## Definition of done

A task is done when:

- The user flow works.
- Durable data is written correctly.
- All durable writes include event scope where required.
- Event logging exists.
- Aggregations filter by event id.
- Partial participation survives total browser-state loss and resumes in the correct persisted session.
- Accidental submission retries are idempotent; intentional revisions remain append-only and auditable.
- Identified-participant recovery requires the access-key recovery flow, never email alone.
- Failure mode is visible in admin/operator view.
- `PLAN.md` is updated with result and next step.
