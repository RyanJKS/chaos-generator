# Chaos Generator

A simple Streamlit app for sending controlled HTTP event traffic to another system.
Choose an event rate, destination URL, and real-time, batch, or micro-batch mode.
Start and stop traffic while watching delivery and error counters.

## Getting started

Install Python 3.12+ and [uv](https://docs.astral.sh/uv/getting-started/installation/).
From the repository root:

```sh
uv sync --locked
uv run streamlit run src/main.py
```

Open http://localhost:8501. Enter an HTTP endpoint that accepts JSON POST requests,
choose the controls, and click **Start**. Click **Stop** before closing the tab.
See [usage and payload details](docs/index.md).

## Example receiver

With [just](https://just.systems/) installed, run the FastAPI receiver:

```sh
just receiver
```

In another terminal, run `just run`. Set the destination to
`http://127.0.0.1:8000/events`. Open `http://127.0.0.1:8000/stats` to see received
request and event counts. Stop either server with Ctrl+C.
See [receiver hosting and endpoints](docs/index.md#example-fastapi-receiver).

## Checks

```sh
uv run pre-commit install
uv run pre-commit run --all-files
uv run python -m unittest discover -s tests -v
uv run python -m compileall -q src tests
```

CI runs these checks on pushes to `main` and pull requests. Tests cover payloads, pacing, failures, lifecycle, and Streamlit controls.

## Layout

- `src/`: application code.
- `infrastructure/`: infrastructure configuration when needed.
- `docs/architecture.md`: design, dependencies, and operational decisions.
- `.github/`: CI, dependency updates, ownership, and contribution templates.

See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidance and [SECURITY.md](SECURITY.md) for vulnerability reporting.

## Project setup

- Confirm GitHub code owners have write access.
- Configure branch protection or rulesets and require the `Checks` CI job.
- Enable private vulnerability reporting where available.
- Select a license before distributing the code.

## Releases

Record changes in [CHANGELOG.md](CHANGELOG.md). Use semantic version tags such as `v0.1.0` when ready to release. Tags do not trigger publishing or deployment.
