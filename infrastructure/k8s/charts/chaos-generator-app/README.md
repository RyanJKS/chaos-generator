## Install Chart

Command to run in current dir next to values.yaml and Chart.yaml
```sh
helm install chaos-generator -n chaos . --create-namespace
```

## Uninstall Chart

```sh
helm uninstall chaos-generator -n chaos
```
