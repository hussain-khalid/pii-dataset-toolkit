# Run the whole pipeline: make all
# Use the virtual environment's Python:  source .venv/bin/activate

PYTHON ?= python
SEED ?= 42
VERSION ?= 0.2.0
RELEASE := data/release/v$(VERSION)
PREDS := build/preds

.PHONY: all data speech release previews benchmark leaderboard-html test refreeze clean

all: data speech release previews benchmark test

data:
	$(PYTHON) -m piikit.text_gen --n 1000 --seed $(SEED) --out data/raw/text.jsonl
	$(PYTHON) -m piikit.validate data/raw/text.jsonl
	$(PYTHON) -m piikit.doc_gen --n 200 --seed $(SEED) --out-dir data/raw/docs
	$(PYTHON) -m piikit.validate_docs data/raw/docs/docs.jsonl

speech: data
	$(PYTHON) -m piikit.speech_gen --text data/raw/text.jsonl --n 50 --seed $(SEED) --out-dir data/raw/speech
	$(PYTHON) -m piikit.validate_speech data/raw/speech/speech.jsonl

release: data
	$(PYTHON) -m piikit.build_release --text data/raw/text.jsonl --docs data/raw/docs/docs.jsonl \
		--out-dir $(RELEASE) --seed $(SEED) --version $(VERSION) --overwrite
	$(PYTHON) -m piikit.validate_release $(RELEASE)
	mkdir -p docs && cp $(RELEASE)/DATASET_CARD.md docs/DATASET_CARD.md

previews: data
	$(PYTHON) -m piikit.preview data/raw/docs/docs.jsonl --per-type --out-dir docs/images/previews

# The benchmark is frozen once. This target only builds it if it does not exist yet;
# it never replaces an existing one. Use `make refreeze` to do that on purpose.
benchmark: release
	test -f benchmark/FROZEN.json || $(PYTHON) -m piikit.freeze build --release $(RELEASE) --out benchmark
	$(PYTHON) -m piikit.freeze verify benchmark
	mkdir -p $(PREDS)
	$(PYTHON) -m piikit.baselines text-empty --bench benchmark --out $(PREDS)/text_empty.jsonl
	$(PYTHON) -m piikit.baselines text-regex --bench benchmark --out $(PREDS)/text_regex.jsonl
	$(PYTHON) -m piikit.baselines docs-empty --bench benchmark --out $(PREDS)/docs_empty.jsonl
	$(PYTHON) -m piikit.baselines docs-ocr   --bench benchmark --out $(PREDS)/docs_ocr.jsonl
	$(PYTHON) -m piikit.score text --pred $(PREDS)/text_empty.jsonl --name empty --save
	$(PYTHON) -m piikit.score text --pred $(PREDS)/text_regex.jsonl --name regex-rules --save
	$(PYTHON) -m piikit.score docs --pred $(PREDS)/docs_empty.jsonl --name empty --save
	$(PYTHON) -m piikit.score docs --pred $(PREDS)/docs_ocr.jsonl   --name ocr-regex --save
	$(PYTHON) -m piikit.leaderboard --bench benchmark
	$(PYTHON) -m piikit.leaderboard_html --bench benchmark --out docs/leaderboard.html

leaderboard-html:
	$(PYTHON) -m piikit.leaderboard_html --bench benchmark --out docs/leaderboard.html

test:
	$(PYTHON) -m pytest -q

# DANGER: replaces the frozen benchmark and invalidates earlier results.
refreeze: release
	$(PYTHON) -m piikit.freeze build --release $(RELEASE) --out benchmark --overwrite
	rm -rf benchmark/results

clean:
	rm -rf data/raw data/release build .pytest_cache