import json
import jwt
from channels.generic.websocket import AsyncWebsocketConsumer
from user.models import User  # Import your custom User model
from django.conf import settings
from channels.db import database_sync_to_async

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        """
        Called when the WebSocket connection is established.
        The room ID is passed in the URL route kwargs.
        """
        self.room_id = self.scope["url_route"]["kwargs"]["room_id"]
        self.group_name = f"chat_{self.room_id}"

        # Get the token from the URL query parameter
        token = self.scope['query_string'].decode().split('=')[1]  # Extract token from 'token=your_token'

        try:
            # Decode the token to get user information
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])  # Adjust your algorithm if needed
            user_id = payload.get('user_id')

            # If user_id exists, fetch the user from the database
            if user_id:
                self.user = await database_sync_to_async(User.objects.get)(id=user_id)  # Use your custom User model
                self.username = self.user.username
            else:
                self.username = 'anonymous'

        except jwt.ExpiredSignatureError:
            self.username = 'anonymous'
        except jwt.InvalidTokenError:
            self.username = 'anonymous'

        # Add the channel to the group for the room
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )

        # Accept the WebSocket connection
        await self.accept()

    async def disconnect(self, close_code):
        """
        Called when the WebSocket connection is closed.
        Remove the channel from the group.
        """
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        """
        Called when a message is received from the WebSocket.
        Broadcasts the message to the room group.
        """
        data = json.loads(text_data)
        message = data.get("message")

        # Use the stored username from the connect method
        username = self.username  # No need to get it from the message anymore

        # Broadcast the message to the group
        await self.channel_layer.group_send(
            self.group_name,
            {
                "type": "chat_message",  # This calls the chat_message method below
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

        # Send the message to WebSocket client
        await self.send(text_data=json.dumps({
            "message": message,
            "username": username,
        }))
