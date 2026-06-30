# P5 Real Smoke / Dify Debug Report

Date: 2026-06-30  
Scope: backend model gateway + Dify V2 workflow synthetic smoke.  
Data policy: only synthetic data was sent to Dify. No `coll_internal` citation text was exported during this debug pass.

## Inputs inspected

- `.env`
  - `GENERATION_PROVIDER=dify`
  - `DIFY_API_URL` is set and currently includes `/v1`
  - `DIFY_API_KEY` is set; value was not printed
- Workflow export:
  - `docs/dify/v2/xhs_production_v2_gateway.yml`
  - Start variables expect `generationInputs`, `cardSequence`, `citations` as paragraph/JSON-string style values.

## Findings

### 1. Backend URL builder duplicated `/v1`

Before this fix, backend built:

```text
{DIFY_API_URL}/v1/workflows/run
```

When `.env` already used a `/v1` base URL, this became:

```text
/v1/v1/workflows/run
```

Synthetic smoke returned HTTP 404.

Fix:

- `api/services/model_gateway.py` now accepts both:
  - `https://api.dify.ai`
  - `https://api.dify.ai/v1`
  - local/private Dify URLs with or without `/v1`

### 2. Backend should send Dify paragraph inputs as JSON strings

The exported workflow accepts JSON-like values through paragraph variables. Backend previously sent raw dict/list values.

Fix:

- `generationInputs` is now `json.dumps(inputs)`
- `cardSequence` is now `json.dumps(card_sequence)`
- `citations` is now `json.dumps(public_citations)`
- `factsBrief` is supplied as an empty string so the workflow can build it from citations.

### 3. Dify API now succeeds with synthetic data, but workflow output is empty

Synthetic request result after URL/payload fix:

```json
{
  "status": 200,
  "dataStatus": "succeeded",
  "error": null
}
```

But `outputs.cards` contained three cards with empty content:

- `title=""`
- `subtitle=""`
- `items=[]`
- citations were preserved

Conclusion: gateway connectivity is working; the remaining defect is in Dify workflow generation quality / prompt behavior / LLM output. The LLM or cleaning node is producing skeleton cards instead of filled copy.

### 4. Backend now rejects empty cards

Fix:

- `api/services/model_gateway.py` now treats cards with no `title`, `subtitle`, `items`, `days`, or `study_material` as `MODEL_GATEWAY_EMPTY_OUTPUT`.
- This prevents empty generated cards from being written as successful `generation.output`.

Synthetic gateway result after validation:

```json
{
  "status": "failed",
  "code": "MODEL_GATEWAY_EMPTY_OUTPUT",
  "message": "Model gateway returned no cards",
  "provider": "dify"
}
```

### 5. Workflow yml prompt strengthened

Updated local workflow export:

- `docs/dify/v2/xhs_production_v2_gateway.yml`

Added hard constraints:

- do not copy the empty template;
- every card must have non-empty `title` and `subtitle`;
- every card must include at least one `items` entry;
- if facts are insufficient, produce safe wording like “以官方通知为准 / 待官方发布” instead of empty strings.

Important: editing this yml does not automatically update the running Dify workflow. It must be re-imported/published in Dify before the next real smoke.

## Tests

```powershell
py -m pytest api\tests\test_model_gateway.py api\tests\test_generation_workflow.py -q
py -m ruff check api\services\model_gateway.py api\tests\test_model_gateway.py api\tests\test_generation_workflow.py
py -m pyright api\services\model_gateway.py api\tests\test_model_gateway.py --pythonversion 3.12
```

Result:

- `9 passed`
- ruff pass
- pyright pass

## Next steps

### 2026-06-30 update: switch Dify to single-card workflow

After synthetic smoke passed but the real internal multi-card backend smoke still returned empty cards, a direct single-card internal smoke succeeded. The production design is now:

- V2 backend owns iteration, retry, merge, persistence, audit, ACL, and citation filtering.
- Dify workflow owns only one high-quality card per run.
- Backend sends `cardSequence=["cover"]`, then `["plan"]`, etc., one workflow call at a time.
- Backend rejects empty output after retry instead of writing empty cards.
- Dify code nodes are limited to input adaptation and JSON cleanup; they must not generate replacement marketing copy.

This matches the older proven “single card generation loop, then merge” logic while keeping V2’s backend/provider boundary.

Implementation changes:

- `api/services/model_gateway.py`
  - always orchestrates Dify card generation per card type;
  - records per-card workflow metadata in `raw_metadata.runs`;
  - only accepts one card matching the requested `card_type`;
  - retries each card up to 4 times;
  - returns `MODEL_GATEWAY_EMPTY_OUTPUT` if a requested card remains empty after retry.
- `docs/dify/v2/xhs_production_v2_gateway.yml`
  - renamed/described as a single-card V2 gateway workflow;
  - defaults `cardSequence` to `["cover"]`;
  - normalizes any incoming sequence to exactly one card type;
  - prompts the LLM to produce only one card;
  - routes LLM output directly to the end node as raw `text`;
  - bypasses Dify-side cleanup/parsing while the production flow is being stabilized.
- `api/tests/test_model_gateway.py`
  - covers per-card orchestration, card type filtering, raw-text wrapping, and empty-output retry failure.

Temporary stabilization rule:

- Dify is currently treated as a raw LLM text provider.
- Backend code owns compatibility parsing for JSON cards, `result`, or plain text.
- Once the end-to-end generation flow is stable and real smoke outputs are acceptable, the proven backend parsing rules can be copied back into Dify if we still want Dify-side structured cleanup.

### 2026-06-30 evidence after raw-text workflow import

Synthetic debug proved the important failure mode:

- Dify final outputs contained only `text`.
- `directCards=[]`.
- `text.present=true`.
- The raw LLM text included visible `<think>...</think>` reasoning before the final answer.
- Therefore the defect was not “LLM produced nothing”; it was backend/Dify parsing treating raw reasoning text as card content or dropping structured output after cleanup.

Backend fix:

- strip complete `<think>...</think>` reasoning blocks before parsing;
- attempt direct JSON parsing;
- if direct parsing fails, extract the first JSON object/array embedded in the text;
- only if no JSON exists, wrap the remaining raw model text as the requested card type.

Smoke evidence:

- Synthetic smoke: PASS
  - provider=`dify`
  - cards=`3`
  - first title=`Synthetic Exam` countdown title
- Real internal smoke: PASS
  - runId=`4`
  - status=`succeeded`
  - modelRoute=`approved_external`
  - confidentiality=`internal`
  - cards=`3`
  - citations=`5`
  - DB `generation.run.status=succeeded`
  - DB output count=`1`
  - card types=`cover/plan/notice`
  - no `<think>` residue in persisted cards

Validation:

```powershell
py -m pytest api\tests db\tests -q
py -m ruff check api db
py -m pyright api db --pythonversion 3.12
```

Result:

- `170 passed`
- ruff pass
- pyright pass

Next steps:

1. Re-import/publish `docs/dify/v2/xhs_production_v2_gateway.yml` in Dify.
2. Re-run synthetic Dify smoke. Pass condition:
   - provider=`dify`
   - cards count > 0
   - at least one card has non-empty title/subtitle/items
   - citations are present
3. Re-run backend smoke with real `coll_internal` citations only after confirming the imported Dify workflow is the single-card version. That exports internal citation text to Dify, so it should remain an explicit approval step.
