# Multi-Repository Restructuring Plan (Isolated Test)

**Goal:** Transition from the current single-repository (`1-t`) structure to a multi-repository setup (`1-t` for management, `opspawn-ops-core` for ops_core, `opspawn-agentkit` for agentkit) while preserving the `src` layout within each component repository to maintain `tox` compatibility. This plan uses an isolated test directory to avoid disrupting the current working state until validation is complete.

**Date:** 2025-04-10

**Rationale:**
- To provide separate, clean Git histories for the `ops_core` and `agentkit` components.
- To enable independent versioning and potential future release of components.
- To maintain the `src` layout which resolved previous `tox` environment issues related to package discovery and installation.

**Prerequisites:**
- User needs to create the test directory structure outside the current `1-t` workspace:
    - `/home/sf2/Workspace/23-opspawn/restructure-test/`
    - `/home/sf2/Workspace/23-opspawn/restructure-test/opspawn-development/`
    - `/home/sf2/Workspace/23-opspawn/restructure-test/opspawn-ops-core/`
    - `/home/sf2/Workspace/23-opspawn/restructure-test/opspawn-agentkit/`

**Plan Steps (To be executed by Cline in ACT MODE):**

1.  **Copy Current Project:**
    *   Command: `cp -r /home/sf2/Workspace/23-opspawn/1-t/. /home/sf2/Workspace/23-opspawn/restructure-test/opspawn-development/`
    *   Purpose: Create a safe, independent copy of the entire current project state in the test directory.

2.  **Populate `opspawn-ops-core` Repo (Copying):**
    *   Create `src` dir: `mkdir -p /home/sf2/Workspace/23-opspawn/restructure-test/opspawn-ops-core/src`
    *   Copy source: `cp -r /home/sf2/Workspace/23-opspawn/restructure-test/opspawn-development/src/ops_core /home/sf2/Workspace/23-opspawn/restructure-test/opspawn-ops-core/src/`
    *   Copy package/test files: `cp /home/sf2/Workspace/23-opspawn/restructure-test/opspawn-development/ops_core/pyproject.toml /home/sf2/Workspace/23-opspawn/restructure-test/opspawn-development/ops_core/alembic.ini /home/sf2/Workspace/23-opspawn/restructure-test/opspawn-development/ops_core/README.md /home/sf2/Workspace/23-opspawn/restructure-test/opspawn-ops-core/` (Adjust if more files needed)
    *   Copy directories: `cp -r /home/sf2/Workspace/23-opspawn/restructure-test/opspawn-development/ops_core/tests /home/sf2/Workspace/23-opspawn/restructure-test/opspawn-development/ops_core/alembic /home/sf2/Workspace/23-opspawn/restructure-test/opspawn-development/ops_core/scripts /home/sf2/Workspace/23-opspawn/restructure-test/opspawn-development/ops_core/load_tests /home/sf2/Workspace/23-opspawn/restructure-test/opspawn-ops-core/` (Adjust if more dirs needed)
    *   Purpose: Set up the `opspawn-ops-core` directory with its source code (in `src/`) and its package/test/config files at the root.

3.  **Populate `opspawn-agentkit` Repo (Copying):**
    *   Create `src` dir: `mkdir -p /home/sf2/Workspace/23-opspawn/restructure-test/opspawn-agentkit/src`
    *   Copy source: `cp -r /home/sf2/Workspace/23-opspawn/restructure-test/opspawn-development/src/agentkit /home/sf2/Workspace/23-opspawn/restructure-test/opspawn-agentkit/src/`
    *   Copy package/test files: `cp /home/sf2/Workspace/23-opspawn/restructure-test/opspawn-development/agentkit/pyproject.toml /home/sf2/Workspace/23-opspawn/restructure-test/opspawn-development/agentkit/README.md /home/sf2/Workspace/23-opspawn/restructure-test/opspawn-agentkit/` (Adjust if more files needed)
    *   Copy directories: `cp -r /home/sf2/Workspace/23-opspawn/restructure-test/opspawn-development/agentkit/tests /home/sf2/Workspace/23-opspawn/restructure-test/opspawn-agentkit/` (Adjust if more dirs needed)
    *   Purpose: Set up the `opspawn-agentkit` directory similarly.

4.  **Verify `pyproject.toml` Files:**
    *   Read `restructure-test/opspawn-ops-core/pyproject.toml` and `restructure-test/opspawn-agentkit/pyproject.toml`.
    *   Confirm the `[tool.setuptools.packages.find]` section correctly points to `src` (e.g., `where = ["src"]` or `packages = [{include = "...", from = "src"}]`). Make necessary edits if incorrect.
    *   Purpose: Ensure build tools will find the source code within the new repositories.

5.  **Clean Up Test Copy (`opspawn-development`):**
    *   Command: `rm -rf /home/sf2/Workspace/23-opspawn/restructure-test/opspawn-development/src/ops_core /home/sf2/Workspace/23-opspawn/restructure-test/opspawn-development/src/agentkit /home/sf2/Workspace/23-opspawn/restructure-test/opspawn-development/ops_core /home/sf2/Workspace/23-opspawn/restructure-test/opspawn-development/agentkit`
    *   Purpose: Remove the original code and config directories from the test copy of the management repo.

6.  **Update `tox.ini` in Test Copy:**
    *   Read `restructure-test/opspawn-development/tox.ini`.
    *   Modify the `[testenv]` section:
        *   Ensure `changedir = .` (or remove if not needed).
        *   Update `deps` to use relative paths:
            ```ini
            deps =
                ../opspawn-ops-core[test]
                ../opspawn-agentkit[test]
                # other deps...
            ```
        *   Update `commands` if necessary to point tests to the correct locations (likely not needed if `pytest` discovery works from the installed packages). Example if needed: `python -m pytest -vv -rA ../opspawn-ops-core/tests ../opspawn-agentkit/tests`
    *   Write the updated content back to `restructure-test/opspawn-development/tox.ini`.
    *   Purpose: Configure the test environment in the management repo copy to install and test the components from the sibling directories.

7.  **Test in Isolation:**
    *   Command: `cd /home/sf2/Workspace/23-opspawn/restructure-test/opspawn-development/ && tox -e py312`
    *   Purpose: Run the full test suite from the management repo copy to validate the multi-repo structure and path dependencies.

8.  **Evaluate:**
    *   Review the `tox` output. If all tests pass (ignoring expected skips), the restructuring is successful in the test environment.
    *   Decision Point: User decides whether to apply these changes to the main repositories or discard the test directory.

**Post-Validation Steps (If successful and user approves):**

*   Initialize Git repositories in `restructure-test/opspawn-ops-core/` and `restructure-test/opspawn-agentkit/`, add files, and make initial commits.
*   Clean up the original `1-t` repository (remove `src/ops_core`, `src/agentkit`, `ops_core`, `agentkit`).
*   Update the original `1-t/tox.ini` with the validated changes from `restructure-test/opspawn-development/tox.ini`.
*   Commit the cleanup and `tox.ini` changes in the `1-t` repository.
