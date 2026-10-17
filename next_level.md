Based on the current state of the project — three modalities (text, docs, speech), a frozen benchmark, leaderboard, and clean 139-test CI — here are concrete ideas grouped by impact:

---

## 🚀 Next Level Ideas

### Tier 1 — High Impact, Relatively Quick

**1. Publish the Dataset on Hugging Face Hub**
The release format (`text/train.jsonl`, `docs/train.jsonl` etc.) maps cleanly to a Hugging Face `DatasetDict`. Add a `push_to_hub.py` script using `datasets` library. This is the single biggest move — it makes the project publicly discoverable and creditable on your portfolio with a live URL.

**2. Multilingual Support**
- Add non-English name/address/date templates (e.g. German, French, Spanish)
- Edge TTS already supports multilingual voices — just pass `de-DE-KatjaNeural`
- A `--locale` flag on `text_gen` and `speech_gen` would make it extensible
- This instantly widens the dataset's appeal for researchers

**3. Handwritten-Style Documents**
- Swap the Pillow font for a cursive/handwriting TTF (freely available)
- Add subtle background noise, slight rotation (`Image.rotate`) and scan-like artifacts
- Currently the docs have "one default font, clean backgrounds" — this is listed as a known limitation in your own README

---

### Tier 2 — Strong Technical Depth

**4. Neural NER Baseline**
- Add a `spaCy` or `Hugging Face transformers` baseline (e.g. `en_core_web_trf` or `dslim/bert-base-NER`)
- Wire it into `piikit.baselines` as `text-ner`
- The leaderboard then shows **rules vs neural** — a much more interesting comparison

**5. Adversarial / Hard Test Split**
- Generate a "hard" frozen split where all values use non-standard formats (the `--hard` flag idea)
- Documents with overlapping fields, low-contrast text, rotated labels
- Gives a second benchmark track: *easy* vs *hard*

**6. Video / Screen Recording Modality (PII Redaction in Video)**
- Combine the document images with `moviepy` or `imageio` to create short synthetic screen-recording clips
- Annotate bounding boxes per frame
- Extremely rare in public datasets — high research value

---

### Tier 3 — Community / Ecosystem

**7. Web Leaderboard (Static Site)**
- Generate a GitHub Pages site from `benchmark/results/*.json` — a simple `leaderboard.html` with a sortable table
- Already have the data — just need a template script
- Looks professional on a portfolio link

**8. Submission API / CLI for External Systems**
- A `piikit submit --pred preds.jsonl --system "My GPT-4 Baseline"` command that validates, scores, and appends to the leaderboard in one step
- Makes it trivially easy for others to contribute a result

**9. Dataset Versioning with DVC or Git LFS**
- Currently `data/` is gitignored; committing the generated dataset under version control with DVC makes the research reproducible for others without re-running the pipeline
- Pairs well with the Hugging Face push

---

### Tier 4 — Research-Grade

**10. Annotation Noise Simulation**
- Introduce a configurable `--noise-rate` that randomly shifts span boundaries by ±1–3 chars, swaps labels with plausible confusors (PERSON↔ORG), or drops spans
- Lets researchers measure model robustness to imperfect annotation — a real research gap

**11. Cross-Dataset Label Mapping Study**
- You already have `label_map.py` with Presidio and CoNLL mappings
- Run the regex baseline on all three label sets, write a short `findings.md` showing F1 degradation from label mismatch
- Publishable as a short dataset paper (e.g. arXiv)

---

## My Top 3 Recommendations

| Priority | Idea | Why |
|---|---|---|
| **#1** | Hugging Face Hub publish | Immediate portfolio credibility, searchable, citable |
| **#2** | Neural NER baseline (`text-ner`) | Transforms the leaderboard from a toy into a real ranking |
| **#3** | Multilingual support | Single biggest coverage gap; edge-tts already supports it |

---

Want me to start implementing any of these? The Hugging Face Hub publish (#1) and the neural NER baseline (#2) are the most self-contained and I can start either immediately.