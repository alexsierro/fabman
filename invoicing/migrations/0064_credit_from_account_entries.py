from django.db import migrations
from django.utils import timezone

# keep in sync with invoicing.credits.MIGRATED_CREDIT_COMMENT, it dates the switch to the credits
MIGRATION_COMMENT = 'Balance migrated from account entries'
# keep in sync with invoicing.credits.TRANSFER_CLOSING_COMMENT
CLOSING_COMMENT = 'Balance transferred to credit'


def create_credits_from_account_entries(apps, schema_editor):
    from invoicing.credits import allocate, transfer_account_entries

    AccountEntry = apps.get_model('invoicing', 'AccountEntry')
    Credit = apps.get_model('invoicing', 'Credit')
    Usage = apps.get_model('invoicing', 'Usage')
    CreditConsumption = apps.get_model('invoicing', 'CreditConsumption')
    now = timezone.now()

    # the historical models send no signal: transfer every member, then allocate the usages not yet invoiced
    for member_id in AccountEntry.objects.values_list('member_id', flat=True).distinct():
        transfer_account_entries(member_id, MIGRATION_COMMENT, account_entry_model=AccountEntry,
                                 credit_model=Credit, at=now)

    member_ids = Usage.objects.filter(invoice=None).exclude(member=None).values_list('member_id', flat=True).distinct()
    for member_id in member_ids:
        allocate(member_id, usage_model=Usage, credit_model=Credit, consumption_model=CreditConsumption)


def delete_migrated_credits(apps, schema_editor):
    Credit = apps.get_model('invoicing', 'Credit')
    AccountEntry = apps.get_model('invoicing', 'AccountEntry')
    migrated = Credit.objects.filter(comment=MIGRATION_COMMENT)
    if migrated.filter(consumptions__usage__invoice__isnull=False).exists():
        raise RuntimeError('Migrated credits are already deducted on invoices, they cannot be removed')
    AccountEntry.objects.filter(comment__in=[f'{CLOSING_COMMENT} #{pk}' for pk in migrated.values_list('pk', flat=True)]) \
        .delete()
    migrated.delete()


class Migration(migrations.Migration):

    dependencies = [
        ('invoicing', '0063_creditconsumption'),
    ]

    operations = [
        migrations.RunPython(create_credits_from_account_entries, delete_migrated_credits),
    ]
