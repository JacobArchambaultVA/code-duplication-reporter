from datetime import date


def write_workspace_report(out_dir, analyzed_files, block_mode, min_dup_lines, rows, cross, per_repo):
    with (out_dir / "workspace-duplication-report.md").open(
        "w", encoding="utf-8"
    ) as handle:
        handle.write("# Workspace Duplication Report\n\n")
        handle.write(f"- Generated: {date.today().isoformat()}\n")
        handle.write(f"- Files analyzed: {analyzed_files}\n")
        if block_mode:
            handle.write("- Matching mode: normalized block matching\n")
            handle.write(f"- Min duplicated block lines: {min_dup_lines}\n")
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
