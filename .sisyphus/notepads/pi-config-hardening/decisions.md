# Decisions — pi-config-hardening

## D1: IPC Architecture (G1)
**Decision**: wiki_bot_server.py — persistent Python process, session_start spawns it, holds singleton FandomBot, communicates via stdin/stdout JSON-RPC.
**Rationale**: Solves per-call login overhead, testable as Python module, clear crash recovery.

## D2: Slash Command Risk Classification (G2)
**Decision**: 3-tier classification. scan --approve-all / move-category NOT exposed as slash commands. --no-test-first blocked by permission gate.
**Table**: See plan Execution Strategy section.

## D3: No package.json in .pi/ (G7)
**Decision**: TS test infra lives in tests/ dir at repo root, NOT in .pi/.
**Rationale**: package.json in .pi/ would interfere with Pi auto-load mechanism.

## D4: Inline Python → Extracted Modules (G4)
**Decision**: Move all inline Python from wiki-tools.ts -c templates to .pi/extensions/wiki_tools/*.py modules + IPC server.
**Rationale**: Solves ARG_MAX limits and JSON injection risks.

## D5: No src/*.py modifications
**Decision**: Even though src/*.py have duplicated rate-limit logic, they are explicitly out of scope.
**Rationale**: Scope control — src/*.py changes risk breaking production wiki operations.
