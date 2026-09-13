# Chaos Generator

Generate controlled HTTP event traffic and observe how another system behaves under load.
The app provides a destination URL, an events/second slider, streaming mode, request
interval, Start and Stop buttons, and live delivery counters.

For repeatable Kubernetes-based CI infrastructure, see the
[self-hosted runner guides](local/self_hosted_gh_runners.md), with separate local
and production walkthroughs using kubectl and Helm.

## Run locally

Install Python 3.12+ and [uv](https://docs.astral.sh/uv/getting-started/installation/).
From the repository root, run:

```sh
uv sync --locked
uv run streamlit run src/main.py
```

Open http://localhost:8501. The destination must accept JSON POST requests.
Enter its full HTTP or HTTPS URL, choose the load settings, and click **Start**.
Controls lock during a run. Click **Stop** to change them and start a new run.
Counters reset on each Start. No destination is contacted before Start.

For Docker builds and Kubernetes health checks, see [Containers and Kubernetes](containers.md).

## Example FastAPI receiver

The included receiver accepts both single events and event arrays. Install
[just](https://just.systems/) and start it from the repository root:

```sh
just receiver
```

In a second terminal, start the generator with `just run`. Set its destination to
`http://127.0.0.1:8000/events`, then click Start. Open
`http://127.0.0.1:8000/stats` and refresh to observe received event and request counts.
The receiver also logs each accepted request's event count without logging payloads.

Endpoints:

- `POST /events`: accepts a JSON object or an array of objects; responds with
  `{"accepted": 1}` for one event. An empty array accepts zero events.
  Invalid body types return HTTP 422 and do not change counters.
- `GET /stats`: returns `requests`, `events`, and `last_batch_size`.
- `GET /health`: returns `{"status": "ok"}`.
- `GET /docs`: opens FastAPI's interactive API documentation.

To listen on other network interfaces or choose another port:

```sh
just receiver 0.0.0.0 9000
```

Use `http://<receiver-host>:9000/events` as the generator destination; replace
`<receiver-host>` with the receiver machine's reachable hostname or IP address.
The default host is `127.0.0.1` and the default port is `8000`.
Without just, the equivalent default command is:

```sh
uv run uvicorn receiver:app --app-dir src --host 127.0.0.1 --port 8000
```

This is an example receiver without authentication. Use a trusted network when
exposing it. It counts accepted events without storing payloads or simulating
processing. Counters live in memory, reset on restart, and are separate per worker;
use the command's default single worker for combined counts. Stop with Ctrl+C.
If the port is occupied, choose another port and update the generator destination.

## Streaming controls

- **Events/second:** target event rate, from 1 to 1,000; defaults to 10.
- **Real-time:** sends one JSON object per request, starting immediately.
  The event rate determines the interval: 10 events/second means 0.1 seconds.
  The separate interval control is disabled in this mode.
- **Batch:** sends a JSON array after each interval; defaults to 10 seconds.
- **Micro-batch:** uses the same window mechanism with a shorter default of 1 second.
- **Time between requests:** batch window duration, from 0.1 to 60 seconds.
  Each array contains events/second × window duration events on average.
  Fractional counts carry into later windows. Empty windows send no request.

For example, 20 events/second with a 5-second batch interval sends 100 events in
one request every 5 seconds. A 0.5-second micro-batch sends 10 events per request.

## Payload

Real-time requests contain an object like this; batch modes contain an array of
these objects. Requests use `Content-Type: application/json`.

```json
{
  "id": "5fa3c8c7-d3ca-4b44-8cd5-8b271dc27de5",
  "run_id": "a6078536-9b9b-4982-82ee-b9745f085244",
  "sequence": 1,
  "timestamp": "2026-09-11T12:00:00+00:00",
  "value": 0.42
}
```

IDs are unique, sequence numbers increase within each run, timestamps record
payload creation in UTC, and values are random numbers from 0 inclusive to 1 exclusive.
There are no custom payload, authentication header, or non-HTTP protocol controls.

## Delivery and stopping

Successful requests have a 2xx status. Only their events count as delivered;
this does not confirm downstream processing. HTTP errors and network failures
increment the failed-request counter. The next scheduled request continues without
retrying failed events. Redirects are not followed.

The sender makes one request at a time. Rates are best effort: network latency,
response time, and payload creation can lower throughput. Missed windows are not
queued or replayed. Connect and read timeouts are 3 and 5 seconds respectively;
these are not a total wall-clock deadline.

Stop interrupts a waiting window and discards its unsent data. An in-flight request
may finish before the status becomes Stopped. **Stop before closing the tab**:
closing a browser tab does not stop the background worker. Exiting the Streamlit
server stops all workers. Each browser session has its own controls and worker.

If requests fail, check the displayed HTTP status or error, destination URL,
network access, and whether the endpoint accepts the selected object or array format.
`localhost` refers to the machine running Streamlit, not a remote browser.

See [architecture](architecture.md) for implementation and validation details.
