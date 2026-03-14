import argparse
import csv
import hashlib
import os
from collections import defaultdict
from datetime import date
from pathlib import Path


DEFAULT_REPOS = [
    # "ped-270-config/",
    # "ped-276-config/",
    # "ped-277-config/",
    # "ped-278-config/",
    # "ped-834-config/",
    # "ped-835-config/",
    # "ped-837-config/",
    # "ped-8pdl-config/",
    # "ped-999-config/",
    # "ped-ack-config/",
    # "ped-database/",
    # "ped-deidentify-config/",
    # "ped-devops/",
    # "ped-environments-config/",
    # "ped-fms-config/",
    # "ped-infra-config/",
    # "ped-paidclaims-config/",
    # "ped-pharmacy-config/",
    # "ped-powerbi/",
    # "ped-product/",
    # "ped-promotionrequest-powerapp/",
    # "ped-remediation-config/",
    # "ped-sor-config/",
    "ped-services-270/",
    "ped-services-274/",
    "ped-services-276/",
    "ped-services-277/",
    "ped-services-278/",
    "ped-services-834/",
    "ped-services-835/",
    "ped-services-837/",
    "ped-services-8pdl/",
    "ped-services-999/",
    "ped-services-ack/",
    "ped-services-common/",
    "ped-services-deidentify/",
    "ped-services-fms/",
    "ped-services-paidclaims/",
    "ped-services-pharmacy/",
    "ped-services-remediation/",
    "ped-services-sor/",
    "ped-services-test-tools/",
]

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


def is_text_file(path: Path) -> bool:
    name = path.name.lower()
    return (
        path.suffix.lower() in TEXT_EXTS
        or "jenkinsfile" in name
        or "dockerfile" in name
        or name.endswith(".j2")
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
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            continue
        lines.append(stripped)
    return "\n".join(lines)


def dup_score(cluster) -> int:
    return sum(item["lines"] for item in cluster) - max(item["lines"] for item in cluster)


def cluster_scope(cluster) -> str:
    return "cross-repo" if len({item["repo"] for item in cluster}) > 1 else "per-repo"


def choose_canonical(cluster):
    def sort_key(item):
        p = item["path"].lower()
        baseline = 0 if ("/all/" in p or p.startswith("environments/all/")) else 1
        return (baseline, len(item["path"]), item["repo"], item["path"])

    return sorted(cluster, key=sort_key)[0]


def flatten_files(cluster):
    return "; ".join(
        f"{item['repo']}:{item['path']} ({item['lines']} lines)"
        for item in sorted(cluster, key=lambda x: (x["repo"], x["path"]))
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
        default=DEFAULT_REPOS,
        help="Repository folder names under base-dir",
    )
    parser.add_argument(
        "--output-dir",
        default="duplication-reports",
        help="Output directory under base-dir",
    )
    args = parser.parse_args()

    base_dir = Path(args.base_dir)
    out_dir = base_dir / args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    records = []
    for root in (base_dir / repo for repo in args.repos):
        if not root.exists():
            continue
        for dp, dns, fns in os.walk(root):
            dns[:] = [d for d in dns if d.lower() not in IGNORE_DIRS]
            for filename in fns:
                path = Path(dp) / filename
                if not is_text_file(path):
                    continue
                text = read_text(path)
                if not text:
                    continue

                records.append(
                    {
                        "repo": root.name,
                        "path": str(path.relative_to(root)).replace("\\", "/"),
                        "lines": text.count("\n") + 1,
                        "exact_hash": hashlib.sha1(
                            text.encode("utf-8", "ignore")
                        ).hexdigest(),
                        "norm_text": normalize(text),
                    }
                )

    norm_map = defaultdict(list)
    for record in records:
        norm_map[
            hashlib.sha1(record["norm_text"].encode("utf-8", "ignore")).hexdigest()
        ].append(record)

    norm_clusters = [c for c in norm_map.values() if len(c) >= 2]

    rows = []
    cluster_num = 1
    for cluster in norm_clusters:
        repos = sorted({item["repo"] for item in cluster})
        canonical = choose_canonical(cluster)
        rows.append(
            {
                "cluster_id": f"normalized-{cluster_num:04d}",
                "mode": "normalized",
                "scope": cluster_scope(cluster),
                "repos": ", ".join(repos),
                "repo_count": len(repos),
                "copy_count": len(cluster),
                "dup_lines_est": dup_score(cluster),
                "canonical_repo": canonical["repo"],
                "canonical_path": canonical["path"],
                "files": flatten_files(cluster),
            }
        )
        cluster_num += 1

    rows.sort(key=lambda r: (r["dup_lines_est"], r["copy_count"]), reverse=True)

    with (out_dir / "workspace-duplication-report.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "cluster_id",
                "mode",
                "scope",
                "repos",
                "repo_count",
                "copy_count",
                "dup_lines_est",
                "canonical_repo",
                "canonical_path",
                "files",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

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
        handle.write(f"- Files analyzed: {len(records)}\n")
        handle.write("- Matching mode: normalized only\n")
        handle.write(f"- Normalized clusters: {len(norm_clusters)}\n")
        handle.write(
            f"- Cross-repo clusters: {sum(1 for row in rows if row['scope'] == 'cross-repo')}\n\n"
        )

        handle.write("## Top Cross-Repo Clusters\n\n")
        for i, row in enumerate(
            sorted(cross, key=lambda r: (r["dup_lines_est"], r["copy_count"]), reverse=True)[
                :25
            ],
            1,
        ):
            handle.write(
                f"{i}. **{row['cluster_id']}** ({row['mode']}): copies={row['copy_count']}, dup_lines~{row['dup_lines_est']}\n"
            )
            handle.write(f"   - Repos: {row['repos']}\n")
            handle.write(
                f"   - Canonical: {row['canonical_repo']}:{row['canonical_path']}\n"
            )
            for member in row["files"].split("; ")[:6]:
                handle.write(f"   - {member}\n")
            handle.write("\n")

        for repo in sorted(per_repo):
            handle.write(f"## Top Per-Repo Clusters: {repo}\n\n")
            for i, row in enumerate(
                sorted(
                    per_repo[repo],
                    key=lambda r: (r["dup_lines_est"], r["copy_count"]),
                    reverse=True,
                )[:20],
                1,
            ):
                handle.write(
                    f"{i}. **{row['cluster_id']}** ({row['mode']}): copies={row['copy_count']}, dup_lines~{row['dup_lines_est']}\n"
                )
                handle.write(
                    f"   - Canonical: {row['canonical_repo']}:{row['canonical_path']}\n"
                )
                for member in row["files"].split("; ")[:6]:
                    handle.write(f"   - {member}\n")
                handle.write("\n")

    print(f"Wrote {out_dir / 'workspace-duplication-report.csv'}")
    print(f"Wrote {out_dir / 'workspace-duplication-report.md'}")
    print(f"Total clusters: {len(rows)}")


if __name__ == "__main__":
    main()