# Security Policy

## Supported versions

Flyan ships from `master`. Only the latest minor release on PyPI gets
security fixes; older versions do not receive backports.

| Version | Supported |
| ------- | --------- |
| 0.4.x   | ✅        |
| < 0.4   | ❌        |

If you need a fix on an older line, please open an issue describing the
constraint — we'll look at it case by case.

## Reporting a vulnerability

**Please do not open a public GitHub issue for security reports.**

Use GitHub's private vulnerability reporting:

1. Go to <https://github.com/victorlane/Flyan/security/advisories/new>.
2. Fill in the form. Include enough detail to reproduce: affected
   versions, environment, a proof-of-concept if you have one, and the
   impact you observed.

If for some reason you can't use the GitHub form, email
**victorbrnk@gmail.com** with `[Flyan security]` in the subject line.

You should receive an acknowledgement within **72 hours**. If you don't,
please follow up — your report may have been caught by a spam filter.

## What to expect

After you report, the maintainer will:

1. Acknowledge receipt within 72 hours.
2. Confirm or refute the vulnerability and share the assessment within
   7 days.
3. Work on a fix on a private branch. You'll be kept in the loop.
4. Coordinate disclosure: typically a patched release on PyPI followed
   by a public GitHub Security Advisory within 90 days of the original
   report. We can shorten or extend the window for good reasons —
   active exploitation, complex upstream dependency, etc. — but we'll
   discuss the timing with you before going public.
5. Credit you in the advisory if you'd like (and stay quiet if you
   wouldn't).

## Scope

The following are **in scope**:

- The published `Flyan` package on PyPI.
- The `flyan-mcp` MCP server entry point.
- Code in this repository on the `master` branch.

The following are **out of scope**:

- **Ryanair's own API.** Flyan is an unofficial client; we don't run
  the upstream service and can't speak to vulnerabilities in it. Report
  those directly to Ryanair.
- **Dependency vulnerabilities** unless Flyan's usage makes them
  exploitable in a way the upstream advisory doesn't already cover.
  File a regular issue, or open a PR bumping the dependency.
- **Issues that require a fully compromised host** (arbitrary file
  read/write by the operator, malicious Python paths, etc.) — these
  are the operator's problem, not Flyan's.
- **Rate-limit avoidance, scraping aggressiveness, or anti-bot
  evasion.** These aren't security issues; they're product decisions
  and they belong in a regular issue if you want to discuss them.

## Safe harbour

We will not pursue legal action against researchers who:

- Make a good-faith effort to comply with this policy.
- Report findings privately and give us reasonable time to fix.
- Don't access, modify, or exfiltrate data beyond what's needed to
  demonstrate the issue.
- Don't degrade service for other users while testing.

If in doubt, ask first.

## Thanks

Thank you for helping keep Flyan and its users safe.
