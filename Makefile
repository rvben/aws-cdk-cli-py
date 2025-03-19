.EXPORT_ALL_VARIABLES:

CDK_VERSION ?= $(shell npm view aws-cdk version)

version:
	@echo $(CDK_VERSION)

clean:
	rm -rf dist
	rm -rf .venv
	rm -rf temp
	rm -rf aws_cdk_cli/node_binaries
	rm -rf aws_cdk_cli/node_modules

fmt:
	uv run --with ruff ruff format .
	uv run --with ruff ruff check --fix .

download-cdk:
	@echo "Downloading CDK version $(CDK_VERSION)..."
	@python3 download_cdk.py

build: download-cdk
	@python3 update_version.py $(CDK_VERSION)
	uv build --sdist

publish-test:
	twine upload --repository testpypi dist/*

publish-prod:
	twine upload --repository pypi dist/*

verify: 
	rm -rf .venv; uv venv; uv pip install dist/aws_cdk_cli-$(CDK_VERSION).tar.gz && ./.venv/bin/cdk --version