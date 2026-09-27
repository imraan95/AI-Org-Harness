"""Per-workspace theme config, stored as a plain markdown file instead of
a database table - the personal-vault architecture pivot (build-plan,
docs/decisions - "markdown theme config"). Each workspace gets one file,
<VAULTS_ROOT>/<workspace_id>/themes.md, holding a "- key: Label" bullet
per theme: human-readable and hand-editable, the same convention
memoryvault-kit's markdown-vault research (docs/research) turned up.

Replaces libs/db's custom_knowledge_types table (T077) as the storage for
a workspace's user-defined themes. That table and its migration are left
in place, unused, rather than dropped in this pass - see the ADR for why.

Deployment note: VAULTS_ROOT should point at a persistent volume outside
the git checkout in any real deployment (this is per-user data, not
source). Left as a plain env var default for local dev; not yet wired
into any deployment config.
"""

from __future__ import annotations

import os
from pathlib import Path

_HEADER = "# Themes"


def vault_root() -> Path:
    """Root directory holding one subdirectory per workspace. Overridable
    via VAULTS_ROOT (e.g. for tests); defaults to ./vaults in the current
    working directory for local dev."""
    return Path(os.environ.get("VAULTS_ROOT", "vaults"))


def _themes_file(workspace_id: str) -> Path:
    return vault_root() / workspace_id / "themes.md"


def read_themes(workspace_id: str = "default") -> list[tuple[str, str]]:
    """Returns [(key, label), ...] in file order. Empty list if the
    workspace has no themes.md yet - the common/default case, same as a
    workspace with no custom_knowledge_types rows under the old table."""
    path = _themes_file(workspace_id)
    if not path.exists():
        return []
    themes: list[tuple[str, str]] = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line.startswith("- ") or ":" not in line:
            continue
        key, _, label = line[2:].partition(":")
        themes.append((key.strip(), label.strip()))
    return themes


def add_theme(workspace_id: str, key: str, label: str) -> bool:
    """Appends a new theme line. Returns False (no-op) if `key` is already
    present, mirroring the old table's unique (workspace_id, key)
    constraint - the caller (harness-api) turns that into a 409."""
    if any(existing_key == key for existing_key, _ in read_themes(workspace_id)):
        return False
    path = _themes_file(workspace_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(_HEADER + "\n\n")
    with path.open("a") as f:
        f.write(f"- {key}: {label}\n")
    return True


def remove_theme(workspace_id: str, key: str) -> bool:
    """Returns True if a theme was removed, False if `key` wasn't found."""
    existing = read_themes(workspace_id)
    if not any(existing_key == key for existing_key, _ in existing):
        return False
    remaining = [(k, label) for k, label in existing if k != key]
    lines = [_HEADER, ""] + [f"- {k}: {label}" for k, label in remaining]
    _themes_file(workspace_id).write_text("\n".join(lines) + "\n")
    return True
