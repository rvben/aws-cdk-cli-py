.EXPORT_ALL_VARIABLES:

# Virtual Environment variables
SHELL = /bin/bash
PY = python3
VENV = .venv

export BASH_ENV=$(VENV)/bin/activate

CDK_VERSION ?= $(shell npm view aws-cdk version)
WRAPPER_VERSION ?= $(CDK_VERSION)

$(VENV): pyproject.toml
	@[[ -d $(VENV) ]] || uv venv --python-fetch automatic --python-preference only-managed -q
	@uv sync
	@touch $(VENV)

version:
	@echo "CDK version: $(CDK_VERSION)"
	@echo "Wrapper version: $(WRAPPER_VERSION)"

# These targets are pure-Python and need neither a virtualenv nor npm. The empty
# overrides stop `.EXPORT_ALL_VARIABLES` from expanding the npm-backed
# CDK_VERSION/WRAPPER_VERSION (a `npm view` network call) into their environment.
NO_NPM_TARGETS := check-cdk-update node-current-version node-latest-version
$(NO_NPM_TARGETS): CDK_VERSION :=
$(NO_NPM_TARGETS): WRAPPER_VERSION :=

# Check whether a newer AWS CDK version is published on npm.
# Writes has_new_version/current_version/latest_version to $GITHUB_OUTPUT when set.
check-cdk-update:
	@$(PY) -m scripts.check_cdk_update

# Print the currently bundled / latest-available Node.js patch for its major.
# Used by the update workflow in place of inline curl|grep so the logic is tested
# and runs locally.
node-current-version:
	@$(PY) scripts/update_node_version.py --current

node-latest-version:
	@$(PY) scripts/update_node_version.py --latest

clean:
	rm -rf dist
	rm -rf .venv
	rm -rf temp
	rm -rf aws_cdk_cli/node_binaries
	rm -rf aws_cdk_cli/node_modules

fmt: $(VENV)
	ruff format .
	ruff check --fix .

download-cdk: $(VENV)
	@echo "Downloading CDK version $(CDK_VERSION)..."
	@python3 download_cdk.py

build: clean download-cdk
	@python3 update_version.py $(CDK_VERSION)
	uv build --sdist

test: $(VENV)
	uv run pytest --integration --slow .

publish-test: $(VENV)
	twine upload --repository testpypi dist/*

publish-prod: $(VENV)
	twine upload --repository pypi dist/*

verify: $(VENV)
	rm -rf .venv; uv venv; uv pip install dist/aws_cdk_cli-$(WRAPPER_VERSION).tar.gz && ./.venv/bin/cdk --version --verbose

verify-testpypi: $(VENV)
	rm -rf .venv; uv venv; \
	uv pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple aws-cdk-cli==$(WRAPPER_VERSION) && \
	./.venv/bin/cdk --version --verbose

docker-bash:
	docker run --rm -it -v $(PWD):/app -w /app sinfallas/base-python-uv bash
	# uv pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple aws-cdk-cli==2.1007.2 --index-strategy unsafe-best-match