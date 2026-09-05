# Repeatable local validation demo

From the application root, with Python 3.12 and the project's dev dependencies installed:

```powershell
docker pull postgres:16-alpine
python scripts/run_local_validation_demo.py
```

Docker must be running and OpenSSL must be on PATH. Image download is an explicit prerequisite;
the script never pulls an image or installs dependencies. Use a dedicated project virtualenv.

The script creates a uniquely labelled disposable PostgreSQL 16 container on a dynamic loopback
port with tmpfs storage. The existing scenario creates and removes its own test database and
applies the existing migrations through 20260808_0025. No shared database is used.

Two separately reported stages run: one Runtime submission/replay/Worker database test and six
local HTTPS tests (delivery, observation, timeout, disconnect, redirect and malformed response).
Runtime HTTP uses ASGITransport and injected verified claims. Worker delivery is synthetic.
The HTTPS tests use real loopback TLS and synthetic credentials. These are separate acceptance
paths, not a combined live-provider or user-login E2E demonstration.

JSON output reports stage pass counts, elapsed seconds and verified cleanup. Exit zero requires
both stages and cleanup to succeed; missing dependencies or skipped tests cannot count as success.
Provider keys and inherited database settings are not passed to test children. Raw test output
is not printed or saved. Test certificates are temporary. Container identity is checked before
stop, and no persistent volume is created. If interrupted externally or cleanup fails, inspect
the reported task container before any manual cleanup; never reset a shared database.

This does not measure user productivity, live Gemini success, browser UX or production readiness.
