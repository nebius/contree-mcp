# Makefile for Sphinx documentation

SPHINXOPTS    ?=
SPHINXBUILD   ?= uv run sphinx-build
SOURCEDIR     = .
BUILDDIR      = _build

# Colors for pretty output
BLUE := \033[0;34m
GREEN := \033[0;32m
YELLOW := \033[0;33m
RED := \033[0;31m
NC := \033[0m # No Color

.PHONY: help clean html dirhtml singlehtml linkcheck doctest coverage serve live

help:
	@echo "$(BLUE)Contree MCP Documentation$(NC)"
	@echo ""
	@echo "$(GREEN)Build targets:$(NC)"
	@echo "  html        Build HTML documentation"
	@echo "  dirhtml     Build HTML docs with directory-based URLs"
	@echo "  singlehtml  Build single-page HTML"
	@echo ""
	@echo "$(GREEN)Quality targets:$(NC)"
	@echo "  linkcheck   Check external links"
	@echo "  doctest     Run doctests in documentation"
	@echo "  coverage    Check documentation coverage"
	@echo ""
	@echo "$(GREEN)Development targets:$(NC)"
	@echo "  serve       Serve docs at http://localhost:8000"
	@echo "  live        Live reload server (requires sphinx-autobuild)"
	@echo "  clean       Remove build directory"
	@echo ""
	@echo "$(YELLOW)Usage:$(NC)"
	@echo "  make html         # Build documentation"
	@echo "  make clean html   # Clean rebuild"
	@echo "  make serve        # Build and serve locally"

clean:
	@echo "$(YELLOW)Cleaning build directory...$(NC)"
	rm -rf $(BUILDDIR)
	@echo "$(GREEN)Done.$(NC)"

html:
	@echo "$(BLUE)Building HTML documentation...$(NC)"
	$(SPHINXBUILD) -b html $(SPHINXOPTS) $(SOURCEDIR) $(BUILDDIR)/html
	@echo ""
	@echo "$(GREEN)Build finished. Output: $(BUILDDIR)/html/index.html$(NC)"

dirhtml:
	@echo "$(BLUE)Building directory-based HTML...$(NC)"
	$(SPHINXBUILD) -b dirhtml $(SPHINXOPTS) $(SOURCEDIR) $(BUILDDIR)/dirhtml
	@echo ""
	@echo "$(GREEN)Build finished. Output: $(BUILDDIR)/dirhtml/$(NC)"

singlehtml:
	@echo "$(BLUE)Building single-page HTML...$(NC)"
	$(SPHINXBUILD) -b singlehtml $(SPHINXOPTS) $(SOURCEDIR) $(BUILDDIR)/singlehtml
	@echo ""
	@echo "$(GREEN)Build finished. Output: $(BUILDDIR)/singlehtml/index.html$(NC)"

linkcheck:
	@echo "$(BLUE)Checking external links...$(NC)"
	$(SPHINXBUILD) -b linkcheck $(SPHINXOPTS) $(SOURCEDIR) $(BUILDDIR)/linkcheck
	@echo ""
	@echo "$(GREEN)Link check complete. Results: $(BUILDDIR)/linkcheck/output.txt$(NC)"

doctest:
	@echo "$(BLUE)Running doctests...$(NC)"
	$(SPHINXBUILD) -b doctest $(SPHINXOPTS) $(SOURCEDIR) $(BUILDDIR)/doctest
	@echo ""
	@echo "$(GREEN)Doctest complete.$(NC)"

coverage:
	@echo "$(BLUE)Checking documentation coverage...$(NC)"
	$(SPHINXBUILD) -b coverage $(SPHINXOPTS) $(SOURCEDIR) $(BUILDDIR)/coverage
	@echo ""
	@echo "$(GREEN)Coverage report: $(BUILDDIR)/coverage/$(NC)"

serve: html
	@echo "$(BLUE)Serving documentation at http://localhost:8000$(NC)"
	@echo "$(YELLOW)Press Ctrl+C to stop$(NC)"
	python -m http.server 8000 --directory $(BUILDDIR)/html

live:
	@echo "$(BLUE)Starting live reload server...$(NC)"
	@echo "$(YELLOW)Install with: uv add --dev sphinx-autobuild$(NC)"
	uv run sphinx-autobuild $(SPHINXOPTS) $(SOURCEDIR) $(BUILDDIR)/html --port 8000 --open-browser
