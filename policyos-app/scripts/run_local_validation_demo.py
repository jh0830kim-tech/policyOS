"""Run bounded existing acceptance tests against disposable local resources."""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMAGE = "postgres:16-alpine"
LABEL = "policyos.local-validation-demo"


def command(args, *, env=None, timeout=120):
    return subprocess.run(
        args,
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def docker(*args):
    result = command(["docker", *args])
    if result.returncode:
        raise RuntimeError("docker_operation_failed")
    return result.stdout.strip()


def main():
    name = "policyos-demo-" + uuid.uuid4().hex
    created = False
    success = False
    started = time.monotonic()
    try:
        if not shutil.which("openssl"):
            raise RuntimeError("openssl_required")
        docker("version", "--format", "{{.Server.Version}}")
        docker("image", "inspect", IMAGE)
        # Only synthetic test configuration reaches children; no provider key is read.
        env = {
            k: v
            for k, v in os.environ.items()
            if k.upper()
            in (
                "PATH",
                "SYSTEMROOT",
                "WINDIR",
                "TEMP",
                "TMP",
                "HOME",
                "USERPROFILE",
            )
        }
        env.update(
            PYTHONDONTWRITEBYTECODE="1",
            PYTHONPATH=str(ROOT),
            AI_PROVIDER="fake",
            PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",
            JWT_ISSUER="https://issuer.policyos.test",
            JWT_AUDIENCES='["policyos-api-test"]',
            RUNTIME_API_REQUIRED_AUDIENCE="policyos-api-test",
        )
        docker(
            "run",
            "--detach",
            "--rm",
            "--pull=never",
            "--name",
            name,
            "--label",
            f"{LABEL}={name}",
            "-p",
            "127.0.0.1::5432",
            "--tmpfs",
            "/var/lib/postgresql/data:rw",
            "-e",
            "POSTGRES_USER=policyos_test",
            "-e",
            "POSTGRES_PASSWORD=policyos_test",
            "-e",
            "POSTGRES_DB=policyos_test",
            IMAGE,
        )
        created = True
        port = docker("port", name, "5432/tcp")
        if not re.fullmatch(r"127\.0\.0\.1:\d+", port):
            raise RuntimeError("unexpected_binding")
        url = f"postgresql+asyncpg://policyos_test:policyos_test@{port}/policyos_test"
        env.update(DATABASE_URL=url, POLICYOS_TEST_DATABASE_URL=url)
        for _ in range(30):
            probe = command(["docker", "exec", name, "pg_isready", "-U", "policyos_test"])
            if probe.returncode == 0:
                break
            time.sleep(1)
        else:
            raise RuntimeError("database_not_ready")
        cases = (
            (
                "runtime_db",
                [
                    "tests/test_runtime_vertical_acceptance.py::"
                    "test_http_submission_to_synthetic_worker_delivery_is_atomic_and_replay_safe"
                ],
                1,
            ),
            (
                "local_https",
                [
                    "tests/test_runtime_connector_provider_acceptance.py",
                    "-k",
                    "real_loopback_https",
                ],
                6,
            ),
        )
        with tempfile.TemporaryDirectory(prefix="policyos-demo-tests-") as temp:
            for label, tests, expected in cases:
                begin = time.monotonic()
                result = command(
                    [
                        sys.executable,
                        "-m",
                        "pytest",
                        "-p",
                        "asyncio",
                        "-p",
                        "no:cacheprovider",
                        "--basetemp",
                        str(Path(temp) / label),
                        "-q",
                        "--tb=no",
                        *tests,
                    ],
                    env=env,
                    timeout=300,
                )
                passed = re.search(r"\b(\d+) passed\b", result.stdout)
                ok = result.returncode == 0 and passed and int(passed[1]) == expected
                print(
                    json.dumps(
                        {
                            "stage": label,
                            "passed": int(passed[1]) if passed else 0,
                            "seconds": round(time.monotonic() - begin, 2),
                            "ok": bool(ok),
                        }
                    )
                )
                if not ok:
                    raise RuntimeError("acceptance_failed")
        success = True
    except (RuntimeError, OSError, subprocess.TimeoutExpired):
        print(json.dumps({"error": "local_demo_failed"}))
    finally:
        if created:
            try:
                info = json.loads(docker("inspect", name))[0]
                if (
                    info["Config"]["Labels"].get(LABEL) != name
                    or not info["HostConfig"]["AutoRemove"]
                    or any(m["Type"] == "volume" for m in info["Mounts"])
                ):
                    raise RuntimeError("cleanup_identity_mismatch")
                docker("stop", name)
                if docker("ps", "-aq", "--filter", f"label={LABEL}={name}"):
                    raise RuntimeError("cleanup_residue")
                print(json.dumps({"cleanup": "verified", "persistent_volumes": 0}))
            except (
                RuntimeError,
                OSError,
                subprocess.TimeoutExpired,
                KeyError,
                ValueError,
            ):
                success = False
                print(json.dumps({"error": "cleanup_failed", "container": name}))
    print(json.dumps({"success": success, "seconds": round(time.monotonic() - started, 2)}))
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
