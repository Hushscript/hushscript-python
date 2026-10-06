# hushscript

The official Python SDK for the [Hushscript](https://hushscript.com) transcription API.

This package is not released yet. It holds the generated low-level client, the error catalog, the
core client (configuration, retrying transport, errors, redaction, logging) and the build, test and
release automation. The friendly layer (`transcribe`, `buy` and the rest) follows.

## Requirements

Python 3.11 or newer. `just build` installs the built wheel on 3.11 with nothing but the runtime
dependencies and imports it, so 3.11 is the tested consumer floor. The package is typed
(`py.typed`).

## Releases

Releases come from release-please and are published to PyPI by `publish.yml` through PyPI trusted
publishing: no PyPI token is stored in GitHub. Before the first release the owner adds a pending
trusted publisher for the project `hushscript` on pypi.org (owner `Hushscript`, this repository,
workflow `publish.yml`, environment `release`).

## Development

Everything runs in containers; nothing touches a host toolchain. You need Docker with Compose v2 and
[just](https://github.com/casey/just).

```sh
just ci                 # lint, then test and conformance on 3.11 and 3.14, then examples and build
just test 3.14          # unit tests with coverage on one interpreter
just lint               # every static check
just regen              # regenerate openapi.json and src/hushscript/generated from the production spec
```

The conformance mock is built from the `hushscript-sdk-conformance` repository at the tag pinned in
`compose.yaml`. To use a local checkout instead:

```sh
CONFORMANCE_CONTEXT=../hushscript-sdk-conformance CONFORMANCE_DIR=../hushscript-sdk-conformance just ci
```

`just test` reads the conformance repo's fixtures (`fixtures/hint-rendering.json`) from
`CONFORMANCE_DIR`, which defaults to `../hushscript-sdk-conformance`; the hint-rendering test fails
without them.

Runtime dependencies in `pyproject.toml` are compatible ranges on purpose: a library that pins exact
versions breaks the resolvers of the projects that install it. Everything else is pinned: the dev
and tool dependencies, the build backend and the container images are locked in `uv.lock` and in
`pyproject.toml`, and `just ci` tests exactly that set.

## Security

See [SECURITY.md](SECURITY.md).

## License

MIT
