# Issues — pi-config-hardening

(No issues yet — Wave 1 starting)

## F3 Real Manual QA — test regex over-broad (non-blocking)

The QA spec for batch-convert.md uses:
`grep -E "/wiki_(test|scan|convert_page)\s" .pi/prompts/batch-convert.md`
commented "Should NOT contain old-format commands".

Issue: `\s` matches any whitespace, so the regex matches the NEW-format
commands too (e.g. `/wiki_scan --limit 10`, `/wiki_convert_page page_name=...`)
because they have a space after the command name. The regex does not
distinguish old-format (`dry_run=`, `scan_only=`, `namespace=`) from new-format
(`--confirm`, `--limit`).

Verification of actual intent (old-format markers `dry_run=|scan_only=|namespace=`)
returns zero matches — the migration is correct. Only the test regex is
too broad. Recommend replacing the regex with one that targets old-format
markers explicitly, e.g. `grep -E "(dry_run|scan_only|namespace)="`.
