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

From this folder:

```bash
python generate_duplication_report.py
```

Default paths:

- `--base-dir`: `~/source/repos`
- `--output-dir`: `duplication-reports` (created under `--base-dir`)
- `--repos`: built-in list in `generate_duplication_report.py`
- `--repos-file`: optional text file with one repo path per line

Example with custom repos and output dir:

```bash
python generate_duplication_report.py \
  --base-dir ~/source/repos \
  --repos repo-a repo-b repo-c \
  --output-dir duplication-reports
```

Example using a repo list file from a neighboring folder:

```bash
python generate_duplication_report.py \
  --base-dir ~/source/repos \
  --repos-file ../va-dev-onboarding/repos.txt
```
