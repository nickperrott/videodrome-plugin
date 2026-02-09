# ADR 0006: Claude Code Plugin Structure

## Status
Accepted

## Context
Beyond basic MCP tools, Claude Code supports a rich plugin system with commands, agents, hooks, and skills. This provides a better user experience than raw tool calls.

## Decision
Provide a full Claude Code plugin alongside the .mcpb Desktop Extension:

- **8 Commands**: User-facing slash commands for common workflows
- **4 Agents**: Specialist agents for media identification, library organization, ingestion, and monitoring
- **2 Hooks**: Safety classification (PreToolUse) and session context injection (SessionStart)
- **1 Skill**: Plex naming conventions knowledge base

## Consequences
- Rich user experience in Claude Code
- Commands provide guided multi-step workflows
- Agents handle complex reasoning tasks
- Safety hook enforces three-tier model
- Must maintain both .mcpb and plugin distributions
