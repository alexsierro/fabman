"""Allocation of the members credits to their usages.

The consumptions of the not yet invoiced usages of a member are always rebuilt from scratch, the consumptions of
invoiced usages are final. The allocation is triggered on every change of a usage, a credit or an invoice, see the
receivers at the end of this module.
"""

import datetime
from collections import defaultdict
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum, Q, Min
from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.utils import timezone

from invoicing.models import Usage, Credit, CreditConsumption, Invoice, AccountEntry

ZERO = Decimal('0.00')


def _cents(value):
    # SQLite sums decimals as floats, round to drop residues like 3.5e-15
    return Decimal(value or 0).quantize(ZERO)


def _credit_priority(credit):
    """Use first the credits that expire first, then the oldest ones."""
    return (credit.valid_to is None, credit.valid_to or timezone.now(),
            credit.valid_from is not None, credit.valid_from or timezone.now(), credit.id)


def _is_valid_at(credit, date):
    return (credit.valid_from is None or credit.valid_from <= date) and \
        (credit.valid_to is None or date <= credit.valid_to)


def allocate(member_id, usage_model=Usage, credit_model=Credit, consumption_model=CreditConsumption, until=None):
    """Rebuild the credit consumptions of the not yet invoiced usages of a member.

    Machine credits only pay resources payable by animation hours, cash credits pay the rest of any usage.
    With `until`, only the open usages before it get credit, as if they were the only ones: used to invoice them
    alone, the next allocation gives credit to the newer ones again.
    The models can be given to run the allocation from a data migration with the historical models.
    """
    with transaction.atomic():
        open_usages = usage_model.objects.filter(member_id=member_id, invoice=None)
        if until is not None:
            open_usages = open_usages.filter(date__lt=until)
        usages = list(open_usages.select_related('resource').order_by('date', 'id'))
        consumption_model.objects.filter(usage__member_id=member_id, usage__invoice=None).delete()

        credits = list(credit_model.objects.filter(member_id=member_id)
                       .annotate(consumed=Sum('consumptions__amount')))
        remaining = {credit.id: credit.amount - _cents(credit.consumed) for credit in credits}
        by_type = {credit_type: sorted((c for c in credits if c.credit_type == credit_type), key=_credit_priority)
                   for credit_type in ('machine', 'cash')}

        consumptions = []  # [credit, usage, amount], in allocation order
        for usage in usages:
            need = usage.total_price
            types = ['machine', 'cash'] if usage.resource and usage.resource.payable_by_animation_hours else ['cash']
            for credit_type in types:
                for credit in by_type[credit_type]:
                    if need <= 0:
                        break
                    if remaining[credit.id] <= 0 or not _is_valid_at(credit, usage.date):
                        continue
                    amount = min(need, remaining[credit.id])
                    remaining[credit.id] -= amount
                    need -= amount
                    consumptions.append([credit, usage, amount])

        # Negative usages (e.g. a contribution to the fee) are not paid by credits but reduce the total: never
        # deduct more than the total of the usages, release the cash credits first then the machine credits.
        # The total comes from the database like the invoice amount: rounding each usage can differ by a few cents.
        total = _cents(open_usages.aggregate(total=Sum('total_price'))['total'])
        excess = sum(amount for _, _, amount in consumptions) - max(total, ZERO)
        for credit_type in ('cash', 'machine'):
            for consumption in reversed(consumptions):
                if excess <= 0:
                    break
                if consumption[0].credit_type == credit_type:
                    released = min(excess, consumption[2])
                    consumption[2] -= released
                    excess -= released

        consumption_model.objects.bulk_create(
            consumption_model(credit=credit, usage=usage, amount=amount)
            for credit, usage, amount in consumptions if amount > 0)


def allocate_credits(member_id):
    if member_id is not None:
        allocate(member_id)


def _not_expired_at(at):
    return Q(valid_to__isnull=True) | Q(valid_to__gt=at)


def _remaining_credits(member, at, invoice=None):
    """The not expired credits of a member at a date, each with its `remaining` amount.

    Without invoice: what remains now, every consumption counted (also the ones of not yet invoiced usages).
    With an invoice: what remained once it was created, only the credits existing then and the consumptions of the
    invoices up to it.
    """
    credits = Credit.objects.filter(_not_expired_at(at), member=member)
    if invoice is None:
        credits = credits.annotate(consumed=Sum('consumptions__amount'))
    else:
        credits = credits.filter(created_at__lte=at).annotate(
            consumed=Sum('consumptions__amount', filter=Q(consumptions__usage__invoice__date_invoice__lte=at)))
    credits = list(credits)
    for credit in credits:
        credit.remaining = credit.amount - _cents(credit.consumed)
    return credits


def _by_type(credits):
    balance = defaultdict(lambda: ZERO)
    for credit in credits:
        balance[credit.credit_type] += credit.remaining
    return {'machine': balance['machine'], 'cash': balance['cash']}


# an invoice lists the next end dates, the later ones are summed on one line
VALIDITY_MAX_DATES = 3


def _date(day):
    return day.strftime('%d.%m.%Y')


def _validity(credits, at):
    """How long the remaining credit stays valid, by credit type, as lines adding up to the balance.

    At most VALIDITY_MAX_DATES + 3 lines per type, whatever the number of credits:
    - the credits valid now with an end date, one line per end date for the VALIDITY_MAX_DATES next ones, the
      later ones summed on a "valable au-delà" line,
    - the credits not yet valid on one line, with their dates when they all have the same,
    - the credits without limit.
    Each line is {'label', 'amount'}, the label to follow "dont". A type is None when all its remaining credit is
    valid without limit: the balance alone says it.
    """
    if timezone.is_naive(at):
        at = timezone.make_aware(at)
    validity = {}
    for credit_type in ('machine', 'cash'):
        by_end = defaultdict(lambda: ZERO)
        upcoming = defaultdict(lambda: ZERO)
        unlimited = ZERO
        for credit in credits:
            if credit.credit_type != credit_type or credit.remaining <= 0:
                continue
            # by local day: credits are valid by whole days
            end = timezone.localdate(credit.valid_to) if credit.valid_to is not None else None
            if credit.valid_from is not None and credit.valid_from > at:
                upcoming[timezone.localdate(credit.valid_from), end] += credit.remaining
            elif end is not None:
                by_end[end] += credit.remaining
            else:
                unlimited += credit.remaining
        if not by_end and not upcoming:
            validity[credit_type] = None
            continue

        ends = sorted(by_end)
        shown_ends = ends[:VALIDITY_MAX_DATES]
        lines = [{'label': f"valable jusqu'au {_date(end)}", 'amount': by_end[end]} for end in shown_ends]
        later = sum((by_end[end] for end in ends[VALIDITY_MAX_DATES:]), ZERO)
        if later:
            # every one of them ends after the last date shown
            lines.append({'label': f'valable au-delà du {_date(shown_ends[-1])}', 'amount': later})
        if upcoming:
            if len(upcoming) == 1:
                (start, end), = upcoming
                label = f'valable du {_date(start)} au {_date(end)}' if end else f'valable dès le {_date(start)}'
            else:
                label = 'pas encore valable'
            lines.append({'label': label, 'amount': sum(upcoming.values(), ZERO)})
        if unlimited:
            lines.append({'label': 'sans limite de validité', 'amount': unlimited})
        validity[credit_type] = lines
    return validity


def available_credit(member, at=None):
    """Remaining amount of the not expired credits of a member, by credit type."""
    return _by_type(_remaining_credits(member, at or timezone.now()))


def credit_validity(member, at=None):
    """How long the remaining credit of a member stays valid, by credit type, see _validity."""
    at = at or timezone.now()
    return _validity(_remaining_credits(member, at), at)


def balance_after_invoice(invoice):
    """Remaining balance of the member once the invoice was created, by credit type.

    The credits existing and not expired at the invoice date, minus what the invoices up to it deducted, plus the
    account entries up to it: they hold the balance of the invoices created before the credits.
    """
    at = invoice.date_invoice
    balance = _by_type(_remaining_credits(invoice.member, at, invoice=invoice))

    entries = AccountEntry.objects.filter(Q(date__lte=at) | Q(invoice=invoice), member=invoice.member) \
        .aggregate(machine=Sum('amount_machine'), cash=Sum('amount_cash'))
    return {'machine': balance['machine'] + _cents(entries['machine']),
            'cash': balance['cash'] + _cents(entries['cash'])}


def credit_validity_after_invoice(invoice):
    """How long the credit remaining once the invoice was created stays valid, by credit type, see _validity."""
    at = invoice.date_invoice
    return _validity(_remaining_credits(invoice.member, at, invoice=invoice), at)


def has_usages_left_out(invoice):
    """True when usages up to the invoice date are on no invoice up to it, e.g. left out by a time buffer.

    They may already hold credit, the balance once the invoice was created does not count them.
    """
    at = invoice.date_invoice
    return Usage.objects.filter(Q(invoice=None) | Q(invoice__date_invoice__gt=at),
                                member=invoice.member, date__lte=at).exists()


# keep in sync with the migration 0064_credit_from_account_entries
MIGRATED_CREDIT_COMMENT = 'Balance migrated from account entries'


def is_from_before_credits(invoice):
    """True for an invoice created with the account entries, before the migration to the credits."""
    switch = Credit.objects.filter(comment=MIGRATED_CREDIT_COMMENT).aggregate(at=Min('created_at'))['at']
    return switch is not None and invoice.date_invoice is not None and invoice.date_invoice < switch


def _when(days):
    return 'today' if days == 0 else 'tomorrow' if days == 1 else f'in {days} days'


# the member page flags the credits valid now and expiring within EXPIRING_WITHIN, in red within SOON_DAYS
EXPIRING_WITHIN = datetime.timedelta(days=60)
SOON_DAYS = 7


def credit_summary(member, max_rows=10):
    """Recap of the credits of a member, for the member details page.

    The usable credits are listed up to max_rows, the first to be used first, each with its `remaining` amount and,
    when it is valid now and ends within EXPIRING_WITHIN, `expires` ('tomorrow', 'in 3 days'...) and
    `expires_soon` (within SOON_DAYS). The totals give, by credit type, the amount available now and what the open
    usages reserve.
    """
    now = timezone.now()
    today = timezone.localdate(now)
    open_usage = Q(consumptions__usage__invoice=None)
    credits = list(Credit.objects.filter(member=member).annotate(
        consumed=Sum('consumptions__amount'),
        pending=Sum('consumptions__amount', filter=open_usage)))

    totals = {credit_type: {'type': credit_type, 'label': label, 'available': ZERO, 'pending': ZERO}
              for credit_type, label in Credit.CREDIT_TYPE}
    usable = []
    expired_unused = ZERO
    other_count = 0
    for credit in credits:
        total = totals[credit.credit_type]
        credit.remaining = credit.amount - _cents(credit.consumed)
        credit.percent_left = int(max(min(credit.remaining / credit.amount, 1), 0) * 100) if credit.amount > 0 else 0
        total['pending'] += _cents(credit.pending)
        if credit.valid_to is not None and credit.valid_to <= now:
            expired_unused += max(credit.remaining, ZERO)
            other_count += 1
        elif credit.remaining <= 0:
            other_count += 1
        else:
            if credit.valid_from is None or credit.valid_from <= now:
                total['available'] += credit.remaining
                if credit.valid_to is not None and credit.valid_to <= now + EXPIRING_WITHIN:
                    # by local day: credits are valid by whole days
                    days = (timezone.localdate(credit.valid_to) - today).days
                    credit.expires = _when(days)
                    credit.expires_soon = days <= SOON_DAYS
            usable.append(credit)

    usable.sort(key=_credit_priority)
    return {
        # only the types with something to show: usable credit or credit reserved by the open usages
        'totals': [total for total in totals.values()
                   if total['pending'] or any(credit.credit_type == total['type'] for credit in usable)],
        'usable': usable[:max_rows],
        'usable_more': max(len(usable) - max_rows, 0),
        'expired_unused': expired_unused,
        'other_count': other_count,
        'count': len(credits),
    }


def credit_balances():
    """Credit of every member with something left, for the admin overview, largest balance first.

    Each row is {'member', 'machine', 'cash', 'pending', 'upcoming', 'next_expiry', 'next_expiry_amount'}:
    machine and cash are available now (what the open usages reserve, `pending`, is already taken out),
    upcoming is the credit not yet valid, next_expiry the first end date of a credit valid now with something left.
    """
    now = timezone.now()
    # every credit: an open usage keeps the credit valid at its date, even if it expired since
    credits = Credit.objects.select_related('member').annotate(
        consumed=Sum('consumptions__amount'),
        pending=Sum('consumptions__amount', filter=Q(consumptions__usage__invoice=None)))

    rows = {}
    for credit in credits:
        row = rows.setdefault(credit.member_id, {
            'member': credit.member, 'machine': ZERO, 'cash': ZERO, 'pending': ZERO, 'upcoming': ZERO,
            'next_expiry': None, 'next_expiry_amount': ZERO})
        remaining = credit.amount - _cents(credit.consumed)
        row['pending'] += _cents(credit.pending)
        if remaining <= 0 or (credit.valid_to is not None and credit.valid_to <= now):
            continue
        if credit.valid_from is not None and credit.valid_from > now:
            row['upcoming'] += remaining
            continue
        row[credit.credit_type] += remaining
        if credit.valid_to is not None:
            # by local day: credits are valid by whole days
            end = timezone.localdate(credit.valid_to)
            if row['next_expiry'] is None or end < row['next_expiry']:
                row['next_expiry'], row['next_expiry_amount'] = end, remaining
            elif end == row['next_expiry']:
                row['next_expiry_amount'] += remaining

    rows = [row for row in rows.values() if row['machine'] or row['cash'] or row['pending'] or row['upcoming']]
    rows.sort(key=lambda row: (-(row['machine'] + row['cash']), row['member'].name, row['member'].surname))
    return rows


TRANSFER_CLOSING_COMMENT = 'Balance transferred to credit'


def transfer_account_entries(member_id, comment, account_entry_model=AccountEntry, credit_model=Credit, at=None):
    """Move the positive account entries balance of a member to credits and close the account entries.

    A compensating account entry puts the balance back to zero, so an invoice showing both does not count it twice.
    Zero and negative balances stay in the account entries. The models can be given to run it from a data migration.
    """
    at = at or timezone.now()
    balance = account_entry_model.objects.filter(member_id=member_id)         .aggregate(machine=Sum('amount_machine'), cash=Sum('amount_cash'))
    credits = []
    for credit_type in ('machine', 'cash'):
        amount = _cents(balance[credit_type])
        if amount > 0:
            # no validity bounds: the balance covers any not yet invoiced usage, past or future
            credit = credit_model.objects.create(member_id=member_id, amount=amount, credit_type=credit_type,
                                                 created_at=at, comment=comment)
            account_entry_model.objects.create(member_id=member_id, date=at,
                                               comment=f'{TRANSFER_CLOSING_COMMENT} #{credit.pk}',
                                               amount_machine=-amount if credit_type == 'machine' else 0,
                                               amount_cash=-amount if credit_type == 'cash' else 0)
            credits.append(credit)
    return credits


def pending_deductions(member):
    """Credit consumed by the not yet invoiced usages of a member, by credit type."""
    rows = CreditConsumption.objects.filter(usage__member=member, usage__invoice=None) \
        .values('credit__credit_type').annotate(total=Sum('amount'))
    deductions = {row['credit__credit_type']: _cents(row['total']) for row in rows}
    return {'machine': deductions.get('machine', ZERO), 'cash': deductions.get('cash', ZERO)}


# --- Receivers: keep the allocation up to date


@receiver(pre_save, sender=Usage)
def remember_previous_member(sender, instance, **kwargs):
    # a usage moved to another member releases the credit of the previous one
    instance._previous_member_id = sender.objects.filter(pk=instance.pk).values_list('member_id', flat=True) \
        .first() if instance.pk else None


@receiver(post_save, sender=Usage)
def usage_saved(sender, instance, **kwargs):
    allocate_credits(instance.member_id)
    previous_member_id = getattr(instance, '_previous_member_id', None)
    if previous_member_id and previous_member_id != instance.member_id:
        allocate_credits(previous_member_id)


@receiver(post_delete, sender=Usage)
@receiver(post_save, sender=Credit)
@receiver(post_delete, sender=Credit)
def member_changed(sender, instance, **kwargs):
    allocate_credits(instance.member_id)


@receiver(post_delete, sender=Invoice)
def invoice_deleted(sender, instance, **kwargs):
    if instance.member_id is None:
        return
    # An invoice from before the credits deducted from the account entries: its deduction entry is deleted with it
    # and the amount it gives back becomes a credit again. Nothing to transfer for an invoice using the credits.
    transfer_account_entries(instance.member_id, f'Balance of deleted invoice {instance.invoice_number}')
    # the usages of the deleted invoice are not invoiced anymore
    allocate_credits(instance.member_id)
