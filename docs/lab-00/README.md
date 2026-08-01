# Lab 00 - Setup and Platform Health Commands

This document captures the shell commands executed while setting up the local platform engineering environment and validating platform health.

## Steps executed

1. Create local directories and project structure
   - `mkdir -p platform/kind/profiles`
   - `mkdir -p platform/foundation`
   - `mkdir -p starter-project/platform-health/www`
   - `mkdir -p evidence/lab-00`

2. Verify tool installation and versions
   - `docker --version`
   - `docker info`
   - `kubectl version --client`
   - `helm version`
   - `kind version`
   - `git --version`
   - `curl --version`
   - `sha256sum --version`

3. Download container images and Helm charts
   - `docker pull kindest/node:v1.35.0`
   - `docker pull registry:2.8.3`
   - `docker pull busybox:1.36.1`
   - `helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx`
   - `helm repo update`

4. Start local registry and verify access
   - `docker volume create supportops-registry-data`
   - `docker run -d --restart=always --name supportops-registry -p 127.0.0.1:5001:5000 -v supportops-registry-data:/var/lib/registry registry:2.8.3`
   - `docker ps --filter name=supportops-registry`
   - `curl -fsS http://127.0.0.1:5001/v2/`

5. Create Kind cluster with custom profile
   - `kind create cluster --name supportops-ai --image kindest/node:v1.35.0 --config platform/kind/profiles/16gb.yaml`
   - `kubectl config use-context kind-supportops-ai`
   - `kubectl get nodes -o wide`
   - `docker network connect kind supportops-registry`

6. Configure registry access inside Kind nodes
   - `for node in $(kind get nodes --name supportops-ai); do docker exec "$node" mkdir -p /etc/containerd/certs.d/localhost:5001; printf '[host."http://supportops-registry:5000"]\ncapabilities = ["pull", "resolve", "push"]\n' | docker exec -i "$node" sh -c 'cat > /etc/containerd/certs.d/localhost:5001/hosts.toml'; done`

7. Create and apply Kubernetes namespaces
   - `touch platform/foundation/namespaces.yaml`
   - `kubectl apply -f platform/foundation/namespaces.yaml`
   - `kubectl get namespaces`

8. Create platform foundation manifests and starter project files
   - `touch platform/foundation/ingress-nginx-values.yaml`
   - `touch starter-project/platform-health/www/index.html`
   - `touch starter-project/platform-health/Dockerfile`
   - `touch starter-project/platform-health/www/healthz`
   - `touch starter-project/platform-health/www/readyz`
   - `touch platform/foundation/platform-health.yaml`

9. Install ingress-nginx with Helm
   - `kubectl create namespace ingress-nginx`
   - `helm pull ingress-nginx/ingress-nginx --version 4.15.1 --destination .cache/helm`
   - `helm install ingress-nginx .cache/helm/ingress-nginx-4.15.1.tgz --namespace ingress-nginx --values platform/foundation/ingress-nginx-values.yaml --wait --timeout 5m`
   - `kubectl -n ingress-nginx get pods`

10. Build and push starter app image
   - `docker build --build-arg BASE_IMAGE=busybox:1.36.1 --tag localhost:5001/supportops/platform-health:0.1.0 starter-project/platform-health`
   - `docker push localhost:5001/supportops/platform-health:0.1.0`

11. Deploy platform health service and verify
   - `kubectl apply -f platform/foundation/platform-health.yaml`
   - `kubectl -n supportops-platform rollout status deployment/platform-health --timeout=180s`
   - `kubectl -n supportops-platform get pods`
   - `kubectl -n supportops-platform exec deployment/platform-health -- wget -qO- http://127.0.0.1:8080/healthz`

12. Clean up cluster
   - `kind delete cluster --name supportops-ai`

## Notes

- The lab evidence folder is `evidence/lab-00`.
- Use this README as a reference for rerunning setup and validation steps.
