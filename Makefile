.PHONY: test run manifest

run:
	python -m src.server --stdio

manifest:
	python -m src.server --manifest

test:
	python -m pytest tests/ -v

test-quick:
	python -m pytest tests/ -q

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; \
	find . -type f -name "*.pyc" -delete
