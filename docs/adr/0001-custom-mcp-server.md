# ADR 0001: Custom MCP Server for Plex

## Status
Accepted

## Context
We need to provide Claude with the ability to manage a Plex Media Server. Options considered:
1. Build a custom MCP server using FastMCP
2. Use existing community Plex integrations

## Decision
Build a custom MCP server following the same patterns as the TrueNAS Claude plugin. This gives us full control over the tool surface, safety model, and user experience.

## Consequences
- Full control over tool design and safety classification
- Can distribute as both .mcpb (Claude Desktop) and Claude Code plugin
- Must maintain the server ourselves
- Can follow proven patterns from TrueNAS plugin
