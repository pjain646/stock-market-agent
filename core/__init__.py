"""Domain core — harness-independent. Data fetchers live in the skill's
scripts/; this package holds labeling, splits, and the evaluator (the honest
judge). Nothing here imports the agent harness, so the orchestration layer
(Claude Agent SDK in v1) can be swapped without touching this code.
"""
