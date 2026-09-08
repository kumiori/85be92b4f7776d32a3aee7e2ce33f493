# YAML-first questionnaire definitions

YAML is the canonical authoring format for new and migrated questionnaires.
Python remains the runtime model and, during migration, may remain as an
equivalence oracle. Git is the detailed revision history.

## Canonical structure

```yaml
questionnaire:
  id: example
  revision: 3
  status: review
  review:
    reviewed_at: 2026-09-09
    reviewed_by: [Reviewer]
    change_note: Changed the evidence categories.

step_order: [welcome, role, review, done]
flow_modes:
  standard:
    title: Standard
    detail: ""
    accent: ""
    steps: [role]
step_copy:
  role:
    title: Role
    body: Choose the closest description.
    cta: Continue
questions:
  - use: shared.role
    id: role
    revision: 2
    legacy_ids: [EXAMPLE_ROLE_V1]
    prompt: What is your main role or lens?
    context: Choose up to three.
    supersedes_revision: 1
    change:
      type: options_changed
      reason: Separated two roles.
      reask_if_answered: true
      preserve_previous_response: true
```

- `id` is the stable semantic identity and never contains a revision number.
- `revision` is the integer content revision of the whole questionnaire or an
  individual question.
- `format` is the YAML grammar version. It defaults to `2` and may normally be
  omitted.
- `status` is lifecycle state: `draft`, `review`, `active`, or `archived` for a
  questionnaire; `active` or `retired` for a question. Lifecycle changes do not
  themselves increment content revision.

Retired questions remain in the definition and historical lookup but are
excluded from participant flow. A revised question is re-asked only when its
revision increases, its lineage matches the stored revision, and
`reask_if_answered` is true. The earlier append-only response remains intact.

## Shared questions and compatibility

`shared_questions.yaml` owns reusable response semantics and options. A
questionnaire includes one with `use: shared.role`. Presentation fields such as
prompt, context, required state, grouping, and maximum selection may be
overridden. Options require an explicit `override_reason`; fields and input type
cannot be silently replaced.

`shared_dimension` declares cross-session comparability without forcing equal
question IDs. Aggregation remains session-scoped by default; a cross-session
analysis must explicitly select compatible dimensions and sessions.

| New model | Compatibility alias retained during migration |
| --- | --- |
| `questionnaire_id: complexity` | `question_set_id: complexity_v2` at the event/repository boundary |
| `questionnaire_revision: 2` | `questionnaire_version` |
| `questionnaire_format: 2` | `schema_id` when older readers require it |
| stable `question_id` | per-question `legacy_ids`, such as `COMPLEXITY_ROLE` |
| question revision provenance | existing `text_id` and append-only response row |

Existing Notion rows are not rewritten. New payloads contain both clean
questionnaire provenance and the legacy aliases required by current repository
filters. `text_id` remains the deployed bundle/session discriminator until those
queries are migrated separately.

Current canonical files are `complexity.yaml`, `prediction.yaml`, and
`shared_questions.yaml`. `complexity_v2.py` remains temporarily as the tested
equivalence oracle. `prediction.yaml` is a review-state skeleton with no
scientific questions.

## Remaining migration risks

- Some specialised WG2 evolution readers still consume `schema_id`,
  `questionnaire_version`, and legacy question IDs; the adapters must remain
  until those readers are migrated and historical Notion data is sampled.
- Aggregates that name question IDs directly need to resolve `legacy_ids` before
  stable IDs can fully replace them.
- `text_id` currently scopes repository reads and cannot be renamed without a
  separate persisted-data migration.
- YAML publication is enforced at runtime (`active` for production; review
  definitions may be exercised in isolated test mode), but there is no heavy
  approval workflow by design.
