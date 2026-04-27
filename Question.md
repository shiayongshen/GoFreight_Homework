Please complete the two-part challenge below.
Part 1: Build a Tool, Break It, and Harden It
The Objective: Build a Command Line Interface (CLI) tool in any language that takes a natural
language query about a public dataset and converts it into a structured API request or database
query.
The Domain: Choose a public API or database to target. (Examples: GitHub API, Wikidata, or
Data Commons).
Requirements:
1. Baseline Execution: Build the core logic. The tool must be able to take a natural
language input, generate the structured query, actually execute that query against the
API/DB, and return the results.
2. Break It: Once your baseline works, try to break it. Feed it ambiguous inputs, conflicting
constraints, typos, and languages other than English. Document the failure cases you
find.
3. Harden &amp; Fix: Fix the most critical failure cases you discovered. As part of this
hardening phase, your tool must now correctly handle complex edge cases.
4. Explain: Provide a detailed technical explanation in your README for why any
remaining failure cases you couldn&#39;t fix are fundamentally hard to solve.
Part 2: The Multi-Model Eval Challenge
The Objective: Evaluating Large Language Models rigorously is often harder than simply
calling their APIs. Now that you have built your tool, design an evaluation pipeline to test how
well different models perform at generating the correct structured queries for your specific
domain.
Requirements:
1. Data Generation: Programmatically gather or generate 30 realistic, diverse natural
language queries targeting your chosen domain. Include edge cases, messy phrasing,
and complex constraints.
2. Ground Truth: Write the perfect, correct structured query (your ground truth) for each of
these inputs. These test cases must be complex, adversarial, and nuanced enough to
actively break the models.
3. Execution &amp; Iteration: Run your evaluation pipeline using at least 3 different models,
which must be a mix of both open-weight and closed-source models.
4. The Threshold: Iterate on your prompts and pipeline until all of your chosen models hit
&gt;85% accuracy against your manually labeled set.
5. Write-up: In your README, provide an analysis covering:

○ Model Selection: How did you choose these specific 3+ models? Why were they
capable of hitting the accuracy threshold across the board?
○ Performance: Compare how the models performed. What patterns did they
initially get wrong?
○ Learnings: What did you learn about eval design and building ground truth for
structured outputs?
