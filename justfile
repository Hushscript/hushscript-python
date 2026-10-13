# Every recipe runs in containers; nothing here touches host toolchains.
# Examples: `just ci`, `just test 3.14`, `CONFORMANCE_CONTEXT=../hushscript-sdk-conformance just conformance`.
set shell := ["bash", "-euo", "pipefail", "-c"]

export HOST_UID := `id -u`
export HOST_GID := `id -g`

hadolint_image := "hadolint/hadolint:v2.14.0@sha256:27086352fd5e1907ea2b934eb1023f217c5ae087992eb59fde121dce9c9ff21e"
actionlint_image := "rhysd/actionlint:1.7.8@sha256:96d4a8c87dbbfb3bdd324f8fdc285fc3df5261e2decc619a4dd7e8ee52bbfd46"
zizmor_image := "ghcr.io/zizmorcore/zizmor:1.16.0@sha256:a6460f1b6fe3dc08e588d314e73563bdd218ee30c995a4be5e9ee5bd300391ce"
shellcheck_image := "koalaman/shellcheck:v0.11.0@sha256:61862eba1fcf09a484ebcc6feea46f1782532571a34ed51fedf90dd25f925a8d"
gitleaks_image := "ghcr.io/gitleaks/gitleaks:v8.28.0@sha256:cdbb7c955abce02001a9f6c9f602fb195b7fadc1e812065883f695d1eeaba854"
sandbox := "--rm --init --label sdk.test=1 --cap-drop ALL --read-only --security-opt no-new-privileges --pids-limit 512 --memory 4g --tmpfs /tmp"
# The conformance suite is read at the ref in conformance-ref, the one place it is pinned.
conformance_ref := `tr -d '[:space:]' < conformance-ref`
export CONFORMANCE_CONTEXT := env("CONFORMANCE_CONTEXT", "https://github.com/Hushscript/hushscript-sdk-conformance.git#" + conformance_ref)
# No scenario may be skipped: an unmapped op fails the conformance run.
export CONFORMANCE_STRICT := env("CONFORMANCE_STRICT", "1")
floor := "3.10"
release_runtime := "3.11"
newest := "3.15"
mutation_runtime := "3.11"
versions := "3.10 3.11 3.12 3.13 3.14 3.15"

# unit tests with coverage on Python 3.10 (default) through 3.15; no network beyond the mock; reads fixtures from CONFORMANCE_DIR (default ../hushscript-sdk-conformance)
test version=floor:
    #!/usr/bin/env bash
    set -euo pipefail
    case "{{version}}" in 3.10|3.11|3.12|3.13|3.14|3.15) ;; *) echo "version must be 3.10, 3.11, 3.12, 3.13, 3.14 or 3.15" >&2; exit 1 ;; esac
    export PYTHON_VERSION={{version}}
    trap 'docker compose down --remove-orphans >/dev/null 2>&1 || true' EXIT
    # The tests read the conformance repo's fixtures (hint-rendering.json); the checkout is
    # CONFORMANCE_DIR, or the sibling hushscript-sdk-conformance repository.
    extra=(-v "$(realpath "${CONFORMANCE_DIR:-../hushscript-sdk-conformance}")":/conformance:ro -e CONFORMANCE_DIR=/conformance)
    docker compose build mock test
    docker compose run --rm ${extra[@]+"${extra[@]}"} test

# mutmut on transport, transcription and billing (nightly)
mutation version=mutation_runtime:
    #!/usr/bin/env bash
    set -euo pipefail
    case "{{version}}" in 3.11|3.14) ;; *) echo "mutation version must be 3.11 or 3.14" >&2; exit 1 ;; esac
    export PYTHON_VERSION={{version}}
    trap 'docker compose down --remove-orphans >/dev/null 2>&1 || true' EXIT
    extra=(-v "$(realpath "${CONFORMANCE_DIR:-../hushscript-sdk-conformance}")":/conformance:ro -e CONFORMANCE_DIR=/conformance)
    docker compose build mock mutation
    docker compose run --rm ${extra[@]+"${extra[@]}"} mutation

# the conformance suite against the mock
conformance version=floor:
    #!/usr/bin/env bash
    set -euo pipefail
    case "{{version}}" in 3.10|3.11|3.12|3.13|3.14|3.15) ;; *) echo "version must be 3.10, 3.11, 3.12, 3.13, 3.14 or 3.15" >&2; exit 1 ;; esac
    export PYTHON_VERSION={{version}}
    trap 'docker compose down --remove-orphans >/dev/null 2>&1 || true' EXIT
    docker compose build mock conformance
    docker compose run --rm conformance

# every example against the mock
examples version=floor:
    #!/usr/bin/env bash
    set -euo pipefail
    case "{{version}}" in 3.10|3.11|3.12|3.13|3.14|3.15) ;; *) echo "version must be 3.10, 3.11, 3.12, 3.13, 3.14 or 3.15" >&2; exit 1 ;; esac
    export PYTHON_VERSION={{version}}
    trap 'docker compose down --remove-orphans >/dev/null 2>&1 || true' EXIT
    docker compose build mock examples
    docker compose run --rm examples

# every static check: ruff, mypy, basedpyright, deptry, hadolint, actionlint, zizmor, shellcheck, gitleaks, typos, pip-audit (Python 3.15 only)
lint version=floor:
    #!/usr/bin/env bash
    set -euo pipefail
    case "{{version}}" in 3.10|3.11|3.12|3.13|3.14|3.15) ;; *) echo "version must be 3.10, 3.11, 3.12, 3.13, 3.14 or 3.15" >&2; exit 1 ;; esac
    export PYTHON_VERSION={{version}}
    trap 'docker compose down --remove-orphans >/dev/null 2>&1 || true' EXIT
    docker compose build mock lint
    docker compose run --rm lint
    run() { docker run {{sandbox}} --network none --user "$(id -u):$(id -g)" -v "$(pwd)":/work:ro -w /work -e HOME=/tmp "$@"; }
    run {{hadolint_image}} /bin/hadolint docker/dev.Dockerfile docker/typos.Dockerfile
    run {{actionlint_image}} -color
    run {{zizmor_image}} --pedantic --offline --config zizmor.yml .github
    run {{shellcheck_image}} scripts/*.sh
    run {{gitleaks_image}} git --no-banner --redact --verbose /work
    docker build --quiet -f docker/typos.Dockerfile -t hushscript-python-typos:local docker
    run hushscript-python-typos:local --config _typos.toml
    # The one lint step with network access: it asks the advisory database about the locked set.
    # It runs once, on the newest supported Python; the other versions skip it.
    if [ "{{version}}" = "{{newest}}" ]; then
      docker run {{sandbox}} "hushscript-python-dev:py{{version}}" \
        sh -c 'uv export --frozen --all-groups --no-emit-project --no-hashes --no-header > /tmp/requirements.txt \
          && timeout 300 pip-audit --requirement /tmp/requirements.txt --no-deps --disable-pip --progress-spinner off --cache-dir /tmp/pip-audit'
    else
      echo "pip-audit skipped on Python {{version}}; it runs on Python {{newest}} only"
    fi

# sdist and wheel, twine and wheel-contents checks, then install the wheel next to the runtime
# dependencies only and import it. Runs with no network: hatchling comes from the dev image.
build version=floor:
    #!/usr/bin/env bash
    set -euo pipefail
    case "{{version}}" in 3.10|3.11|3.12|3.13|3.14|3.15) ;; *) echo "version must be 3.10, 3.11, 3.12, 3.13, 3.14 or 3.15" >&2; exit 1 ;; esac
    export PYTHON_VERSION={{version}}
    docker build --quiet --target dev --build-arg PYTHON_VERSION={{version}} -f docker/dev.Dockerfile -t "hushscript-python-dev:py{{version}}" .
    docker build --quiet --target proddeps --build-arg PYTHON_VERSION={{version}} -f docker/dev.Dockerfile -t "hushscript-python-proddeps:py{{version}}" .
    out="$(mktemp -d)"
    trap 'rm -rf "$out"' EXIT
    mkdir -p "$out/dist"
    user="$(id -u):$(id -g)"
    docker run {{sandbox}} --network none --user "$user" -v "$out/dist":/out "hushscript-python-dev:py{{version}}" \
      sh -c 'timeout 600 uv build --no-build-isolation --offline --out-dir /out \
        && timeout 120 twine check --strict /out/* \
        && timeout 120 check-wheel-contents /out/*.whl'
    check='import importlib.resources as r, hushscript; assert hushscript.ERROR_CATALOG and hushscript.HINTS and hushscript.OPERATION_SCOPES; assert r.files("hushscript").joinpath("py.typed").is_file(); hushscript.Hushscript("hsr1:eu:pat.0123456789abcdef0123456789abcdef.0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"); print("wheel ok", hushscript.__version__)'
    docker run {{sandbox}} --network none --user "$user" -v "$out/dist":/dist:ro -w /tmp "hushscript-python-proddeps:py{{version}}" \
      sh -c 'uv pip install --python /opt/venv/bin/python --target /tmp/site --no-deps --offline /dist/*.whl \
        && PYTHONPATH=/tmp/site timeout 60 /opt/venv/bin/python -c "$0"' "$check"

# release artifacts for publish.yml: the sdist and wheel in <out>/dist (twine checked) and a CycloneDX SBOM
# of the locked runtime set in <out>/sbom.cdx.json
dist out:
    #!/usr/bin/env bash
    set -euo pipefail
    export PYTHON_VERSION={{release_runtime}}
    docker build --quiet --target dev --build-arg PYTHON_VERSION={{release_runtime}} -f docker/dev.Dockerfile -t "hushscript-python-dev:py{{release_runtime}}" .
    mkdir -p "{{out}}/dist"
    docker run {{sandbox}} --network none --user "$(id -u):$(id -g)" -v "$(realpath "{{out}}")":/out "hushscript-python-dev:py{{release_runtime}}" \
      sh -c 'timeout 600 uv build --no-build-isolation --offline --out-dir /out/dist \
        && rm -f /out/dist/.gitignore \
        && timeout 120 twine check --strict /out/dist/* \
        && uv export --frozen --no-dev --no-emit-project --no-hashes --no-header > /tmp/requirements.txt \
        && timeout 120 cyclonedx-py requirements --of JSON --output-file /out/sbom.cdx.json /tmp/requirements.txt'

# regenerate openapi.json and src/hushscript/generated from the production spec, or from a local spec file (outbound network)
regen spec="":
    #!/usr/bin/env bash
    set -euo pipefail
    export PYTHON_VERSION={{release_runtime}}
    trap 'docker compose down --remove-orphans >/dev/null 2>&1 || true' EXIT
    extra=()
    if [ -n "${CONFORMANCE_DIR:-}" ]; then
      extra=(-v "$(realpath "$CONFORMANCE_DIR")":/conformance:ro -e CONFORMANCE_DIR=/conformance)
    fi
    spec="{{spec}}"
    # A local file is bind-mounted, so the generator reads exactly the bytes that were diffed.
    if [ -n "$spec" ] && [ -f "$spec" ]; then
      extra+=(-v "$(realpath "$spec")":/spec/openapi.json:ro)
      spec=/spec/openapi.json
    fi
    docker compose build regen
    docker compose run --rm ${extra[@]+"${extra[@]}"} regen timeout 600 python scripts/generate.py ${spec:+"$spec"}

# lint, then test and conformance, then examples, then build on each version; no argument runs Python 3.10 through 3.15
ci version="":
    #!/usr/bin/env bash
    set -euo pipefail
    if [ -n "{{version}}" ]; then versions="{{version}}"; else versions="{{versions}}"; fi
    for v in $versions; do
      case "$v" in 3.10|3.11|3.12|3.13|3.14|3.15) ;; *) echo "unsupported Python version: $v" >&2; exit 1 ;; esac
    done
    for v in $versions; do
      just lint "$v"
      just test "$v"
      just conformance "$v"
      just examples "$v"
      just build "$v"
    done

# nightly smoke against production; needs SMOKE_TOKEN (outbound network)
smoke:
    #!/usr/bin/env bash
    set -euo pipefail
    : "${SMOKE_TOKEN:?set SMOKE_TOKEN to a token that can read the account}"
    export PYTHON_VERSION={{floor}}
    docker compose build smoke
    docker compose run --rm smoke
