# Data Commons NL Query CLI

Natural-language CLI for public statistics over Data Commons, plus a multi-model evaluation pipeline for structured query generation.

This repository is the final submission for a two-part challenge:

1. Build a tool that converts natural language into a structured public-data query and executes it.
2. Design an eval pipeline that measures how well multiple LLMs generate the correct structured query for that domain.

---

## Challenge Summary

This project targets **Data Commons** because it naturally decomposes a user query into:

- place
- statistical variable
- time constraint
- optional comparison or aggregation intent

The final system does not ask the model to generate raw API URLs. It asks the model to generate a canonical intermediate payload, then resolves that payload into Data Commons IDs and executes the request.

Final deliverables in this repo include:

- a working CLI for natural-language statistical queries
- a documented baseline failure report
- a hardened parser and execution pipeline
- a programmatic eval-data generator
- verified 30-case adversarial datasets
- multi-model evaluation reports
- a final three-model comparison in which all chosen models exceed 85% accuracy on the verified dataset

---

## Repository Map

Primary implementation:

- [src/dc_nl_cli/cli.py](/Users/vincenthsia/GoFreight_Homework/src/dc_nl_cli/cli.py:1)
- [src/dc_nl_cli/pipeline.py](/Users/vincenthsia/GoFreight_Homework/src/dc_nl_cli/pipeline.py:1)
- [src/dc_nl_cli/parser/service.py](/Users/vincenthsia/GoFreight_Homework/src/dc_nl_cli/parser/service.py:1)
- [src/dc_nl_cli/judge.py](/Users/vincenthsia/GoFreight_Homework/src/dc_nl_cli/judge.py:1)
- [src/dc_nl_cli/datacommons/query_builder.py](/Users/vincenthsia/GoFreight_Homework/src/dc_nl_cli/datacommons/query_builder.py:1)

Evaluation tooling:

- [eval/generate_dataset.py](/Users/vincenthsia/GoFreight_Homework/eval/generate_dataset.py:1)
- [eval/run_eval.py](/Users/vincenthsia/GoFreight_Homework/eval/run_eval.py:1)
- [src/dc_nl_cli/eval_runner.py](/Users/vincenthsia/GoFreight_Homework/src/dc_nl_cli/eval_runner.py:1)

Primary datasets and reports:

- [eval/datasets/generated_cases_verified.json](/Users/vincenthsia/GoFreight_Homework/eval/datasets/generated_cases_verified.json:1)
- [eval/reports/baseline_report.md](/Users/vincenthsia/GoFreight_Homework/eval/reports/baseline_report.md:1)
- [eval/reports/generated_eval_report_openai_verified.json](/Users/vincenthsia/GoFreight_Homework/eval/reports/generated_eval_report_openai_verified.json:1)
- [eval/reports/generated_eval_report_gemini25flash_repaired.json](/Users/vincenthsia/GoFreight_Homework/eval/reports/generated_eval_report_gemini25flash_repaired.json:1)
- [eval/reports/generated_eval_report_groq_verified.json](/Users/vincenthsia/GoFreight_Homework/eval/reports/generated_eval_report_groq_verified.json:1)

---

## Quick Start

Install dependencies:

```bash
uv sync
```

Run a single query:

```bash
uv run dc-query "What was Taiwan's population in 2020?"
```

Run the verified eval dataset:

```bash
uv run python eval/run_eval.py --dataset eval/datasets/generated_cases_verified.json
```

Example provider-specific eval commands:

```bash
LLM_PROVIDER=openai LLM_MODEL=gpt-4.1-mini uv run python eval/run_eval.py --dataset eval/datasets/generated_cases_verified.json --resolver-mode api --max-workers 10 --output eval/reports/generated_eval_report_openai_verified.json
```

```bash
LLM_PROVIDER=gemini LLM_MODEL=gemini-2.5-flash REQUEST_TIMEOUT_SECONDS=90 uv run python eval/run_eval.py --dataset eval/datasets/generated_cases_verified.json --resolver-mode api --max-workers 10 --output eval/reports/generated_eval_report_gemini25flash_repaired.json
```

```bash
LLM_PROVIDER=groq LLM_MODEL=llama-3.3-70b-versatile REQUEST_TIMEOUT_SECONDS=90 uv run python eval/run_eval.py --dataset eval/datasets/generated_cases_verified.json --resolver-mode api --max-workers 1 --max-rpm 20 --output eval/reports/generated_eval_report_groq_verified.json
```

```bash
LLM_PROVIDER=ollama LLM_MODEL=gemma4:e2b REQUEST_TIMEOUT_SECONDS=180 uv run python eval/run_eval.py --dataset eval/datasets/generated_cases_verified.json --resolver-mode api --max-workers 1 --output eval/reports/generated_eval_report_ollama_gemma4_e2b.json
```

---

## Part 1: Build a Tool, Break It, and Harden It

### Part 1 Overview

The baseline tool accepts a natural-language question about public statistics, converts it into a canonical payload, resolves user-facing labels into Data Commons-compatible IDs, executes the downstream request, and returns normalized structured output.

The domain choice is deliberate: Data Commons is broad enough to create meaningful ambiguity and failure cases, but structured enough to support exact-match evaluation.

### Part 1 Architecture

```text
User query
  -> LLM parser
  -> canonical payload
  -> place / stat-var / time resolution
  -> resolution judge
  -> Data Commons query
  -> normalized result
```

### Part 1 Canonical Schema

The model is asked to produce an intermediate canonical payload rather than raw API syntax.

Current canonical fields:

- `intent`
- `place_query`
- `metric_query`
- `time`
- `comparison`

Representative shape:

```json
{
  "intent": "get_stat_point | get_stat_series | compare_places",
  "place_query": "string | null",
  "metric_query": "string",
  "time": {
    "type": "year | range | latest",
    "value": "string | null",
    "start": "string | null",
    "end": "string | null"
  },
  "comparison": {
    "places": ["string"],
    "operation": "compare | rank | difference | sum | average | min | max"
  }
}
```

### Part 1 Baseline Execution

The baseline pipeline already supports end-to-end execution.

Example:

```text
What was Taiwan's population in 2020?
```

Expected flow:

1. Parse into canonical payload.
2. Resolve `Taiwan -> country/TWN`.
3. Resolve `population -> Count_Person`.
4. Resolve `2020 -> 2020`.
5. Query Data Commons and return normalized JSON.

Additional supported patterns:

- single-place latest-value queries
- multi-place compare queries
- application-layer aggregation queries
- missing-place partial responses
- multilingual input when the LLM path is enabled

Representative supported queries:

```bash
uv run dc-query "What was Taiwan's population in 2020?"
uv run dc-query "What is the population of Taiwan?"
uv run dc-query "average GDP of California and Texas in 2018"
uv run dc-query "rank California, Texas, and New York by population in 2020"
```

### Part 1 Break It

The baseline was intentionally stress-tested with:

- typos
- multilingual prompts
- ambiguous places
- missing geography
- unsupported metrics
- temporal contradictions
- malformed structured outputs
- comparison and aggregation phrasing

The detailed failure log lives in [baseline_report.md](/Users/vincenthsia/GoFreight_Homework/eval/reports/baseline_report.md:1).

The break-it phase surfaced two broad classes of failure:

- **domain failures**, such as ambiguous places, unsupported metrics, and contradictory time constraints
- **structured-output failures**, such as malformed JSON, extra helper fields, top-level lists, and stringified arrays

That split became important later in the multi-model eval, because some models understood the question semantically but still failed on output conformance.

### Part 1 Harden It

The baseline was then hardened in several ways:

- compare payload normalization
- multilingual normalization
- type-robust canonical schema
- API-driven place resolution
- statistical-variable filtering
- missing-place partial responses
- application-layer aggregation
- temporal conflict detection
- deterministic resolution judge
- syntax-level malformed-JSON repair
- parser self-correction after schema failure
- stricter general structured-output guidance in the parser prompt

These changes were motivated by concrete break-it failures, not speculative cleanup.

The most important hardening decisions were:

- keep the model responsible for high-level interpretation, but never for final API syntax
- let deterministic resolution and judging catch unsafe executions
- keep local normalization limited to syntax-level cleanup, and push schema-shape repair back onto the LLM through validation-guided self-correction
- keep unresolved ambiguity visible rather than silently forcing a brittle guess

### Part 1 Remaining Hard Problems

Some failures remain fundamentally difficult:

- ambiguous entity resolution such as `Georgia`
- metric ambiguity such as `income`
- sparse or missing downstream observations for a requested year
- peer-group disambiguation such as `New York` state versus `New York City`
- semantic drift between operations such as `average` and `compare`

---

## Part 2: The Multi-Model Eval Challenge

### Part 2 Overview

The eval does not score whether an API call merely succeeds. It scores whether the model generated the correct structured interpretation of the user query for this domain.

### Part 2 Dataset Generation

The final dataset pipeline is programmatic rather than purely handwritten:

1. Define a blueprint containing the intended ground truth.
2. Ask an LLM to generate natural-language adversarial queries from that blueprint.
3. Validate those generated queries against the current parser and execution path.
4. Rewrite failed generations until the generated query matches the intended blueprint.

This is implemented in [generate_dataset.py](/Users/vincenthsia/GoFreight_Homework/eval/generate_dataset.py:1).

Two important dataset artifacts exist:

- [generated_cases.json](/Users/vincenthsia/GoFreight_Homework/eval/datasets/generated_cases.json:1): raw first-pass generation
- [generated_cases_verified.json](/Users/vincenthsia/GoFreight_Homework/eval/datasets/generated_cases_verified.json:1): validated and corrected version used for final evals

### Part 2 Ground Truth Design

The dataset contains 30 adversarial cases spanning:

- typos
- multilingual input
- missing geography
- unsupported metrics
- ambiguous places
- contradictory time constraints
- ranking and aggregation requests
- comparison payload edge cases

The eval dataset was designed to break both semantic understanding and structured-output reliability.

### Part 2 Models Evaluated

The final three-model set used for submission is:

1. `gemini-2.5-flash` via Gemini API
   Closed-source. Chosen because it is a widely used fast general-purpose model and provided a strong baseline for multilingual and structured-output tasks.
2. `gpt-4.1-mini` via OpenAI
   Closed-source. Chosen because it is strong on instruction following and compact structured outputs, which makes it a useful comparison point for canonical-payload generation.
3. `llama-3.3-70b-versatile` via Groq
   Open-weight serving target. Chosen to satisfy the open-weight requirement while still testing a large instruction-tuned model on the same structured-output task.

This set gives:

- at least 3 models
- a mix of closed-source and open-weight
- providers with meaningfully different failure patterns

### Part 2 Evaluation Method

The current scoring logic is implemented in [eval_runner.py](/Users/vincenthsia/GoFreight_Homework/src/dc_nl_cli/eval_runner.py:1).

Current rules:

- success cases pass only when the resolved query exactly matches the expected fields
- error cases pass only when the deterministic judge rejects the query
- comparison fields are exact-match checked when present

The eval intentionally scores the **resolved query**, not just the raw parser payload. This matters because many practical failures happen after parsing:

- place resolution can select the wrong entity
- a metric can resolve to a topic instead of a usable statistical variable
- contradiction handling can fail before execution
- aggregation operations can drift semantically even when the JSON shape is valid

### Part 2 Results

Final results on [generated_cases_verified.json](/Users/vincenthsia/GoFreight_Homework/eval/datasets/generated_cases_verified.json:1):

| Model | Provider | Type | Accuracy | Success Accuracy | Error Accuracy | Report |
| --- | --- | --- | ---: | ---: | ---: | --- |
| `gemini-2.5-flash` | Gemini | Closed-source | `0.9333` | `0.9048` | `1.0000` | [report](/Users/vincenthsia/GoFreight_Homework/eval/reports/generated_eval_report_gemini25flash_repaired.json:1) |
| `gpt-4.1-mini` | OpenAI | Closed-source | `0.9333` | `0.9048` | `1.0000` | [report](/Users/vincenthsia/GoFreight_Homework/eval/reports/generated_eval_report_openai_verified.json:1) |
| `llama-3.3-70b-versatile` | Groq | Open-weight serving target | `0.8667` | `0.8571` | `0.8889` | [report](/Users/vincenthsia/GoFreight_Homework/eval/reports/generated_eval_report_groq_verified.json:1) |

All three chosen models exceeded the `>85%` threshold on the verified 30-case adversarial dataset.

### Part 2 Performance Analysis

`gemini-2.5-flash` tied for best overall after parser hardening, reaching `0.9333`. Its biggest early weakness was structured-output robustness: malformed JSON keys, top-level list returns, and stringified fields. After tightening the correction prompt and making schema-shape repair validation-guided, those failures mostly disappeared. Its remaining misses are resolver-level, not formatting-level: both are `New York` state-vs-city ambiguity cases downstream of an otherwise correct parse.

`gpt-4.1-mini` improved to the same `0.9333` overall accuracy after the same parser hardening. Earlier failures around helper fields such as `additional_times` and malformed `time` shapes disappeared once those cases were routed through validation-guided self-correction rather than local shape patches. Its remaining misses are the same two difficult downstream cases: `New York` state-vs-city ambiguity, with one of those also drifting from `max` to `rank`.

`llama-3.3-70b-versatile` via Groq cleared the threshold, but it was more sensitive to provider operational limits during experimentation. On final successful runs, its main weaknesses were still a mix of one output-shape inconsistency on a multilingual latest-value case, one contradiction case that degraded into a `warn` rather than a hard reject, and the same `New York` ambiguity seen in the other models.

Across all three models, the most persistent shared failure was not generic parsing. It was **context-sensitive entity resolution** after parsing, especially when a place name matched both a state and a city.

### Part 2 Prompt and Pipeline Iteration

The eval exceeded the threshold only after several concrete iterations:

1. The parser prompt was rewritten from a mostly schema-oriented instruction into a more general structured-output guideline that explicitly forbids top-level lists, helper fields, and stringified nested structures.
2. The parser path added narrow syntax-level normalization before validation. This catches serialization issues such as malformed JSON keys, top-level single-item lists, and stringified comparison lists without silently repairing semantic field shapes.
3. A self-correction pass was added when the first parser candidate fails schema validation. The correction prompt preserves intent while repairing malformed field shapes such as bare-string `time` values or extra helper keys.
4. The dataset generator itself was hardened. A first-pass generated dataset was not reliable enough, so the final dataset generation flow became generate-then-validate-then-rewrite.
5. Eval-time provider controls were added, including optional global RPM limiting, because operational rate limits can otherwise distort evaluation quality.

The most important lesson from these iterations is that structured-output eval quality depends on the evaluation pipeline itself being robust, not just the model prompt.

### Part 2 Learnings

1. **Structured-output reliability is a separate engineering problem from semantic understanding.** A model can understand the task and still fail the eval because it emitted malformed JSON, extra fields, or stringified substructures.
2. **Programmatically generated eval data must itself be validated.** The first generated dataset drifted away from the intended blueprint. Without a verification loop, the eval set would have measured dataset-generation noise instead of model quality.
3. **Exact-match scoring on resolved queries is stricter but more honest.** It exposes resolver ambiguity and downstream grounding errors that would be hidden by payload-only scoring.
4. **Different models fail differently.** Some models are more likely to fail structurally, while others are more likely to fail semantically on contradiction handling or aggregation wording.
5. **Hardening should prefer general guidance over brittle hard rules.** The most useful fixes were output-discipline improvements, repair passes, and self-correction loops, not narrow one-off prompt patches for individual examples.

### Part 2 Limitations

Current limitations that should remain visible:

- `New York` state versus city ambiguity
- `average` phrasing drifting toward plain compare
- missing observations in Data Commons
- provider-specific timeout and quota behavior

These are real limitations of the current system, not hidden eval bugs. They are intentionally left visible so the submission reflects the actual boundary between engineering hardening and unresolved ambiguity.

---

## Development Notes

Run tests:

```bash
uv run pytest
```

Useful eval-related tests:

- [tests/test_eval_runner.py](/Users/vincenthsia/GoFreight_Homework/tests/test_eval_runner.py:1)
- [tests/test_generate_dataset.py](/Users/vincenthsia/GoFreight_Homework/tests/test_generate_dataset.py:1)
- [tests/test_parser_service.py](/Users/vincenthsia/GoFreight_Homework/tests/test_parser_service.py:1)
- [tests/test_gemini_client.py](/Users/vincenthsia/GoFreight_Homework/tests/test_gemini_client.py:1)
- [tests/test_llm_wrappers.py](/Users/vincenthsia/GoFreight_Homework/tests/test_llm_wrappers.py:1)
- [tests/test_llm_factory.py](/Users/vincenthsia/GoFreight_Homework/tests/test_llm_factory.py:1)

---
