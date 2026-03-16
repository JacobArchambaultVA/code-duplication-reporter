# Code Duplication Reporter

Scans a set of repositories, finds duplicated text-based files by normalized content, and writes workspace-level duplication reports.

## What it does

- Walks each target repo under a base directory.
- Reads common text/config/code file types.
- Normalizes content before matching (ignores blank lines and `#` comment lines).
- Groups duplicate clusters as either:
  - `cross-repo` (same content in multiple repos)
  - `per-repo` (duplicates inside one repo)
- Writes:
  - `workspace-duplication-report.csv`
  - `workspace-duplication-report.md`

## Run

Example with custom repos and output dir:

```bash
python generate_duplication_report.py \
  --base-dir ~/source/repos \
  --repos repo-a repo-b repo-c \
  --output-dir duplication-reports
```

Example passing in a subset of neighboring repos from the command line:

```bash
python generate_duplication_report.py \
  --repos $(ls .. | grep -i ped-services)
```

Default paths:

- `--base-dir`: `~/source/repos`
- `--output-dir`: `duplication-reports` (created under `--base-dir`)

