import hashlib


def add_file_mode_match(norm_map, normalized_lines, root_name, relative_path, line_count):
    norm_map[
        hashlib.sha1("\n".join(normalized_lines).encode("utf-8", "ignore")).hexdigest()
    ].append(
        {
            "repo": root_name,
            "path": relative_path,
            "lines": line_count,
        }
    )
