from urllib.parse import parse_qs
from typing import Optional
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser, User
from django.core.exceptions import ObjectDoesNotExist
from rest_framework.authtoken.models import Token
import logging

logger = logging.getLogger(__name__)

class TokenAuthMiddleware:
    """
    Custom WebSocket authentication middleware that authenticates users
    using a token passed in the query string. Uses Django REST Framework's
    TokenAuthentication system.

    Expected query string format: ?token=<token_key>
    Sets scope['user'] to the authenticated user or AnonymousUser if authentication fails.
    """
    def __init__(self, inner):
        """
        Initialize the middleware with the inner application.

        Args:
            inner: The inner ASGI application to wrap
        """
        self.inner = inner

    async def __call__(self, scope: dict, receive: callable, send: callable) -> None:
        """
        Process the WebSocket connection and authenticate the user.

        Args:
            scope: The ASGI scope dictionary
            receive: The receive callable for getting messages
            send: The send callable for sending messages

        Returns:
            None: Continues to the inner application with updated scope
        """
        try:
            # Parse query string
            query_string = scope.get("query_string", b"").decode("utf-8")
            token_key = self._extract_token_from_query(query_string)

            if not token_key:
                logger.debug("No token provided in WebSocket connection")
                scope["user"] = AnonymousUser()
                return await self.inner(scope, receive, send)

            # Validate token format (basic check)
            if len(token_key) > 128:  # Reasonable maximum length
                logger.warning(f"Invalid token length: {len(token_key)}")
                scope["user"] = AnonymousUser()
                return await self.inner(scope, receive, send)

            # Authenticate user
            user = await self._authenticate_user(token_key)
            scope["user"] = user

            logger.debug(f"WebSocket authentication {'successful' if not user.is_anonymous else 'failed'} "
                        f"for user: {user.id if not user.is_anonymous else 'anonymous'}")

        except Exception as e:
            logger.error(f"Error in TokenAuthMiddleware: {str(e)}")
            scope["user"] = AnonymousUser()

        return await self.inner(scope, receive, send)

    def _extract_token_from_query(self, query_string: str) -> Optional[str]:
        """
        Extract the token from the query string.

        Args:
            query_string: The query string from the WebSocket connection

        Returns:
            Optional[str]: The token key if found, None otherwise
        """
        if not query_string:
            return None

        query_params = parse_qs(query_string)
        token_list = query_params.get("token", [])

        return token_list[0] if token_list else None

    @database_sync_to_async
    def _authenticate_user(self, token_key: str) -> User:
        """
        Authenticate the user using the provided token key.

        Args:
            token_key: The token key to authenticate with

        Returns:
            User: The authenticated user or AnonymousUser if authentication fails
        """
        try:
            token = Token.objects.select_related('user').get(key=token_key)
            # Optionally check token expiration if you have a custom implementation
            # if token.expires_at and token.expires_at < timezone.now():
            #     logger.warning(f"Expired token attempted: {token_key}")
            #     return AnonymousUser()

            if not token.user.is_active:
                logger.warning(f"Inactive user attempted connection: {token.user.id}")
                return AnonymousUser()

            return token.user

        except ObjectDoesNotExist:
            logger.warning(f"Invalid token attempted: {token_key}")
            return AnonymousUser()
        except Exception as e:
            logger.error(f"Error authenticating token: {str(e)}")
            return AnonymousUser()