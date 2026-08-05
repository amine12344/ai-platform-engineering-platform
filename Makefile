SHELL := /bin/bash
.SHELLFLAGS := -Eeuo pipefail -c
.NOTPARALLEL:

include platform/versions.env

CLUSTER := supportops-ai
CONTEXT := kind-$(CLUSTER)
REGISTRY := supportops-registry
REGISTRY_PORT := 5001
REGISTRY_VOLUME := supportops-registry-data
PROFILE ?= 16gb
PROFILE_FILE := platform/kind/profiles/$(PROFILE).yaml
DVC_SITE_CACHE_DIR := $(CURDIR)/.local/dvc-site-cache
CREDENTIAL_DIR := .local/platform
export DVC_SITE_CACHE_DIR

.PHONY: help doctor registry cluster images ingress namespaces \
	platform-health-image foundation data dataset migrate database dvc \
	mlflow-image mlflow api-image api install up \
	verify verify-foundation verify-data verify-mlflow verify-api \
	validate test test-foundation test-api lint-api \
	demo-foundation demo-api-local demo-api-kubernetes \
	restore status down clean uninstall reset

help:
	@printf '%s\n' \
		'make install    Install and verify the complete platform' \
		'make verify     Verify every installed component' \
		'make status     Show platform resources' \
		'make restore    Rebuild and reapply every component' \
		'make clean      Remove the cluster and local registry' \
		'make reset      Clean, reinstall, and verify the platform' \
		'' \
		'Component targets:' \
		'make foundation Install ingress and platform health' \
		'make data       Install PostgreSQL and SeaweedFS' \
		'make dvc        Generate, load, and publish the dataset' \
		'make mlflow     Build and deploy MLflow' \
		'make api        Build and deploy the SupportOps API' \
		'' \
		'make train      Train and register the SupportOps classifier' \
		'make promote-model Evaluate and alias a qualified model' \
		'make test-ml    Run ML lifecycle unit tests' \
		'make demo-mlflow-lifecycle Run training and promotion end to end' \
		'' \
		'Development targets:' \
		'make validate   Validate the repository contract' \
		'make test       Run foundation and API tests plus API linting' \
		'make demo-foundation       Demonstrate the local foundation' \
		'make demo-api-kubernetes   Exercise the deployed API'

doctor:
	@echo '[doctor] Checking commands'
	@for command in docker kind kubectl helm python3 curl; do \
		command -v $$command >/dev/null || { echo "Missing command: $$command"; exit 1; }; \
	done
	@docker info >/dev/null
	@echo '[doctor] All prerequisites are available'

registry: doctor
	@echo '[registry] Creating registry'
	@if docker container inspect $(REGISTRY) >/dev/null 2>&1; then \
		docker start $(REGISTRY) >/dev/null 2>&1 || true; \
	else \
		docker volume create $(REGISTRY_VOLUME) >/dev/null; \
		docker run -d \
			--restart=always \
			-p 127.0.0.1:$(REGISTRY_PORT):5000 \
			--name $(REGISTRY) \
			-v $(REGISTRY_VOLUME):/var/lib/registry \
			$(REGISTRY_IMAGE) >/dev/null; \
	fi

cluster: registry
	@echo '[cluster] Creating Kind cluster'
	@if ! kind get clusters | grep -Fxq '$(CLUSTER)'; then \
		kind create cluster \
			--name $(CLUSTER) \
			--image $(KIND_NODE_IMAGE) \
			--config $(PROFILE_FILE) \
			--wait 180s; \
	fi
	@docker network connect kind $(REGISTRY) >/dev/null 2>&1 || true
	@for node in $$(kind get nodes --name $(CLUSTER)); do \
		docker exec $$node mkdir -p /etc/containerd/certs.d/localhost:$(REGISTRY_PORT); \
		printf '[host."http://$(REGISTRY):5000"]\n  capabilities = ["pull", "resolve", "push"]\n' \
			| docker exec -i $$node sh -c \
			'cat > /etc/containerd/certs.d/localhost:$(REGISTRY_PORT)/hosts.toml'; \
	done
	@kubectl config use-context $(CONTEXT) >/dev/null
	@kubectl --context $(CONTEXT) wait --for=condition=Ready nodes --all --timeout=180s

images: cluster
	@echo '[images] Pulling images'
	@docker pull $(KIND_NODE_IMAGE)
	@docker pull $(REGISTRY_IMAGE)
	@docker pull $(PLATFORM_HEALTH_BASE_IMAGE)
	@docker pull $(POSTGRES_IMAGE)
	@docker pull $(SEAWEEDFS_IMAGE)
	@echo '[images] Loading database images into Kind'
	@kind load docker-image --name $(CLUSTER) \
		$(POSTGRES_IMAGE) \
		$(SEAWEEDFS_IMAGE)

ingress: images
	@echo '[ingress] Installing ingress-nginx'
	@helm repo add ingress-nginx \
		https://kubernetes.github.io/ingress-nginx \
		--force-update >/dev/null
	@helm repo update ingress-nginx >/dev/null
	@helm upgrade --install ingress-nginx \
		ingress-nginx/ingress-nginx \
		--version $(INGRESS_NGINX_CHART_VERSION) \
		--kube-context $(CONTEXT) \
		--namespace ingress-nginx \
		--create-namespace \
		--values platform/foundation/ingress-nginx-values.yaml \
		--wait \
		--timeout 5m

namespaces: cluster
	@echo '[namespaces] Creating namespaces'
	@kubectl --context $(CONTEXT) apply \
		-f platform/foundation/namespaces.yaml

platform-health-image: cluster
	@echo '[health] Building platform-health image'
	@docker build \
		--build-arg BASE_IMAGE=$(PLATFORM_HEALTH_BASE_IMAGE) \
		--tag $(PLATFORM_HEALTH_IMAGE) \
		starter-project/platform-health
	@docker push $(PLATFORM_HEALTH_IMAGE)

foundation: namespaces platform-health-image ingress
	@echo '[foundation] Deploying platform health'
	@kubectl --context $(CONTEXT) apply \
		-f platform/foundation/platform-health.yaml
	@kubectl --context $(CONTEXT) \
		-n supportops-platform \
		rollout status deployment/platform-health \
		--timeout=180s

data: foundation
	@echo '[data] Creating local credential directory'
	@mkdir -p $(CREDENTIAL_DIR)
	@umask 077; \
	if [ ! -s $(CREDENTIAL_DIR)/postgres-password ]; then \
		python3 -c 'import secrets; print(secrets.token_urlsafe(32))' \
			> $(CREDENTIAL_DIR)/postgres-password; \
	fi
	@umask 077; \
	if [ ! -s $(CREDENTIAL_DIR)/s3-access-key ]; then \
		printf 'supportops-%s\n' \
			"$$(python3 -c 'import secrets; print(secrets.token_hex(8))')" \
			> $(CREDENTIAL_DIR)/s3-access-key; \
	fi
	@umask 077; \
	if [ ! -s $(CREDENTIAL_DIR)/s3-secret-key ]; then \
		python3 -c 'import secrets; print(secrets.token_urlsafe(32))' \
			> $(CREDENTIAL_DIR)/s3-secret-key; \
	fi
	@python3 -c '\
import json, pathlib; \
p = pathlib.Path("$(CREDENTIAL_DIR)"); \
json.dump({"identities":[{"name":"supportops-dvc","credentials":[{"accessKey":(p/"s3-access-key").read_text().strip(),"secretKey":(p/"s3-secret-key").read_text().strip()}],"actions":["Read","Write","List","Tagging","Admin"]}]}, (p/"s3.json").open("w"))'
	@kubectl --context $(CONTEXT) \
		-n supportops-data \
		create secret generic postgresql-credentials \
		--from-literal=password="$$(cat $(CREDENTIAL_DIR)/postgres-password)" \
		--dry-run=client -o yaml \
		| kubectl --context $(CONTEXT) apply -f -
	@kubectl --context $(CONTEXT) \
		-n supportops-data \
		create secret generic seaweedfs-s3-credentials \
		--from-file=s3.json=$(CREDENTIAL_DIR)/s3.json \
		--dry-run=client -o yaml \
		| kubectl --context $(CONTEXT) apply -f -
	@kubectl --context $(CONTEXT) apply \
		-f platform/data/seaweedfs.yaml \
		-f platform/data/postgresql.yaml
	@kubectl --context $(CONTEXT) \
		-n supportops-data \
		rollout status statefulset/seaweedfs \
		--timeout=240s
	@kubectl --context $(CONTEXT) \
		-n supportops-data \
		rollout status statefulset/postgresql \
		--timeout=240s

dataset:
	@echo '[dataset] Generating dataset'
	@python3 datasets/generate_supportops.py
	@python3 datasets/verify_supportops.py \
		datasets/releases/sample/tickets.csv

migrate: data
	@echo '[database] Applying versioned migrations'
	@KUBE_CONTEXT=$(CONTEXT) \
		bash scripts/migrate_database.sh kubernetes

database: migrate
	@echo '[database] Generating and importing versioned dataset'
	@KUBE_CONTEXT=$(CONTEXT) \
		bash scripts/import_dataset.sh kubernetes
	@kubectl --context $(CONTEXT) \
		-n supportops-data exec postgresql-0 -- \
		psql -U supportops -d supportops \
		-c 'SELECT release_name, row_count, sha256 FROM helpdesk.dataset_releases;'

dvc: database
	@echo '[dvc] Creating Python environment and S3 remote'
	@test -x .venv/bin/python || python3 -m venv .venv
	@.venv/bin/python -m pip install \
		--quiet 'dvc[s3]==$(DVC_VERSION)'
	@.venv/bin/dvc init --no-scm 2>/dev/null || true
	@.venv/bin/dvc remote add \
		--force -d supportops-s3 s3://supportops-dvc/dvc
	@.venv/bin/dvc remote modify \
		supportops-s3 endpointurl http://s3.supportops.local
	@.venv/bin/dvc remote modify \
		supportops-s3 use_ssl false
	@.venv/bin/dvc remote modify --local \
		supportops-s3 access_key_id \
		"$$(cat $(CREDENTIAL_DIR)/s3-access-key)"
	@.venv/bin/dvc remote modify --local \
		supportops-s3 secret_access_key \
		"$$(cat $(CREDENTIAL_DIR)/s3-secret-key)"
	@.venv/bin/python -c 'import boto3, pathlib; p=pathlib.Path("$(CREDENTIAL_DIR)"); s3=boto3.client("s3", endpoint_url="http://s3.supportops.local", aws_access_key_id=(p/"s3-access-key").read_text().strip(), aws_secret_access_key=(p/"s3-secret-key").read_text().strip()); names={item["Name"] for item in s3.list_buckets().get("Buckets", [])}; "supportops-dvc" not in names and s3.create_bucket(Bucket="supportops-dvc")'
	@.venv/bin/dvc add \
		datasets/releases/sample/tickets.csv
	@echo '[dvc] Pushing dataset artifacts'
	@.venv/bin/dvc push \
		datasets/releases/sample/tickets.csv.dvc

mlflow-image: cluster
	@echo '[mlflow] Building MLflow image'
	@docker build \
		--build-arg MLFLOW_BASE_IMAGE=$(MLFLOW_BASE_IMAGE) \
		--tag $(MLFLOW_IMAGE) \
		starter-project/mlflow
	@docker push $(MLFLOW_IMAGE)

mlflow: data mlflow-image
	@echo '[mlflow] Creating credentials'
	@kubectl --context $(CONTEXT) \
		-n supportops-ml \
		create secret generic mlflow-credentials \
		--from-literal=backend-store-uri="postgresql://supportops:$$(cat $(CREDENTIAL_DIR)/postgres-password)@postgresql.supportops-data.svc.cluster.local:5432/supportops" \
		--from-literal=aws-access-key-id="$$(cat $(CREDENTIAL_DIR)/s3-access-key)" \
		--from-literal=aws-secret-access-key="$$(cat $(CREDENTIAL_DIR)/s3-secret-key)" \
		--dry-run=client -o yaml \
		| kubectl --context $(CONTEXT) apply -f -
	@echo '[mlflow] Deploying MLflow'
	@kubectl --context $(CONTEXT) apply \
		-f platform/mlflow/mlflow.yaml
	@kubectl --context $(CONTEXT) \
		-n supportops-ml \
		set image deployment/mlflow \
		mlflow=$(MLFLOW_IMAGE)
	@kubectl --context $(CONTEXT) \
		-n supportops-ml \
		rollout restart deployment/mlflow
	@kubectl --context $(CONTEXT) \
		-n supportops-ml \
		rollout status deployment/mlflow \
		--timeout=240s
	@echo '[mlflow] Ensuring artifact bucket exists'
	@kubectl --context $(CONTEXT) \
		-n supportops-ml \
		exec deployment/mlflow -- python -c 'import boto3; s3=boto3.client("s3", endpoint_url="http://seaweedfs.supportops-data.svc.cluster.local:8333"); names={item["Name"] for item in s3.list_buckets().get("Buckets", [])}; "supportops-models" not in names and s3.create_bucket(Bucket="supportops-models")'

api-image: cluster
	@echo '[api] Building SupportOps API image'
	@docker build \
		--build-arg PYTHON_IMAGE=$(PYTHON_IMAGE) \
		--tag $(SUPPORTOPS_API_IMAGE) \
		services/supportops-api
	@docker push $(SUPPORTOPS_API_IMAGE)

api: database api-image
	@echo '[api] Creating database credentials'
	@kubectl --context $(CONTEXT) \
		-n supportops-platform \
		create secret generic supportops-api-database \
		--from-literal=password="$$(cat $(CREDENTIAL_DIR)/postgres-password)" \
		--dry-run=client -o yaml \
		| kubectl --context $(CONTEXT) apply -f -
	@echo '[api] Deploying SupportOps API'
	@kubectl --context $(CONTEXT) apply \
		-f platform/apps/supportops-api.yaml
	@kubectl --context $(CONTEXT) \
		-n supportops-platform \
		set image deployment/supportops-api \
		api=$(SUPPORTOPS_API_IMAGE)
	@kubectl --context $(CONTEXT) \
		-n supportops-platform \
		rollout restart deployment/supportops-api
	@kubectl --context $(CONTEXT) \
		-n supportops-platform \
		rollout status deployment/supportops-api \
		--timeout=180s

install: dvc mlflow api verify
	@echo '[install] Complete platform is ready'

up: install
	@echo '[up] Alias complete; use make install'

verify-foundation:
	@echo '[verify] Foundation and ingress'
	@kubectl --context $(CONTEXT) \
		-n ingress-nginx \
		rollout status deployment/ingress-nginx-controller \
		--timeout=180s
	@kubectl --context $(CONTEXT) \
		-n supportops-platform \
		rollout status deployment/platform-health \
		--timeout=180s
	@test "$$(curl --silent --show-error --output /dev/null --write-out '%{http_code}' --resolve platform.supportops.local:80:127.0.0.1 http://platform.supportops.local/healthz)" = 200

verify-data:
	@echo '[verify] PostgreSQL, SeaweedFS, and DVC'
	@kubectl --context $(CONTEXT) \
		-n supportops-data \
		rollout status statefulset/postgresql \
		--timeout=240s
	@kubectl --context $(CONTEXT) \
		-n supportops-data \
		rollout status statefulset/seaweedfs \
		--timeout=240s
	@test "$$(kubectl --context $(CONTEXT) -n supportops-data exec postgresql-0 -- psql -U supportops -d supportops -Atc 'SELECT COUNT(*) FROM helpdesk.tickets;')" = 250
	@test "$$(kubectl --context $(CONTEXT) -n supportops-data exec postgresql-0 -- psql -U supportops -d supportops -Atc 'SELECT COUNT(*) FROM helpdesk.schema_migrations;')" = 2
	@test "$$(kubectl --context $(CONTEXT) -n supportops-data exec postgresql-0 -- psql -U supportops -d supportops -Atc "SELECT row_count FROM helpdesk.dataset_releases WHERE release_name = 'sample';")" = 250
	@.venv/bin/python -c 'import boto3, pathlib; p=pathlib.Path("$(CREDENTIAL_DIR)"); s3=boto3.client("s3", endpoint_url="http://s3.supportops.local", aws_access_key_id=(p/"s3-access-key").read_text().strip(), aws_secret_access_key=(p/"s3-secret-key").read_text().strip()); names={item["Name"] for item in s3.list_buckets().get("Buckets", [])}; assert "supportops-dvc" in names, "missing bucket: supportops-dvc"'
	@.venv/bin/dvc status --quiet --cloud \
		datasets/releases/sample/tickets.csv.dvc

verify-mlflow:
	@echo '[verify] MLflow lifecycle service'
	@kubectl --context $(CONTEXT) \
		-n supportops-ml \
		rollout status deployment/mlflow \
		--timeout=240s
	@test "$$(curl --silent --show-error --output /dev/null --write-out '%{http_code}' --resolve mlflow.supportops.local:80:127.0.0.1 http://mlflow.supportops.local/health)" = 200
	@kubectl --context $(CONTEXT) \
		-n supportops-ml \
		exec deployment/mlflow -- python -c 'import boto3; s3=boto3.client("s3", endpoint_url="http://seaweedfs.supportops-data.svc.cluster.local:8333"); s3.head_bucket(Bucket="supportops-models")'

verify-api:
	@echo '[verify] SupportOps API'
	@kubectl --context $(CONTEXT) \
		-n supportops-platform \
		rollout status deployment/supportops-api \
		--timeout=180s
	@test "$$(curl --silent --show-error --output /dev/null --write-out '%{http_code}' --resolve api.supportops.local:80:127.0.0.1 http://api.supportops.local/healthz)" = 200
	@test "$$(curl --silent --show-error --output /dev/null --write-out '%{http_code}' --resolve api.supportops.local:80:127.0.0.1 http://api.supportops.local/readyz)" = 200
	@test "$$(curl --silent --show-error --output /dev/null --write-out '%{http_code}' --resolve api.supportops.local:80:127.0.0.1 http://api.supportops.local/api/v1/tickets?limit=1)" = 200
	@test "$$(curl --silent --show-error --output /dev/null --write-out '%{http_code}' --resolve api.supportops.local:80:127.0.0.1 http://api.supportops.local/api/v1/summary)" = 200

verify: verify-foundation verify-data verify-mlflow verify-api
	@echo '[verify] All platform checks passed'

validate:
	@python3 scripts/validate_repository.py

test-foundation:
	@python3 -m unittest discover -s tests -v

test-api:
	@PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
		python3 -m pytest services/supportops-api/tests -q

lint-api:
	@cd services/supportops-api && python3 -m ruff check src tests
	@cd services/supportops-api && python3 -m mypy src

test: validate test-foundation test-api test-ml lint-api
	@echo '[test] All repository checks passed'

demo-foundation:
	@bash scripts/demo_foundation.sh

demo-api-local:
	@bash scripts/demo_api_local.sh

demo-api-kubernetes: api
	@KUBE_CONTEXT=$(CONTEXT) bash scripts/demo_api_kubernetes.sh

restore: dvc mlflow api verify
	@echo '[restore] Platform restored'

.PHONY: test-ml train promote-model demo-mlflow-lifecycle

test-ml:
	@python3 -m unittest discover -s tests/ml -v

train:
	@echo '[train] Training and registering priority classifier'
	@MLFLOW_TRACKING_URI=$(MLFLOW_TRACKING_URI) \
		python3 train.py \
		--dataset datasets/releases/sample/tickets.csv \
		--experiment supportops-ticket-priority \
		--registered-model $(MODEL_NAME)

promote-model:
	@echo '[lifecycle] Evaluating latest model for promotion'
	@MLFLOW_TRACKING_URI=$(MLFLOW_TRACKING_URI) \
		python3 lifecycle.py \
		--model $(MODEL_NAME) \
		--alias $(MODEL_ALIAS) \
		--metric macro_f1 \
		--threshold $(MODEL_QUALITY_THRESHOLD)

demo-mlflow-lifecycle: mlflow dataset train promote-model
	@echo '[demo] MLflow training lifecycle completed'
	@cat .local/training/result.json
	@cat .local/training/promotion.json

status:
	@kubectl --context $(CONTEXT) get nodes -o wide
	@kubectl --context $(CONTEXT) get namespaces
	@kubectl --context $(CONTEXT) \
		-n supportops-platform \
		get pods,service,ingress -o wide
	@kubectl --context $(CONTEXT) \
		-n supportops-data \
		get pods,pvc,service,ingress -o wide
	@kubectl --context $(CONTEXT) \
		-n supportops-ml \
		get pods,service,ingress -o wide
	@docker ps
	@docker network ls

down:
	@echo '[down] Removing Kind cluster only'
	@kind delete cluster --name $(CLUSTER) 2>/dev/null || true

clean:
	@echo '[clean] Removing Kind cluster'
	@kind delete cluster --name $(CLUSTER) 2>/dev/null || true
	@echo '[clean] Removing local registry'
	@docker rm -f $(REGISTRY) 2>/dev/null || true
	@docker volume rm $(REGISTRY_VOLUME) 2>/dev/null || true
	@echo '[clean] Removing Docker Kind network'
	@docker network rm kind 2>/dev/null || true

uninstall: clean
	@echo '[uninstall] Platform runtime removed'

reset:
	@$(MAKE) clean
	@$(MAKE) install
