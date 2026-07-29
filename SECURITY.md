# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in PayFlow, please **do not** open a
public GitHub issue. Instead, report it privately by emailing
**dashjyotiraditya906@gmail.com** with:

- A description of the vulnerability and its potential impact
- Steps to reproduce it
- Any relevant logs, payloads, or proof-of-concept code

You should expect an initial response within a few days. Once a fix is
available, we'll coordinate disclosure timing with you.

## Supported Versions

PayFlow is a portfolio/reference project rather than a versioned product;
security fixes are applied to the `main` branch only.

| Branch  | Supported |
|---------|-----------|
| `main`  | ✅        |
| others  | ❌        |

## Scope Notes

This project demonstrates production-style patterns (JWT auth, rate limiting,
input validation, secrets via `.env`) but has not undergone a formal
third-party security audit. Do not deploy it as-is against real payment data
or PII without a full review.
