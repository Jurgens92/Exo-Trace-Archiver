# Generated migration for adding AppSettings model

from django.conf import settings
import django.core.validators
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('accounts', '0003_add_domains_last_updated'),
    ]

    operations = [
        migrations.CreateModel(
            name='AppSettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('domain_discovery_auto_refresh', models.BooleanField(default=True, help_text='Automatically refresh domains before each trace pull')),
                ('domain_discovery_refresh_hours', models.IntegerField(default=24, help_text='How often to refresh domains (in hours). Default: 24 hours', validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(168)])),
                ('scheduled_pull_enabled', models.BooleanField(default=True, help_text='Enable automated scheduled trace pulls')),
                ('scheduled_pull_hour', models.IntegerField(default=1, help_text='Hour of day to run scheduled pulls (0-23, UTC)', validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(23)])),
                ('scheduled_pull_minute', models.IntegerField(default=0, help_text='Minute of hour to run scheduled pulls (0-59)', validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(59)])),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('updated_by', models.ForeignKey(blank=True, help_text='User who last updated these settings', null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Application Settings',
                'verbose_name_plural': 'Application Settings',
            },
        ),
    ]
