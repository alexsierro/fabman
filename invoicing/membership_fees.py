"""Yearly membership fees: create the fee usages, invoice them and send the invoices."""

from dataclasses import dataclass, field
from decimal import Decimal

from django.db import transaction
from django.db.models import Q, Sum

from invoicing.models import Usage, Resource, AccountEntry, Invoice
from invoicing.views import prepare_invoice
from members.models import Member

FEE_SLUG_PREFIX = 'cotisation-'

FEE_SLUG_BY_MEMBER_TYPE = {
    'membre': 'cotisation-membre',
    'alias': 'cotisation-membre',
    'etudiant': 'cotisation-reduit',
    'avs': 'cotisation-reduit',
    'ai': 'cotisation-reduit',
    'passif': 'cotisation-passif',
    'angel': 'cotisation-angel',
}

SWISS_ENGINEERING_SLUG = 'contribution-swissengineering'
# Swiss Engineering pays half of the fee, but not for angel and company fees
SWISS_ENGINEERING_ELIGIBLE_SLUGS = ['cotisation-membre', 'cotisation-reduit', 'cotisation-passif']
SWISS_ENGINEERING_SHARE = Decimal('0.5')

LAST_INVOICES_COUNT = 5

STAFF_MACHINE_CREDIT = 1000
STAFF_MACHINE_CREDIT_TEMPORARY = 9000


def fee_resources():
    return Resource.objects.filter(slug__startswith=FEE_SLUG_PREFIX).order_by('name')


def _for_year(usages, year):
    # A fee for next year can be entered at the end of the year (then tagged with its year),
    # untagged fees belong to the year of their date
    return usages.filter(Q(year=year) | Q(year=None, date__year=year))


def fee_usages(year):
    return _for_year(Usage.objects.filter(resource__slug__startswith=FEE_SLUG_PREFIX), year)


def swiss_engineering_usages(year):
    return _for_year(Usage.objects.filter(resource__slug=SWISS_ENGINEERING_SLUG), year)


def _covering_year(usages, year):
    # a fee entered during the year for a next year (e.g. late subscription) also covers this year
    return _for_year(usages, year) | usages.filter(date__year=year, year__gt=year)


def fee_usages_covering(year):
    return _covering_year(Usage.objects.filter(resource__slug__startswith=FEE_SLUG_PREFIX), year)


def has_swiss_engineering(member):
    return bool((member.swiss_engineering_number or '').strip())


def tag_untagged_fees(year):
    return Usage.objects.filter(year=None, date__year=year, resource__slug__startswith=FEE_SLUG_PREFIX) \
        .update(year=year)


@dataclass
class FeeRow:
    member: Member
    existing: list = field(default_factory=list)
    proposed_resource: Resource = None
    last_invoices: list = field(default_factory=list)
    uninvoiced_total: Decimal = Decimal(0)

    @property
    def swiss_engineering(self):
        return has_swiss_engineering(self.member)

    @property
    def swiss_engineering_applies(self):
        return self.swiss_engineering and self.proposed_resource is not None \
            and self.proposed_resource.slug in SWISS_ENGINEERING_ELIGIBLE_SLUGS


def build_fee_rows(year):
    resources_by_slug = {resource.slug: resource for resource in fee_resources()}

    existing_by_member = {}
    swiss_engineering = _covering_year(Usage.objects.filter(resource__slug=SWISS_ENGINEERING_SLUG), year)
    for usage in (fee_usages_covering(year) | swiss_engineering).select_related('resource', 'invoice'):
        existing_by_member.setdefault(usage.member_id, []).append(usage)

    members = Member.objects.filter(date_resigned__isnull=True).order_by('name', 'surname')

    last_invoices_by_member = {}
    for invoice in Invoice.objects.filter(member__in=members).order_by('-date_invoice'):
        invoices = last_invoices_by_member.setdefault(invoice.member_id, [])
        if len(invoices) < LAST_INVOICES_COUNT:
            invoices.append(invoice)

    # as in "To invoice", machine usages of the staff are paid by their machine credit
    uninvoiced_totals = dict(
        Usage.objects.filter(member__in=members, invoice=None)
        .exclude(member__is_staff=True, resource__payable_by_animation_hours=True)
        .values_list('member_id').annotate(total=Sum('total_price')))

    rows = []
    for member in members:
        rows.append(FeeRow(member=member,
                           existing=existing_by_member.get(member.id, []),
                           proposed_resource=resources_by_slug.get(FEE_SLUG_BY_MEMBER_TYPE.get(member.member_type)),
                           # oldest first, so the most recent is on the right
                           last_invoices=last_invoices_by_member.get(member.id, [])[::-1],
                           uninvoiced_total=uninvoiced_totals.get(member.id) or Decimal(0)))
    return rows


@transaction.atomic
def create_fees(year, resource_by_member_id):
    """Create the fee usages for the given members, members having already a fee for the year are skipped.

    Returns the created usages.
    """
    tag_untagged_fees(year)

    already_billed = set(fee_usages_covering(year).values_list('member_id', flat=True))
    already_contributed = set(swiss_engineering_usages(year).values_list('member_id', flat=True))
    swiss_engineering = None

    created = []
    for member in Member.objects.filter(pk__in=resource_by_member_id.keys()).order_by('name', 'surname'):
        if member.id in already_billed:
            continue

        resource = resource_by_member_id[member.id]
        fee = Usage.objects.create(member=member, resource=resource, qty=1, year=year)
        created.append(fee)

        if has_swiss_engineering(member) and resource.slug in SWISS_ENGINEERING_ELIGIBLE_SLUGS \
                and member.id not in already_contributed:
            if swiss_engineering is None:
                swiss_engineering = Resource.objects.get(slug=SWISS_ENGINEERING_SLUG)

            contribution = Usage.objects.create(member=member, resource=swiss_engineering, qty=1, year=year)
            # the price depends on the fee, override the one set from the resource at creation
            contribution.unit_price = -fee.unit_price * SWISS_ENGINEERING_SHARE
            contribution.save()
            created.append(contribution)

    return created


def members_to_invoice(year):
    member_ids = fee_usages(year).filter(invoice=None).values('member_id')
    return Member.objects.filter(pk__in=member_ids).order_by('name', 'surname')


@transaction.atomic
def create_yearly_invoice(member):
    """Invoice all non invoiced usages of a member, the machine credit of the staff is reset."""
    adjustment = None
    if member.is_staff:
        balance = AccountEntry.objects.filter(member=member).aggregate(machine=Sum('amount_machine'))['machine'] or 0

        # temporary credit so all machine usages are deducted, then adjusted to leave the yearly credit
        if balance < STAFF_MACHINE_CREDIT_TEMPORARY:
            adjustment = AccountEntry.objects.create(member=member,
                                                     amount_machine=STAFF_MACHINE_CREDIT_TEMPORARY - balance,
                                                     invoice=None, comment='Ajustement credit machine animateur')

    invoice = prepare_invoice(member.id, create=True)['invoice']

    if adjustment:
        adjustment.amount_machine = STAFF_MACHINE_CREDIT - balance + invoice.amount_deduction_machine
        adjustment.save()

    return invoice


def fee_invoices(year):
    return Invoice.objects.filter(usage__in=fee_usages(year)).distinct().select_related('member') \
        .order_by('member__name', 'member__surname')


def unsent_fee_invoices(year):
    return fee_invoices(year).filter(was_sent_by_email=False, was_sent_by_post=False)
