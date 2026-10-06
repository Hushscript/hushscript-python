from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.job_failure_kind_type_1 import (
    JobFailureKindType1,
    check_job_failure_kind_type_1,
)
from ..models.job_failure_kind_type_2_type_1 import (
    JobFailureKindType2Type1,
    check_job_failure_kind_type_2_type_1,
)
from ..models.job_failure_kind_type_3_type_1 import (
    JobFailureKindType3Type1,
    check_job_failure_kind_type_3_type_1,
)
from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.options_summary import OptionsSummary


T = TypeVar("T", bound="Job")


@_attrs_define
class Job:
    """
    Attributes:
        id (str):
        state (str): One of uploading, fetching, queued, processing, done or failed.
        mode (str):
        declared_seconds (int):
        verified_seconds (int | None): The probed exact duration, once known.
        actual_seconds (int | None):
        billable_seconds (int):
        error (None | str): A short failure reason when state is failed, otherwise null.
        failure_kind (JobFailureKindType1 | JobFailureKindType2Type1 | JobFailureKindType3Type1 | None): Set when the
            file itself could not be read: `media_unreadable` when the upload could not be probed as audio,
            `media_undecodable` when the transcription provider could not decode it. Either way the file needs converting
            (for example to MP3 or WAV) and uploading again; nothing was charged and the hold was released. Null for every
            other job, including failures of any other kind and jobs that failed before this field existed.
        retry_of (None | str): The id of an earlier failed job of yours that this job retries, set when the browser app
            re-uploaded a converted copy of an unreadable file, otherwise null.
        created_at (int):
        transcript_id (None | str): The resulting transcript's id, once transcription has finished.
        private_result_expires_at (int | None):
        private_result_available (bool):
        options (OptionsSummary): A content-free summary of the transcription options a job was submitted with: what was
            requested, never the free-text content itself.
        fetched_bytes (int | Unset): Bytes fetched so far for a from-url import. Present only while a fetch is in
            progress.
        fetch_total_bytes (int | Unset): The total byte size a from-url import is fetching toward. Present only while a
            fetch is in progress.
    """

    id: str
    state: str
    mode: str
    declared_seconds: int
    verified_seconds: int | None
    actual_seconds: int | None
    billable_seconds: int
    error: None | str
    failure_kind: (
        JobFailureKindType1 | JobFailureKindType2Type1 | JobFailureKindType3Type1 | None
    )
    retry_of: None | str
    created_at: int
    transcript_id: None | str
    private_result_expires_at: int | None
    private_result_available: bool
    options: OptionsSummary
    fetched_bytes: int | Unset = UNSET
    fetch_total_bytes: int | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        state = self.state

        mode = self.mode

        declared_seconds = self.declared_seconds

        verified_seconds: int | None
        verified_seconds = self.verified_seconds

        actual_seconds: int | None
        actual_seconds = self.actual_seconds

        billable_seconds = self.billable_seconds

        error: None | str
        error = self.error

        failure_kind: None | str
        if isinstance(self.failure_kind, str):
            failure_kind = self.failure_kind
        elif isinstance(self.failure_kind, str):
            failure_kind = self.failure_kind
        elif isinstance(self.failure_kind, str):
            failure_kind = self.failure_kind
        else:
            failure_kind = self.failure_kind

        retry_of: None | str
        retry_of = self.retry_of

        created_at = self.created_at

        transcript_id: None | str
        transcript_id = self.transcript_id

        private_result_expires_at: int | None
        private_result_expires_at = self.private_result_expires_at

        private_result_available = self.private_result_available

        options = self.options.to_dict()

        fetched_bytes = self.fetched_bytes

        fetch_total_bytes = self.fetch_total_bytes

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "id": id,
                "state": state,
                "mode": mode,
                "declared_seconds": declared_seconds,
                "verified_seconds": verified_seconds,
                "actual_seconds": actual_seconds,
                "billable_seconds": billable_seconds,
                "error": error,
                "failure_kind": failure_kind,
                "retry_of": retry_of,
                "created_at": created_at,
                "transcript_id": transcript_id,
                "private_result_expires_at": private_result_expires_at,
                "private_result_available": private_result_available,
                "options": options,
            }
        )
        if fetched_bytes is not UNSET:
            field_dict["fetched_bytes"] = fetched_bytes
        if fetch_total_bytes is not UNSET:
            field_dict["fetch_total_bytes"] = fetch_total_bytes

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.options_summary import OptionsSummary  # noqa: PLC0415

        d = dict(src_dict)
        id = d.pop("id")

        state = d.pop("state")

        mode = d.pop("mode")

        declared_seconds = d.pop("declared_seconds")

        def _parse_verified_seconds(data: object) -> int | None:
            if data is None:
                return data
            return cast(int | None, data)

        verified_seconds = _parse_verified_seconds(d.pop("verified_seconds"))

        def _parse_actual_seconds(data: object) -> int | None:
            if data is None:
                return data
            return cast(int | None, data)

        actual_seconds = _parse_actual_seconds(d.pop("actual_seconds"))

        billable_seconds = d.pop("billable_seconds")

        def _parse_error(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        error = _parse_error(d.pop("error"))

        def _parse_failure_kind(
            data: object,
        ) -> (
            JobFailureKindType1
            | JobFailureKindType2Type1
            | JobFailureKindType3Type1
            | None
        ):
            if data is None:
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                failure_kind_type_1 = check_job_failure_kind_type_1(data)

                return failure_kind_type_1
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            try:
                if not isinstance(data, str):
                    raise TypeError()
                failure_kind_type_2_type_1 = check_job_failure_kind_type_2_type_1(data)

                return failure_kind_type_2_type_1
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            try:
                if not isinstance(data, str):
                    raise TypeError()
                failure_kind_type_3_type_1 = check_job_failure_kind_type_3_type_1(data)

                return failure_kind_type_3_type_1
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(
                JobFailureKindType1
                | JobFailureKindType2Type1
                | JobFailureKindType3Type1
                | None,
                data,
            )

        failure_kind = _parse_failure_kind(d.pop("failure_kind"))

        def _parse_retry_of(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        retry_of = _parse_retry_of(d.pop("retry_of"))

        created_at = d.pop("created_at")

        def _parse_transcript_id(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        transcript_id = _parse_transcript_id(d.pop("transcript_id"))

        def _parse_private_result_expires_at(data: object) -> int | None:
            if data is None:
                return data
            return cast(int | None, data)

        private_result_expires_at = _parse_private_result_expires_at(
            d.pop("private_result_expires_at")
        )

        private_result_available = d.pop("private_result_available")

        options = OptionsSummary.from_dict(d.pop("options"))

        fetched_bytes = d.pop("fetched_bytes", UNSET)

        fetch_total_bytes = d.pop("fetch_total_bytes", UNSET)

        job = cls(
            id=id,
            state=state,
            mode=mode,
            declared_seconds=declared_seconds,
            verified_seconds=verified_seconds,
            actual_seconds=actual_seconds,
            billable_seconds=billable_seconds,
            error=error,
            failure_kind=failure_kind,
            retry_of=retry_of,
            created_at=created_at,
            transcript_id=transcript_id,
            private_result_expires_at=private_result_expires_at,
            private_result_available=private_result_available,
            options=options,
            fetched_bytes=fetched_bytes,
            fetch_total_bytes=fetch_total_bytes,
        )

        job.additional_properties = d
        return job

    @property
    def additional_keys(self) -> list[str]:
        return list(self.additional_properties.keys())

    def __getitem__(self, key: str) -> Any:
        return self.additional_properties[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self.additional_properties[key] = value

    def __delitem__(self, key: str) -> None:
        del self.additional_properties[key]

    def __contains__(self, key: str) -> bool:
        return key in self.additional_properties
