from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="OrgSummaryResponse")


@_attrs_define
class OrgSummaryResponse:
    """
    Attributes:
        id (str):
        name (str):
        role (str): The caller's own role in this organization: admin or member.
        plan (str):
        plan_term (None | str): annual or monthly, or null if the org has never had a plan.
        plan_active_until (int | None): Unix seconds the current term runs until, or null before the org's first plan is
            paid.
        plan_active (bool): Whether the term itself is still running (ignores grace).
        plan_state (str): pending, active, grace, or frozen.
        grace_until (int | None):
        seats_limit (int | None):
        seats_used (int):
        seats_pending (int): Seats held by pending, unexpired invites.
        balance_seconds (int): The pool's raw balance. Can be negative after a void clawback or a negative pool
            adjustment.
        spendable_seconds (int): balance_seconds floored at zero, and zeroed outright when the org is outside its
            funding window (frozen or lapsed past grace).
        pool_expires_at (int | None): Unix seconds the pool's own rolling 365-day expiry falls at, re-anchored on every
            credit and every settle. Null if the pool has never held a positive balance.
        default_retention_days (int | None):
        max_retention_days (int | None):
        billing_email (None | str): The workspace's billing contact. Null unless the caller is an admin or holds the
            billing right.
        billing_details (None | str): Free-text billing details shown on invoices. Null when none are set, and always
            null unless the caller is an admin or holds the billing right.
        tax_id (None | str): The buyer's self-declared tax id, shown on invoices. Not validated against any registry.
            Null unless the caller is an admin or holds the billing right.
        tax_id_label (None | str): The buyer's own word for tax_id, e.g. VAT, EIN, ABN. Null unless the caller is an
            admin or holds the billing right.
        created_at (int):
        auto_renew (bool):
        renewal_failures (int):
        renewal_capped (bool): Whether renewal_failures has reached the cap the daily renewal lane stops retrying at.
        renewal_source_stored (bool): Whether a saved card is on file for the renewal lane to charge. Never the payment
            method id itself.
        renewal_user_id (None | str): The id of the member whose saved card the renewal lane charges. Visible to admins
            only; a non-admin member always sees null here regardless of whether a source is stored (see
            renewal_source_stored).
        member_cap_seconds (int | None): The workspace-wide default per-member monthly spending cap against the pool.
            Null means no org-wide default.
        caller_effective_cap_seconds (int | None): The signed-in caller's own effective monthly cap: their personal
            override if one is set, else member_cap_seconds, else null for no cap. Also null when the caller is outside the
            org's current funding window.
        caller_spent_seconds_this_month (int | None): The signed-in caller's own month-to-date spend against the pool.
            Null under the same condition caller_effective_cap_seconds is null.
        is_owner (bool): Whether the signed-in caller is the workspace's single transferable owner (distinct from
            is_admin).
        owner_user_id (str): The id of the workspace's transferable owner, visible to every member. Falls back to the
            org's creator if owner_user_id was never explicitly set on the row.
        custody (str): private or firm. private: transcripts belong to the member, no reviewer can open them. firm: a
            transcript created while a member belongs to the workspace is workspace property; is_reviewer members can open
            it.
        custody_switch_at (int | None): Unix seconds the pending private-to-firm switch takes effect, or null when no
            switch is scheduled. Only ever set while custody is still private.
        retention_reclamp_at (int | None): Unix seconds the currently armed retention re-clamp takes effect, or null
            when none is scheduled. Set only while a tightened max_retention_days still has existing transcripts left to
            pull in.
        retention_reclamp_days (int | None): The retention day count the armed re-clamp will apply, or null when none is
            scheduled. Mirrors max_retention_days at the moment the re-clamp was armed, not necessarily the current value.
    """

    id: str
    name: str
    role: str
    plan: str
    plan_term: None | str
    plan_active_until: int | None
    plan_active: bool
    plan_state: str
    grace_until: int | None
    seats_limit: int | None
    seats_used: int
    seats_pending: int
    balance_seconds: int
    spendable_seconds: int
    pool_expires_at: int | None
    default_retention_days: int | None
    max_retention_days: int | None
    billing_email: None | str
    billing_details: None | str
    tax_id: None | str
    tax_id_label: None | str
    created_at: int
    auto_renew: bool
    renewal_failures: int
    renewal_capped: bool
    renewal_source_stored: bool
    renewal_user_id: None | str
    member_cap_seconds: int | None
    caller_effective_cap_seconds: int | None
    caller_spent_seconds_this_month: int | None
    is_owner: bool
    owner_user_id: str
    custody: str
    custody_switch_at: int | None
    retention_reclamp_at: int | None
    retention_reclamp_days: int | None
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        name = self.name

        role = self.role

        plan = self.plan

        plan_term: None | str
        plan_term = self.plan_term

        plan_active_until: int | None
        plan_active_until = self.plan_active_until

        plan_active = self.plan_active

        plan_state = self.plan_state

        grace_until: int | None
        grace_until = self.grace_until

        seats_limit: int | None
        seats_limit = self.seats_limit

        seats_used = self.seats_used

        seats_pending = self.seats_pending

        balance_seconds = self.balance_seconds

        spendable_seconds = self.spendable_seconds

        pool_expires_at: int | None
        pool_expires_at = self.pool_expires_at

        default_retention_days: int | None
        default_retention_days = self.default_retention_days

        max_retention_days: int | None
        max_retention_days = self.max_retention_days

        billing_email: None | str
        billing_email = self.billing_email

        billing_details: None | str
        billing_details = self.billing_details

        tax_id: None | str
        tax_id = self.tax_id

        tax_id_label: None | str
        tax_id_label = self.tax_id_label

        created_at = self.created_at

        auto_renew = self.auto_renew

        renewal_failures = self.renewal_failures

        renewal_capped = self.renewal_capped

        renewal_source_stored = self.renewal_source_stored

        renewal_user_id: None | str
        renewal_user_id = self.renewal_user_id

        member_cap_seconds: int | None
        member_cap_seconds = self.member_cap_seconds

        caller_effective_cap_seconds: int | None
        caller_effective_cap_seconds = self.caller_effective_cap_seconds

        caller_spent_seconds_this_month: int | None
        caller_spent_seconds_this_month = self.caller_spent_seconds_this_month

        is_owner = self.is_owner

        owner_user_id = self.owner_user_id

        custody = self.custody

        custody_switch_at: int | None
        custody_switch_at = self.custody_switch_at

        retention_reclamp_at: int | None
        retention_reclamp_at = self.retention_reclamp_at

        retention_reclamp_days: int | None
        retention_reclamp_days = self.retention_reclamp_days

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "id": id,
                "name": name,
                "role": role,
                "plan": plan,
                "plan_term": plan_term,
                "plan_active_until": plan_active_until,
                "plan_active": plan_active,
                "plan_state": plan_state,
                "grace_until": grace_until,
                "seats_limit": seats_limit,
                "seats_used": seats_used,
                "seats_pending": seats_pending,
                "balance_seconds": balance_seconds,
                "spendable_seconds": spendable_seconds,
                "pool_expires_at": pool_expires_at,
                "default_retention_days": default_retention_days,
                "max_retention_days": max_retention_days,
                "billing_email": billing_email,
                "billing_details": billing_details,
                "tax_id": tax_id,
                "tax_id_label": tax_id_label,
                "created_at": created_at,
                "auto_renew": auto_renew,
                "renewal_failures": renewal_failures,
                "renewal_capped": renewal_capped,
                "renewal_source_stored": renewal_source_stored,
                "renewal_user_id": renewal_user_id,
                "member_cap_seconds": member_cap_seconds,
                "caller_effective_cap_seconds": caller_effective_cap_seconds,
                "caller_spent_seconds_this_month": caller_spent_seconds_this_month,
                "is_owner": is_owner,
                "owner_user_id": owner_user_id,
                "custody": custody,
                "custody_switch_at": custody_switch_at,
                "retention_reclamp_at": retention_reclamp_at,
                "retention_reclamp_days": retention_reclamp_days,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        id = d.pop("id")

        name = d.pop("name")

        role = d.pop("role")

        plan = d.pop("plan")

        def _parse_plan_term(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        plan_term = _parse_plan_term(d.pop("plan_term"))

        def _parse_plan_active_until(data: object) -> int | None:
            if data is None:
                return data
            return cast(int | None, data)

        plan_active_until = _parse_plan_active_until(d.pop("plan_active_until"))

        plan_active = d.pop("plan_active")

        plan_state = d.pop("plan_state")

        def _parse_grace_until(data: object) -> int | None:
            if data is None:
                return data
            return cast(int | None, data)

        grace_until = _parse_grace_until(d.pop("grace_until"))

        def _parse_seats_limit(data: object) -> int | None:
            if data is None:
                return data
            return cast(int | None, data)

        seats_limit = _parse_seats_limit(d.pop("seats_limit"))

        seats_used = d.pop("seats_used")

        seats_pending = d.pop("seats_pending")

        balance_seconds = d.pop("balance_seconds")

        spendable_seconds = d.pop("spendable_seconds")

        def _parse_pool_expires_at(data: object) -> int | None:
            if data is None:
                return data
            return cast(int | None, data)

        pool_expires_at = _parse_pool_expires_at(d.pop("pool_expires_at"))

        def _parse_default_retention_days(data: object) -> int | None:
            if data is None:
                return data
            return cast(int | None, data)

        default_retention_days = _parse_default_retention_days(
            d.pop("default_retention_days")
        )

        def _parse_max_retention_days(data: object) -> int | None:
            if data is None:
                return data
            return cast(int | None, data)

        max_retention_days = _parse_max_retention_days(d.pop("max_retention_days"))

        def _parse_billing_email(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        billing_email = _parse_billing_email(d.pop("billing_email"))

        def _parse_billing_details(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        billing_details = _parse_billing_details(d.pop("billing_details"))

        def _parse_tax_id(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        tax_id = _parse_tax_id(d.pop("tax_id"))

        def _parse_tax_id_label(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        tax_id_label = _parse_tax_id_label(d.pop("tax_id_label"))

        created_at = d.pop("created_at")

        auto_renew = d.pop("auto_renew")

        renewal_failures = d.pop("renewal_failures")

        renewal_capped = d.pop("renewal_capped")

        renewal_source_stored = d.pop("renewal_source_stored")

        def _parse_renewal_user_id(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        renewal_user_id = _parse_renewal_user_id(d.pop("renewal_user_id"))

        def _parse_member_cap_seconds(data: object) -> int | None:
            if data is None:
                return data
            return cast(int | None, data)

        member_cap_seconds = _parse_member_cap_seconds(d.pop("member_cap_seconds"))

        def _parse_caller_effective_cap_seconds(data: object) -> int | None:
            if data is None:
                return data
            return cast(int | None, data)

        caller_effective_cap_seconds = _parse_caller_effective_cap_seconds(
            d.pop("caller_effective_cap_seconds")
        )

        def _parse_caller_spent_seconds_this_month(data: object) -> int | None:
            if data is None:
                return data
            return cast(int | None, data)

        caller_spent_seconds_this_month = _parse_caller_spent_seconds_this_month(
            d.pop("caller_spent_seconds_this_month")
        )

        is_owner = d.pop("is_owner")

        owner_user_id = d.pop("owner_user_id")

        custody = d.pop("custody")

        def _parse_custody_switch_at(data: object) -> int | None:
            if data is None:
                return data
            return cast(int | None, data)

        custody_switch_at = _parse_custody_switch_at(d.pop("custody_switch_at"))

        def _parse_retention_reclamp_at(data: object) -> int | None:
            if data is None:
                return data
            return cast(int | None, data)

        retention_reclamp_at = _parse_retention_reclamp_at(
            d.pop("retention_reclamp_at")
        )

        def _parse_retention_reclamp_days(data: object) -> int | None:
            if data is None:
                return data
            return cast(int | None, data)

        retention_reclamp_days = _parse_retention_reclamp_days(
            d.pop("retention_reclamp_days")
        )

        org_summary_response = cls(
            id=id,
            name=name,
            role=role,
            plan=plan,
            plan_term=plan_term,
            plan_active_until=plan_active_until,
            plan_active=plan_active,
            plan_state=plan_state,
            grace_until=grace_until,
            seats_limit=seats_limit,
            seats_used=seats_used,
            seats_pending=seats_pending,
            balance_seconds=balance_seconds,
            spendable_seconds=spendable_seconds,
            pool_expires_at=pool_expires_at,
            default_retention_days=default_retention_days,
            max_retention_days=max_retention_days,
            billing_email=billing_email,
            billing_details=billing_details,
            tax_id=tax_id,
            tax_id_label=tax_id_label,
            created_at=created_at,
            auto_renew=auto_renew,
            renewal_failures=renewal_failures,
            renewal_capped=renewal_capped,
            renewal_source_stored=renewal_source_stored,
            renewal_user_id=renewal_user_id,
            member_cap_seconds=member_cap_seconds,
            caller_effective_cap_seconds=caller_effective_cap_seconds,
            caller_spent_seconds_this_month=caller_spent_seconds_this_month,
            is_owner=is_owner,
            owner_user_id=owner_user_id,
            custody=custody,
            custody_switch_at=custody_switch_at,
            retention_reclamp_at=retention_reclamp_at,
            retention_reclamp_days=retention_reclamp_days,
        )

        org_summary_response.additional_properties = d
        return org_summary_response

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
