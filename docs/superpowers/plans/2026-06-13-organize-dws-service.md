# DWS Service Organization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the DWS service under `apps`, group root pretrained weights under `weights/pretrained`, and remove machine-specific source paths.

**Architecture:** Keep the DWS application internally self-contained under `apps/DWSVisionCountService`. Resolve configuration-relative paths from the YAML file location, while the release script derives the repository root from its own location and accepts explicit parameter or environment overrides.

**Tech Stack:** Python, pytest, PowerShell, Markdown, Git repository layout tests

---

### Task 1: Lock the target repository layout

**Files:**
- Modify: `tests/test_repository_layout.py`

- [x] Add assertions for the new DWS, pretrained weight, and Markdown locations.
- [x] Run the layout tests and confirm they fail because files have not moved.

### Task 2: Make DWS paths portable

**Files:**
- Modify: `DWSVisionCountService/tests/test_config.py`
- Modify: `DWSVisionCountService/app/config.py`
- Modify: `DWSVisionCountService/app/main.py`
- Modify: `DWSVisionCountService/scripts/build_windows_release.ps1`
- Modify: `DWSVisionCountService/config.yaml`
- Modify: `DWSVisionCountService/config/config.yaml`
- Modify: `DWSVisionCountService/packaging/windows/config.yaml`

- [x] Add tests proving relative model and default config paths are independent of the current working directory.
- [x] Run the tests and confirm the old working-directory behavior fails.
- [x] Resolve relative paths from the loaded YAML file and derive release defaults from the repository root.
- [x] Run the focused DWS tests and Ruff.

### Task 3: Move the service, weights, and scoped documents

**Files:**
- Move: `DWSVisionCountService` to `apps/DWSVisionCountService`
- Move: root `*.pt` files to `weights/pretrained`
- Move: `CHANGELOG.md` to `apps/cvds_annotation_tool_v2_3/CHANGELOG.md`
- Move: `OPENCODE_TUNING.md` to `.opencode/docs/OPENCODE_TUNING.md`
- Move: DWS `WINDOWS_USER_GUIDE.md` to `apps/DWSVisionCountService/docs/WINDOWS_USER_GUIDE.md`

- [x] Verify all source and destination paths are inside the repository.
- [x] Move the approved files without deleting unrelated content.
- [x] Update source, tests, `.gitignore`, `opencode.json`, README, and architecture references.

### Task 4: Verify and record

**Files:**
- Modify: `CONTEXT.md`

- [x] Run focused repository and DWS tests.
- [x] Run the full Python test suite and Ruff checks.
- [x] Search for obsolete active paths and machine-specific DWS build defaults.
- [x] Review the diff for accidental changes, then update `CONTEXT.md`.
