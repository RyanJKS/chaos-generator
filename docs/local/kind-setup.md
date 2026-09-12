# Kind Cluster Setup

## Install KIND Cluster configs
```sh
cat <<EOF | kind create cluster --config=-
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
 - role: control-plane
   kubeadmConfigPatches:
   - |
     kind: InitConfiguration
     nodeRegistration:
       kubeletExtraArgs:
          node-labels: "ingress-ready=true"
   extraPortMappings:
   - containerPort: 80
     hostPort: 80
     protocol: TCP   
 EOF
```

## Install NGINX Ingress Controller 
```sh
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/kind/deploy.yaml
```