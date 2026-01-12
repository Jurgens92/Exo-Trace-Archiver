"""
WSGI config for exo_trace_archiver project.
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'exo_trace_archiver.settings')

application = get_wsgi_application()
