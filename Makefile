SHELL := /bin/bash

.PHONY: deps deps-gpu verify-gpu fix pull kill llama smi

# llama.cpp GPU build config
LLAMA_CUDACXX ?= /usr/local/cuda-13.1/bin/nvcc
LLAMA_CMAKE_ARGS ?= -DGGML_CUDA=on -DCMAKE_CUDA_ARCHITECTURES=120

deps:
	poetry lock
	poetry update
	poetry install

verify-gpu:
	poetry run python -c "import llama_cpp.llama_cpp as lib; print('supports_gpu_offload =', bool(lib.llama_supports_gpu_offload()))"

fix:
	ruff check --fix .
	ruff format .

pull:
	git pull
	git submodule update --init --recursive

kill:
	sudo pkill -f python
	sudo pkill -f ipykernel
	sudo pkill -f jupyter-kernel
	sudo pkill -f jupyter-notebook
	sudo pkill -f jupyter-lab

smi:
	watch -n 1 -d nvidia-smi
