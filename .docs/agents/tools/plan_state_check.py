#!/usr/bin/env python3
"""Check UV project .docs plan state consistency.

This script is intentionally dependency-free so it can be copied into any
project at `.docs/agents/tools/plan_state_check.py`.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path


CURRENT_STAGE_KEYS = ("current_stage", "current stage")
CURRENT_CHECKPOINT_KEYS = ("current_checkpoint", "current checkpoint")
NON_ACTIVE_STATUSES = {"completed", "archived", "cancelled", "canceled"}
PORTFOLIO_STATES = ("active", "paused", "completed")


@dataclass
class Finding:
    level: str
    path: Path
    message: str


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def parse_frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---"):
        return {}

    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}

    data: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        value = value.strip().strip("'\"")
        data[key.strip()] = value
    return data


def get_status(path: Path) -> str:
    return parse_frontmatter(read_text(path)).get("status", "").strip().lower()


def get_current_value(text: str, frontmatter: dict[str, str], keys: tuple[str, ...]) -> str:
    for key in keys:
        if key in frontmatter:
            return normalize_id(frontmatter[key])

    label = "|".join(re.escape(key).replace("\\ ", r"\s+") for key in keys)
    match = re.search(rf"(?im)^\s*(?:{label})\s*:\s*`?([0-9]{{2}}(?:-[0-9]{{2}})?)`?\s*$", text)
    return normalize_id(match.group(1)) if match else ""


def normalize_id(value: str) -> str:
    match = re.search(r"\d{2}(?:-\d{2})?", value)
    return match.group(0) if match else value.strip()


def find_prefixed_file(folder: Path, prefix: str) -> Path | None:
    if not folder.exists():
        return None

    exact = folder / f"{prefix}.md"
    if exact.exists():
        return exact

    matches = sorted(folder.glob(f"{prefix}*.md"))
    return matches[0] if matches else None


def extract_section(text: str, heading: str) -> str:
    pattern = rf"(?ims)^##\s+{re.escape(heading)}\s*$([\s\S]*?)(?=^##\s+|\Z)"
    match = re.search(pattern, text)
    return match.group(1).strip() if match else ""


def plan_title(plan_text: str) -> str:
    match = re.search(r"(?m)^#\s+(.+?)\s*$", plan_text)
    return match.group(1).strip() if match else ""


def get_labeled_value(text: str, *labels: str) -> str:
    """Return a non-placeholder Markdown `Label: value` field when present."""
    label = "|".join(re.escape(item) for item in labels)
    match = re.search(rf"(?im)^\s*(?:-\s+)?(?:{label})\s*:\s*(.+?)\s*$", text)
    if not match:
        return ""
    value = match.group(1).strip().strip("`")
    return "" if value.startswith("<") and value.endswith(">") else value


def has_heading(text: str, heading: str) -> bool:
    return bool(re.search(rf"(?im)^##\s+{re.escape(heading)}\s*$", text))


def check_plan(project_root: Path, plan_dir: Path) -> list[Finding]:
    findings: list[Finding] = []
    plan_path = plan_dir / "plan.md"
    if not plan_path.exists():
        return [Finding("ERROR", plan_dir, "active plan directory has no plan.md")]

    plan_text = read_text(plan_path)
    fm = parse_frontmatter(plan_text)
    plan_status = fm.get("status", "").strip().lower()
    current_stage = get_current_value(plan_text, fm, CURRENT_STAGE_KEYS)
    current_checkpoint = get_current_value(plan_text, fm, CURRENT_CHECKPOINT_KEYS)

    if plan_status and plan_status != "active":
        findings.append(Finding("ERROR", plan_path, f"active plan has status={plan_status!r}"))
    if not current_stage:
        findings.append(Finding("ERROR", plan_path, "missing current_stage/current stage"))
    if not current_checkpoint:
        findings.append(Finding("ERROR", plan_path, "missing current_checkpoint/current checkpoint"))

    stage_path = find_prefixed_file(plan_dir / "stages", current_stage) if current_stage else None
    checkpoint_path = (
        find_prefixed_file(plan_dir / "checkpoints", current_checkpoint) if current_checkpoint else None
    )

    if current_stage and not stage_path:
        findings.append(Finding("ERROR", plan_path, f"current stage {current_stage} file not found"))
    if current_checkpoint and not checkpoint_path:
        findings.append(Finding("ERROR", plan_path, f"current checkpoint {current_checkpoint} file not found"))

    if stage_path:
        stage_status = get_status(stage_path)
        if stage_status in NON_ACTIVE_STATUSES:
            findings.append(
                Finding(
                    "ERROR",
                    stage_path,
                    f"plan points to stage {current_stage}, but stage status is {stage_status!r}",
                )
            )

    if checkpoint_path:
        checkpoint_status = get_status(checkpoint_path)
        if checkpoint_status in NON_ACTIVE_STATUSES:
            findings.append(
                Finding(
                    "ERROR",
                    checkpoint_path,
                    f"plan points to checkpoint {current_checkpoint}, but checkpoint status is {checkpoint_status!r}",
                )
            )

    handoff_path = plan_dir / "handoff.md"
    if handoff_path.exists() and current_checkpoint:
        handoff_text = read_text(handoff_path)
        next_step = extract_section(handoff_text, "Next Step") or extract_section(handoff_text, "Next Action")
        if next_step and current_checkpoint not in next_step:
            findings.append(
                Finding(
                    "ERROR",
                    handoff_path,
                    f"handoff next step does not mention current checkpoint {current_checkpoint}",
                )
            )
        elif not next_step:
            findings.append(Finding("WARN", handoff_path, "handoff has no Next Step/Next Action section"))
    elif not handoff_path.exists():
        findings.append(Finding("WARN", plan_dir, "active plan has no handoff.md"))

    plans_index = project_root / ".docs" / "plans" / "index.md"
    if plans_index.exists():
        index_text = read_text(plans_index)
        title = plan_title(plan_text)
        if plan_dir.name not in index_text and (not title or title not in index_text):
            findings.append(Finding("WARN", plans_index, f"active plan {plan_dir.name!r} not referenced"))

    return findings


def check_portfolio_plan(project_root: Path, plan_dir: Path, state: str) -> list[Finding]:
    """Check lifecycle fields without changing the normal active-plan checker."""
    plan_path = plan_dir / "plan.md"
    if not plan_path.exists():
        return [Finding("ERROR", plan_dir, f"{state} plan directory has no plan.md")]

    findings: list[Finding] = []
    plan_text = read_text(plan_path)
    actual_status = get_status(plan_path)
    if actual_status != state:
        findings.append(Finding("ERROR", plan_path, f"{state} plan has status={actual_status!r}"))

    handoff_path = plan_dir / "handoff.md"
    handoff_text = read_text(handoff_path) if handoff_path.exists() else ""

    if state == "active":
        if not handoff_path.exists():
            findings.append(Finding("ERROR", plan_dir, "active plan has no handoff.md"))
        if not get_labeled_value(plan_text, "Current checkpoint"):
            findings.append(Finding("ERROR", plan_path, "active plan lacks a current checkpoint"))
        if not (get_labeled_value(plan_text, "Owner") or get_labeled_value(handoff_text, "Owner")):
            findings.append(Finding("ERROR", plan_path, "active plan lacks an owner"))
        if not (get_labeled_value(plan_text, "Next action") or get_labeled_value(handoff_text, "Next action")):
            findings.append(Finding("ERROR", plan_path, "active plan lacks a concrete next action"))
        if not get_labeled_value(plan_text, "Intended integration branch"):
            findings.append(Finding("ERROR", plan_path, "active plan lacks an intended integration branch"))

    if state == "paused":
        if not (get_labeled_value(plan_text, "Paused because") or get_labeled_value(handoff_text, "Paused because")):
            findings.append(Finding("ERROR", plan_path, "paused plan lacks a waiting reason"))
        if not (get_labeled_value(plan_text, "Resume trigger") or get_labeled_value(handoff_text, "Resume trigger")):
            findings.append(Finding("ERROR", plan_path, "paused plan lacks a resume trigger"))

    if state == "completed":
        if not has_heading(plan_text, "Completion Evidence"):
            findings.append(Finding("ERROR", plan_path, "completed plan lacks Completion Evidence"))
        if not get_labeled_value(plan_text, "Integration"):
            findings.append(Finding("ERROR", plan_path, "completed plan lacks integration evidence"))
        if not get_labeled_value(plan_text, "Verification"):
            findings.append(Finding("ERROR", plan_path, "completed plan lacks verification evidence"))

    disposition = get_labeled_value(plan_text, "Worktree disposition") or get_labeled_value(
        handoff_text, "Worktree disposition"
    )
    if disposition and disposition not in {"integrate", "preserve-paused", "commit-and-resume", "remove"}:
        findings.append(Finding("ERROR", plan_path, f"unknown worktree disposition {disposition!r}"))

    return findings


def run_portfolio(project_root: Path) -> int:
    master_root = project_root / ".docs" / "plans" / "master"
    all_findings: list[Finding] = []
    plans_checked = 0
    for state in PORTFOLIO_STATES:
        state_root = master_root / state
        if not state_root.exists():
            continue
        for plan_dir in sorted(path for path in state_root.iterdir() if path.is_dir()):
            plans_checked += 1
            if state == "active":
                # Reuse the normal state gate so a portfolio audit also catches
                # current-pointer and handoff drift.
                all_findings.extend(check_plan(project_root, plan_dir))
            all_findings.extend(check_portfolio_plan(project_root, plan_dir, state))

    errors = [finding for finding in all_findings if finding.level == "ERROR"]
    for finding in all_findings:
        rel_path = finding.path.relative_to(project_root) if finding.path.is_relative_to(project_root) else finding.path
        print(f"{finding.level}: {rel_path}: {finding.message}")
    if errors:
        print(f"FAIL: portfolio audit found {len(errors)} error(s)")
        return 1
    print(f"OK: portfolio audit checked {plans_checked} plan(s)")
    return 0


def run(project_root: Path, only_plan: str | None = None) -> int:
    docs_root = project_root / ".docs"
    active_root = docs_root / "plans" / "master" / "active"
    if not active_root.exists():
        print(f"OK: no active master plans under {active_root}")
        return 0

    plan_dirs = [path for path in sorted(active_root.iterdir()) if path.is_dir()]
    if only_plan:
        plan_dirs = [path for path in plan_dirs if path.name == only_plan]
        if not plan_dirs:
            print(f"ERROR: active plan {only_plan!r} not found under {active_root}")
            return 1

    all_findings: list[Finding] = []
    for plan_dir in plan_dirs:
        all_findings.extend(check_plan(project_root, plan_dir))

    errors = [finding for finding in all_findings if finding.level == "ERROR"]
    for finding in all_findings:
        rel_path = finding.path.relative_to(project_root) if finding.path.is_relative_to(project_root) else finding.path
        print(f"{finding.level}: {rel_path}: {finding.message}")

    if errors:
        print(f"FAIL: {len(errors)} error(s), {len(all_findings) - len(errors)} warning(s)")
        return 1

    print(f"OK: checked {len(plan_dirs)} active master plan(s), {len(all_findings)} warning(s)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Check .docs master-plan state consistency.")
    parser.add_argument("project_root", nargs="?", default=".", help="Project root with .docs/")
    parser.add_argument("--plan", help="Check one active master plan directory name")
    parser.add_argument(
        "--portfolio",
        action="store_true",
        help="Audit active, paused, and completed plan lifecycle fields",
    )
    args = parser.parse_args()

    if args.portfolio:
        return run_portfolio(Path(args.project_root).resolve())
    return run(Path(args.project_root).resolve(), args.plan)


if __name__ == "__main__":
    raise SystemExit(main())
