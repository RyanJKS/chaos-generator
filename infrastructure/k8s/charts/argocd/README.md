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
helm upgrade --install argocd argo/argo-cd -n argocd --create-namespace -f values-argo.yaml
```

## Post Installatiton Notes

```sh
In order to access the server UI you have the following options:

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

## Get Secret

```sh
kubectl get secrets -n <namespace> argocd-initial-admin-secret -o yaml
kubectl get secrets -n argocd argocd-initial-admin-secret -o yaml
```

Extract data.password and base64 decode
```sh
kubectl get secret argocd-initial-admin-secret -n argocd -o yaml | yq ".data.password" | base64 -d
```