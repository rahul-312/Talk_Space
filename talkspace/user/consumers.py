import logging
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from .models import ChatMessage, ChatRoom
from django.contrib.auth.models import User
from channels.db import database_sync_to_async
from django.utils.html import strip_tags

# Set up logging
logger = logging.getLogger(__name__)

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        """Handle WebSocket connection."""
        self.room_name = self.scope['url_route']['kwargs']['room_name']
        self.room_group_name = f"chat_{self.room_name}"

        # Validate the room name (optional)
        if not self.room_name or not self.room_name.isalnum():
            await self.send(json.dumps({'error': 'Invalid room name.'}))
            await self.close()
            return

        # Check if the room exists
        self.room = await self.get_room(self.room_name)
        if not self.room:
            await self.send(json.dumps({'error': 'Room does not exist.'}))
            await self.close()
            return

        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        """Receive message from WebSocket and broadcast."""
        try:
            text_data_json = json.loads(text_data)
            message = text_data_json.get('message', '').strip()
            user = self.scope["user"]

            # Check user authentication
            if not user.is_authenticated:
                await self.send(json.dumps({'error': 'User is not authenticated.'}))
                await self.close()
                return

            # Ensure message is not empty
            if not message:
                await self.send(json.dumps({'error': 'Message cannot be empty.'}))
                return

            # Sanitize the message
            sanitized_message = strip_tags(message)

            # Save message to the database
            saved_message = await self.save_message(user, sanitized_message)

            # Broadcast the message to the room group
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'chat_message',
                    'message': {
                        'id': saved_message['id'],
                        'room': saved_message['room'],
                        'user': saved_message['user'],
                        'message': saved_message['message'],
                        'timestamp': saved_message['timestamp'],
                    },
                }
            )
        except Exception as e:
            logger.error(f"Error in ChatConsumer: {str(e)}")
            await self.send(json.dumps({'error': str(e)}))

    async def chat_message(self, event):
        """Receive message from room group and send it to WebSocket."""
        message = event['message']
        await self.send(text_data=json.dumps(message))

    @database_sync_to_async
    def save_message(self, user, message):
        """Save a new chat message to the database."""
        chat_message = ChatMessage.objects.create(
            room=self.room,
            user=user,
            message=message
        )
        return {
            'id': chat_message.id,
            'room': chat_message.room.name,
            'user': chat_message.user.username,
            'message': chat_message.message,
            'timestamp': chat_message.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
        }

    @database_sync_to_async
    def get_room(self, room_name):
        """Get a chat room by name."""
        try:
            return ChatRoom.objects.get(name=room_name, is_deleted=False)
        except ChatRoom.DoesNotExist:
            return None
