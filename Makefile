# Ollama Nextcloud ExApp - Build System

REGISTRY ?= ghcr.io/conductionnl
IMAGE_NAME ?= ollama-nextcloud
VERSION ?= 1.0.0

.PHONY: build push run run-cpu test clean help

help:
	@echo "Ollama Nextcloud ExApp"
	@echo ""
	@echo "Usage:"
	@echo "  make build    - Build Docker image"
	@echo "  make push     - Push to registry"
	@echo "  make run      - Run locally with GPU"
	@echo "  make run-cpu  - Run locally without GPU"
	@echo "  make test     - Test endpoints"
	@echo "  make clean    - Remove local images"
	@echo ""
	@echo "Variables:"
	@echo "  REGISTRY=$(REGISTRY)"
	@echo "  VERSION=$(VERSION)"

build:
	docker build -t $(REGISTRY)/$(IMAGE_NAME):$(VERSION) -t $(REGISTRY)/$(IMAGE_NAME):latest .

push: build
	docker push $(REGISTRY)/$(IMAGE_NAME):$(VERSION)
	docker push $(REGISTRY)/$(IMAGE_NAME):latest

run:
	docker run -it --rm \
		--gpus all \
		-e APP_ID=ollama \
		-e APP_SECRET=dev-secret \
		-e NEXTCLOUD_URL=http://host.docker.internal:8080 \
		-e OLLAMA_DEFAULT_MODEL=llama3.2:1b \
		-p 9000:9000 \
		-p 11434:11434 \
		$(REGISTRY)/$(IMAGE_NAME):latest

run-cpu:
	docker run -it --rm \
		-e APP_ID=ollama \
		-e APP_SECRET=dev-secret \
		-e NEXTCLOUD_URL=http://host.docker.internal:8080 \
		-e OLLAMA_DEFAULT_MODEL=llama3.2:1b \
		-p 9000:9000 \
		-p 11434:11434 \
		$(REGISTRY)/$(IMAGE_NAME):latest

test:
	@echo "Testing heartbeat endpoint..."
	@curl -s http://localhost:9000/heartbeat || echo "Container not running"
	@echo ""
	@echo "Listing models..."
	@curl -s http://localhost:9000/api/tags || echo "Ollama not running"

clean:
	-docker rmi $(REGISTRY)/$(IMAGE_NAME):$(VERSION)
	-docker rmi $(REGISTRY)/$(IMAGE_NAME):latest
