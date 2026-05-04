.PHONY: install run clean

NICHE ?= ai_tech
PROMPT ?= ""

install:
	poetry install --no-root

run:
	poetry run python flows/generate_short.py --niche $(NICHE) --prompt "$(PROMPT)"

clean:
	rm -rf output/*