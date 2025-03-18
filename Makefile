build:
	uv build --sdist

publish-test:
	twine upload --repository testpypi dist/*

publish-prod:
	twine upload --repository pypi dist/*