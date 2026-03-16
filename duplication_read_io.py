from pathlib import Path


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
