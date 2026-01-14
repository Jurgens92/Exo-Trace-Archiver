# Generated migration for adding domains_last_updated field

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0002_tenant_domains'),
    ]

    operations = [
        migrations.AddField(
            model_name='tenant',
            name='domains_last_updated',
            field=models.DateTimeField(blank=True, help_text='When domains were last discovered from Microsoft 365', null=True),
        ),
    ]
