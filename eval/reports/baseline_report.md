# Baseline Failure Report

This report documents failure cases discovered while testing the baseline Data Commons NL Query CLI.

## Summary

The baseline pipeline is functional for straightforward English queries such as:

- `What was the population of USA in 2020?`

However, it still fails or degrades on multilingual inputs, ambiguous entity resolution, topic-vs-stat-var confusion, and sparse downstream data coverage.

---

## Failure Cases

### 1. Multilingual Metric Resolved to the Wrong Entity

```json
{
  "input": "台灣 2020 年人口是多少？",
  "expected_behavior": "Normalize the query into English, resolve Taiwan and population correctly, and return a 2020 population observation or a clear fallback.",
  "actual_behavior": "Before prompt hardening, the metric query remained in Chinese and the resolver returned an unrelated topic-like entity instead of a usable statistical variable.",
  "root_cause": "The parser did not initially normalize multilingual metric terms into English. The indicator resolver also returned mixed-quality candidates, and the baseline metric resolver trusted the first candidate too aggressively.",
  "fix_status": "partially_fixed"
}
```

Notes:

- The parser prompt was updated to force English normalization for `place_query` and `metric_query`.
- This improved the canonical payload from `台灣 / 人口` to `Taiwan / population`.
- The issue is only partially fixed because multilingual robustness still depends on the LLM parser path.

---

### 2. LLM Output Type Drift Broke Schema Validation

```json
{
  "input": "What was Taiwan's population in 2020?",
  "expected_behavior": "Accept a valid canonical payload even if the LLM emits the year as a number.",
  "actual_behavior": "The baseline schema rejected payloads where `time.value` was returned as an integer instead of a string.",
  "root_cause": "The schema assumed strict string types and did not initially account for common LLM formatting variations.",
  "fix_status": "fixed"
}
```

Notes:

- The schema now coerces `value`, `start`, and `end` into strings before validation.

---

### 3. Ambiguous Place Resolution Was Too Conservative

```json
{
  "input": "Taiwan",
  "expected_behavior": "Resolve to the most likely place candidate and continue.",
  "actual_behavior": "The baseline resolver originally raised an ambiguity error as soon as the place resolver returned more than one candidate.",
  "root_cause": "The resolver was too conservative and did not trust the Data Commons candidate ranking.",
  "fix_status": "fixed"
}
```

Notes:

- The place resolver now takes the first API candidate in `api` mode.
- This made common cases such as `Taiwan` and `California` runnable again.

---

### 4. State-Level Places Also Produced Multiple Candidates

```json
{
  "input": "GDP of California in 2018",
  "expected_behavior": "Resolve California to the U.S. state and return the requested GDP observation.",
  "actual_behavior": "The place resolver initially failed because Data Commons returned multiple candidates for California.",
  "root_cause": "The original place-resolution strategy treated any multi-candidate response as a hard failure.",
  "fix_status": "fixed"
}
```

Notes:

- This failure mode was addressed by trusting the first place candidate in baseline `api` mode.
- After that fix, `California` correctly resolved to `geoId/06`.

---

### 5. Metric Resolution Returned a Topic Instead of a Statistical Variable

```json
{
  "input": "GDP of California in 2018",
  "expected_behavior": "Resolve GDP to a usable statistical variable such as `Amount_EconomicActivity_GrossDomesticProduction`.",
  "actual_behavior": "The metric resolver returned `dc/topic/GDP`, which is a topic rather than an observation-ready statistical variable.",
  "root_cause": "The Data Commons indicator resolver can return both `Topic` and `StatisticalVariable` candidates, but the baseline resolver currently picks the first candidate without filtering for `StatisticalVariable`.",
  "fix_status": "fixed"
}
```

Notes:

- The stat-var resolver now scans candidates and selects the first item whose `typeOf` includes `StatisticalVariable`.
- A deterministic resolution judge was added before execution. If the selected metric is still a `dc/topic/...` node, the query is rejected instead of executed.

Hardening solution:

- Prefer `StatisticalVariable` candidates over `Topic` candidates during resolution.
- Add a pre-execution guardrail that rejects topic-like metrics even if the resolver falls back to a non-stat-var candidate.
- Expose top candidates and scores in `resolution_evidence` so mismatches can be debugged and audited.

---

### 6. Correct Resolution Still Failed When the Requested Observation Was Missing

```json
{
  "input": "台灣 2020 年人口是多少？",
  "expected_behavior": "Return a 2020 population value for Taiwan, or clearly explain that the requested year is unavailable and offer the latest available observation.",
  "actual_behavior": "After the parser and resolvers were corrected, the final query resolved to `country/TWN + Count_Person + 2020`, but the observation endpoint still returned no value.",
  "root_cause": "The downstream Data Commons data source does not expose a matching 2020 observation for this exact entity/stat-var/date combination, even though a latest observation is available.",
  "fix_status": "unresolved"
}
```

Notes:

- `LATEST` returned a recent observation for Taiwan population, while `2020` returned no observation.
- This indicates a data-availability problem, not a parsing or entity-resolution problem.

---

### 7. Missing Geography Was Silently Hallucinated

```json
{
  "input": "female population over 50",
  "expected_behavior": "Return a canonical payload with no geography and surface a clear execution error indicating that a place is required.",
  "actual_behavior": "The parser previously filled in `United States` even though the user never specified any geography.",
  "root_cause": "The original schema required `place_query`, which encouraged the LLM to invent a default place instead of leaving the field empty.",
  "fix_status": "fixed"
}
```

Notes:

- The canonical payload now allows `place_query` to be `null`.
- The prompt explicitly forbids inventing a place when the query does not specify one.
- The execution layer now returns a partial response with `place = null` and a warning instead of silently assuming a geography.

Hardening solution:

- Relax the schema so `place_query` can be `null`.
- Update the prompt so the model must not invent a default geography.
- Return a non-executed partial response rather than failing closed or inventing a place.

---

### 8. Aggregation Operations Were Not Supported in the Baseline

```json
{
  "input": "average GDP of California and Texas in 2018",
  "expected_behavior": "Resolve both places and the GDP metric, execute the observation lookups, and compute the requested aggregation in the application layer.",
  "actual_behavior": "The baseline pipeline only supports single-place execution and does not yet perform application-layer aggregation such as average, sum, min, max, ranking, or pairwise difference.",
  "root_cause": "The original baseline focused on single observation retrieval and did not implement post-query arithmetic or ranking over multiple returned place values.",
  "fix_status": "fixed"
}
```

Notes:

- Data Commons observation APIs do not expose general-purpose request-time aggregation operators such as `sum` or `avg`.
- Aggregation is now implemented in the application layer after retrieving one observation result per place.
- The hardened implementation supports:
  - `compare`
  - `difference`
  - `rank`
  - `sum`
  - `average`
  - `min`
  - `max`

Hardening solution:

- Extend the canonical schema to represent aggregation operations explicitly.
- Parse multi-place aggregation queries into one primary place plus comparison places.
- Execute one observation lookup per resolved place and compute the final aggregate in the application layer.

---

### 9. Compare Queries Could Be Parsed Correctly but Serialized into an Unexecutable Shape

```json
{
  "input": "Compare the unemploymnt rate of Japan and Korea in 2020",
  "expected_behavior": "Normalize the typo, identify both places, and represent the comparison as one primary place plus one comparison place so the execution layer can run it.",
  "actual_behavior": "The LLM produced a `compare_places` payload with `place_query = null` and both places inside `comparison.places`, which caused the execution layer to treat the query as missing geography and skip execution.",
  "root_cause": "The model captured the semantic intent correctly, but its compare payload shape did not match the canonical downstream assumption that one place lives in `place_query` and the rest live in `comparison.places`.",
  "fix_status": "fixed"
}
```

Notes:

- The schema now normalizes this pattern automatically.
- If `intent = compare_places`, `place_query = null`, and at least two places are present in `comparison.places`, the first place is promoted into `place_query` and the remaining places stay in `comparison.places`.

Hardening solution:

- Normalize compare payloads after parsing so the downstream execution shape is always consistent.
- Deduplicate any place that appears in both `place_query` and `comparison.places`.

---

### 10. General API-Driven Place Resolution Still Fails on Ambiguous or Underspecified Place Names

```json
{
  "input": "Compare the unemploymnt rate of Japan and Korea in 2020",
  "expected_behavior": "Normalize the typo, resolve both places through the general resolver flow, and execute the comparison or clearly surface unresolved ambiguity.",
  "actual_behavior": "The parser normalized the metric and extracted both places, but the upstream Data Commons place resolver returned no candidates for `Korea`, so execution failed at place resolution.",
  "root_cause": "The system intentionally relies on a general API-driven resolver rather than ad hoc alias rules for ambiguous place names. `Korea` is underspecified, and the upstream resolve API does not return a stable candidate for it.",
  "fix_status": "partially_fixed"
}
```

Notes:

- `South Korea` resolves to `country/KOR`.
- `North Korea` resolves to `country/PRK`.
- During later testing, the upstream resolve API began returning `country/KOR` for `Korea`, so this particular example now succeeds without local hardcoded aliases.
- The broader ambiguity problem remains unresolved because the system still depends on upstream ranking for underspecified place names.

---

### 11. Conflicting Time Constraints Are Silently Collapsed Instead of Rejected

```json
{
  "input": "Show Taiwan population in 2020 and 2021 only from 2010 to 2015",
  "expected_behavior": "Detect that the query contains incompatible time constraints and return a structured conflict error.",
  "actual_behavior": "The pipeline silently chose the range `2010-2015` and discarded the explicit years `2020` and `2021`.",
  "root_cause": "The baseline parser and execution flow do not perform explicit constraint-consistency checks. When conflicting time expressions are present, one interpretation is selected and the rest are ignored.",
  "fix_status": "fixed"
}
```

Notes:

- The hardened pipeline now runs a separate time-constraint analyzer over the raw query and rejects incompatible combinations before execution.

Hardening solution:

- Extract all temporal signals from the raw query using a dedicated time analyzer.
- Keep the execution payload simple (`year | range | latest`) but compare it against the full set of observed time constraints.
- Reject contradictory combinations such as `range + explicit year` or `latest + explicit year` before calling the observation API.

---

### 12. Single-Year and Range Constraints Compete Without Any Conflict Check

```json
{
  "input": "Show unemployment rate of Japan from 2015 to 2020 in 2018 only",
  "expected_behavior": "Reject the query as temporally inconsistent or request clarification.",
  "actual_behavior": "The pipeline selected the single year `2018` and ignored the range `2015-2020`.",
  "root_cause": "The baseline treats time parsing as a best-effort extraction task rather than a validated constraint-solving step.",
  "fix_status": "fixed"
}
```

Notes:

- A similar collapse also happens for queries such as `average population of Japan and Korea from 2010 to 2020 in 2018`.
- The presence of a valid answer should not hide the fact that the input constraints were contradictory.

---

### 13. `latest` and Explicit Year Constraints Are Not Treated as Mutually Exclusive

```json
{
  "input": "What was the latest population of USA in 2020?",
  "expected_behavior": "Recognize that `latest` and `in 2020` are incompatible and return a controlled conflict response.",
  "actual_behavior": "The pipeline resolved the query as a plain 2020 point lookup and silently dropped the `latest` instruction.",
  "root_cause": "The baseline has no post-parse temporal conflict validator, so one time expression can dominate the other without surfacing the contradiction.",
  "fix_status": "fixed"
}
```

Notes:

- The current behavior effectively assigns hidden precedence to the explicit year.
- That precedence is not documented or exposed to the user.

---

### 14. Multiple Explicit Year Constraints Can Collapse Into a Different Single Year

```json
{
  "input": "Compare GDP of California and Texas in 2018 and 2020, but only for 2019",
  "expected_behavior": "Reject the query as temporally inconsistent or ask for clarification about the intended year selection.",
  "actual_behavior": "The pipeline kept only `2019` and dropped the earlier explicit years `2018` and `2020`.",
  "root_cause": "The baseline does not preserve or validate multiple time constraints once a single parse path has been selected.",
  "fix_status": "fixed"
}
```

Notes:

- This shows that conflict collapse is not limited to year-vs-range conflicts.
- Multiple explicit years can also be overwritten by another explicit year later in the sentence.

Hardening solution for cases 12-14:

- Add a pre-execution temporal conflict check fed by an LLM-assisted time-signal extractor with heuristic fallback.
- Reject `latest + year`, `range + year`, and multi-year contradictions with `only` / `but` modifiers.
- Treat aggregation and ranking queries as single-time-point operations unless explicitly redesigned for time-series aggregation.

---

## Additional Failures Found During Eval Generation and Multi-Model Evaluation

After the baseline was hardened, a second round of failures surfaced while programmatically generating adversarial eval data and running the same dataset across multiple models. These failures were important because they were not simple domain-resolution bugs; they exposed weaknesses in structured-output robustness and model-to-model payload consistency.

### 15. The Model Sometimes Returned a Top-Level List Instead of a Single Payload Object

```json
{
  "input": "What was the population of Taiwan in 2020 and 2021, and also from 2010 to 2015?",
  "expected_behavior": "Return one canonical payload object, even if the query is contradictory.",
  "actual_behavior": "Some models returned a JSON list of candidate payloads instead of one canonical payload object, which failed schema validation before the judge could reject the query.",
  "root_cause": "The parser prompt originally emphasized the target schema but did not strongly constrain the model away from returning alternate interpretations as multiple objects.",
  "fix_status": "fixed"
}
```

Notes:

- This showed up most clearly on contradiction-heavy prompts.
- A lenient normalization pass now unwraps single-item top-level lists before schema validation.
- The parser prompt was updated to explicitly require exactly one JSON object and forbid alternate interpretations.

---

### 16. The Model Sometimes Serialized Arrays or Objects as Strings

```json
{
  "input": "Rank the population of California, Texas, and New York in 2020.",
  "expected_behavior": "Return `comparison.places` as a JSON array of strings.",
  "actual_behavior": "Some model outputs serialized the place list as a string such as `\"['Texas', 'New York']\"`, which later degraded comparison-place handling.",
  "root_cause": "The prompt specified the semantic schema but did not explicitly forbid stringified JSON fragments, and some models collapsed structured fields into string literals under pressure.",
  "fix_status": "fixed"
}
```

Notes:

- A normalization layer now attempts to parse embedded JSON-like and Python-like structures inside string fields.
- This significantly improved robustness on ranking and multi-place comparison prompts.

---

### 17. Gemini Occasionally Returned Malformed JSON Keys Such as `\"\"value\"\"`

```json
{
  "input": "Compare Japan's unemployement rate in 2020 with Korea.",
  "expected_behavior": "Return valid JSON keys and values in the canonical payload.",
  "actual_behavior": "Gemini occasionally returned malformed JSON with keys such as `\"\"value\"\"`, which caused strict `json.loads` parsing to fail before the payload even reached schema validation.",
  "root_cause": "The model occasionally emitted near-JSON rather than valid JSON, especially on typo-heavy compare queries.",
  "fix_status": "fixed"
}
```

Notes:

- The Gemini client now applies a small lenient repair pass before decoding.
- This repair step is intentionally narrow and only targets obvious formatting corruption, not semantic rewrites.

---

### 18. Some Models Added Extra Helper Fields Instead of Returning Only the Canonical Payload

```json
{
  "input": "What was the population of Taiwan in 2020 and 2021, and also from 2010 to 2015?",
  "expected_behavior": "Return only the canonical payload fields expected by the schema.",
  "actual_behavior": "Some models injected extra fields such as `additional_times` or alternate-comparison helper fields, which caused `extra_forbidden` validation failures.",
  "root_cause": "The original parser prompt was not explicit enough that the payload must contain only the canonical keys and no helper metadata.",
  "fix_status": "fixed"
}
```

Notes:

- The parser now runs a self-correction round when the first candidate fails validation.
- The correction prompt asks the model to preserve meaning while removing helper fields and malformed structure.

---

### 19. Eval Data Generation Drifted Away From the Intended Ground Truth

```json
{
  "input": "請告訴我台灣在2023年的人口數。",
  "expected_behavior": "For a `LATEST` blueprint, generate a query that still means `latest`, not a specific year.",
  "actual_behavior": "The first-generation eval dataset sometimes drifted semantically, such as converting `latest` into `2023` or turning `average` into a generic comparison phrasing.",
  "root_cause": "A generation-only pipeline trusted the model to preserve semantics without verifying the generated query against the system's own parser and execution path.",
  "fix_status": "fixed"
}
```

Notes:

- This issue affected the usefulness of the generated eval set itself.
- The dataset generator now performs a generate-then-validate loop and rewrites cases whose resolved query does not match the blueprint.
- This is why `generated_cases_verified.json` is the preferred dataset over the earlier raw generated version.

---

### 20. Operation Semantics Can Still Drift Even When the JSON Shape Is Valid

```json
{
  "input": "What is the average GDP for California in 2018 compared to Texas?",
  "expected_behavior": "Interpret the request as an `average` aggregation over two places.",
  "actual_behavior": "Even after the payload format is valid, some models still choose `comparison.operation = compare` instead of `average`.",
  "root_cause": "This is a semantic interpretation error rather than a formatting error. The phrase `compared to` can pull some models toward the default compare operation even when `average` is also present.",
  "fix_status": "partially_fixed"
}
```

Notes:

- Prompt tightening improved this in some cases but did not eliminate it.
- This remains a genuine model-understanding issue rather than a pure schema-robustness problem.

---

### 21. Place Resolution Still Confuses `New York` State with `New York City`

```json
{
  "input": "Rank the population of California, Texas, and New York in 2020.",
  "expected_behavior": "Resolve `New York` to the U.S. state when it appears in a list of peer U.S. states.",
  "actual_behavior": "The resolver often returns `geoId/3651000` (New York City) instead of `geoId/36` (New York State), which causes otherwise-correct structured outputs to fail exact-match eval scoring.",
  "root_cause": "The current API-driven place resolver trusts the top-ranked candidate and does not yet use peer-group context strongly enough to disambiguate state-vs-city candidates.",
  "fix_status": "unresolved"
}
```

Notes:

- This issue also affects max/rank queries such as `Which place had the highest GDP in 2018 among California, Texas, and New York?`
- The remaining gap is no longer payload formatting. It is context-sensitive entity disambiguation at resolution time.

Hardening solution for cases 15-21:

- Tighten the parser prompt around general structured-output discipline rather than adding brittle domain-specific hard rules.
- Normalize single-item top-level lists and parse stringified structured fields before schema validation.
- Add a self-correction LLM pass when the first candidate fails schema validation.
- Keep semantic failures such as `average -> compare` and `New York state -> New York City` visible as true remaining challenges rather than hiding them with overfitted post-processing.

---

## Remaining Hard Problems

The most difficult remaining failures are not simple bugs:

1. Topic vs StatisticalVariable disambiguation
   The resolver must distinguish between concept-like entities and observation-ready variables, even when the API returns both.

2. Multilingual normalization quality
   The current system relies on the LLM parser to normalize non-English input into English canonical phrases. Without the LLM path, multilingual behavior is weaker.

3. Missing downstream observations
   Even when parsing and resolution are correct, the requested data may not exist for the requested year. This requires a product decision about fallbacks, not just a code fix.

4. Ambiguity handling strategy
   The baseline now prefers execution by trusting the first candidate. This is useful for demoability, but it is not a fully reliable long-term strategy for ambiguous places or metrics.

5. Structured-output reliability across models
   Different models fail in different ways even when they broadly understand the task. Some fail semantically, while others fail by returning malformed JSON or extra helper fields. This means eval quality depends not only on domain reasoning but also on robust output-conformance handling.
