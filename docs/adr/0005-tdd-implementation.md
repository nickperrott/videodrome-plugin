# ADR 0005: Test-Driven Development Approach

## Status
Accepted

## Context
The plugin has multiple interacting components (Plex client, TMDb cache, media matcher, file manager, watcher). We need a strategy to ensure correctness and enable parallel development.

## Decision
Use TDD (test-driven development) for all components:
1. Write tests first with mocks for all external services
2. Tests must fail before implementation (red)
3. Implement minimum code to pass (green)
4. Refactor if needed

All external dependencies are mocked:
- Plex API: mock PlexServer and library objects
- TMDb API: mock HTTP responses
- Filesystem: use pytest tmp_path fixtures
- watchdog: mock Observer and events

## Consequences
- Tests run without any external services
- Parallel development is safe (each subagent works on isolated modules)
- High test coverage from the start
- Mocks must accurately represent real API behavior
