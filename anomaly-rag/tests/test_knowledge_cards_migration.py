"""Static verification for the prepared central SQL Server migration."""

from __future__ import annotations

import ast
from pathlib import Path


MIGRATION_PATH = Path(__file__).parents[1] / "alembic" / "versions" / "0007_create_knowledge_cards.py"


def test_knowledge_card_migration_targets_existing_revision_0006() -> None:
    module = ast.parse(MIGRATION_PATH.read_text(encoding="utf-8"))
    assignments = {
        node.targets[0].id: ast.literal_eval(node.value)
        for node in module.body
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id in {"revision", "down_revision"}
    }
    assert assignments == {
        "revision": "0007",
        "down_revision": "0006",
    }


def test_migration_uses_role_not_direct_application_user_grants() -> None:
    migration_source = MIGRATION_PATH.read_text(encoding="utf-8")
    assert "GRANT SELECT, INSERT, UPDATE, DELETE" in migration_source
    assert "TO [astra_app_role]" in migration_source
    assert "TO [astra_collaborator]" not in migration_source
    assert "astra_collaborator is not a member" in migration_source
