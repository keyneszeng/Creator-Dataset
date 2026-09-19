# Authentication

## Principle

Creator Dataset does not store platform credentials in SQLite.

For V0.1, Xiaohongshu authentication is supplied through an environment variable:

```text
CREATOR_DATASET_XHS_COOKIE
```

The value should come from the operator's own authenticated browser session.

## Local Setup

```bash
cp .env.example .env
```

Then edit:

```dotenv
CREATOR_DATASET_XHS_COOKIE=your_cookie_header
```

Never commit `.env`.

## Runtime Integration

Install the optional Xiaohongshu adapter dependency:

```bash
pip install -e ".[dev,xhs]"
```

The current adapter wraps the Apache-2.0 project:

- https://github.com/jackwener/xiaohongshu-cli

The package is kept behind a gateway boundary so Creator Dataset's database, job system and export format are not coupled to the third-party library.

## Credential Flow

```text
.env
  ↓
Settings
  ↓
EnvironmentCredentialProvider
  ↓
parse Cookie header
  ↓
XiaohongshuGateway
  ↓
platform client
```

Credentials must never be:

- written to SQLite
- included in raw response archives
- printed in logs
- returned through API responses
- committed to Git

## Error Mapping

Authentication/session failures should be normalized into application errors:

- AUTH_REQUIRED
- PLATFORM_BLOCKED
- PLATFORM_REQUEST_ERROR

Captcha, IP blocking and expired sessions should stop aggressive retries and surface as BLOCKED rather than causing tight retry loops.

## Production Direction

Environment variables are sufficient for V0.1 local development.

Before multi-user deployment, replace this with a dedicated encrypted secret store and per-user credential isolation.
