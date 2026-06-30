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

1. Re-import/publish `docs/dify/v2/xhs_production_v2_gateway.yml` in Dify.
2. Re-run synthetic Dify smoke. Pass condition:
   - provider=`dify`
   - cards count > 0
   - at least one card has non-empty title/subtitle/items
   - citations are present
3. Only after synthetic smoke passes, decide whether to run backend smoke with real `coll_internal` citations. That exports internal citation text to Dify, so it should be an explicit approval step.

