"""Shapes on the wire for the chart of accounts.

**Read serializers only produce; they never write.** Every change goes through
`services.accounts` or `services.instantiation`, because that is where the rules
of Spec B section 2.4 live -- a system account is not renamed, a subaccount only
appears under an account that permits one, nothing is ever deleted. A
``ModelSerializer`` with ``update()`` would offer a second way in, past all three.

So the input serializers below validate *shape* and stop. Whether the operation is
allowed is not their question, and answering it here would mean answering it
twice.
"""

from __future__ import annotations

from rest_framework import serializers

from evidenta.accounting.coa.models import CoaTemplate, CompanyAccount, CompanyChart


class TemplateSerializer(serializers.ModelSerializer[CoaTemplate]):
    """A published chart version, with the act it transcribes.

    ``source_act`` and ``source_reference`` are on the wire deliberately: a
    client choosing a version is choosing a normative act, and a picker that
    showed only ``code/version`` would be asking someone to choose between two
    opaque strings.
    """

    class Meta:
        model = CoaTemplate
        fields = (
            "id",
            "code",
            "version",
            "valid_from",
            "valid_to",
            "source_act",
            "source_reference",
            "published_at",
            "status",
        )
        read_only_fields = fields


class ChartSerializer(serializers.ModelSerializer[CompanyChart]):
    class Meta:
        model = CompanyChart
        fields = ("id", "company_id", "template_id", "instantiated_at", "last_propagation_at")
        read_only_fields = fields


class AccountSerializer(serializers.ModelSerializer[CompanyAccount]):
    """One account as a screen needs it.

    ``parent`` is the identifier, not a nested object: the chart is a tree of a
    few hundred rows and a client builds it once from a flat list. Nesting would
    make the payload depth-dependent and the flat list is what a grid wants
    anyway.
    """

    parent_id = serializers.UUIDField(read_only=True, allow_null=True)
    template_account_id = serializers.UUIDField(read_only=True, allow_null=True)
    #: The declared slots in position order, holes excluded -- one list rather
    #: than four nullable fields, because the client reads a declaration, not a
    #: row (ADR-048).
    dimension_slots = serializers.SerializerMethodField()

    def get_dimension_slots(self, account: CompanyAccount) -> list[str]:
        return list(account.declared_slots())

    class Meta:
        model = CompanyAccount
        fields = (
            "id",
            "account_code",
            "name_ro",
            "parent_id",
            "origin",
            "template_account_id",
            "account_class",
            "normal_balance",
            "allows_subaccounts",
            "currency_tracking",
            "quantity_tracking",
            "required_dimensions",
            "dimension_slots",
            "is_blocked",
            "valid_from",
            "valid_to",
        )
        read_only_fields = fields


class InstantiateChartSerializer(serializers.Serializer[dict[str, object]]):
    template_id = serializers.UUIDField()


class CreateSubaccountSerializer(serializers.Serializer[dict[str, object]]):
    """Input for a company's own subaccount.

    ``account_class`` and ``normal_balance`` are absent on purpose -- they are
    inherited from the parent by the service, so there is no field in which to
    get them wrong.
    """

    parent_id = serializers.UUIDField()
    account_code = serializers.CharField(max_length=64)
    name_ro = serializers.CharField(max_length=255)
    valid_from = serializers.DateField()
    currency_tracking = serializers.BooleanField(default=False)
    quantity_tracking = serializers.BooleanField(default=False)
    required_dimensions = serializers.ListField(
        child=serializers.CharField(max_length=64), default=list
    )
    dimension_slots = serializers.ListField(
        child=serializers.CharField(max_length=64), default=list
    )
    allows_subaccounts = serializers.BooleanField(default=False)


class UpdateAccountSerializer(serializers.Serializer[dict[str, object]]):
    """The three changes a company may make, each optional.

    Deliberately not one ``PUT`` of the whole row. Renaming, blocking and closing
    are different operations with different rules and different audit entries;
    collapsing them into a full replacement would make "what changed" a diff the
    server has to reconstruct, and the audit trail is exactly what must not be
    reconstructed.
    """

    name_ro = serializers.CharField(max_length=255, required=False)
    is_blocked = serializers.BooleanField(required=False)
    valid_to = serializers.DateField(required=False)
    #: The fourth change (ADR-048): what the account carries and demands. The
    #: whole declaration each time, never a delta -- see the service.
    dimension_slots = serializers.ListField(
        child=serializers.CharField(max_length=64), required=False
    )
    required_dimensions = serializers.ListField(
        child=serializers.CharField(max_length=64), required=False
    )

    def validate(self, attrs: dict[str, object]) -> dict[str, object]:
        if not attrs:
            raise serializers.ValidationError("no change requested")
        if "required_dimensions" in attrs and "dimension_slots" not in attrs:
            raise serializers.ValidationError(
                "required_dimensions is declared together with dimension_slots; a "
                "requirement is a subset of what the account carries"
            )
        return attrs
