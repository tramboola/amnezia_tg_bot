import runpy
from pathlib import Path

import pytest

HELPERS = runpy.run_path(str(Path(__file__).parents[1] / ".docs/agents/tools/plan_state_check.py"))


@pytest.mark.parametrize("text", ["Owner: Codex", "- Owner: Codex", "  Owner: Codex"])
def test_portfolio_checker_reads_lifecycle_labels_from_supported_markdown(text):
    assert HELPERS["get_labeled_value"](text, "Owner") == "Codex"


def test_portfolio_checker_finds_headings():
    assert HELPERS["has_heading"]("## Completion Evidence\n\nVerified", "Completion Evidence")
