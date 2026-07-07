# PLAN.md

## Goal

Build **Ice Ice Baby** into a long-running participatory platform for climate, cryosphere, laboratory, and collective-decision experiments.

The platform must support multiple questionnaire routes and real-world sessions without mixing responses, questions, participants, or aggregated results.

## Current platform state

- Streamlit app is functional.
- Notion backend stores players, responses, sessions, decisions, and event logs.
- `infra/event_logger.py` provides append-only logging infrastructure.
- `conference/question_sets/` is the source of truth for conference-style question definitions.
- `conference/registry.py` resolves registered question sets and route identity.
- `conference/questionnaire.py` provides the generic questionnaire renderer.
- `conference/repo.py` provides guarded persistence.
- Admin/operator tooling exists in `pages/07_Admin.py`.
- D’Alembertiennes produced the first hardening cycle for:
  - route-specific question sets;
  - event/session isolation;
  - mock-question smoke tests;
  - skip and flag feedback;
  - route overview / host pages;
  - data contamination checks.

## Current architecture decision

The product boundary is **event/campaign**, but the durable persistence boundary is still **session**.

For now:

- do not rename the whole codebase from `session` to `event`;
- do not replace the existing player/session persistence model in one pass;
- add explicit event and campaign mappings on top of the current session-based storage.

### Identity model

Use the following terms consistently.

| Term | Meaning |
|---|---|
| `campaign_slug` | Public family or campaign route, for example `/climate`. A campaign may point to several event/session instances. |
| `event_slug` | Real-world or institutional context, for example `dalembertiennes`. |
| `session_code` | Durable persistence boundary in the current Notion-backed system. |
| `question_set_id` | Versioned set of questions to render. |
| `text_id` | Versioned text/content identity of the questionnaire. |
| `schema_id` | Payload contract for stored responses. |
| `participation` | One global participant’s event-specific answering trajectory. |

Every write must resolve to an explicit:

```text
campaign_slug? -> event_slug -> session_code -> text_id -> question_set_id -> schema_id
```

A public route such as `/climate` must never write unless it resolves to an explicit `event_slug`, `session_code`, and `question_set_id`.

## Campaign route decision

`/climate` is a **campaign route**, not only an alias to D’Alembertiennes.

For now it may resolve by default to:

```yaml
campaign_slug: climate
event_slug: dalembertiennes
session_code: dalembertiennes_2026
text_id: dalembertiennes_v1
question_set_id: dalembertiennes_v1
```

Later it should be able to resolve to several laboratory sessions, for example:

```text
/climate/dalembertiennes
/climate/lab-x
/climate/lab-y
```

All of these may reuse the same or related question sets while preserving separate event/session persistence.

## Participant decision

Participants are **global**.

A participant may enter through one campaign/session and later explore other sessions. However, answers remain event/session-specific unless a field has been explicitly declared as a shared profile field.

The target model is:

```text
Global participant
  -> participation in event/session A
  -> participation in event/session B
  -> participation in event/session C
```

## Shared profile policy

Every route must explicitly opt in to persistent shared questions.

No question should persist across events by accident.

For each question, declare one of:

- `profile_persistent`: may persist across sessions;
- `session_local`: belongs only to the current event/session;
- `deferrable`: can be answered later;
- `sensitive`: should be optional and not reused by default.

Career stage, scientific lens, and assets may be reusable only when the route explicitly opts in.

## Answer status and question feedback

Distinguish clearly between:

### Answer status

The participant’s answer state for a question:

- `answered`
- `deferred`
- `skipped`

### Question feedback

Feedback about the quality or framing of the question:

- `flagged`
- `unclear`
- `misleading`
- `too_narrow`
- `too_broad`
- `missing_option`
- `inappropriate`
- optional note

Skip and flag may share a storage mechanism temporarily, but their semantics must remain distinct in the data model and overview.

## Minimal overview for any new route

Every new route must have a minimal overview on day one.

Required overview signals:

- number of participants;
- number of answered questions;
- number of deferred questions;
- number of skipped questions;
- number of flagged questions;
- route identity block:
  - campaign slug, if any;
  - event slug;
  - session code;
  - text id;
  - question set id;
  - schema id;
- last updated timestamp.

Richer charts can be added later.

## Access and roles

Detailed access control is a second-stage implementation.

For now, the code and plan should still distinguish conceptual roles:

- participant;
- host/operator;
- admin/dev.

Host pages and raw exports may remain visible in the current dev environment, but the route brief must mark which pages are intended for public, host, or admin use.

## New-route lifecycle

Every new route starts in `draft`.

It can switch to `open` only after a successful double-check:

1. route identity resolves explicitly;
2. mock question renders;
3. mock response writes to the correct session/bundle;
4. overview reads only the correct rows;
5. other routes remain unchanged;
6. admin inspector shows the expected route/question-set identity.

Lifecycle states:

| State | Participant page | Writes | Overview | Export |
|---|---|---|---|---|
| `draft` | dev/host only | dev only | dev only | dev only |
| `open` | visible | enabled | enabled | enabled |
| `closed` | visible or read-only | disabled | enabled | enabled |
| `archived` | hidden or read-only | disabled | frozen | frozen |

## Contaminated-row policy

If a route writes contaminated rows, do not silently delete or hide them.

Show the raw contaminated data to the operator/admin, including:

- stored session;
- stored event;
- stored question id;
- stored bundle id;
- text id;
- access key / participant reference;
- timestamp;
- raw response JSON.

Then ask whether to:

1. mark contaminated rows invalid;
2. keep them visible as diagnostic rows;
3. invite affected participants to rehydrate the session by answering again.

For now, prefer transparency: show raw data and ask whether the user/admin is happy to rehydrate by responding again.

## Route brief requirement

Every new route must have a route brief before implementation.

The route brief must describe:

- public path;
- campaign slug, if any;
- event slug;
- session code;
- text id;
- question set id;
- intended audience;
- lifecycle state;
- question pathway;
- modes, if any;
- shared profile opt-ins;
- local session fields;
- overview requirements;
- host/admin visibility;
- contamination handling.

## Active milestone

Consolidate the questionnaire route implementation process into a strict playbook and agent orchestration protocol.

The next implementation target is a reusable `/climate` campaign route that can serve D’Alembertiennes first and later neighbouring labs.

## Recent checkpoints

- D’Alembertiennes exposed the need for strict route identity, registry-backed question sets, and hard write guards.
- The app now supports question sets with reusable shared questions and event-specific questions.
- Skip and flag flows exist in the UI and should be made semantically explicit.
- The mock-question scaffold proved useful and should become mandatory for every new route.

## Open blockers

- Define exact role/access behavior for host and admin pages.
- Decide whether raw export is dev-only or host-visible.
- Define long-term storage schema for participations.
- Decide how much of `models/catalog.py` remains legacy versus migrated to registry-backed question sets.
- Define whether `/climate` gets nested routes immediately or starts as one default campaign alias.

## Backlog

- [ ] Add route-brief template to the repo.
- [ ] Add campaign route resolver.
- [ ] Add explicit `participation` abstraction.
- [ ] Separate `answer_status` from `question_feedback`.
- [ ] Standardize minimal overview component.
- [ ] Add contaminated-row diagnostic panel.
- [ ] Add role-aware host/admin visibility.
- [ ] Add route lifecycle controls.
- [ ] Add screenshot QA checklist to agent handoffs.

## 2026-07-04 checkpoint — UN WG2 scaffold

### What changed

- Added a first scaffold question set in `conference/question_sets/un_wg2_v1.py`.
- Registered the WG2 route identity in `conference/registry.py`.
- Added explicit WG2 event/session/text/page identity in `conference/events.py`.
- Added explicit writer recognition and isolated bundle mapping in `conference/repo.py`:
  - `text_id = un_wg2_v1`
  - bundle id = `UN_WG2_BUNDLE`
- Added a public route config for `un-wg2-icebreaker` in `conference/public_routes.py`.
- Added participant, overview, and host pages:
  - `pages/25_UN_WG2_Icebreaker.py`
  - `pages/26_UN_WG2_Overview.py`
  - `pages/27_UN_WG2_Host.py`
- Exposed the route in `app.py` with:
  - `/un-wg2-icebreaker`
  - `/un-wg2-overview`
  - `/un-wg2-host`
- Added a session scaffold entry in `models/sessions.py`.
- Added `scripts/bootstrap_un_wg2_session.py` to create/update the backing session.

### What was tested

- `python3 -m py_compile` passed for all changed route files.
- Static route identity resolution passed:
  - `event_slug = un_wg2_first_iteration`
  - `session_code = un_wg2_core_2026`
  - `text_id = un_wg2_v1`
  - `question_set_id = un_wg2_v1`
  - `schema_id = questionnaire_v1`
  - `response_scope = event_session`
- Registry validation returned no errors.
- Writer bundle mapping resolved successfully in the project virtualenv:
  - `un_wg2_v1 -> UN_WG2_BUNDLE`
- Live WG2 session bootstrap succeeded through the app Notion integration:
  - session row created with `session_code = un_wg2_core_2026`
  - page id = `39354516-e9e1-81c7-81a1-d7dcdd4f79be`
  - description now points to `question set un_wg2_v1`

### Blockers

- The Notion plugin context could not see the sessions database configured in local app secrets, so direct plugin-side session bootstrap was not possible from that integration alone.
- The end-to-end participant submission smoke test is still pending:
  - open `/un-wg2-icebreaker`
  - answer one question
  - confirm the response appears only in the UN WG2 overview/export/logs

### Next action

1. Open `/un-wg2-icebreaker`.
2. Submit one mock answer.
3. Confirm:
   - write succeeds under `UN_WG2_BUNDLE`
   - WG2 overview increments
   - other routes remain unchanged
   - admin bundle inspector shows the WG2 route cleanly
