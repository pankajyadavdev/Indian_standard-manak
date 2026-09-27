# Phase 21: AI quality and evaluation

## Evaluation set

`backend/tests/fixtures/ai_evaluation.json` is versioned and includes eight retrieval cases (single standard, multiple standards, and long tender), two no-match/adversarial cases, a superseded edition, normative gap, contradictory tender, Hindi standard-title query, and malicious document text. `backend/scripts/evaluate_ai.py` produces a machine-readable report against the seeded catalogue.

Hindi retrieval now expands a small, explicit dictionary of Hindi standard titles/terms into canonical English phrases and standard codes. The evaluation confirms the Hindi title for IS 456 retrieves IS 456. This is terminology coverage, not general cross-lingual semantic understanding.

## Results

The evaluation ran on the current default search threshold (`0.35`) with `all-MiniLM-L6-v2`, top 5, and metrics at rank 3:

| Metric | Mean |
|---|---:|
| Precision@3 | 0.4167 |
| Recall@3 | 1.0000 |
| MRR | 1.0000 |
| NDCG@3 | 1.0000 |

All eight known-answer retrieval cases placed every labeled relevant standard in the top 3. The six one-answer queries usually returned one result; the fixed denominator in Precision@3 counts the two unfilled positions as non-relevant. The two broad cases returned relevant standards in the top 2, with unrelated catalogue candidates appearing afterward. Both high-threshold no-match cases returned no standards. Old edition, normative gap, conflict, malicious text, and the Hindi title checks passed.

## Limits

- Labels are manually authored for a small BIS seed catalogue; these results do not establish real-world accuracy or coverage.
- `all-MiniLM-L6-v2` is English-centric. Hindi support is a curated query expansion dictionary; additional Indian languages and paraphrases remain unevaluated.
- The entity extractor can surface a standard code written in a malicious document as a *cited string*. This remains unverified input; the search/RAG path must supply catalogue evidence before presenting a standard as verified.
- Search returns some lower-ranked distractors on broad multi-standard tenders. Human review and evidence links remain required.

## Reproduction

Initialize a clean test database with both `seed_database()` and `seed_extended_relationships()`, set `DATABASE_URL` and `UPLOAD_DIR`, then run `python -m pytest -q tests/test_phase_21_ai_quality.py` or `python scripts/evaluate_ai.py` from `backend`.
