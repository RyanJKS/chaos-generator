# Setting Up ArgoCD

Main documentation: https://github.com/argoproj/argo-helm/tree/main/charts/argo-cd

## Adding helm repo - Argo CD

```sh
helm repo add <repo-name> <url>
helm repo add argo https://argoproj.github.io/argo-helm
```

Check if repo was installed

```sh
helm repo list
```

## Install release

Release name is the deployment name, we will call it: "argocd".
```sh
helm upgrade --install <my-release> <repo/config> -n <namespace> -f <values.yaml>
helm upgrade --install argocd argo/argo-cd -n argocd --create-namespace -f infrastructure/k8s/platform/argocd/values.yaml
```

## Post Installatiton Notes

In order to access the server UI you have the following options:

```sh
1. kubectl port-forward service/argocd-server -n argocd 8080:443

    and then open the browser on http://localhost:8080 and accept the certificate

2. enable ingress in the values file `server.ingress.enabled` and either
      - Add the annotation for ssl passthrough: https://argo-cd.readthedocs.io/en/stable/operator-manual/ingress/#option-1-ssl-passthrough
      - Set the `configs.params."server.insecure"` in the values file and terminate SSL at your ingress: https://argo-cd.readthedocs.io/en/stable/operator-manual/ingress/#option-2-multiple-ingress-objects-and-hosts


After reaching the UI the first time you can login with username: admin and the random password generated during the installation. You can find the password by running:

kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d

(You should delete the initial secret afterwards as suggested by the Getting Started Guide: https://argo-cd.readthedocs.io/en/stable/getting_started/#4-login-using-the-cli)
```

## Hack - Expose custom endpoint on localhostt

Update the hosts file from `C:\Windows\System32\drivers\etc\hosts` from notepad to include at the end of the file:

```sh
127.0.0.1       argocd.test.com
```

Or if you are on WSL/Linux

Add this to `/etc/hosts` on the machine running argocd:

```sh
127.0.0.1       argocd.test.com
```

which is: <INGRESS_IP> argocd.test.com

## Get Secret

```sh
kubectl get secrets -n <namespace> argocd-initial-admin-secret -o yaml
kubectl get secrets -n argocd argocd-initial-admin-secret -o yaml
```

Extract data.password and base64 decode

```sh
kubectl get secret argocd-initial-admin-secret -n argocd -o yaml | yq ".data.password" | base64 -d
```

## Create an application in argocd

### 1: Manual
Create it on the UI post login

### 2: Yaml Config
The Argo CD `kind: Application` manifest is
`infrastructure/k8s/argocd/applications/chaos-app.yaml` is used by the pipeline.
Apply it from the repository root after pushing the chart to Git:

```sh
kubectl apply -f infrastructure/k8s/argocd/applications/chaos-app.yaml
```

### Helm chart with Kustomize overlays

These dev/prod overlays are for local learning and manual use. The GitHub Actions
pipeline deploys the direct Helm Application only. You can render and apply an
overlay locally without creating an Argo CD Application (Helm and kubectl are
required):

```sh
kubectl create namespace chaos-generator-learning-dev --dry-run=client -o yaml | kubectl apply -f -
kubectl kustomize infrastructure/k8s/apps/chaos-generator/kustomize/overlays/dev \
  --enable-helm --load-restrictor LoadRestrictionsNone | \
  kubectl apply --namespace chaos-generator-learning-dev -f -
```

Use a separate local cluster for this example: dev's `localhost` ingress host
matches the direct Helm deployment. For prod, use `overlays/prod` and a separate
namespace such as `chaos-generator-learning-prod`; its ingress host is
`prod.localhost`. Manual kubectl application does not automatically prune resources
removed from the overlay. Argo CD installation and build options below are needed
only if you also want to practice deploying these examples through Argo CD.

Run these commands from the repository root with Helm, kubectl, and an existing
Argo CD installation. The layout follows a shared base and environment overlays:

```text
infrastructure/k8s/
├── apps/chaos-generator/
│   ├── chart/                      # Helm chart and values.yaml
│   └── kustomize/
│       ├── base/kustomization.yaml # Renders the chart using helmCharts
│       └── overlays/
│           ├── dev/
│           │   ├── kustomization.yaml # References ../../base
│           │   └── replica-patch.yaml # One replica
│           └── prod/
│               ├── kustomization.yaml # References ../../base
│               ├── replica-patch.yaml # Three replicas
│               └── ingress-patch.yaml # prod.localhost
├── platform/
│   ├── argocd/values.yaml
│   └── github-runner/runner-deployment.yaml
├── argocd/applications/
│   ├── dev/kustomize-app.yaml       # Dev overlay
│   ├── prod/kustomize-app.yaml      # Prod overlay
│   └── chaos-app.yaml               # Direct Helm alternative
└── examples/intro/                 # Standalone learning manifests
```

The Application's `spec.source.path` points to the **directory**
`infrastructure/k8s/apps/chaos-generator/kustomize/overlays/dev`, where Argo CD discovers
`kustomization.yaml`. The overlay references `../../base`. The base uses
`helmGlobals.chartHome: ../..` and `helmCharts.name: chart`
to find the existing chart. A Helm chart cannot be listed directly under
Kustomize `resources`; it must first be rendered through `helmCharts`.

Here `chart` identifies the local directory; `Chart.yaml` still names the chart
`chaos-generator-app`. Chart defaults come from
`apps/chaos-generator/chart/values.yaml`. The release
name stays `chaos-generator`, preserving resource names and selectors from the
direct Helm Application. Each overlay references its own `replica-patch.yaml`:
dev sets one replica and prod sets three. Add environment patches or image
overrides to the relevant overlay. Argo CD supplies each Application's destination namespace and creates it through
`CreateNamespace=true`: dev uses `chaos-generator-ns`, and prod uses
`chaos-generator-prod-ns`. Dev retains the `localhost` ingress host; prod uses
`prod.localhost` through `ingress-patch.yaml`. Configure host resolution to your
ingress controller before browsing these endpoints.

The Argo CD Helm values configure:

```yaml
configs:
  cm:
    kustomize.buildOptions: --enable-helm --load-restrictor LoadRestrictionsNone
```

Both flags are required: Helm rendering is opt-in, and the chart's values file
is outside the Kustomize base directory. These flags apply to all Kustomize
applications on this Argo CD instance and allow loading files outside a
Kustomization root. Helm must be available in the repo-server image.

Preview locally (no cluster changes):

```sh
helm lint infrastructure/k8s/apps/chaos-generator/chart
kubectl kustomize infrastructure/k8s/apps/chaos-generator/kustomize/overlays/dev \
  --enable-helm --load-restrictor LoadRestrictionsNone
kubectl kustomize infrastructure/k8s/apps/chaos-generator/kustomize/overlays/prod \
  --enable-helm --load-restrictor LoadRestrictionsNone
```

Expect a Service, Deployment, and Ingress, with one Deployment replica for dev
and three for prod. Each Application points to its matching overlay; there is
no need to edit dev's source path to select prod. The prod overlay supplies a
separate ingress host but does not configure production TLS, resource limits,
or shared application state.

Rendered resources leave the namespace to Argo CD. For manual application,
supply `--namespace chaos-generator-ns` for dev or
`--namespace chaos-generator-prod-ns` for prod, and create that namespace first.

Commit and push the chart, Kustomize files, and Application to the repository
revision Argo CD watches before switching the Application. Update the existing
Argo CD installation with the values file (retain your installed chart version
using `--version`), then apply the Application:

```sh
helm upgrade argocd argo/argo-cd -n argocd --reuse-values \
  --version <installed-argo-cd-chart-version> \
  -f infrastructure/k8s/platform/argocd/values.yaml
kubectl apply -f infrastructure/k8s/argocd/applications/dev/kustomize-app.yaml
kubectl apply -f infrastructure/k8s/argocd/applications/prod/kustomize-app.yaml
kubectl -n argocd get applications chaos-generator-dev chaos-generator-prod
```

The available Applications are:

| Manifest under `infrastructure/k8s/argocd/applications/` | Application | Source | Destination namespace |
| --- | --- | --- | --- |
| `dev/kustomize-app.yaml` | `chaos-generator-dev` | Dev overlay | `chaos-generator-ns` |
| `prod/kustomize-app.yaml` | `chaos-generator-prod` | Prod overlay | `chaos-generator-prod-ns` |
| `chaos-app.yaml` | `chaos-generator` | Direct Helm | `chaos-generator-ns` |

Dev and prod can run together. Direct Helm remains an alternative to dev and
requires no Kustomize build flags. Direct Helm and dev target the same workloads,
so do not enable both for that namespace or recursively apply the entire
applications directory. When migrating from the existing direct Helm Application
to dev, retire `chaos-generator` without cascading deletion of its workloads
before enabling `chaos-generator-dev`. Applying the dev manifest creates a new
Application; it does not rename the old one.

After moving files or changing source paths, reapply the relevant manifests.
If a learning Application was already installed with automated sync, reapply its
updated manifest to disable automated sync. Check resource ownership before
changing an existing Application's destination or pruning its old resources. Automated sync and pruning remain enabled only for the pipeline's direct Helm
Application. The dev/prod example Applications require manual sync. All options render Helm templates;
none creates a Helm release.

If rendering reports `must specify --enable-helm` or a file security restriction,
the running Argo CD instance needs the build options above. Committing its Helm
values file does not update the installed release. Apply the Helm upgrade above,
or patch the live ConfigMap from a shell with cluster access:

```sh
kubectl -n argocd patch configmap argocd-cm --type merge \
  -p '{"data":{"kustomize.buildOptions":"--enable-helm --load-restrictor LoadRestrictionsNone"}}'
kubectl -n argocd rollout restart deployment argocd-repo-server
kubectl -n argocd rollout status deployment argocd-repo-server
```

This replaces the instance-wide Kustomize build options with the repository's
settings. Keep the Helm values aligned so a later Helm upgrade retains them.
Rerun the failed workflow after the repo-server rollout completes. If the
Application already exists, a hard refresh also clears cached manifest errors:

```sh
argocd app get chaos-generator-dev --hard-refresh
```

### GitHub Actions deployment

`.github/workflows/docker-build-push.yaml` updates the image tag in
`infrastructure/k8s/apps/chaos-generator/chart/values.yaml` and commits it.
Both push and manual runs deploy only the direct Helm Application:
`infrastructure/k8s/argocd/applications/chaos-app.yaml`. The CD job upserts that
manifest, then syncs `chaos-generator`. There is no Kustomize deployment selector.
Kustomize dev/prod overlays and their Application manifests are learning examples
for manual use; the workflow never creates or syncs them. Helm inflation flags
are not required for the pipeline's direct Helm deployment.

The overlays inherit the chart's image tag, but their example Applications have
no automated sync. A manual render or sync picks up the current tag.

If a live `chaos-generator` Application still reports `app path does not exist`
for the old chart directory, commit and push the updated workflow and manifest,
then run the workflow from the updated branch using **Run workflow** to repair that existing direct Helm Application. Changes
only under `infrastructure/` do not trigger this image build workflow automatically.
For an immediate repair after the new chart path is pushed, run while logged
into Argo CD:

```sh
argocd app create --file infrastructure/k8s/argocd/applications/chaos-app.yaml --upsert
argocd app sync chaos-generator
```

### Optional: switch the workflow to Kustomize

Kubernetes itself needs no Kustomize installation or CRD. Kustomize renders
ordinary Kubernetes manifests before they reach the API server. For local use,
`kubectl kustomize` performs that rendering. For the workflow, Argo CD's
repo-server performs it, so that is where Helm support must be enabled.

The workflow remains direct Helm by default. To deliberately change it:

1. **Configure the running Argo CD instance.** Helm must be available in its
   repo-server image. The repository's
   `infrastructure/k8s/platform/argocd/values.yaml` supplies:

   ```yaml
   configs:
     cm:
       kustomize.buildOptions: --enable-helm --load-restrictor LoadRestrictionsNone
   ```

   Apply those values to the installed release, keeping its existing chart version:

   ```sh
   helm upgrade argocd argo/argo-cd -n argocd --reuse-values \
     --version <installed-argo-cd-chart-version> \
     -f infrastructure/k8s/platform/argocd/values.yaml
   kubectl -n argocd rollout restart deployment argocd-repo-server
   kubectl -n argocd rollout status deployment argocd-repo-server
   kubectl -n argocd get configmap argocd-cm \
     -o jsonpath='{.data.kustomize\.buildOptions}'
   ```

   Expect both flags in the output. The live ConfigMap patch in the troubleshooting
   section above is an alternative to the Helm upgrade. Committing the values
   file alone does not configure the running instance. These flags affect all
   Kustomize Applications on that Argo CD instance.

2. **Choose the destination and resolve ownership.** Dev targets
   `chaos-generator-ns`, which the direct Helm Application already manages.
   Before enabling dev, retire the old `chaos-generator` Application without
   cascading deletion of its workloads, or assign dev a separate namespace.
   Prod targets `chaos-generator-prod-ns` and uses `prod.localhost` for ingress.
   `CreateNamespace=true` requests namespace creation; Argo CD's cluster
   credentials and AppProject must permit deployment to the selected namespace.
   The existing nginx ingress controller handles both overlays; configure hostname
   resolution to reach it. A separate namespace alone does not prevent duplicate
   ingress host/path conflicts.

3. **Change the workflow's selected manifest.** In
   `.github/workflows/docker-build-push.yaml`, replace the CD job's environment
   variable with the dev path:

   ```yaml
   env:
     ARGOCD_APPLICATION_FILE: infrastructure/k8s/argocd/applications/dev/kustomize-app.yaml
   ```

   For prod, use `infrastructure/k8s/argocd/applications/prod/kustomize-app.yaml`.
   The existing upsert/sync step reads the Application name from that file, so
   no hard-coded sync name needs changing. The runner needs its existing Argo CD
   CLI and yq; it does not need Kustomize or Helm for this deployment step.

4. **Push and verify.** Commit and push the selected Application, overlay,
   chart, and workflow changes before running the updated workflow. Inspect dev
   afterward (substitute `chaos-generator-prod` for prod):

   ```sh
   argocd app get chaos-generator-dev --hard-refresh
   argocd app wait chaos-generator-dev --sync --health --timeout 180
   ```

   The learning Application manifests keep automated sync disabled. The workflow's
   explicit `argocd app sync` still deploys the selected environment; enabling
   automated sync is not required. Both overlays share the chart image tag, so
   the next manual sync of either environment uses that current tag. Switching
   the workflow does not introduce independent image promotion.

## ArgoCD CLI

Connect to argocd using cli if using the hack above to have an endpoint

```sh
argocd login argocd.test.com --insecure --grpc-web --username admin --password $(kubectl get secret argocd-initial-admin-secret -n argocd -o yaml | yq ".data.password" | base64 -d)
```

Output:

```sh
'admin:login' logged in successfully
Context 'argocd.test.com' updated
```

Else: Use 127.0.0.1 only if the ingress is exposed on that machine. A Windows hosts entry won’t necessarily apply to a CLI running inside Linux or WSL.
To log in immediately using port forwarding, run:

```sh
kubectl -n argocd port-forward svc/argocd-server 8080:443
```

Then, in another terminal:

```sh
argocd login localhost:8080 --insecure --grpc-web \
--username admin \
--password "$(kubectl -n argocd get secret argocd-initial-admin-secret \
    -o jsonpath='{.data.password}' | base64 -d)"
```

Check if you can see the apps

```sh
argocd app list
```

Sync an app

```sh
argocd app sync <app-name>
```

Adding an app:
First, set the current namespace to argocd by running the following command:

```sh
kubectl config set-context --current --namespace=argocd
```

Create the example guestbook application with the following command:

```sh
argocd app create guestbook --repo https://github.com/argoproj/argocd-example-apps.git --
``
