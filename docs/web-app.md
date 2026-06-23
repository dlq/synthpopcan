# Local Web App

The `serve` command starts the local SynthPopCan web app. It is meant for local
inspection and guided workflows: configuring runs, reviewing controls, checking
outputs, and downloading generated artifacts. It is not a public deployment
command.

## Getting Started

From an installed environment:

```bash
synthpopcan serve
```

From a source checkout without an activated environment:

```bash
uv run synthpopcan serve
```

By default, the app listens on `127.0.0.1:8000` and opens in the default
browser.

## Options

```bash
synthpopcan serve \
  --host 127.0.0.1 \
  --port 8000 \
  --open
```

Important options:

- `--host`: host interface for the local web app. The default is `127.0.0.1`,
  which keeps the server on the local machine.
- `--port`: local port. Use another port if `8000` is already in use.
- `--open / --no-open`: open the browser automatically, or start the server
  without opening a browser.

## Troubleshooting

**The port is already in use:** choose another port:

```bash
synthpopcan serve --port 8001
```

**The browser does not open:** start with `--no-open` and visit the printed
local URL manually.

**The app cannot see expected local data:** run {doc}`data` first to check the
local data layout, then use {doc}`sources` to inspect specific files.

**You need command-line reproducibility:** use the command-line pages for the
workflow you are building. The web app is useful for guided inspection, while
the CLI is easier to record in scripts, notebooks, and methods sections.
