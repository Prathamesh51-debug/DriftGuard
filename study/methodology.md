# Study data: what it can and cannot show

`study/repos.json` contains 25 anonymized rows with labels for payment integration patterns. The scripts in this folder count those labels and test the report format. They are useful for exercising the scanner and for designing a future study.

The repository does **not** include source repository URLs, pinned commits, hand-labeling notes, raw scanner outputs, or PayPal Sandbox run records for those 25 rows. We therefore cannot independently reproduce the labels or treat their percentages as measured vulnerability prevalence. The earlier claim that 5 of 7 external apps double-charged or lost orders under live faults is also unsupported by saved per-app evidence here. Neither number belongs in a public impact claim.

The supported live result is narrower: DriftGuard's deliberately seeded demo shop has saved F1–F4 local red-to-green runs against PayPal Sandbox. See [the fixer evaluation](../evals/fixer/results/live-fixer-eval.md). Those runs measure this one controlled target, not a population of public shops.

To turn the annotations into a reproducible study, each row would need a public source URL and commit, inclusion rule, scanner output, human review record, and a link to any dynamic test result. Sandbox tests would also need isolated credentials and order IDs for each target. Until then, use the rows as exploratory test data only.
