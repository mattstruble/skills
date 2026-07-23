.PHONY: readme extract-prompts
readme:
	python3 scripts/generate_readme.py

extract-prompts:
	python3 scripts/extract_prompts.py $(SKILL) $(OUTPUT)
