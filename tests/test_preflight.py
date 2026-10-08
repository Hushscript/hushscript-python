from __future__ import annotations

import io

import pytest

from hushscript import (
    DailyLimitError,
    FileLimitError,
    PreflightError,
    UnsupportedMediaError,
)
from hushscript.transcribe.preflight import (
    Media,
    Options,
    check_account,
    check_media,
    create_body,
)
from hushscript.transcribe.source import BytesSource, SeekableSource
from pipe import media

MP3 = media(4000)


@pytest.mark.parametrize(
    "changes",
    [
        {"concurrency": 0},
        {"concurrency": 9},
        {"concurrency": True},
        {"concurrency": 2.5},
        {"wait_timeout": 0},
        {"wait_timeout": -1},
        {"wait_timeout": float("nan")},
        {"duration_seconds": 0},
        {"duration_seconds": -3},
        {"duration_seconds": float("inf")},
        {"idempotency_key": "short"},
        {"idempotency_key": "k" * 129},
        {"idempotency_key": "tab\there-and-more-chars"},
        {"medical": True},
        {"medical": True, "language": "ja"},
        {"keyterms": ("a",) * 1001},
        {"keyterms": ("one two three four five six seven",)},
        {"matter_code": "m" * 65},
    ],
)
def test_a_bad_option_is_a_preflight_error_with_its_own_code(changes: dict[str, object]) -> None:
    with pytest.raises(PreflightError) as raised:
        Options(**changes).validate()  # type: ignore[arg-type]
    assert raised.value.code == "invalid_option"
    assert raised.value.status is None


def test_the_edges_of_every_option_are_accepted() -> None:
    Options(
        concurrency=8,
        wait_timeout=0.5,
        duration_seconds=15,
        idempotency_key="k" * 16,
        medical=True,
        language="de",
        keyterms=("one two three four five six",) * 1000,
        matter_code="m" * 64,
    ).validate()
    Options(idempotency_key="k" * 128).validate()


def test_a_key_is_minted_once_and_a_given_one_is_kept() -> None:
    options = Options()
    assert len(options.new_key()) == 36
    assert options.new_key() != options.new_key()
    assert Options(idempotency_key="k" * 20).new_key() == "k" * 20


def test_the_wire_options_carry_only_what_was_set() -> None:
    assert Options().transcription_options() == {}
    wire = Options(
        language="en",
        speakers=False,
        keyterms=("a", "b"),
        prompt="p",
        medical=True,
        multichannel=True,
        auto_insights=False,
    ).transcription_options()
    assert wire == {
        "language_code": "en",
        "speaker_detection": False,
        "keyterms_prompt": ["a", "b"],
        "prompt": "p",
        "medical_mode": True,
        "multichannel": True,
        "auto_generate_insights": False,
    }


def test_translation_forces_speaker_detection_on() -> None:
    wire = Options(speakers=False, translate_to=("de", "fr")).transcription_options()
    assert wire == {"translation_targets": ["de", "fr"]}


def test_the_create_body_names_every_field_it_has() -> None:
    options = Options(matter_code="M-1", language="en")
    body = create_body(Media(size=10, duration_seconds=21), options, "k" * 20, title="T")
    assert body == {
        "size_bytes": 10,
        "duration_seconds": 21,
        "idempotency_key": "k" * 20,
        "title": "T",
        "matter_code": "M-1",
        "transcription_options": {"language_code": "en"},
    }
    bare = create_body(Media(size=10, duration_seconds=21), Options(), "k" * 20, title=None)
    assert set(bare) == {"size_bytes", "duration_seconds", "idempotency_key"}


def test_the_declared_duration_is_the_ceiling_of_the_override() -> None:
    result = check_media(BytesSource(MP3), Options(duration_seconds=20.2))
    assert result == Media(size=4000, duration_seconds=21)


def test_a_file_that_is_not_media_is_refused_by_its_bytes() -> None:
    with pytest.raises(UnsupportedMediaError) as raised:
        check_media(BytesSource(b"\x1a\x45\xdf\xa3" + bytes(100)), Options(duration_seconds=60))
    assert raised.value.code == "unsupported_media"
    assert raised.value.hint is not None
    assert "ffmpeg -i input -vn -c:a libopus output.opus" in raised.value.hint


def test_an_empty_file_is_refused_by_its_bytes() -> None:
    with pytest.raises(UnsupportedMediaError) as raised:
        check_media(BytesSource(b""), Options(duration_seconds=60))
    assert raised.value.code == "unsupported_media"
    assert raised.value.status is None


def test_the_size_lower_bound_is_checked_after_supported_magic() -> None:
    class HeaderStream(SeekableSource):
        def head(self) -> bytes:
            return self.read_range(0, 100)

    source = HeaderStream(io.BytesIO(MP3), size=0)
    with pytest.raises(FileLimitError) as raised:
        check_media(source, Options(duration_seconds=60))
    assert raised.value.code == "size_out_of_range"
    assert raised.value.status is None
    assert (
        check_media(HeaderStream(io.BytesIO(MP3), size=1), Options(duration_seconds=60)).size == 1
    )


@pytest.mark.parametrize("seconds", [14, 36_001])
def test_a_duration_outside_15_to_36000_seconds_is_a_file_limit(seconds: float) -> None:
    with pytest.raises(FileLimitError) as raised:
        check_media(BytesSource(MP3), Options(duration_seconds=seconds))
    assert raised.value.code == "duration_out_of_range"


def test_the_limits_are_inclusive() -> None:
    assert check_media(BytesSource(MP3), Options(duration_seconds=15)).duration_seconds == 15
    assert (
        check_media(BytesSource(MP3), Options(duration_seconds=36_000)).duration_seconds == 36_000
    )


def test_declared_stream_size_stops_at_5_gb() -> None:
    source = SeekableSource(io.BytesIO(MP3), size=5_000_000_000)
    assert check_media(source, Options(duration_seconds=60)).size == 5_000_000_000
    source = SeekableSource(io.BytesIO(MP3), size=5_000_000_001)
    with pytest.raises(FileLimitError) as raised:
        check_media(source, Options(duration_seconds=60))
    assert raised.value.code == "size_out_of_range"
    assert raised.value.status is None


def test_an_mp3_with_no_readable_duration_asks_for_one() -> None:
    with pytest.raises(UnsupportedMediaError) as raised:
        check_media(BytesSource(b"ID3" + bytes(100)), Options())
    assert raised.value.code == "duration_unreadable"


MEDIA = Media(size=100, duration_seconds=21)


def _account(balance: int = 36000, used: int = 0, daily: int = 36000) -> dict[str, object]:
    return {
        "balance_seconds": balance,
        "held_seconds": 4,
        "limits": {"max_daily_seconds": daily, "used_today_seconds": used},
    }


def test_exactly_the_daily_headroom_passes() -> None:
    check_account(_account(used=36000 - 21), MEDIA)


def test_a_balance_below_any_estimate_is_not_a_preflight_refusal() -> None:
    check_account(_account(balance=0), MEDIA)
    check_account(_account(balance=-5), MEDIA)


def test_the_daily_limit_is_refused_with_the_numbers() -> None:
    with pytest.raises(DailyLimitError) as raised:
        check_account(_account(used=36000 - 20, daily=36000), MEDIA)
    error = raised.value
    assert error.code == "daily_limit"
    assert error.details == {"used_today_seconds": 35980, "max_daily_seconds": 36000}
    assert error.hint is not None
    assert "599 of 600 min" in error.hint


@pytest.mark.parametrize(
    "account",
    [None, {}, {"limits": []}, {"limits": {"max_daily_seconds": "7", "used_today_seconds": 1}}],
)
def test_an_account_the_sdk_cannot_read_is_not_a_refusal(account: object) -> None:
    check_account(account, MEDIA)
