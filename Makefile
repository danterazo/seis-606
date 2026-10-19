SHELL := /bin/bash

# llama.cpp GPU build config
LLAMA_CUDACXX ?= /usr/local/cuda-13.1/bin/nvcc
LLAMA_CMAKE_ARGS ?= -DGGML_CUDA=on -DCMAKE_CUDA_ARCHITECTURES=120

deps:
	@bash scripts/update-dependencies.sh

init-ssh-trust:
	@bash project/scripts/trust-ssh-host-keys.sh

# alias
update: deps

run:
	@fuser -k 8766/tcp 2>/dev/null || true
	DASHBOARD_DEV=1 PORT=8766 poetry run python project/dev.py

upgrade:
	uv tool upgrade --all

verify-gpu:
	poetry run python -c "import llama_cpp.llama_cpp as lib; print('supports_gpu_offload =', bool(lib.llama_supports_gpu_offload()))"

.PHONY: format fix fix-python fix-web fix-markdown lint lint-python lint-web

format: fix

fix: fix-python fix-web fix-markdown
	$(MAKE) lint

fix-python:
	poetry run ruff check --fix .
	poetry run ruff format .

fix-web:
	npm --prefix project/web run fix

fix-markdown:
	@git ls-files -z -- '*.md' | xargs -0 project/web/node_modules/.bin/prettier --write

lint: lint-python lint-web

lint-python:
	poetry run ruff check .

lint-web:
	npm --prefix project/web run lint

pull:
	git pull
	$(MAKE) protect-submodules
	git submodule foreach --recursive 'git switch main && git pull --ff-only origin main'

protect-submodules:
	git submodule update --init --recursive
	git submodule foreach --recursive 'git remote set-url --push origin DISABLED'

kill:
	sudo pkill -f python
	sudo pkill -f ipykernel
	sudo pkill -f jupyter-kernel
	sudo pkill -f jupyter-notebook
	sudo pkill -f jupyter-lab

smi:
	watch -n 1 -d nvidia-smi

sync:
	@bash scripts/sync-common.sh
