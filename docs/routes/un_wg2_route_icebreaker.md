# UN WG2 Route Icebreaker Brief

## Purpose

This brief instantiates the generic questionnaire-route rules for the first UN WG2 scaffold route.

This is not yet the full WG2 coordination platform.

It is the first coordination layer of WG2:

- the questionnaire is the interface through which coordination begins;
- the immediate goal is to make the Working Group visible to itself;
- the first route should prove route identity, scoped persistence, and route-specific overview behavior before real content expands.

The route starts as a pilot for the core leadership of WG2, then may widen to the broader Working Group.

---

## Working Framing

WG2 is not only a collection of experts. It is a coordination problem.

Before collaboration can intensify, the group needs a shared representation of:

- who composes WG2;
- what perspectives and capabilities are already present;
- what people are actively trying to do;
- where coordination would create immediate value.

The platform is therefore a coordination instrument, not a repository.

Its purpose is to let collaboration emerge from visibility.

---

## Route Identity

```yaml
route:
  campaign_root: /un-wg2
  public_path: /un-wg2-icebreaker
  campaign_slug: un-cryosphere-decade
  event_slug: un_wg2_first_iteration
  session_code: un_wg2_core_2026
  text_id: un_wg2_v1
  question_set_id: un_wg2_v1
  schema_id: questionnaire_v1
  response_scope: event_session
  lifecycle: draft
  title: Working Group 2 — First Iteration
  subtitle: Actionable Cryosphere Projections
  framing: WG2 Coordination Platform
  edition: First implementation (Pilot)
  intended_audience: Core Working Group 2 first, then extended WG2
```

Identity rule:

All writes through `/un-wg2-icebreaker` must resolve explicitly to:

- `campaign_slug = un-cryosphere-decade`
- `event_slug = un_wg2_first_iteration`
- `session_code = un_wg2_core_2026`
- `text_id = un_wg2_v1`
- `question_set_id = un_wg2_v1`
- `schema_id = questionnaire_v1`
- `response_scope = event_session`

No fallback to another route is acceptable.

---

## Audiences

```yaml
audiences:
  core:
    label: Core WG2
    access: invited
    purpose: initial calibration and framing
  extended:
    label: Extended WG2
    access: invited_later
    purpose: broaden views, collect priorities, identify tensions
```

Phase rule:

- the first live scaffold is for `core`
- `extended` remains planned but not open during the first smoke-test cycle

---

## Persistence

```yaml
persistence:
  response_scope: event_session
  participant_model: global_participant_with_event_specific_participations
  allow_profile_persistence: true
  profile_persistent_fields:
    - name
    - email
    - affiliation
    - role_in_decade
  session_local_fields:
    - priorities
    - concerns
    - projections_needs
    - collaboration_preferences
```

Additional persistence notes:

- participants are global
- answers in this route are session-local unless explicitly opted into persistence
- the route must not write into any existing climate, complexity, Pisa, UNESCO, or Dalembertiennes bundle

---

## Route Goal

The immediate goal is not to collect a full WG2 programme.

The immediate goal is to prove that a first WG2 coordination route can:

1. identify participants in a shared WG2 context
2. collect one bounded coordination signal
3. persist that signal with explicit route identity
4. expose it only in the WG2 overview/export
5. leave every other route unchanged

This is the acceptance threshold for scaffolding.

---

## Pathway

```yaml
pathway:
  ordered_steps:
    - orientation
    - participant_context
    - projection_needs
    - uncertainty_and_usability
    - decision_support
    - coordination
    - open_reflection
```

Interpretation:

- `orientation`: what this route is for and why WG2 is using it
- `participant_context`: who is speaking and from which institutional/scientific position
- `projection_needs`: what kinds of projections or outputs are needed
- `uncertainty_and_usability`: what makes outputs hard to use or compare
- `decision_support`: how outputs need to support decisions
- `coordination`: where WG2 coordination would create value
- `open_reflection`: unresolved issues, tensions, or priorities

---

## Modes

```yaml
modes:
  quick:
    target_minutes: 5
  standard:
    target_minutes: 12
  deep:
    target_minutes: 20
```

Scaffold rule:

For the first smoke test, the route may launch with only one active mode if that reduces complexity.

Recommended first scaffold:

- enable `quick` only, or
- set `standard` as default and hide mode choice

The route brief keeps all three modes visible so later implementation does not drift.

---

## Pilot Philosophy

The first implementation remains deliberately lightweight.

It should be completable in a few minutes while already generating useful collective information.

The pilot serves two purposes at once:

1. test the coordination mechanism;
2. produce the first collective picture of WG2.

The platform should therefore privilege clarity, short duration, and interpretability over completeness.

---

## Broader Platform Direction

This first route belongs to a larger WG2 coordination platform with three long-term modules:

### Module 1 — Who are we?

Collective map of expertise, perspectives, institutions, countries, roles, interests, and availability.

### Module 2 — What are we doing?

Map of active work:

- research
- datasets
- publications
- software
- field campaigns
- proposals
- policy dialogue
- training
- decision-support tools

### Module 3 — Timeline of contributions

Shared decade timeline for activities across 2025–2034 so trajectories become visible as a collective trajectory.

Route-scoping rule:

`/un-wg2-icebreaker` is only the first entry layer, not the full delivery of Modules 1–3.

---

## Initial Icebreaker Scope

For the scaffold, the route should act as a lightweight entry route into Module 1.

It should begin by making visible:

- who is participating in WG2;
- what perspectives they bring;
- what they most need from WG2 coordination;
- what one immediate coordination signal looks like.

This keeps the first route small enough to test while aligning with the larger platform.

---

## Mock Question Requirement

The first implementation must use one mock question before real WG2 content is added.

Suggested scaffold question:

```yaml
mock_question:
  step: coordination
  field: wg2_coordination_signal
  question_id: UN_WG2_COORDINATION_SIGNAL
  title: First coordination signal
  prompt: What should WG2 make more visible or better coordinated first?
  context: This is a smoke-test question for the first WG2 coordination route. It is only here to prove the route resolves, writes, and reads back safely.
  input_type: text
  required: false
```

Rule:

Do not add the real WG2 question set until this mock route passes the acceptance test.

---

## Pages

```yaml
pages:
  participant:
    route: /un-wg2-icebreaker
    visibility: invited_core_draft
  overview:
    route: /un-wg2-overview
    visibility: host_admin_draft
  host:
    route: /un-wg2-host
    visibility: host_admin_draft
  admin_visibility:
    conference_bundle_inspector: required
    recent_event_logs: required
```

Participant rule:

The participant page must remain thin and must call the generic conference renderer.

---

## UI Requirements

This route must follow the questionnaire playbook and current shared UI contract.

### Participant flow

- mobile-first
- one screen = one action
- prompt and context shown separately
- no raw debug panels in the participant flow
- no event selector at the top

### Action hierarchy

- `Continue` is the dominant action
- `Flag` is available as a secondary control
- `Skip` is available as a smaller secondary control

### Feedback systems

- question flagging must work
- skip must open a reason dialog
- skip reason must persist
- review must show question feedback

### Screenshot gate

Before opening the route, capture:

1. landing page
2. mock question
3. flag control open
4. skip dialog open
5. review page
6. done page
7. overview page
8. host page
9. admin bundle inspector entry

Both desktop and narrow/mobile widths are required where relevant.

---

## Overview Requirements

The first overview may be minimal, but it must be scoped.

Required first-pass overview elements:

- route identity block
  - `campaign_slug`
  - `event_slug`
  - `session_code`
  - `text_id`
  - `question_set_id`
  - `schema_id`
- submission count
- answered question count
- skipped question count
- flagged question count
- blank state if no submissions
- export filtered only to `un_wg2_core_2026`

The overview must read only WG2 rows.

---

## Contamination Handling

```yaml
contamination_policy:
  silent_deletion: false
  host_visibility: required
  admin_visibility: required
  recovery_preference: rehydrate_after_visibility
```

If contaminated rows appear:

- expose them in host/admin
- do not silently delete them
- log the contamination
- decide whether to mark invalid, keep diagnostic, or rehydrate by answering again

---

## Minimal Implementation Sequence

```yaml
implementation_sequence:
  - Add route brief: docs/routes/un_wg2_route_icebreaker.md
  - Add mock question set: conference/question_sets/un_wg2_v1.py
  - Register route in conference/registry.py
  - Add event/session resolver entry in conference/events.py
  - Expose participant route /un-wg2-icebreaker
  - Add minimal overview filtered only by un_wg2_core_2026
  - Add host/operator page
  - Smoke test with one mock answer
  - Only then add real WG2 questions
```

---

## Core Acceptance Test

The decisive scaffold test is:

Can a core WG2 participant answer one mock question through `/un-wg2-icebreaker`, and does the response appear only in the UN WG2 overview/export, with no contamination?

Pass criteria:

1. route identity resolves explicitly
2. mock question renders
3. one answer writes successfully
4. the row is stored under the WG2 bundle/text identity
5. the WG2 overview increments
6. other routes remain unchanged
7. admin inspector shows the expected route configuration
8. screenshots confirm intended UI state

If yes, the scaffolding is ready.

---

## Next Real Questions Direction

Once the mock scaffold passes, the first real WG2 route should likely move toward:

- participant context
- expertise/capabilities
- current activity
- projection needs
- uncertainty/usability tensions
- coordination priorities
- open reflection

This route should still remain concise at first.

Do not start by implementing the full decade timeline or complete contribution-tracking model inside the very first route.
