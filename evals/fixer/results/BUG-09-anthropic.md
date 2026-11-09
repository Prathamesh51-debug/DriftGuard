### Fixer eval: BUG-09 (anthropic)

| Runs | Diff applies | Applies on first try | Source check passes | Avg generation seconds |
|---|---|---|---|---|
| 3 | 3/3 | 3/3 | 2/3 | 10.1 |

Answered by: anthropic x3

Source checks only. This does not establish a live PayPal Sandbox fix rate for BUG-09.

Failures:
- run 2: the webhook deduplication guard was not found
