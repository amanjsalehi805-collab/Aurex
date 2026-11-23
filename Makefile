.PHONY: test lint
test:
	PYTHONPATH=src python3 -m unittest discover -s tests -v
lint:
	ruff check src tests
	mypy src
