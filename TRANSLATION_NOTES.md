

---

## Upstream provenance

This branch was created **relative to current `main`**. Insert the exact commit for provenance:

```bash
# capture upstream main SHA
MAIN_SHA=$(git rev-parse origin/main)
# record in notes
printf "
Source Python baseline: origin/main @ %s
" "$MAIN_SHA" >> TRANSLATION_NOTES.md
```

Each D file can also embed a header line like:

```d
// Provenance: dasFlex Python @ <MAIN_SHA>
```


Source Python baseline: origin/main @ 63004718a333b9576d3525190b26cd7eda8cda0e
