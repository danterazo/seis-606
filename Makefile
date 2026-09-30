SHELL := /bin/bash

# llama.cpp GPU build config
LLAMA_CUDACXX ?= /usr/local/cuda-13.1/bin/nvcc
LLAMA_CMAKE_ARGS ?= -DGGML_CUDA=on -DCMAKE_CUDA_ARCHITECTURES=120

deps:
	@bash scripts/deps.sh

# alias
update: deps

upgrade:
	sudo apt update
	sudo apt full-upgrade -y
	sudo apt clean
	sudo apt autoremove --purge -y
	uv tool upgrade --all

verify-gpu:
	poetry run python -c "import llama_cpp.llama_cpp as lib; print('supports_gpu_offload =', bool(lib.llama_supports_gpu_offload()))"

fix:
	ruff check --fix .
	ruff format .

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
