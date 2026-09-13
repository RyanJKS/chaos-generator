# Containers and Kubernetes

## Build and run

Install Docker and run these commands from the repository root:

```sh
docker build -t chaos-generator:local .
docker run --rm -p 8501:8501 chaos-generator:local
```

Open http://localhost:8501. Stop traffic with **Stop** before closing the browser.
Stop the container with Ctrl+C. If host port 8501 is occupied, use
`-p 8502:8501` and open http://localhost:8502 instead.

The image uses Astral's `ghcr.io/astral-sh/uv:0.7.13-python3.12-bookworm-slim`
base image and installs runtime dependencies from `uv.lock`
with `uv sync --locked --no-dev --no-install-project`. It runs as UID/GID
10001:10001 and listens on `0.0.0.0:8501`. The build context includes only
application source and dependency manifests, excluding local environments and secrets.
The default command starts the generator, not the example receiver.

Use a destination reachable from the container. `localhost` refers to the
container itself; in Kubernetes, use the destination Service's DNS name.

## Health checks

Streamlit provides `GET /_stcore/health` on port 8501. A ready server responds
with HTTP 200 and `ok`. Check a locally published container with:

```sh
curl --fail http://localhost:8501/_stcore/health
```

The Docker health check calls this endpoint using Python's standard library.
It checks every 30 seconds, allows 30 seconds for startup, and marks the container
unhealthy after three consecutive failures. Docker health status alone does not
restart a container.

Kubernetes does not use Dockerfile health checks. Add the following fields under
the generator container in your Deployment's `spec.template.spec.containers`:

```yaml
ports:
  - name: http
    containerPort: 8501
startupProbe:
  httpGet:
    path: /_stcore/health
    port: http
  periodSeconds: 2
  timeoutSeconds: 2
  failureThreshold: 30
readinessProbe:
  httpGet:
    path: /_stcore/health
    port: http
  periodSeconds: 5
  timeoutSeconds: 2
livenessProbe:
  httpGet:
    path: /_stcore/health
    port: http
  periodSeconds: 10
  timeoutSeconds: 2
  failureThreshold: 3
```

The startup probe allows approximately 60 seconds for startup before Kubernetes
restarts the container. Readiness failures remove the Pod from Service endpoints;
liveness failures trigger a restart. These probes check Streamlit server readiness,
not successful script execution, background traffic delivery, or destination health.
If you configure Streamlit's `server.baseUrlPath`, prepend that path to every
probe URL, including the Docker health check.

Publish the image to a registry reachable by your cluster and reference that image
in your Deployment. Each browser session has its own worker; replicas do not share
run state. Container shutdown stops its workers and resets in-memory counters.
