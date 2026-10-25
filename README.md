# say-headline

Speak the topic sentence of every Claude Code reply out loud. Only the first line is spoken, so write replies with a one-line headline first (the bullets and paragraph below it stay silent).

macOS only (uses `afplay` and `say`).

## Install

```
claude plugin marketplace add 7Zenox/say-headline
claude plugin install say-headline@say-headline
```

Out of the box it speaks with macOS `say` (voice Tara). For a much better voice, set up Kokoro (below).

## How it works

- A `Stop` hook takes the first real line of Claude's last reply (skips blank lines and `★ Insight` blocks, strips markdown) and speaks it.
- A `UserPromptSubmit` hook stops speech the moment you send your next prompt.
- With Kokoro installed, a small background daemon keeps the model loaded: first reply of a session starts speaking after ~5 s, later ones after ~0.4 s. It exits after 30 idle minutes.
- A new line always interrupts the one still playing.

## Better voice: Kokoro (optional)

```
brew install espeak-ng
uv venv --python 3.12 ~/.cache/tts-lab/.venv
uv pip install --python ~/.cache/tts-lab/.venv/bin/python kokoro soundfile
```

The first speech downloads the model (~330 MB). The plugin looks for `~/.cache/tts-lab/.venv/bin/python`; point elsewhere with `KOKORO_PYTHON`.

## Settings (environment variables)

| Variable | Default | Effect |
|---|---|---|
| `SAY_HEADLINE=off` | on | mute |
| `SAY_VOICE` | `af_heart` | Kokoro voice (e.g. `af_bella`, `bf_emma`) |
| `SAY_FALLBACK_VOICE` | `Tara` | macOS `say` voice when Kokoro is missing |
| `KOKORO_PYTHON` | `~/.cache/tts-lab/.venv/bin/python` | Python that has Kokoro |
| `SAY_IDLE` | `1800` | seconds before the daemon exits |

## Notes

- The daemon patches spaCy to a blank English tokenizer, because the spaCy model load crashes with current wheels. Unusual words may be mispronounced.
- The text being spoken at daemon start appears in the process list while the daemon runs. Don't put secrets in a headline.
- Audio never leaves your machine.

## Test

`python3 tests/check.py` runs an end-to-end check (plays real audio).

## License

MIT
