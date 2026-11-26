"""Which web-push addresses the server is willing to call.

The browser hands us the address, so a signed-in user could otherwise point the server at
anything it can reach (the PLC, the router, itself). Browsers use their vendor's push
service, so only those are accepted.
"""

from urllib.parse import urlsplit

PUSH_HOSTS = (
    "fcm.googleapis.com",  # Chrome, Samsung Internet, Opera, Edge on Android
    "push.services.mozilla.com",  # Firefox
    "push.apple.com",  # Safari, iPhone and iPad
    "notify.windows.com",  # Edge on Windows
)


def is_push_service_url(url: str) -> bool:
    # backslashes and spaces are read differently by different URL libraries
    if "\\" in url or any(ch.isspace() for ch in url):
        return False
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError:
        return False
    host = parts.hostname or ""
    if parts.scheme != "https" or parts.username or parts.password or port not in (None, 443):
        return False
    return any(host == allowed or host.endswith("." + allowed) for allowed in PUSH_HOSTS)
