SHELL := /bin/bash

# make multi-line blocks behave like scripts
.ONESHELL:
.SHELLFLAGS = -e

# llama.cpp GPU build config
LLAMA_CUDACXX ?= /usr/local/cuda-13.1/bin/nvcc
LLAMA_CMAKE_ARGS ?= -DGGML_CUDA=on -DCMAKE_CUDA_ARCHITECTURES=120

deps:
	# resolve and lock root dependencies
	poetry lock
	poetry update

	# install root env
	poetry install

	# install lab envs (without mutating lockfiles)
	@find labs -mindepth 1 -type f -name pyproject.toml -printf '%h\n' | sort -u | while read -r DIR; do
		echo -e "Running 'uv sync --locked' in \033[1;34m$$DIR\033[0m"
		(cd "$$DIR" && uv sync --locked)
	done

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
	@SRC="$$(basename "$$(pwd)")"
	case "$$SRC" in
		seis-606-vibe) DST="../seis-765-ops" ;;
		seis-765-ops)  DST="../seis-606-vibe" ;;
		*) echo -e "\033[1;31mERROR:\033[0m Sync must be run from \033[1;36mseis-606-vibe\033[0m or \033[1;36mseis-765-ops\033[0m" >&2; exit 1 ;;
	esac
	echo -e "Syncing \033[1;36m$$SRC\033[0m -> \033[1;36m$$(basename "$$DST")\033[0m"
	rsync -avh --mkpath .vscode/settings.json "$$DST/.vscode/"
	rsync -avh .envrc Makefile "$$DST/"
