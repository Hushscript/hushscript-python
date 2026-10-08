# hushscript

The official Python SDK for the [Hushscript](https://hushscript.com) transcription API. It uploads a
file, waits for the transcript and hands it back, and it handles the failures in between so you do
not have to.

## Quick start

```sh
pip install hushscript
export HUSHSCRIPT_TOKEN=hsr1:...   # Account → MCP in the Hushscript app
```

```python
from pathlib import Path

from hushscript import Hushscript

with Hushscript() as hs:  # reads HUSHSCRIPT_TOKEN
    transcript = hs.transcribe("meeting.mp3")
    print(transcript.text)
    Path("meeting.srt").write_text(transcript.to_srt(), encoding="utf-8")
```

Every call has an asyncio twin on `AsyncHushscript` with the same names (`await` the calls and use
`async for` on the lists); the examples below use the synchronous client.

## Inputs

`transcribe()` and `resume()` take a path, `bytes` or a binary file object. A seekable file is
probed and read like a path; a non-seekable one (a pipe, a socket) is read once, in order, one part
at a time, so it needs its exact `size` and `duration_seconds`:

```python
transcript = hs.transcribe(sys.stdin.buffer, size=size_in_bytes, duration_seconds=1800)
```

## Check my balance

```python
balance = hs.balance()
print(f"{balance.minutes} minutes to spend")
```

`balance.minutes` is what you can spend now. Minutes held for jobs that are still running are
already taken out of it, so do not subtract `held_seconds` again.

## List my transcripts

```python
for summary in hs.transcripts.list():
    print(summary.id, summary.title)
```

The list holds finished transcripts only. A recording that is still processing is a job, so look for
it in `hs.jobs.list(active=True)`. `hs.jobs.wait(job_id)` waits for one, and
`hs.transcripts.get(transcript_id)` returns the full `Transcript` once it is done.

## Buy a pack

```python
for pack in hs.billing.packs():
    print(pack.id, f"{pack.minutes} minutes", pack.price.formatted)

purchase = hs.buy("300min", acknowledge_no_refund=True)
print(f"{purchase.minutes} minutes to spend now")
```

The packs are `45min`, `300min`, `900min`, `1800min` and `6000min`. Prices depend on your country,
so read them from `pack.price` and never hard-code one.

`buy()` charges your saved default card, or the only card that can be charged when there is no
default, and returns a `Purchase`: the `seconds` and `minutes` you have after it settled. It makes
no request after the charge, so nothing can fail once the money has moved. With no usable card it
raises `PaymentMethodRequiredError` and sends nothing: `no_default_card` when there is none (add one
at the URL from `hs.billing.add_card_url()` or in the app), `default_card_required` when several
cards could be charged and none is the default (pick one with `hs.billing.set_default_card(card_id)`).

Show your buyer this notice before you call it, then pass `acknowledge_no_refund=True`:

> Minutes are added to your account instantly after payment. All purchases are final and
> non-refundable.

The flag records that the notice was shown. It does not gate the charge, and without it `buy()`
still goes ahead.

### Allow buying first

Buying from code is off until you allow it in three places. If any is missing, the call fails with
`pat_scope_missing`.

1. The token has the permission labeled "Buy minutes and manage your saved payment methods" (the
   `billing` scope), ticked when you create it.
2. The token has "Let this token buy minutes" turned on, on the same "Create a new token" form.
3. "Let connected apps buy minutes" is on for the whole account.

All of it is in the app under Account → MCP.

### When a purchase does not go through

If the saved card was declined or cannot be charged without you, the call fails with
`pat_purchase_requires_app` (code 4021, status 403). If the bank wants to confirm the payment, it
fails with `pat_purchase_requires_authentication` (code 4023, status 403). In both cases nothing was
charged: buy that pack in the app. A key that met 4021 is spent, so the next `buy()` call makes a
new one.

A purchase is retried at most once, on a network error, a 502 or a 503, with the same idempotency
key, so those retries cannot charge you twice. When `buy()` still gives up after the request was
sent, the card may have been charged: this includes network failures, answers the SDK cannot
use, a 401, a 429, any 403 other than codes 4021 and 4023, and any 5xx response. Every such error carries `idempotency_key`; ask again with it and the purchase can
never happen twice:

```python
from hushscript import HushscriptError

try:
    purchase = hs.buy("300min", acknowledge_no_refund=True)
except HushscriptError as error:
    refused = error.status in {400, 402, 404, 422} or (
        error.status == 403 and error.numeric_code in {4021, 4023}
    )
    if error.idempotency_key is None or refused:
        raise  # only these refusals charged nothing; any other failure keeps the key for a retry
    purchase = hs.buy("300min", acknowledge_no_refund=True, idempotency_key=error.idempotency_key)
```

A key you pass yourself must be 1 to 128 characters from `A-Za-z0-9_-`. Do not reuse a key for a
different pack.

## Export subtitles

```python
Path("meeting.srt").write_text(transcript.to_srt(), encoding="utf-8")
Path("meeting.vtt").write_text(transcript.to_vtt("es"), encoding="utf-8")
Path("meeting.txt").write_text(transcript.to_text(timestamps=True), encoding="utf-8")
```

The output is byte for byte what the Hushscript app exports. `to_srt` and `to_vtt` wrap lines into
caption cues by default; pass `captions=False` for one cue per utterance.

## Agents: sign up without a human account

An agent can open an account, have it paid for at a hosted checkout page, and claim its own token.
The first two calls need no token yet, so they are static.

```python
import os
import tempfile
from pathlib import Path

from hushscript import AgentInfo, Hushscript

TOKEN_FILE = Path("agent-token")


def keep(token: str) -> None:
    """Writes the token to a private temporary file and renames it into place: the file is never
    half a token, and an older token is not truncated before the new one is safely on disk."""
    descriptor, temporary = tempfile.mkstemp(dir=TOKEN_FILE.parent, prefix=".token-")  # mode 0600
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as file:
            file.write(f"{token}\n")
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, TOKEN_FILE)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


signup = Hushscript.agent_signup(
    email="agent@example.com",
    pack="45min",
    accept_terms="<the policy version you accept>",
    agent=AgentInfo(name="My agent", platform="custom"),
)
print(f"Pay {signup.price.formatted} at {signup.checkout_url}")

# After the checkout is paid:
account = Hushscript.agent_claim(signup.signup_id, signup.claim_secret)
keep(account.token)  # before anything else can fail
with Hushscript(account.token) as hs:
    rotated = hs.agent.rotate_token()  # revokes the claimed token; the client sends the new one
    keep(rotated.token)
```

- `accept_terms` is never filled in for you; an empty one raises `ValidationError` with the code
  `accept_terms_required` before any request. A wrong version fails with `policy_version_stale`, and
  the error's `hint` names the current one.
- The claim answers `wrong_state` (a `ConflictError`) until the checkout is paid.
- New agent accounts can buy only `45min` and `300min` until earlier purchases settle.
- Keep `claim_secret` and every token: the server shows each of them once, and a rotation revokes
  the token it replaces, so lose the new one and the account is out of reach. A claim or a rotation
  whose answer is lost, or comes back without a usable token, raises `OutcomeUnknownError` and is
  never retried, because a retry could not succeed; its `hint` says what to check. When the answer
  did carry something that looked like a token, `error.received_token` holds it, so you can store it
  before anything else. It is kept out of the error's text, repr, pickle and logs.
- `dry_run=True` validates a signup without opening a checkout.

## Errors

Every error the SDK raises extends `HushscriptError`, so one `except` covers everything:

```python
from hushscript import HushscriptError, InsufficientBalanceError

try:
    hs.transcribe("meeting.mp3")
except InsufficientBalanceError as error:
    print(error.hint)
except HushscriptError as error:
    print(error.code, error.hint or error.message)
```

An error carries `code` (a slug such as `insufficient_balance`), `numeric_code`, `status`,
`message`, `hint` (what to do next, or `None`), `details` and `retry_after`. The classes:

```
HushscriptError
├─ ConfigurationError
├─ PreflightError                  no credit was held
│  ├─ UnsupportedMediaError
│  ├─ FileLimitError
│  ├─ DailyLimitError
│  └─ ResumeMismatchError
├─ ApiError                        has status
│  ├─ AuthenticationError          401
│  ├─ PermissionDeniedError        403
│  ├─ InsufficientBalanceError     402
│  ├─ NotFoundError                404
│  ├─ ConflictError                409
│  ├─ ValidationError              400, 422
│  └─ RateLimitError               429
├─ PaymentMethodRequiredError
├─ UploadError
├─ JobFailedError
├─ WaitTimeoutError                has resume_token
├─ AbortError                      has resume_token once a job exists
├─ NetworkError
└─ OutcomeUnknownError
```

An error raised after an upload started, or after a purchase was sent, carries `idempotency_key`;
once the job exists it carries `resume_token` too. Pass the token to `hs.resume(token, file)` to
carry on without a second charge.

## What the SDK does for you

- **Checks before it spends.** It sniffs the format from the file's bytes, probes the duration,
  and refuses a file the server would refuse, or one your daily limit cannot cover,
  before any minutes are held.
- **Keeps retries from charging twice.** Every upload and purchase carries an idempotency key, and
  retries reuse it. A `resume_token` replays the same job instead of starting a new one, and the
  key on a failed purchase does the same for `buy()`.
- **Retries what is safe.** Reads, heartbeats and part uploads retry on network errors, 429 and 5xx
  with jittered backoff, and honor `Retry-After` up to 60 seconds. A purchase retries once on a
  network error, 502 or 503. A claim, a rotation and a signup never retry.
- **Paces uploads.** The API allows four upload creates a minute. A loop over a folder waits as
  needed, and `on_progress` keeps reporting.
- **Keeps the upload alive.** It uploads parts in parallel with bounded memory, falls back to the
  proxied route when direct upload fails, refreshes expired part URLs and sends a heartbeat every
  two minutes.
- **Waits and fetches.** It polls the job until it is done, raises `JobFailedError` if it fails,
  and gives you a `resume_token` if the wait times out. The job keeps running.
- **Redacts secrets.** The token, a received token and every signed upload URL stay out of every
  error, log line, `repr`, pickle and copy. The results that hand you a secret
  (`AgentSignup.claim_secret`, `AgentAccount.token`, `RotatedToken.token`) keep it readable as a
  field, but `repr`, `str` and `pprint` show `[redacted]` in its place; `dataclasses.asdict`, `json`
  and `pickle` are your own export and carry the value. The SDK keeps secrets out of the local
  variables of its own frames, but an error reporter that captures local variables (for example
  Sentry with `include_local_variables`) can still see them inside the HTTP library's frames.

## Supported formats

MP3, M4A, MP4 and MOV (the audio track of a video is used), WAV, FLAC, and OGG with Vorbis or Opus.
Files can be up to 5 GB and from 15 seconds to 10 hours. The SDK does not convert media. For
anything else, convert it first:

```sh
ffmpeg -i input -vn -c:a libopus output.opus
```

## Configuration

| Option                   | Env var               | Default                                                              |
| ------------------------ | --------------------- | -------------------------------------------------------------------- |
| `token` (first argument) | `HUSHSCRIPT_TOKEN`    | none                                                                 |
| `base_url`               | `HUSHSCRIPT_BASE_URL` | `https://api.hushscript.com`                                         |
| `timeout`                | none                  | 60 s per request                                                     |
| `max_retries`            | none                  | 3                                                                    |
| `log_level`              | `HUSHSCRIPT_LOG`      | `off` (`debug` logs one metadata line per request to standard error) |
| `clock`                  | none                  | `SystemClock`; pass a `Clock` in tests                               |

An explicit option beats its environment variable. A `None`, empty or whitespace-only option, and
an empty or whitespace-only environment variable, count as not set: the option falls back to the
environment variable, then to the default. A token that is still missing raises `ConfigurationError`
with the setup hint. The base URL must be `https://`, or `http://` to `localhost`, `127.0.0.1` or
`[::1]`, with no path. Each upload part has its own 300 s timeout, which you cannot change.

## Privacy

The SDK sends no telemetry. The only client identification is the `User-Agent` header
(`hushscript-python/<version> python/<version>`). Logging is off by default;
`HUSHSCRIPT_LOG=debug` (or `log_level="debug"`) writes one line per request with the method, path,
status and timing, and never a header, body, title or transcript text.

## The low-level API

Every `/v1` operation is available as `hs.api`, the generated client on the same retries, timeouts
and redaction:

```python
from hushscript.generated.api.default import get_account

response = get_account.sync_detailed(client=hs.api)
```

An answer the generated code cannot read (a body that is not JSON, or lacks a field) raises
`HushscriptError` with code `bad_response`, or the error for its status, never a bare
`JSONDecodeError` or `KeyError`. A failure after a purchase went out carries its `idempotency_key`.

## Server only

The SDK is for servers and scripts. The API does not accept browser origins, and a token shipped in
client-side code is a leaked token.

## Pricing

Personal accounts buy prepaid minute packs. The price of a pack depends on your country, and your
minutes stay valid for a year after your last transcription or purchase. A transcription uses the
minutes of the recording; medical mode and each translation target use more. Current prices are on
[hushscript.com/pricing](https://hushscript.com/pricing).

## Requirements

Python 3.11 or newer. `just build` installs the built wheel on 3.11 and on 3.14 with nothing but the
runtime dependencies and imports it. The package is typed (`py.typed`).

## Releases

Releases come from release-please. The package is published to PyPI by `publish.yml` through PyPI
trusted publishing (OIDC) with PEP 740 attestations: no PyPI token is stored in GitHub. The build job
has no secrets and no `id-token`; the publish job runs behind the `release` environment, checks the
digest of every artifact the build job produced, and only then attests and uploads. Before the first
release the owner adds a pending trusted publisher for the project `hushscript` on pypi.org (owner
`Hushscript`, this repository, workflow `publish.yml`, environment `release`).

## Development

Everything runs in containers; nothing touches a host toolchain. You need Docker with Compose v2 and
[just](https://github.com/casey/just).

```sh
just ci                 # lint, then test and conformance on 3.11 and 3.14, then examples and build
just test 3.14          # unit tests with coverage on one interpreter
just lint               # every static check
just examples           # every program in examples/ against the conformance mock
just build              # sdist and wheel, twine and wheel-contents checks, install on 3.11 and 3.14
just regen              # regenerate openapi.json and src/hushscript/generated from the production spec
```

The conformance mock is built from the `hushscript-sdk-conformance` repository at the tag in
`conformance-ref`; `just ci` fails when a scenario is skipped (`CONFORMANCE_STRICT=1`). To use a local
checkout instead:

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
