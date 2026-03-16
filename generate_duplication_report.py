import argparse
import hashlib
import os
from collections import defaultdict
from datetime import date
from pathlib import Path


TEXT_EXTS = {
    ".bat",
    ".conf",
    ".cfg",
    ".cs",
    ".csv",
    ".groovy",
    ".ini",
    ".j2",
    ".js",
    ".json",
    ".jsonc",
    ".md",
    ".properties",
    ".ps1",
    ".py",
    ".sh",
    ".sql",
    ".template",
    ".tf",
    ".tfvars",
    ".ts",
    ".txt",
    ".xml",
    ".yml",
    ".yaml",
}

IGNORE_DIRS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    ".pytest_cache",
    "__pycache__",
    ".mypy_cache",
    ".idea",
    ".vscode",
    ".terraform",
    ".vs",
    "bin",
    "obj",
    "testresults",
    "publish",
    "artifacts",
}


def is_text_file(path: Path, text_extensions) -> bool:
    name = path.name.lower()
    return (
        path.suffix.lower() in text_extensions
        or "jenkinsfile" in name
        or "dockerfile" in name
    )


def read_text(path: Path):
    data = path.read_bytes()
    if b"\x00" in data:
        return None
    for encoding in ("utf-8", "latin-1"):
        try:
            return data.decode(encoding)
        except Exception:
            pass
    return None


def normalize(text: str) -> str:
    return "\n".join(
        stripped
        for line in text.splitlines()
        if (stripped := line.strip()) and not stripped.startswith("#")
    )


def normalize_lines(text: str):
    return [
        stripped
        for line in text.splitlines()
        if (stripped := line.strip())
        and not stripped.startswith("#")
        and not stripped.startswith("//")
    ]


def iter_block_hashes(lines, block_size):
    if len(lines) < block_size:
        return

    for start in range(0, len(lines) - block_size + 1):
        window = "\n".join(lines[start : start + block_size])
        yield (
            hashlib.sha1(window.encode("utf-8", "ignore")).hexdigest(),
            start + 1,
            start + block_size,
        )


def dup_score(cluster) -> int:
    total_lines = 0
    max_lines = 0
    for item in cluster:
        line_count = item["lines"]
        total_lines += line_count
        if line_count > max_lines:
            max_lines = line_count
    return total_lines - max_lines


def flatten_files(cluster):
    if cluster and "start" in cluster[0] and "end" in cluster[0]:
        return "; ".join(
            f"{item['repo']}:{item['path']} (norm-lines {item['start']}-{item['end']})"
            for item in sorted(cluster, key=lambda x: (x["repo"], x["path"]))
        )

    return "; ".join(
        f"{item['repo']}:{item['path']} ({item['lines']} lines)"
        for item in sorted(cluster, key=lambda x: (x["repo"], x["path"]))
    )


def members_key(cluster):
    return tuple(sorted((item["repo"], item["path"]) for item in cluster))


def starts_key(cluster):
    return tuple(
        item["start"] for item in sorted(cluster, key=lambda x: (x["repo"], x["path"]))
    )


def overlaps_or_adjacent(a_cluster, b_cluster):
    a_members = sorted(a_cluster, key=lambda x: (x["repo"], x["path"]))
    b_members = sorted(b_cluster, key=lambda x: (x["repo"], x["path"]))
    return all(
        b["start"] <= a["end"] + 1 and a["start"] <= b["end"] + 1
        for a, b in zip(a_members, b_members)
    )


def merge_cluster_members(a_cluster, b_cluster):
    a_members = sorted(a_cluster, key=lambda x: (x["repo"], x["path"]))
    b_members = sorted(b_cluster, key=lambda x: (x["repo"], x["path"]))
    merged = []
    for a, b in zip(a_members, b_members):
        merged.append(
            {
                "repo": a["repo"],
                "path": a["path"],
                "start": min(a["start"], b["start"]),
                "end": max(a["end"], b["end"]),
                "lines": max(a["end"], b["end"]) - min(a["start"], b["start"]) + 1,
            }
        )
    return merged


def merge_overlapping_clusters(clusters):
    grouped = defaultdict(list)
    for cluster in clusters:
        grouped[members_key(cluster)].append(cluster)

    merged_clusters = []
    for file_key in grouped:
        ordered = sorted(grouped[file_key], key=starts_key)
        current = ordered[0]
        for candidate in ordered[1:]:
            if overlaps_or_adjacent(current, candidate):
                current = merge_cluster_members(current, candidate)
            else:
                merged_clusters.append(current)
                current = candidate
        merged_clusters.append(current)

    return merged_clusters


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
        "--block-mode",
        action="store_true",
        help="Enable normalized block-level duplicate detection instead of whole-file matching",
    )
    parser.add_argument(
        "--min-dup-lines",
        type=int,
        default=10,
        help="Minimum normalized contiguous lines for block duplication matching",
    )
    args = parser.parse_args()

    base_dir = Path(args.base_dir)
    text_extensions = {ext.lower() for ext in args.text_extensions}

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
                if args.block_mode:
                    lines = normalize_lines(text)
                    for block_hash, start, end in iter_block_hashes(
                        lines, args.min_dup_lines
                    ):
                        norm_map[block_hash].append(
                            {
                                "repo": root.name,
                                "path": str(path.relative_to(root)).replace("\\", "/"),
                                "lines": args.min_dup_lines,
                                "start": start,
                                "end": end,
                            }
                        )
                else:
                    norm_map[
                        hashlib.sha1(normalize(text).encode("utf-8", "ignore")).hexdigest()
                    ].append(
                        {
                            "repo": root.name,
                            "path": str(path.relative_to(root)).replace("\\", "/"),
                            "lines": text.count("\n") + 1,
                        }
                    )

    if args.block_mode:
        raw_clusters = [cluster for cluster in norm_map.values() if len(cluster) >= 2]
        clusters = merge_overlapping_clusters(raw_clusters)
    else:
        clusters = [cluster for cluster in norm_map.values() if len(cluster) >= 2]

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

    with (out_dir / "workspace-duplication-report.md").open(
        "w", encoding="utf-8"
    ) as handle:
        handle.write("# Workspace Duplication Report\n\n")
        handle.write(f"- Generated: {date.today().isoformat()}\n")
        handle.write(f"- Files analyzed: {analyzed_files}\n")
        if args.block_mode:
            handle.write("- Matching mode: normalized block matching\n")
            handle.write(f"- Min duplicated block lines: {args.min_dup_lines}\n")
        else:
            handle.write("- Matching mode: normalized only\n")
        handle.write(f"- Normalized clusters: {len(rows)}\n")
        handle.write(f"- Cross-repo clusters: {len(cross)}\n\n")

        handle.write("## Top Cross-Repo Clusters\n\n")
        for i, row in enumerate(cross[:25], 1):
            handle.write(
                f"{i}. **{row['cluster_id']}** ({row['mode']}): copies={row['copy_count']}, dup_lines~{row['dup_lines_est']}\n"
            )
            handle.write(f"   - Repos: {row['repos']}\n")
            for member in row["files"].split("; ")[:6]:
                handle.write(f"   - {member}\n")
            handle.write("\n")

        for repo in sorted(per_repo):
            handle.write(f"## Top Per-Repo Clusters: {repo}\n\n")
            for i, row in enumerate(per_repo[repo][:20], 1):
                handle.write(
                    f"{i}. **{row['cluster_id']}** ({row['mode']}): copies={row['copy_count']}, dup_lines~{row['dup_lines_est']}\n"
                )
                for member in row["files"].split("; ")[:6]:
                    handle.write(f"   - {member}\n")
                handle.write("\n")

    print(f"Wrote {out_dir / 'workspace-duplication-report.md'}")
    print(f"Total clusters: {len(rows)}")


if __name__ == "__main__":
    main()