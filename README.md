# Fallow

Fallow is a local file-triage tool. You label files in your Downloads folder as archive, keep or delete, and Fallow learns your habits, then predicts the same call for every other file, ranks the best archive candidates, proposes cleaner filenames, and tells you how many gigabytes you can probably reclaim. It never moves, renames or deletes anything.

You don't need to label hundreds by hand: `collect --autolabel` pre-marks obvious files (temp/cache→delete, old archives→archive, recent media/docs→keep), and `label --review` only prompts for the ambiguous remainder.

## Install

```bash
pip install -r requirements.txt
# optional extras
pip install tabpfn            # local TabPFN (needs accepted model licence, see below)
pip install tabpfn-client     # hosted TabPFN API fallback
pip install openai            # optional report prose (Ultramarine)
pip install sentry-sdk        # optional tracing
cp .env.example .env          # then fill in only the keys you want
python -m fallow.doctor       # prints what will work, fall back or skip on this machine
```

Contributions are welcome: see CONTRIBUTING.md.

Python 3.11+, CPU only, 8GB RAM is enough. Without any optional package, classification still runs, using a scikit-learn random forest and a loud warning that it is not TabPFN. Local TabPFN needs an accepted model licence and may fall back to the random forest if it cannot download weights headless — no TabPFN timing is promised.

## Run order

```bash
python -m fallow.collect --dir ~/Downloads --out fallow_data.csv --autolabel
python -m fallow.label --review --file fallow_data.csv
python -m fallow.classify --file fallow_data.csv
python -m fallow.rename --file fallow_predictions.csv --limit 25
python -m fallow.report --file fallow_predictions.csv
python -m fallow.prose --file fallow_predictions.csv
python -m fallow.speak --text "Fallow triaged 400 files and found 2.31 GB that can likely be deleted."
python -m fallow.site --redact     # builds site/index.html from your real results
```

`collect` refuses to overwrite a CSV that already holds labels (use another `--out`, or `--force`). Pass `--autolabel` to pre-label obvious files; pass `--review` to `label` so it only prompts for unlabeled (ambiguous) rows. `site` writes plain HTML with no JavaScript; `--redact` swaps real file names for `file_0001.ext` and leaves out the rename table, so you can publish it safely.

Extras that need no key:

```bash
python -m fallow.doctor                          # what works, falls back or skips on this machine
python -m fallow.site --redact                   # build site/index.html from your real results
python -m pytest -q                              # run the tests
```

`fallow.site` shows real file names unless you pass `--redact`, so review the page before publishing. `collect` refuses to overwrite a CSV that already holds labels unless you pass `--force`.

`collect --autolabel` pre-labels obvious files and writes `label_source` (`auto` or empty). `label --review` skips auto-labelled rows and only prompts for the unlabeled remainder. Labelling is crash-safe and resumable: every keypress is saved, and a restart picks up at the first unlabelled row.

Steps 4, 6 and 7 skip cleanly (exit code 0) when Ollama or the relevant API key is missing. Labelling is crash-safe and resumable: every keypress is saved, and a restart picks up at the first unlabelled row. Around 200 labels is enough for a valid model.

Sentry: set `SENTRY_DSN`, run `classify` or `prose`, then open Sentry and look under Traces for the spans `fallow.classify` and `fallow.prose`.

## Features and columns

`fallow_data.csv` (one row per file, newest first, capped at 2000, skipping `.git`, `node_modules`, `venv` and files over 2GB):

| Column | Meaning |
| --- | --- |
| `path`, `name` | Full path and file name |
| `ext` | Lower-case extension without the dot (one-hot encoded) |
| `size_bytes` | File size in bytes |
| `age_days` | Days since last access (atime) |
| `mtime_days` | Days since last modification |
| `is_hidden` | 1 if the file or any parent folder below the scanned root starts with a dot |
| `parent_folder` | Name of the containing folder (one-hot encoded) |
| `depth` | Folder depth below the scanned root |
| `name_len` | Length of the file name |
| `has_number_in_name` | 1 if the name contains a digit |
| `label` | Your answer: 1 = archive, 2 = keep, 3 = delete |
| `label_source` | `auto` if `collect --autolabel` pre-labeled it, empty if you labeled it by hand |

The model uses every numeric and boolean column plus one-hot `ext` and `parent_folder` (the 30 most common values of each, the rest grouped as "other"). `age_days` depends on your filesystem recording access times; on a volume mounted with `noatime` it can be stale.

`fallow_predictions.csv` adds `true_label` (empty for files you never labelled), `pred_label` and `confidence_archive`, `confidence_keep`, `confidence_delete`. Accuracy is measured on a stratified 20% holdout (`random_state=42`); files you labelled for training are scored in-sample in this file.

Classifier order: local TabPFN, then the Prior Labs API if `TABPFN_API_KEY` is set, then a random forest. TabPFN model weights are released under a non-commercial licence and must be accepted on Hugging Face/Prior Labs before the first local use; if the licence step can't complete (e.g. headless with no browser/token), Fallow falls back to the random forest and prints a loud warning. No TabPFN timing is promised — it may be much slower than the random forest on CPU. Gemma weights come with Google's terms of use. Fallow itself is MIT licensed; downloaded models keep their own licenses.

## Why local

By default nothing leaves your machine: collection, labelling, classification, the report and the rename proposals (a local Gemma model through Ollama) all run offline. Four optional calls exist, each off unless you set its key:

- **TabPFN API** (`TABPFN_API_KEY`): only used if local TabPFN fails. Sends the numeric features, one-hot extension and folder names, and your labels. File names and paths are not sent.
- **Report prose** (`ULTRAMARINE_API_KEY`): sends the Step 5 report text, which includes the names of the 10 oldest archive candidates.
- **Voice line** (`ELEVENLABS_API_KEY`): sends only the sentence you pass to `--text`.
- **Sentry** (`SENTRY_DSN`): sends timing traces for `fallow.classify` and `fallow.prose`.

## Tests and contributing

```bash
pip install pytest
python -m pytest -q
```

Contributions are welcome: read [CONTRIBUTING.md](CONTRIBUTING.md) for the ground rules and a few good first issues. Released under the [MIT License](LICENSE). Model weights you download (TabPFN, Gemma) keep their own licenses.

## Cost

Classification costs $0. The optional prose call is a fraction of a cent per run at Ultramarine's published list prices (estimated and printed after each call); the voice line is billed against your ElevenLabs plan.
