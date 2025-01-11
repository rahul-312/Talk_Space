from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from .serializers import UserRegistrationSerializer , UserLoginSerializer,  UserListSerializer, FriendRequestSerializer
from .models import User, FriendRequest
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.db.models import Q
from rest_framework_simplejwt.tokens import RefreshToken
from django.db import models

class UserRegistrationView(APIView):
    permission_classes = [AllowAny]
    def post(self, request):
        serializer = UserRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            return Response({"message": "User registered successfully!"}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
class UserLoginView(APIView):
    permission_classes = [AllowAny]
    def post(self, request):
        serializer = UserLoginSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data
            tokens = serializer.get_tokens_for_user(user)
            return Response({"message": "Login successful", "tokens": tokens}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class UserListView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        users = User.objects.all()
        serializer = UserListSerializer(users, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

class UserSearchView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, username):
        try:
            user = User.objects.get(username=username)
            serializer = UserListSerializer(user)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except User.DoesNotExist:
            return Response(
                {"error": "User not found."},
                status=status.HTTP_404_NOT_FOUND
            )


class SendFriendRequestView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = FriendRequestSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            friend_request = serializer.save()
            response_serializer = FriendRequestSerializer(friend_request)
            return Response(
                {
                    "message": "Friend request sent!",
                    "friend_request": response_serializer.data,
                },
                status=status.HTTP_201_CREATED,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class RespondToFriendRequestView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, request_id):
        try:
            friend_request = FriendRequest.objects.get(id=request_id, receiver=request.user)
        except FriendRequest.DoesNotExist:
            return Response({"error": "Friend request not found."}, status=status.HTTP_404_NOT_FOUND)

        action = request.data.get('action')
        if action == 'accept':
            friend_request.status = 'accepted'
            friend_request.save()
            return Response({"message": "Friend request accepted!"}, status=status.HTTP_200_OK)
        elif action == 'reject':
            friend_request.status = 'rejected'
            friend_request.save()
            return Response({"message": "Friend request rejected."}, status=status.HTTP_200_OK)
        else:
            return Response({"error": "Invalid action."}, status=status.HTTP_400_BAD_REQUEST)
    
class FriendsListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        friends = FriendRequest.objects.filter(
            Q(sender=user) | Q(receiver=user),
            status='accepted'
        )
        friends_list = [
            {
                "id": friend.sender.id if friend.sender != user else friend.receiver.id,
                "username": friend.sender.username if friend.sender != user else friend.receiver.username
            }
            for friend in friends
        ]

        return Response({"friends": friends_list}, status=status.HTTP_200_OK)

class UserLogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data["refresh"]
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response({"message": "Logout successful!"}, status=status.HTTP_205_RESET_CONTENT)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)



from .models import ChatRoom, ChatMessage
from .serializers import ChatRoomSerializer, ChatMessageSerializer
from django.shortcuts import get_object_or_404
class ChatRoomListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        """Retrieve chat rooms for a specific user if user_id is provided."""
        user_id = request.query_params.get('user_id')
        if user_id:
            chatrooms = ChatRoom.objects.filter(is_deleted=False, users__id=user_id)  # Use users__id for filtering
        else:
            chatrooms = ChatRoom.objects.filter(is_deleted=False)
        serializer = ChatRoomSerializer(chatrooms, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):
        """Create a new chat room."""
        user_ids = request.data.get('users', [])

        if not user_ids or len(user_ids) != 2:
            return Response(
                {"detail": "Exactly two user IDs are required to create a chat room."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        authenticated_user = request.user
        other_user_ids = set(user_ids) - {authenticated_user.id}

        if len(other_user_ids) != 1:
            return Response(
                {"detail": "You can only create a chat room with exactly one friend."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        other_user_id = other_user_ids.pop()  # Get the second user ID
        other_user = User.objects.filter(id=other_user_id).first()

        if not other_user:
            return Response(
                {"detail": "The specified user does not exist."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not authenticated_user.get_friends().filter(id=other_user.id).exists():
            return Response(
                {"detail": "You are not friends with the specified user."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not other_user.get_friends().filter(id=authenticated_user.id).exists():
            return Response(
                {"detail": "The specified user is not friends with you."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        existing_room = ChatRoom.objects.filter(
            Q(users=authenticated_user) & Q(users=other_user)
        ).first()

        if existing_room:
            return Response(
                {"detail": "A one-on-one chat room already exists with this user."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        data = {
            "users": [authenticated_user.id, other_user.id]
        }
        serializer = ChatRoomSerializer(data=data)
        if serializer.is_valid():
            chatroom = serializer.save()
            chatroom.users.add(authenticated_user, other_user)  # Add both users
            chatroom.save()

            return Response(serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class ChatRoomDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get_object(self, pk):
        """Retrieve a single chat room by its primary key."""
        return get_object_or_404(ChatRoom, pk=pk, is_deleted=False)

    def get(self, request, pk, *args, **kwargs):
        """Retrieve details of a specific chat room."""
        chatroom = self.get_object(pk)
        serializer = ChatRoomSerializer(chatroom)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, pk, *args, **kwargs):
        """Update a specific chat room."""
        chatroom = self.get_object(pk)
        serializer = ChatRoomSerializer(chatroom, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk, *args, **kwargs):
        """Soft delete a chat room."""
        chatroom = self.get_object(pk)
        chatroom.is_deleted = True
        chatroom.save()
        return Response({"detail": "Chat room deleted successfully."}, status=status.HTTP_204_NO_CONTENT)


class ChatMessageListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        """Retrieve all messages for a specific room."""
        room_id = request.query_params.get('room_id')
        if not room_id:
            return Response({"error": "room_id is required."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            room = ChatRoom.objects.get(id=room_id)
        except ChatRoom.DoesNotExist:
            return Response({"error": "Chat room does not exist."}, status=status.HTTP_404_NOT_FOUND)
        
        messages = ChatMessage.objects.filter(room=room).order_by('timestamp')
        serializer = ChatMessageSerializer(messages, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):
        """Create a new chat message."""
        room_id = request.data.get('room_id')
        if not room_id:
            return Response({"error": "room_id is required."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            room = ChatRoom.objects.get(id=room_id)
        except ChatRoom.DoesNotExist:
            return Response({"error": "Chat room does not exist."}, status=status.HTTP_404_NOT_FOUND)
        if request.user not in room.users.all():
            return Response({"error": "User is not part of this chat room."}, status=status.HTTP_403_FORBIDDEN)
        serializer = ChatMessageSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(user=request.user, room=room)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)