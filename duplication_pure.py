def normalize_lines(text: str):
    return [
        stripped
        for line in text.splitlines()
        if (stripped := line.strip())
        and not stripped.startswith("#")
        and not stripped.startswith("//")
    ]


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
