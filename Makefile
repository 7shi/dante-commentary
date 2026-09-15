.PHONY: help clean-dist build serve deploy

help:
	@echo "Usage: make <target>"
	@echo ""
	@echo "Targets:"
	@echo "  clean-dist       Remove dist/"
	@echo "  build            Build the static site into dist/ (see templates/README.md)"
	@echo "  serve            Serve dist/ locally at http://localhost:8000"
	@echo "  deploy           Build and publish dist/ to the gh-pages branch"

clean-dist:
	rm -rf dist

build:
	uv run templates/build.py

serve:
	cd dist && uv run python -m http.server 8000

deploy: build
	bash templates/deploy.sh
