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
`infrastructure/k8s/argocd/applications/kustomize-app.yaml`. Complete the
Helm/Kustomize configuration below before applying it from the repository root:

```sh
kubectl apply -f infrastructure/k8s/argocd/applications/kustomize-app.yaml
```

### Helm chart with Kustomize overlays

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
│               └── replica-patch.yaml # Three replicas
├── platform/
│   ├── argocd/values.yaml
│   └── github-runner/runner-deployment.yaml
├── argocd/applications/
│   ├── kustomize-app.yaml           # Helm rendered through Kustomize
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
overrides to the relevant overlay. Argo CD supplies the destination namespace
`chaos-generator-ns` and creates it through `CreateNamespace=true`.

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
and three for prod. The Application selects dev by default. To select prod,
change its `spec.source.path` suffix from `overlays/dev` to `overlays/prod`.
This switches the existing deployment; running both environments at once needs
separate Application names and destination namespaces or clusters. The prod
overlay changes only replica count; it does not configure production ingress,
resources, or shared application state.

Rendered resources
leave the namespace to Argo CD; for manual application, supply
`--namespace chaos-generator-ns` to kubectl and create that namespace first.

Commit and push the chart, Kustomize files, and Application to the repository
revision Argo CD watches before switching the Application. Update the existing
Argo CD installation with the values file (retain your installed chart version
using `--version`), then apply the Application:

```sh
helm upgrade argocd argo/argo-cd -n argocd --reuse-values \
  --version <installed-argo-cd-chart-version> \
  -f infrastructure/k8s/platform/argocd/values.yaml
kubectl apply -f infrastructure/k8s/argocd/applications/kustomize-app.yaml
kubectl -n argocd get application chaos-generator
```

This guide uses `kustomize-app.yaml`. Both manifests are supported:

- `kustomize-app.yaml` renders the Helm chart through the dev Kustomize overlay.
- `chaos-app.yaml` points directly to the Helm chart and uses its values without
  applying Kustomize overlays. This option does not require the Kustomize build flags.

Both define the same `chaos-generator` Application in the `argocd` namespace,
so use one at a time. Applying either manifest switches the existing Application
to that source; do not apply the whole applications directory. To switch to
direct Helm after committing and pushing the new paths:

```sh
kubectl apply -f infrastructure/k8s/argocd/applications/chaos-app.yaml
```

Reapply `kustomize-app.yaml` to switch back. After moving files from the old layout,
reapply your chosen manifest so the live Application uses the new source path.
Automated sync and pruning remain enabled, so Argo CD reconciles once the source
is available. Both options render Helm templates; neither creates a Helm release.

If rendering reports `must specify --enable-helm` or a file security restriction,
check `argocd-cm` contains the build options above and hard-refresh the Application
after updating the configuration.

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
