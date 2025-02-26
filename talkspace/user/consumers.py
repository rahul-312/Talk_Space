import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import ChatRoom, ChatMessage

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_id = self.scope['url_route']['kwargs']['room_id']
        self.room_group_name = f'chat_{self.room_id}'

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept()
        print(f"WebSocket connected for room: {self.room_id}")

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
        print(f"WebSocket disconnected for room: {self.room_id}, code: {close_code}")

    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        message = text_data_json['message']
        user = self.scope['user']

        msg = await self.create_message(user, message)

        event = {
            'type': 'chat_message',
            'message': message,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'user': user.id,  # Changed to 'user' for consistency with serializer
            'timestamp': str(msg.timestamp),
        }
        print(f"Sending event from receive: {event}")
        await self.channel_layer.group_send(self.room_group_name, event)

    async def chat_message(self, event):
        print(f"Received event in chat_message: {event}")
        try:
            await self.send(text_data=json.dumps({
                'message': event.get('message', ''),  # Graceful fallback
                'first_name': event.get('first_name', 'Unknown'),
                'last_name': event.get('last_name', ''),
                'user': event.get('user', None),  # Changed to 'user'
                'timestamp': event.get('timestamp', ''),
            }))
        except Exception as e:
            print(f"Error in chat_message: {e}, event: {event}")
            await self.send(text_data=json.dumps({
                'message': 'Error processing message',
                'first_name': 'System',
                'last_name': '',
                'user': None,
                'timestamp': str(datetime.now()),
            }))

    @database_sync_to_async
    def create_message(self, user, message):
        room = ChatRoom.objects.get(id=self.room_id)
        return ChatMessage.objects.create(
            room=room,
            user=user,
            message=message
        )