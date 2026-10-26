# Git Workflow & Release Engineering Guide

This repository follows a strict multi-phase feature branch and release tagging workflow for NEXUS-OS.

## Initial Setup & Remote Sync
To attach this repository to your remote GitHub repository:
```bash
git remote add origin <YOUR_GITHUB_REPO_URL>
git push -u origin main
```

## Branch Strategy & Phase Progression
Each phase of development is executed on an isolated feature branch branched from `main`:
1. `phase-0-foundation`
2. `phase-1-processes-scheduling`
3. `phase-2-resources-deadlock`
4. `phase-3-distributed-fs`
5. `phase-4-cache-sync`
6. `phase-5-logical-clocks`
7. `phase-6-distributed-locks`
8. `phase-7-sync-engine`
9. `phase-8-grpc-ipc`
10. `phase-9-docker-chaos`
11. `phase-10-demo-release`

## Commit Standards
- Commits are atomic and focused on individual modules and concepts.
- Commit messages adhere to `<area>: <what and why>` (e.g. `scheduler: add preemptive priority with aging`).
- Tests and smoke tests (`python app.py`) are validated before merging each phase.

## Release Tagging
Each completed phase is tagged (`phase-<N>-complete`). The final deliverable is merged into `main` and tagged `v1.0`.
