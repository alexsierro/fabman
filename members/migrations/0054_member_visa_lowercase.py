import django.db.models.functions.text
from django.db import migrations, models


def lowercase_visas(apps, schema_editor):
    Member = apps.get_model('members', 'Member')
    members = list(Member.objects.exclude(visa__isnull=True))

    seen = {}
    for member in members:
        visa = member.visa.strip().lower() or None
        if visa and visa in seen:
            raise RuntimeError(f"Visa '{visa}' used by members {seen[visa]} and {member.pk}: rename one before migrating.")
        seen[visa] = member.pk
        member.visa = visa

    Member.objects.bulk_update(members, ['visa'])


class Migration(migrations.Migration):

    dependencies = [
        ('members', '0053_member_comment'),
    ]

    operations = [
        migrations.RunPython(lowercase_visas, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name='member',
            constraint=models.CheckConstraint(
                condition=models.Q(visa=django.db.models.functions.text.Lower('visa')),
                name='member_visa_lowercase',
                violation_error_message='Le visa doit être en minuscules.',
            ),
        ),
    ]
