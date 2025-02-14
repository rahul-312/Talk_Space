from urllib.parse import parse_qs
import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth.models import AnonymousUser
from user.models import ChatMessage
from channels.db import database_sync_to_async
from datetime import datetime
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework.exceptions import AuthenticationFailed

# Setting up logging
logger = logging.getLogger(__name__)
class ChatRoomConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        print(f"Connecting to WebSocket with headers: {self.scope.get('headers', {})}")

        # Extract token from query string
        query_string = parse_qs(self.scope['query_string'].decode())
        token = query_string.get('token', [None])[0]

        if not token:
            print("No token found in query parameters.")
            await self.close()
            return

        # Validate and get user from token
        try:
            AccessToken(token)  # Validate the token
            self.user = await database_sync_to_async(self.get_user_from_token)(token)
            if not self.user:
                raise AuthenticationFailed("User not found.")
            print(f"User {self.user.username} found.")
        except AuthenticationFailed as e:
            print(f"Authentication failed: {str(e)}")
            await self.close()
            return
        except Exception as e:
            print(f"Error during token validation or user lookup: {str(e)}")
            await self.close()
            return

        # Proceed to join the room
        self.room_id = self.scope['url_route']['kwargs']['room_id']
        self.room_group_name = f"chat_{self.room_id}"

        # Add the user to the chat room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name,
        )
        
        # Notify others that a user has joined
        # await self.channel_layer.group_send(
        #     self.room_group_name,
        #     {
        #         'type': 'user_join',
        #         'username': self.user.username,
        #     }
        # )

        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, 'user') and self.user and not isinstance(self.user, AnonymousUser):
            print(f"Disconnecting {self.user.username} from room group {self.room_group_name}.")
            # Remove the user from the chat room group
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name,
            )

            # Notify group about user leaving
        #     print(f"User {self.user.username} has left the room.")
        #     await self.channel_layer.group_send(
        #         self.room_group_name,
        #         {
        #             'type': 'user_leave',
        #             'username': self.user.username,
        #         }
        #     )
        # else:
        #     print("No valid user or anonymous user trying to disconnect.")

    async def receive(self, text_data):
        try:
            print(f"Received message: {text_data}")
            data = json.loads(text_data)
            message = data.get('message')

            if self.user and not isinstance(self.user, AnonymousUser) and message:
                print(f"Saving message from {self.user.username}: {message}")
                # Save the message to the database
                await database_sync_to_async(ChatMessage.objects.create)( 
                    room_id=self.room_id,
                    user=self.user,
                    message=message,
                )

                # Broadcast the message to the room group
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'chat_message',
                        'message': message,
                        'username': self.user.username,
                        'timestamp': str(datetime.now()),
                    }
                )
            else:
                print(f"Received message without valid user or empty message.")
        except json.JSONDecodeError as e:
            print(f"Error decoding received message: {e}")
        except Exception as e:
            print(f"Error processing received message: {e}")

    def get_user_from_token(self, token):
        try:
            token_obj = AccessToken(token)
            user_id = token_obj['user_id']
            User = get_user_model()
            user = User.objects.get(id=user_id)
            print(f"User retrieved from token: {user.username}")
            return user
        except Exception as e:
            print(f"Error retrieving user from token: {e}")
            return None

    async def chat_message(self, event):
        message = event['message']
        username = event['username']
        timestamp = event['timestamp']

        print(f"Sending chat message to WebSocket: {message}")
        # Send the chat message to WebSocket
        await self.send(text_data=json.dumps({
            'type': 'chat_message',
            'message': message,
            'username': username,
            'timestamp': timestamp,
        }))

    async def user_join(self, event):
        username = event['username']

        print(f"User joined: {username}")
        # Notify all WebSocket clients in the group that a user joined
        await self.send(text_data=json.dumps({
            'type': 'user_join',
            'username': username,
        }))

    async def user_leave(self, event):
        username = event['username']

        print(f"User left: {username}")
        # Notify all WebSocket clients in the group that a user left
        await self.send(text_data=json.dumps({
            'type': 'user_leave',
            'username': username,
        }))
