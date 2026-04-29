
.PHONY: install run clean
 
install:
	poetry install
 
run:
	poetry run python flows/generate_short.py
 
clean:
	rm -rf output/*
 