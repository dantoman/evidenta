"""WSGI entry point."""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.prod")

application = get_wsgi_application()

# The event_type registry is checked here, not in AppConfig.ready() -- ADR-038
# section 5. In `ready()` every manage.py command fails including `migrate`, so a
# deploy that lands code with a missing handler could not run the migration that
# fixes it. Here it fails at the point where refusing to serve is the right
# answer: a process that would post to a fallback account should not accept
# traffic.
from evidenta.accounting.events.registry import check_registry  # noqa: E402

check_registry()
