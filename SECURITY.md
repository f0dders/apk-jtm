# Security Policy

## Scope

APK-JTM is a local security analysis tool. It runs entirely on your machine — no data is sent to any APK-JTM server. Findings are only shared with whichever AI provider you configure (Ollama for fully local, or a cloud provider of your choice).

Vulnerabilities in scope:

- The APK-JTM web UI (XSS, CSRF, path traversal, etc.)
- The FastAPI backend (injection, auth bypass, insecure file handling)
- The launcher scripts (command injection, privilege escalation)
- Prompt injection via a malicious APK causing harmful AI output

Out of scope:

- Vulnerabilities in MobSF, Docker, Ollama, or other third-party dependencies — please report those to their respective projects
- Issues that require physical access to the machine running the tool
- Theoretical vulnerabilities with no practical exploit path

## Reporting a vulnerability

**Please do not open a public GitHub issue for security vulnerabilities.**

Report privately via GitHub's [Security Advisories](../../security/advisories/new) feature, or email the maintainer directly (address on GitHub profile).

Include:

- A description of the vulnerability and its impact
- Steps to reproduce or a proof of concept
- The version of APK-JTM affected
- Your suggested severity (low / medium / high / critical)

You can expect an acknowledgement within 48 hours and a fix or mitigation plan within 14 days for high/critical issues.

## Supported versions

Only the latest release receives security fixes. If you're on an older version, please update before reporting.
