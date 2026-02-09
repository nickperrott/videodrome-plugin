# ADR 0007: .mcpb Desktop Extension Distribution

## Status
Accepted

## Context
Claude Desktop users need a simple way to install and configure the plugin.

## Decision
Distribute as a .mcpb bundle (manifest v0.4) with:
- UV-based Python runtime (no user Python setup needed)
- user_config with sensitive field support (tokens stored in macOS Keychain)
- Auto-generated UI for configuration

## Consequences
- One-click install for Claude Desktop users
- Credentials stored securely in OS keychain
- No manual JSON editing needed
- Must keep manifest.json in sync with server capabilities
