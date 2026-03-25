"""
View for serving the React frontend SPA.

When the frontend is built (npm run build), Django serves the index.html
for all non-API routes, allowing React Router to handle client-side routing.
"""
from pathlib import Path

from django.conf import settings
from django.http import HttpResponse, Http404


def serve_frontend(request):
    """Serve the React frontend index.html for SPA routing."""
    frontend_dir = settings.BASE_DIR.parent / 'frontend' / 'dist'
    index_file = frontend_dir / 'index.html'

    if not index_file.exists():
        return HttpResponse(
            '<h1>Frontend not built</h1>'
            '<p>Run <code>npm run build</code> in the frontend directory first.</p>'
            '<p>Or access the API directly at <a href="/api/">/api/</a></p>',
            content_type='text/html',
            status=200,
        )

    return HttpResponse(index_file.read_text(), content_type='text/html')
