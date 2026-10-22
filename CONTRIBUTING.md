# Contributing to Fallow

Thanks for helping. Fallow is small on purpose, so a few ground rules keep it that way.

## Set up and test

```bash
pip install -r requirements.txt pytest
python -m pytest -q
python -m fallow.doctor      # shows what works on your machine
```

Every pull request should keep the tests green and add a test for new behaviour.

## Ground rules

- **The core stays offline.** Collecting, labelling, classifying and reporting must work with no network and no API key. Anything that calls a service is optional, skips cleanly when its key is missing, and never crashes the run.
- **Never hang silently.** Print progress, put a timeout on every network call, and warn and carry on when it fails.
- **Fallow only suggests.** It must never rename, move or delete a user's files.
- **Out of scope:** schedulers, daemons, web servers, databases, undo logs and agent frameworks.
- **No real data or keys in commits.** `.gitignore` covers the usual files. Check your diff before you push.

## Good first issues

- A `--exclude` option for `collect` to skip extra folders.
- Show the model's most important features after `classify`.
- Support `.tsv` and `.xlsx` export of `fallow_predictions.csv`.
- A Windows check for `label.py` single-key input and `speak.py` playback.
- Translate the README.

## Pull requests

Keep them focused: one change, a short description of what and why, and the output of `python -m pytest -q`.
