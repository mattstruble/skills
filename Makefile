.PHONY: readme extract-prompts check
export ALL CHECK_ROOT CHECK_BASE

readme:
	python3 scripts/generate_readme.py

extract-prompts:
	python3 scripts/extract_prompts.py $(SKILL) $(OUTPUT)

check:
	python3 scripts/check_routing.py
	python3 scripts/check_lessons.py
	python3 -m pytest -q tests
