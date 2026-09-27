from __future__ import annotations

from vault_config import add_theme, read_themes, remove_theme


def _use_tmp_vault(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("VAULTS_ROOT", str(tmp_path))


def test_read_themes_returns_empty_list_when_no_file_exists(monkeypatch, tmp_path):
    _use_tmp_vault(monkeypatch, tmp_path)

    assert read_themes("some_workspace") == []


def test_add_theme_then_read_themes_returns_it_in_order(monkeypatch, tmp_path):
    _use_tmp_vault(monkeypatch, tmp_path)

    add_theme("ws1", "customer_problems", "Customer Problems")
    add_theme("ws1", "strategic", "Strategic")

    assert read_themes("ws1") == [
        ("customer_problems", "Customer Problems"),
        ("strategic", "Strategic"),
    ]


def test_add_theme_returns_false_and_is_a_no_op_when_key_already_exists(monkeypatch, tmp_path):
    _use_tmp_vault(monkeypatch, tmp_path)
    add_theme("ws1", "strategic", "Strategic")

    added = add_theme("ws1", "strategic", "Strategic (again)")

    assert added is False
    assert read_themes("ws1") == [("strategic", "Strategic")]


def test_remove_theme_returns_true_and_removes_the_line(monkeypatch, tmp_path):
    _use_tmp_vault(monkeypatch, tmp_path)
    add_theme("ws1", "customer_problems", "Customer Problems")
    add_theme("ws1", "strategic", "Strategic")

    removed = remove_theme("ws1", "customer_problems")

    assert removed is True
    assert read_themes("ws1") == [("strategic", "Strategic")]


def test_remove_theme_returns_false_when_key_not_found(monkeypatch, tmp_path):
    _use_tmp_vault(monkeypatch, tmp_path)

    assert remove_theme("ws1", "nope") is False


def test_themes_are_scoped_per_workspace(monkeypatch, tmp_path):
    _use_tmp_vault(monkeypatch, tmp_path)
    add_theme("ws1", "strategic", "Strategic")

    assert read_themes("ws2") == []


def test_themes_file_is_plain_hand_editable_markdown(monkeypatch, tmp_path):
    """The whole point of moving off Postgres - a person should be able to
    open this file and understand/edit it directly."""
    _use_tmp_vault(monkeypatch, tmp_path)
    add_theme("ws1", "org_decisions", "Org Decisions")

    contents = (tmp_path / "ws1" / "themes.md").read_text()

    assert "# Themes" in contents
    assert "- org_decisions: Org Decisions" in contents
