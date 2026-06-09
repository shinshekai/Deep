# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.2.x   | :white_check_mark: |
| 1.1.x   | :white_check_mark: |
| 1.0.x   | :white_check_mark: |
| < 1.0   | :x:                |

## Reporting a Vulnerability

If you discover a security vulnerability within DEEP, please send an email to the maintainers. All security vulnerabilities will be promptly addressed.

**Please do NOT report security vulnerabilities through public GitHub issues.**

### What to include

- Type of issue (e.g. buffer overflow, SQL injection, cross-site scripting, etc.)
- Full paths of source file(s) related to the manifestation of the issue
- The location of the affected source code (tag/branch/commit or direct URL)
- Any special configuration required to reproduce the issue
- Step-by-step instructions to reproduce the issue
- Proof-of-concept or exploit code (if possible)
- Impact of the issue, including how an attacker might exploit the issue

### Response timeline

- **Acknowledgment**: Within 48 hours of receiving the report
- **Initial assessment**: Within 1 week
- **Fix or mitigation**: Within 2 weeks for critical vulnerabilities, 1 month for others
- **Disclosure**: Coordinated with the reporter

## Security Design Principles

### Local-First Architecture

- All data stays on the user's machine
- No external API calls for core functionality
- SQLite database with WAL mode for concurrent access
- Device-scoped privacy with UUID v4 identifiers

### Authentication & Authorization

- WebSocket authentication via first-message (not URL query parameters)
- Token endpoint requires Bearer authorization header
- OS keyring integration for API key storage
- Rate limiting on all endpoints (SlowAPI)

### Data Protection

- No secrets or keys committed to the repository
- SQL injection prevention via parameterized queries
- Input validation on all user-provided data
- Content sanitization for HTML output

### Infrastructure

- Docker containers run with read-only filesystems
- Capability dropping (no root, no network unless needed)
- Resource limits (CPU, memory, file descriptors)
- Health checks for all services

## Known Security Considerations

### Local-First Trade-offs

DEEP is designed for local-first operation. This means:

- **No cloud dependency**: All inference happens locally via LM Studio, Ollama, or llama.cpp
- **No data leakage**: Your documents and queries never leave your machine
- **Device isolation**: Each device gets its own memory store, no cross-device data access

### Vulnerability Management

- Dependabot alerts are monitored for dependency vulnerabilities
- Security patches are applied within 2 weeks of release
- Regular security audits of codebase and dependencies

## Security Features

| Feature | Status |
|---------|--------|
| Parameterized SQL queries | :white_check_mark: |
| Input validation | :white_check_mark: |
| Rate limiting | :white_check_mark: |
| WebSocket auth (first-message) | :white_check_mark: |
| OS keyring integration | :white_check_mark: |
| Device-scoped privacy | :white_check_mark: |
| Read-only Docker containers | :white_check_mark: |
| Capability dropping | :white_check_mark: |
