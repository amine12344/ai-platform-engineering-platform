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

.PHONY: help doctor registry cluster images ingress namespaces health baseline \
	data dataset database dvc lab0-up lab1-up up restore status down clean reset

help:
	@printf '%s\n' \
		'make lab0-up    Create Lab-00' \
		'make lab1-up    Create Lab-00 and Lab-01' \
		'make up         Create complete environment' \
		'make restore    Reapply manifests' \
		'make status     Show environment status' \
		'make down       Delete Kind cluster only' \
		'make clean      Delete cluster, registry, volume, and network' \
		'make reset      Clean and rebuild everything'

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

namespaces:
	@echo '[namespaces] Creating namespaces'
	@kubectl --context $(CONTEXT) apply \
		-f platform/foundation/namespaces.yaml

health: cluster
	@echo '[health] Building platform-health image'
	@docker build \
		--build-arg BASE_IMAGE=$(PLATFORM_HEALTH_BASE_IMAGE) \
		--tag $(PLATFORM_HEALTH_IMAGE) \
		starter-project/platform-health
	@docker push $(PLATFORM_HEALTH_IMAGE)

baseline: namespaces health ingress
	@echo '[baseline] Deploying platform health'
	@kubectl --context $(CONTEXT) apply \
		-f platform/foundation/platform-health.yaml
	@kubectl --context $(CONTEXT) \
		-n supportops-platform \
		rollout status deployment/platform-health \
		--timeout=180s

data: baseline
	@echo '[data] Creating local credential directory'
	@mkdir -p .local/lab-01
	@umask 077; \
	if [ ! -s .local/lab-01/postgres-password ]; then \
		python3 -c 'import secrets; print(secrets.token_urlsafe(32))' \
			> .local/lab-01/postgres-password; \
	fi
	@umask 077; \
	if [ ! -s .local/lab-01/s3-access-key ]; then \
		printf 'supportops-%s\n' \
			"$$(python3 -c 'import secrets; print(secrets.token_hex(8))')" \
			> .local/lab-01/s3-access-key; \
	fi
	@umask 077; \
	if [ ! -s .local/lab-01/s3-secret-key ]; then \
		python3 -c 'import secrets; print(secrets.token_urlsafe(32))' \
			> .local/lab-01/s3-secret-key; \
	fi
	@python3 -c '\
import json, pathlib; \
p = pathlib.Path(".local/lab-01"); \
json.dump({"identities":[{"name":"supportops-dvc","credentials":[{"accessKey":(p/"s3-access-key").read_text().strip(),"secretKey":(p/"s3-secret-key").read_text().strip()}],"actions":["Read","Write","List","Tagging","Admin"]}]}, (p/"s3.json").open("w"))'
	@kubectl --context $(CONTEXT) \
		-n supportops-data \
		create secret generic postgresql-credentials \
		--from-literal=password="$$(cat .local/lab-01/postgres-password)" \
		--dry-run=client -o yaml \
		| kubectl --context $(CONTEXT) apply -f -
	@kubectl --context $(CONTEXT) \
		-n supportops-data \
		create secret generic seaweedfs-s3-credentials \
		--from-file=s3.json=.local/lab-01/s3.json \
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

database: data dataset
	@echo '[database] Copying CSV into PostgreSQL'
	@kubectl --context $(CONTEXT) \
		-n supportops-data \
		cp datasets/releases/sample/tickets.csv \
		postgresql-0:/tmp/tickets.csv
	@kubectl --context $(CONTEXT) \
		-n supportops-data \
		exec -i postgresql-0 -- \
		psql -U supportops -d supportops <<'SQL'
	CREATE SCHEMA IF NOT EXISTS helpdesk;
	CREATE TABLE IF NOT EXISTS helpdesk.tickets (
	  ticket_id text PRIMARY KEY,
	  created_at timestamptz NOT NULL,
	  channel text NOT NULL,
	  language text NOT NULL,
	  customer_tier text NOT NULL,
	  product text NOT NULL,
	  subject text NOT NULL,
	  body text NOT NULL,
	  category text NOT NULL,
	  priority text NOT NULL CHECK (priority IN ('P1','P2','P3','P4')),
	  escalated boolean NOT NULL,
	  resolution_time_minutes integer NOT NULL CHECK (resolution_time_minutes > 0),
	  agent_response text NOT NULL,
	  satisfaction_score integer NOT NULL CHECK (satisfaction_score BETWEEN 1 AND 5)
	);
	TRUNCATE helpdesk.tickets;
	\copy helpdesk.tickets FROM '/tmp/tickets.csv' WITH (FORMAT csv, HEADER true);
	SQL
	@kubectl --context $(CONTEXT) \
		-n supportops-data \
		exec postgresql-0 -- \
		psql -U supportops -d supportops \
		-c 'SELECT COUNT(*) FROM helpdesk.tickets;'

dvc: database
	@echo '[dvc] Creating Python environment'
	@test -x .venv/bin/python || python3 -m venv .venv
	@.venv/bin/python -m pip install \
		--quiet 'dvc[s3]==$(DVC_VERSION)'
	@.venv/bin/dvc init --no-scm 2>/dev/null || true
	@.venv/bin/dvc remote add \
		--force -d supportops-s3 s3://supportops-dvc/dvc
	@.venv/bin/dvc remote modify \
		supportops-s3 endpointurl http://s3.supportops.local

lab0-up: baseline
	@echo '[lab0] Lab-00 is ready'

lab1-up: dvc
	@echo '[lab1] Lab-01 is ready'

up: lab1-up
	@echo '[up] Complete environment is ready'

restore: baseline data
	@echo '[restore] Environment restored'

status:
	@kubectl --context $(CONTEXT) get nodes -o wide
	@kubectl --context $(CONTEXT) get namespaces
	@kubectl --context $(CONTEXT) \
		-n supportops-platform \
		get pods,service,ingress -o wide
	@kubectl --context $(CONTEXT) \
		-n supportops-data \
		get pods,pvc,service,ingress -o wide
	@docker ps
	@docker network ls

down:
	@echo '[down] Deleting Kind cluster only'
	@kind delete cluster --name $(CLUSTER) 2>/dev/null || true

clean:
	@echo '[clean] Deleting Kind cluster'
	@kind delete cluster --name $(CLUSTER) 2>/dev/null || true
	@echo '[clean] Deleting registry'
	@docker rm -f $(REGISTRY) 2>/dev/null || true
	@docker volume rm $(REGISTRY_VOLUME) 2>/dev/null || true
	@echo '[clean] Deleting Docker Kind network'
	@docker network rm kind 2>/dev/null || true

reset:
	@$(MAKE) clean
	@$(MAKE) up