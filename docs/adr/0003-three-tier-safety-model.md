# ADR 0003: Three-Tier Safety Model

## Status
Accepted

## Context
MCP tools can perform operations ranging from safe reads to potentially destructive actions. We need a safety classification system.

## Decision
Adopt the same three-tier model as the TrueNAS plugin:

1. **Read-only** (auto-approved): Tools that only query data - list, search, parse, preview
2. **Write** (require confirmation): Tools that modify state - scan, rename, copy, move, ingest
3. **Destructive** (blocked): Tools that could cause irreversible damage - delete operations

Implemented via a PreToolUse hook in the Claude Code plugin that classifies tools by name prefix/suffix.

## Consequences
- Users are protected from accidental destructive operations
- Write operations require explicit confirmation
- Read operations are frictionless
- Safety hook must be maintained as new tools are added
