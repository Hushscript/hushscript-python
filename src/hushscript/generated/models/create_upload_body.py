from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.create_upload_body_transcription_options_type_0 import (
        CreateUploadBodyTranscriptionOptionsType0,
    )


T = TypeVar("T", bound="CreateUploadBody")


@_attrs_define
class CreateUploadBody:
    """
    Attributes:
        size_bytes (int): The exact declared byte size of the audio file, up to the 5 GB cap.
        duration_seconds (int): The declared duration in seconds, from 15 seconds up to the 10 hour cap. Rechecked
            against the probed exact duration at complete_upload.
        title (None | str | Unset): An optional display title. A value longer than 300 bytes is truncated on a character
            boundary rather than rejected, and this response does not echo the stored value; read it back from the
            transcript once the job completes. In `private` mode the title is not stored at all.
        mode (None | str | Unset): Optional job mode, e.g. a private-result upload.
        part_size_bytes (int | None | Unset): Optional smaller part size for a flaky connection. Clamped to this API's
            supported range; omit for the 32 MiB default.
        idempotency_key (None | str | Unset): An optional client-minted key, 16 to 128 bytes. Resending the same key
            returns the same job with no second hold.
        matter_code (None | str | Unset): Free text, trimmed, at most 64 characters; blank is valid and clears it.
            Refused with org_matter_code_required when the caller's workspace sets matter_code_policy to required and this
            is absent or blank.
        client_code (None | str | Unset): Free text, trimmed, at most 64 characters; blank is valid. Accepted for
            backward compatibility: for an org caller the client is always resolved from the matter instead, never from this
            field.
        transcription_options (CreateUploadBodyTranscriptionOptionsType0 | None | Unset):
    """

    size_bytes: int
    duration_seconds: int
    title: None | str | Unset = UNSET
    mode: None | str | Unset = UNSET
    part_size_bytes: int | None | Unset = UNSET
    idempotency_key: None | str | Unset = UNSET
    matter_code: None | str | Unset = UNSET
    client_code: None | str | Unset = UNSET
    transcription_options: CreateUploadBodyTranscriptionOptionsType0 | None | Unset = (
        UNSET
    )
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        from ..models.create_upload_body_transcription_options_type_0 import (
            CreateUploadBodyTranscriptionOptionsType0,  # noqa: PLC0415
        )

        size_bytes = self.size_bytes

        duration_seconds = self.duration_seconds

        title: None | str | Unset
        if isinstance(self.title, Unset):
            title = UNSET
        else:
            title = self.title

        mode: None | str | Unset
        if isinstance(self.mode, Unset):
            mode = UNSET
        else:
            mode = self.mode

        part_size_bytes: int | None | Unset
        if isinstance(self.part_size_bytes, Unset):
            part_size_bytes = UNSET
        else:
            part_size_bytes = self.part_size_bytes

        idempotency_key: None | str | Unset
        if isinstance(self.idempotency_key, Unset):
            idempotency_key = UNSET
        else:
            idempotency_key = self.idempotency_key

        matter_code: None | str | Unset
        if isinstance(self.matter_code, Unset):
            matter_code = UNSET
        else:
            matter_code = self.matter_code

        client_code: None | str | Unset
        if isinstance(self.client_code, Unset):
            client_code = UNSET
        else:
            client_code = self.client_code

        transcription_options: dict[str, Any] | None | Unset
        if isinstance(self.transcription_options, Unset):
            transcription_options = UNSET
        elif isinstance(
            self.transcription_options, CreateUploadBodyTranscriptionOptionsType0
        ):
            transcription_options = self.transcription_options.to_dict()
        else:
            transcription_options = self.transcription_options

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "size_bytes": size_bytes,
                "duration_seconds": duration_seconds,
            }
        )
        if title is not UNSET:
            field_dict["title"] = title
        if mode is not UNSET:
            field_dict["mode"] = mode
        if part_size_bytes is not UNSET:
            field_dict["part_size_bytes"] = part_size_bytes
        if idempotency_key is not UNSET:
            field_dict["idempotency_key"] = idempotency_key
        if matter_code is not UNSET:
            field_dict["matter_code"] = matter_code
        if client_code is not UNSET:
            field_dict["client_code"] = client_code
        if transcription_options is not UNSET:
            field_dict["transcription_options"] = transcription_options

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.create_upload_body_transcription_options_type_0 import (
            CreateUploadBodyTranscriptionOptionsType0,  # noqa: PLC0415
        )

        d = dict(src_dict)
        size_bytes = d.pop("size_bytes")

        duration_seconds = d.pop("duration_seconds")

        def _parse_title(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        title = _parse_title(d.pop("title", UNSET))

        def _parse_mode(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        mode = _parse_mode(d.pop("mode", UNSET))

        def _parse_part_size_bytes(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        part_size_bytes = _parse_part_size_bytes(d.pop("part_size_bytes", UNSET))

        def _parse_idempotency_key(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        idempotency_key = _parse_idempotency_key(d.pop("idempotency_key", UNSET))

        def _parse_matter_code(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        matter_code = _parse_matter_code(d.pop("matter_code", UNSET))

        def _parse_client_code(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        client_code = _parse_client_code(d.pop("client_code", UNSET))

        def _parse_transcription_options(
            data: object,
        ) -> CreateUploadBodyTranscriptionOptionsType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                transcription_options_type_0 = (
                    CreateUploadBodyTranscriptionOptionsType0.from_dict(data)
                )

                return transcription_options_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(CreateUploadBodyTranscriptionOptionsType0 | None | Unset, data)

        transcription_options = _parse_transcription_options(
            d.pop("transcription_options", UNSET)
        )

        create_upload_body = cls(
            size_bytes=size_bytes,
            duration_seconds=duration_seconds,
            title=title,
            mode=mode,
            part_size_bytes=part_size_bytes,
            idempotency_key=idempotency_key,
            matter_code=matter_code,
            client_code=client_code,
            transcription_options=transcription_options,
        )

        create_upload_body.additional_properties = d
        return create_upload_body

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
