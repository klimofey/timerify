# Timerify

Timers for any Home Assistant entity — without writing automations.

Timerify attaches timer controls directly to entities you already have. A boiler that is just a
smart switch gets, on its own device page:

- **Run for** — set 10 minutes and the boiler turns on and turns itself off when the countdown
  ends; set 0 and it turns off; turn it off by hand and the countdown resets.
- **Auto-off after** — whenever it is turned on, turn it off after a fixed duration.
- **Schedule** — a weekly on/off schedule.
- **Remaining time** — a sensor you can show on dashboards.

It also teaches Assist to use them: "turn on the boiler for 10 minutes",
"how long is left on the boiler?", "cancel the boiler timer".

> **Status:** early design phase — not usable yet.

## Development

Requires Python 3.14.2+ and [uv](https://docs.astral.sh/uv/).

```sh
git config core.hooksPath .githooks
uv sync
uv run pytest
```

## License

MIT
