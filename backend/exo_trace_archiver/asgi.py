"""
ASGI config for exo_trace_archiver project.
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'exo_trace_archiver.settings')

application = get_asgi_application()
