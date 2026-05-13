.PHONY: install run resume clean clean-all

# ── Defaults ──────────────────────────────────────────────────────────────────
NICHE          ?= ai_tech
PROMPT         ?=
DURATION       ?=
MODE           ?=
PIPELINE_MODE  ?=
FORMAT         ?= short

# ── Install ───────────────────────────────────────────────────────────────────
install:
	poetry install --no-root

# ── Run ───────────────────────────────────────────────────────────────────────
run:
	poetry run python flows/generate_short.py \
		--niche $(NICHE) \
		--format $(FORMAT) \
		$(if $(PROMPT),--prompt "$(PROMPT)",) \
		$(if $(DURATION),--duration $(DURATION),) \
		$(if $(MODE),--mode $(MODE),) \
		$(if $(PIPELINE_MODE),--pipeline-mode $(PIPELINE_MODE),)

# ── Resume (después de revisar en Modo B1) ────────────────────────────────────
resume:
	poetry run python flows/generate_short.py \
		--niche $(NICHE) \
		--format $(FORMAT) \
		--pipeline-mode b2

# ── Clean ─────────────────────────────────────────────────────────────────────
clean:
	rm -rf output/*

clean-all:
	rm -rf output/*
	rm -f input/script.txt
	rm -f input/prompts.txt
	rm -rf input/images/*
	rm -rf input/audio/*

# ── Ejemplos de uso (comentados) ─────────────────────────────────────────────
# Modo A — totalmente automático
#   make run NICHE=geopolitica
#   make run NICHE=geopolitica FORMAT=long
#
# Modo B1 — Gemini genera, tú revisas antes de continuar
#   make run NICHE=geopolitica PIPELINE_MODE=b1
#   make resume NICHE=geopolitica
#
# Modo B2 — guión y prompts manuales en input/
#   make run NICHE=geopolitica PIPELINE_MODE=b2
#   make run NICHE=geopolitica PIPELINE_MODE=b2 FORMAT=long
#
# Modo C — imágenes y audios externos numerados
#   make run PIPELINE_MODE=c
#   make run PIPELINE_MODE=c FORMAT=long
#
# Limpiar outputs
#   make clean
#
# Limpiar todo incluyendo inputs
#   make clean-all