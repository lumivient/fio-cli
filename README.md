# FIO CLI

A command line interface exposing read-only requests to https://doc.fnar.net/ via https://github.com/lumivient/fio-sdk

## Dependencies

- [Python 3.11+](https://www.python.org/)
- [uv](https://docs.astral.sh/uv/)

## Setup

1. `git clone https://github.com/lumivient/fio-cli.git`
2. `cd fio-cli`
3. `cp config.toml.example config.toml`
4. Get an FIO API key from https://fio.fnar.net/ if you haven't already
5. Edit `~/.config/prun-ai/config.toml` and enter your details

## Usage

Just run `./fio` to get started.

Run `./fio search <term>` or `./fio list` to find available endpoints.

## Filtering

Data can be filtered using [JMESPath](https://jmespath.org/) expressions.

Run `./fio shape {Endpoint}` (e.g. `./fio shape csv/sites`) to discover its shape and therefore how to filter its response.

Apply a filter like so: `./fio get csv/prices/condensed --filter "[?Ticker=='RAT' && CX=='IC1'][]"`

## Placeholders

Some endpoints have placeholders like `{UserName}`. If a matching value exists in `config.toml` the CLI will automatically inject it, like `./fio get 'ship/ships/{UserName}'` might become `./fio get 'ship/ships/Lumivient'`.

Replacing placeholders with custom values is also supported.
