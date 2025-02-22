import json
import jwt
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from user.models import User  # Import your custom User model
from django.conf import settings
from channels.db import database_sync_to_async
from urllib.parse import parse_qs

logger = logging.getLogger(__name__)

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        """
        Called when the WebSocket connection is established.
        The room ID is passed in the URL route kwargs.
        """
        self.room_id = self.scope["url_route"]["kwargs"]["room_id"]
        self.group_name = f"chat_{self.room_id}"

        # Extract the token from the URL query parameters using parse_qs
        query_params = parse_qs(self.scope['query_string'].decode())
        token = query_params.get('token', [None])[0]

        # Attempt to decode the token and fetch the user
        if token:
            try:
                payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
                user_id = payload.get('user_id')

                if user_id:
                    self.user = await database_sync_to_async(User.objects.get)(id=user_id)
                    self.username = self.user.username
                    logger.info(f"User {self.username} connected to room {self.room_id}.")
                else:
                    self.username = 'anonymous'
                    logger.warning("Token did not contain user_id; setting username to anonymous.")
            except jwt.ExpiredSignatureError:
                self.username = 'anonymous'
                logger.warning("Token has expired; setting username to anonymous.")
            except jwt.InvalidTokenError:
                self.username = 'anonymous'
                logger.warning("Invalid token provided; setting username to anonymous.")
        else:
            self.username = 'anonymous'
            logger.warning("No token provided in query parameters; setting username to anonymous.")

        # Add the channel to the group for the room
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        # Accept the WebSocket connection
        await self.accept()

    async def disconnect(self, close_code):
        """
        Called when the WebSocket connection is closed.
        Remove the channel from the group.
        """
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        """
        Called when a message is received from the WebSocket.
        Broadcasts the message to the room group.
        """
        data = json.loads(text_data)
        message = data.get("message")
        
        # Use the stored username from the connect method
        username = self.username

        # Broadcast the message to the group
        await self.channel_layer.group_send(
            self.group_name,
            {
                "type": "chat_message",
                "message": message,
                "username": username,
            }
        )

    async def chat_message(self, event):
        """
        Called by the channel layer when a message is sent to the group.
        Sends the message to the WebSocket client.
        """
        message = event["message"]
        username = event["username"]

        # Send the message to the WebSocket client
        await self.send(text_data=json.dumps({
            "message": message,
            "username": username,
        }))
