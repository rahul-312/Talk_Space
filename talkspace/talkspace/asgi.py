import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
import user.routing

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'talkspace.settings')

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": URLRouter(
        user.routing.websocket_urlpatterns
    ),
})
