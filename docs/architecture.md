# Architecture

## Components and flow

`src/main.py` provides the Streamlit interface. A fragment refreshes controls and
counters every second. Session state holds one `TrafficRunner` per browser session.
`src/generator.py` validates settings and runs a daemon thread that creates synthetic
events and sends HTTP POST requests through a reusable `requests.Session`.

The worker never calls Streamlit. A lock protects shared counters, and a threading
Event interrupts waits when Stop is pressed. A new worker cannot start until the
previous worker exits. Each run has a fresh ID, sequence, and counters.

Real-time mode sends one object per request. Batch and micro-batch modes share a
window algorithm, with different default intervals. Fractional events carry across
windows, avoiding rate rounding loss. Each window creates at most 60,000 events
(1,000 events/second × 60 seconds). No unbounded event queue or response body is kept.

Requests are sequential. Slow destinations reduce throughput instead of creating
concurrent requests or catch-up bursts. Failed events are not retried. There is no
persistence, broker, scheduler service, or distributed load generation. Closing a tab
does not stop its worker; Stop or server shutdown is required.

## Example receiver

`src/receiver.py` provides a separate FastAPI app served by Uvicorn. The `receiver`
recipe in `justfile` accepts optional host and port arguments. The existing `run`
recipe starts Streamlit. Both processes run independently.

The receiver counts JSON objects and arrays at `/events` and exposes totals at
`/stats`, health at `/health`, and interactive documentation at `/docs`. Async
handlers update counters without yielding between updates. Counters are local to
one process; payloads are not retained. There is no persistence or authentication.

## Dependencies and configuration

Python 3.12+, Streamlit, Requests, FastAPI, and Uvicorn are declared in `pyproject.toml`; `uv.lock`
records resolved versions. The development group supplies pre-commit, Ruff, and HTTPX for receiver tests.
All load settings come from the UI. No environment variables or credentials are required.

## Validation

From the repository root:

```sh
uv run pre-commit run --all-files
uv run python -m unittest discover -s tests -v
uv run python -m compileall -q src tests
```

Tests use a mocked HTTP session to check payload shapes, window counts, stopping,
restarting, and failure counters. Streamlit AppTest checks controls and lifecycle. FastAPI TestClient checks receiver
acceptance, counts, health, and invalid payloads.
These tests do not measure production throughput or downstream processing.
CI installs application and development tools, runs pre-commit, tests, and compilation.

The `check-yaml` hook excludes Helm templates under
`infrastructure/k8s/charts/*/templates/`, which contain Go template syntax.
Chart metadata, values files, and plain Kubernetes manifests remain checked,
including duplicate-key detection. Validate application chart changes separately
with Helm installed, from the repository root:

```sh
helm lint infrastructure/k8s/charts/chaos-generator-app
helm template chaos-generator infrastructure/k8s/charts/chaos-generator-app
```

## Documentation

`mkdocs.yml` lists published pages and enables `techdocs-core`.
`catalog-info.yaml` retains `backstage.io/techdocs-ref: dir:.` so Backstage finds
that configuration. With MkDocs and `mkdocs-techdocs-core` available, validate using:

```sh
mkdocs build --strict --site-dir /tmp/chaos-generator-docs
```

Generated output is not source. A local build does not verify Backstage publishing.
