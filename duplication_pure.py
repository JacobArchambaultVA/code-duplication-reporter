import hashlib
from collections import defaultdict


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
