import hashlib
import json
from pathlib import Path

import yaml


def parse_markdown_frontmatter(content: str) -> tuple[dict, str]:
    if not content.startswith("---"):
        return {}, content
    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}, content
    frontmatter = yaml.safe_load(parts[1]) or {}
    body = parts[2].strip()
    return frontmatter, body


def write_markdown_with_frontmatter(frontmatter: dict, body: str) -> str:
    yaml_str = yaml.dump(frontmatter, allow_unicode=True, sort_keys=False)
    return f"---\n{yaml_str}---\n\n{body}"


def parse_json_documents(content: str) -> list[dict]:
    data = json.loads(content)
    if isinstance(data, list):
        return data
    return [data]


def parse_yaml_documents(content: str) -> list[dict]:
    data = yaml.safe_load(content)
    if isinstance(data, dict):
        if "documents" in data:
            return data["documents"]
        return [data]
    if isinstance(data, list):
        return data
    return []


def calculate_file_hash(path: Path) -> str:
    content = path.read_bytes()
    return hashlib.sha256(content).hexdigest()
