# Contributing

## Development Setup

1. Fork and clone the repository.
2. Install [poetry](https://python-poetry.org/).
3. In the root directory, run `poetry shell`.
4. Run `poetry install`.
5. `unitunes` should now be runnable.

## Testing

Run `pytest` to run tests. With no arguments, it will skip tests that require service configs.

Add a service config to run more tests.

```bash
pytest -s --spotify=spotify_config.json --ytm=ytm_config.json # may need to run with -s to paste spotify redirect URL the first time
```
