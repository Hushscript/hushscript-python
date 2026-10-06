from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.agent_signup_request_agent import AgentSignupRequestAgent


T = TypeVar("T", bound="AgentSignupRequest")


@_attrs_define
class AgentSignupRequest:
    """The client must never supply amount: it is derived server side from pack.

    Attributes:
        contact_email (str): Address for receipts and notices only. Never used to sign in; the created account has no
            login path of its own.
        pack_id (str): Which minute pack to buy. See GET /v1/billing/packs for the catalogue.
        accept_terms_version (str): Must equal the server's current policy version or the request is refused with
            policy_version_stale, which names the current value.
        agent (AgentSignupRequestAgent):
        data_region (str | Unset): Optional region hint. Honored only when it agrees with the region derived from your
            network location; otherwise the derived region is used silently.
        dry_run (bool | Unset): Validate the request and return a synthetic response with no Stripe session and no
            charge. Defaults to false.
    """

    contact_email: str
    pack_id: str
    accept_terms_version: str
    agent: AgentSignupRequestAgent
    data_region: str | Unset = UNSET
    dry_run: bool | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        contact_email = self.contact_email

        pack_id = self.pack_id

        accept_terms_version = self.accept_terms_version

        agent = self.agent.to_dict()

        data_region = self.data_region

        dry_run = self.dry_run

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "contact_email": contact_email,
                "pack_id": pack_id,
                "accept_terms_version": accept_terms_version,
                "agent": agent,
            }
        )
        if data_region is not UNSET:
            field_dict["data_region"] = data_region
        if dry_run is not UNSET:
            field_dict["dry_run"] = dry_run

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.agent_signup_request_agent import (
            AgentSignupRequestAgent,  # noqa: PLC0415
        )

        d = dict(src_dict)
        contact_email = d.pop("contact_email")

        pack_id = d.pop("pack_id")

        accept_terms_version = d.pop("accept_terms_version")

        agent = AgentSignupRequestAgent.from_dict(d.pop("agent"))

        data_region = d.pop("data_region", UNSET)

        dry_run = d.pop("dry_run", UNSET)

        agent_signup_request = cls(
            contact_email=contact_email,
            pack_id=pack_id,
            accept_terms_version=accept_terms_version,
            agent=agent,
            data_region=data_region,
            dry_run=dry_run,
        )

        agent_signup_request.additional_properties = d
        return agent_signup_request

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
