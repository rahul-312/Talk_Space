from urllib.parse import parse_qs
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ObjectDoesNotExist
from rest_framework.authtoken.models import Token

class TokenAuthMiddleware:
    """
    Custom middleware that takes a token from the query string and
    authenticates via DRF's TokenAuthentication.
    """
    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        # Parse the query string to get the token.
        query_string = scope.get("query_string", b"").decode()
        query_params = parse_qs(query_string)
        token_key = query_params.get("token")
        if token_key:
            token_key = token_key[0]
            try:
                token = await database_sync_to_async(Token.objects.get)(key=token_key)
                scope["user"] = token.user
            except ObjectDoesNotExist:
                scope["user"] = AnonymousUser()
        else:
            scope["user"] = AnonymousUser()

        # Correctly call the inner application with all three arguments.
        return await self.inner(scope, receive, send)
