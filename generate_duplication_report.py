import argparse
import os
from collections import defaultdict
from pathlib import Path

from duplication_block_mode import iter_block_hashes, merge_overlapping_clusters
from duplication_constants import IGNORE_DIRS, TEXT_EXTS
from duplication_file_mode import add_file_mode_match
from duplication_read_io import is_text_file, read_text
from duplication_write_io import write_workspace_report
from duplication_pure import (
    dup_score,
    flatten_files,
    normalize_lines,
)

def main():
    parser = argparse.ArgumentParser(description="Generate duplicate-code report")
    parser.add_argument(
        "--base-dir",
        default=str(Path.home() / "source" / "repos"),
        help="Base directory containing repositories",
    )
    parser.add_argument(
        "--repos",
        nargs="*",
        default=[],
        help="Repository folder names under base-dir",
    )
    parser.add_argument(
        "--output-dir",
        default="duplication-reports",
        help="Output directory under base-dir",
    )
    parser.add_argument(
        "--text-extensions",
        nargs="*",
        default=TEXT_EXTS,
        help="List of text file extensions to scan (for example: .py .cs .json)",
    )
    parser.add_argument(
        "--min-dup-lines",
        type=int,
        default=None,
        help=(
            "Enable block-level duplication matching using this minimum number "
            "of normalized contiguous lines"
        ),
    )
    args = parser.parse_args()

    if args.min_dup_lines is not None and args.min_dup_lines < 1:
        parser.error("--min-dup-lines must be a positive integer")

    base_dir = Path(args.base_dir)
    text_extensions = {ext.lower() for ext in args.text_extensions}
    block_mode = args.min_dup_lines is not None

    repos = args.repos
    out_dir = base_dir / args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    analyzed_files = 0
    norm_map = defaultdict(list)
    for root in (base_dir / repo for repo in repos):
        if not root.exists():
            continue
        for dp, dns, fns in os.walk(root):
            dns[:] = [d for d in dns if d.lower() not in IGNORE_DIRS]
            for filename in fns:
                path = Path(dp) / filename
                if not is_text_file(path, text_extensions):
                    continue
                text = read_text(path)
                if not text:
                    continue

                analyzed_files += 1
                normalized_lines = normalize_lines(text)
                relative_path = str(path.relative_to(root)).replace("\\", "/")
                if block_mode:
                    for block_hash, start, end in iter_block_hashes(
                        normalized_lines, args.min_dup_lines
                    ):
                        norm_map[block_hash].append(
                            {
                                "repo": root.name,
                                "path": relative_path,
                                "lines": args.min_dup_lines,
                                "start": start,
                                "end": end,
                            }
                        )
                else:
                    add_file_mode_match(
                        norm_map,
                        normalized_lines,
                        root.name,
                        relative_path,
                        text.count("\n") + 1,
                    )
    raw_clusters = [cluster for cluster in norm_map.values() if len(cluster) >= 2]
    clusters = merge_overlapping_clusters(raw_clusters) if block_mode else raw_clusters

    rows = [
        {
            "cluster_id": f"normalized-{cluster_num:04d}",
            "mode": "normalized",
            "scope": "cross-repo" if len(repos) > 1 else "per-repo",
            "repos": ", ".join(repos),
            "repo_count": len(repos),
            "copy_count": len(cluster),
            "dup_lines_est": dup_score(cluster),
            "files": flatten_files(cluster),
        }
        for cluster_num, cluster in enumerate(clusters, 1)
        if (repos := {item["repo"] for item in cluster})
    ]

    rows.sort(key=lambda r: (r["dup_lines_est"], r["copy_count"]), reverse=True)

    per_repo = defaultdict(list)
    cross = []
    for row in rows:
        if row["scope"] == "cross-repo":
            cross.append(row)
        else:
            per_repo[row["repos"].split(",")[0].strip()].append(row)

    write_workspace_report(
        out_dir,
        analyzed_files,
        block_mode,
        args.min_dup_lines,
        rows,
        cross,
        per_repo,
    )

    print(f"Wrote {out_dir / 'workspace-duplication-report.md'}")
    print(f"Total clusters: {len(rows)}")


if __name__ == "__main__":
    main()