# Ice Ice Baby

Ice Ice Baby / Decade Coordination Map is a Streamlit and Notion application
for participatory scientific events. One application engine serves multiple
events while keeping their questions, participation, responses, and results
explicitly isolated by persisted session.

## Multi-event architecture

- An `EventConfig` declares public copy, production/debug session codes,
  question-set reference, identity policy, and result configuration.
- `event` is the product-level gathering; `session` remains the durable Notion
  boundary used by repositories and relations.
- A participant is a durable player identity. A participation is that player's
  event-scoped progress through one persisted session.
- Player session relations are union-preserving: joining a new event does not
  remove earlier event membership.
- Aggregates, exports, recovery tools, and host views must resolve an explicit
  event/session scope. Production and debug sessions are distinct persisted
  records.

## CISM / PREDICTION

The current second-session vertical slice is the CISM-EUROMECH Advanced Course
“Damage and Fracture Mechanics of Fluid-Infiltrated Geomaterials”, Udine,
7–11 September 2026.

| Purpose | Event slug | Session code | Entry URL |
| --- | --- | --- | --- |
| Production | `prediction` | `prediction_2026` | `/event?event=prediction` |
| Test/debug | `prediction_debug` | `prediction_debug_2026` | `/event?event=prediction&test=1` |

The test entry resolves `prediction_debug_2026` before any read or write. The
explicit `prediction_debug` slug remains a compatibility alias. Public URLs are
canonicalised to the minimum routing contract (`event`, plus `test=1` for a
debug run); legacy `public_route` and `campaign` parameters are accepted where
older links require them but are not emitted by the generic event flow.

The generic companion routes are `/event-overview?event=<slug>` and
`/event-host?event=<slug>`. Loading a page never creates a session; operators
must run the explicit bootstrap first:

```bash
./.venv/bin/python scripts/bootstrap_prediction_sessions.py
```

PREDICTION currently uses the infrastructure-only `prediction_v0` question-set
shell. Its scientific questions are intentionally not yet defined.

For platform QA only, append `&fixture=controls` to the test URL. This loads a
temporary, debug-only single-choice/scale/free-text fixture used to verify the
shared Flag and Skip controls. It is never selected by the production route and
is not CISM scientific content.

## Participant lifecycle

The supported conference-ready flow is:

```text
identify -> participate -> checkpoint -> leave -> recover -> resume -> submit
```

Identified events collect name and normalised email separately from scientific
answers, with institution and base location optional. Email is a host-searchable
recovery handle, not authentication. The access key is the participant
credential. Email collection does not imply communication or mailing-list
consent.

Every scientific question supports Flag and Skip unless explicitly configured
as structurally non-skippable. Answered, intentionally skipped, unanswered, and
flagged state are durably distinguishable and restored with participation
checkpoints. Semantic location fields use the shared lookup and store a
structured place value rather than unrelated free-text variants.

Flag and Skip are a universal visual grammar rather than scientific-question
decorations. Every rendered questionnaire step exposes `can_flag` and
`can_skip`; both controls remain visible, and unsupported actions render as
disabled native buttons with a short explanation. Required identity enables
Flag but disables Skip, optional profile and scientific steps enable both, and
review disables both while directing participants back to editable steps.

Identified-event access-key copy describes the key as the return credential and
email as a host-assisted recovery handle. Participant completion pages show the
full key directly; implementation identifiers and hashes remain hidden in
production and are available only in a collapsed debug diagnostic surface.

The displayed session navigation is generated from declarative metadata and
groups current work under Complexity, Young, Prediction, and D'Alembertiennes.
Existing URL aliases remain available for compatibility.

Completed steps are checkpointed incrementally in the shared interaction store.
On return, the app resolves the participant and participation, reloads the
latest checkpoint, and reconstructs progress without relying on Streamlit or
browser state. Recovery is host-assisted through signed, one-time links; the
public route never grants access from an email address alone.

Submission writes carry `submission_id`, `revision_id`,
`write_idempotency_key`, and optional `supersedes_response_id`. Retries reuse
the same logical submission, while intentional revisions append a new,
auditable record.

## Development

The Streamlit deployment has no required system-level apt packages. Credential
PDF rendering uses fonts already available in the runtime and degrades through
the fallback chain in `infra/credentials_pdf.py`; do not add `packages.txt`
solely for optional emoji typography.

Run the deployable regression suite with:

```bash
./.venv/bin/python -m pytest -q tests
```

Architecture and operational rules are maintained in `AGENTS.md`; current
delivery checkpoints and remaining work are tracked in `PLAN.md`.

Questionnaire content is YAML-first. The authoring grammar, lifecycle,
revision model, shared-question references, and compatibility aliases are
documented in `docs/questionnaire_yaml.md`.
