SHELL := /bin/bash

.PHONY: deps deps-gpu verify-gpu fix pull protect-submodules kill llama smi identify-pylance-paths

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
	$(MAKE) protect-submodules
	git submodule foreach --recursive 'git pull --ff-only'

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

identify-pylance-paths:
	@mkdir -p .vscode
	@tmp="$$(mktemp)"; \
	{ \
		echo '$${workspaceFolder}/assignments'; \
		find assignments -mindepth 1 -maxdepth 1 -type d | sort | sed 's#^#$${workspaceFolder}/#'; \
	} > "$$tmp"; \
	count="$$(wc -l < "$$tmp")"; \
	{ \
		echo '{'; \
		echo '  "git.detectSubmodules": false,'; \
		echo '  "python.analysis.extraPaths": ['; \
		i=0; \
		while IFS= read -r p; do \
			i="$$((i + 1))"; \
			if [[ "$$i" -lt "$$count" ]]; then \
				printf '    "%s",\n' "$$p"; \
			else \
				printf '    "%s"\n' "$$p"; \
			fi; \
		done < "$$tmp"; \
		echo '  ]'; \
		echo '}'; \
	} > .vscode/settings.json; \
	rm -f "$$tmp"; \
	echo 'Wrote .vscode/settings.json with assignment import roots.'
