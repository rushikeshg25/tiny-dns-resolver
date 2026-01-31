.PHONY: run test clean help

help:
	@echo "Available commands:"
	@echo "  make run   - Run the DNS resolver"
	@echo "  make test  - Run tests"
	@echo "  make clean - Remove temporary files"

run:
	uv run python -m tiny_dns_resolver.main $(ARGS)

test:
	uv run pytest tests/

clean:
	rm -rf __pycache__ .pytest_cache .venv
