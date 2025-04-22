from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from .serializers import UserRegistrationSerializer , UserLoginSerializer,  UserListSerializer, FriendRequestSerializer,FriendSerializer, UserSerializer, ForgotPasswordSerializer, ResetPasswordSerializer
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.db.models import Q
from rest_framework_simplejwt.tokens import RefreshToken
from django.db.models import Count
from .models import User,FriendRequest

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
            return Response({"message": "Login successful", "tokens": tokens, "user_id": user.id}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
class UserDetailAPIView(APIView):
    """
    Retrieve, update, or delete the authenticated user's details.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Retrieve the authenticated user's details."""
        serializer = UserSerializer(request.user)
        return Response(serializer.data)

    def put(self, request):
        print("Request data:", request.data)
        print("Request files:", request.FILES)
        serializer = UserSerializer(request.user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request):
        """Soft delete: Deactivate the user instead of deleting."""
        user = request.user
        user.is_active = False  # Mark user as inactive
        user.save()
        return Response({"message": "User account has been deactivated."}, status=status.HTTP_200_OK)

class UserListView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        users = User.objects.all()
        serializer = UserListSerializer(users, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

class ForgotPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({"detail": "Password reset link sent."}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class ResetPasswordView(APIView):
    permission_classes = [AllowAny]
    
    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({"detail": "Password has been reset."}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class UserSearchView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, query):
        users = list(User.objects.filter(
            Q(username__icontains=query) |
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query)
        ))  # Convert QuerySet to list to avoid AttributeError

        if not users:
            return Response({"error": "User not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = UserListSerializer(users, many=True)  # Ensure many=True
        return Response({"users": serializer.data}, status=status.HTTP_200_OK)


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

class PendingFriendRequestsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        requests = FriendRequest.objects.filter(receiver=request.user, status='pending')
        serialized_requests = [
            {
                "id": req.id,
                "sender": {"id": req.sender.id, "username": req.sender.username}
            }
            for req in requests
        ]
        return Response({"requests": serialized_requests})

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
        search_query = request.query_params.get("search", "").strip()

        # Base queryset of accepted friend requests
        friends_qs = FriendRequest.objects.filter(
            Q(sender=user) | Q(receiver=user),
            status="accepted"
        ).select_related("sender", "receiver")

        if search_query:
            # Build a query to filter friend requests by user's attributes.
            friends_qs = friends_qs.filter(
                Q(sender__first_name__icontains=search_query) |
                Q(receiver__username__icontains=search_query) |
                Q(receiver__first_name__icontains=search_query)
            )

        # Extract the friend object: If the sender is the current user, take the receiver; otherwise, sender.
        friends = [f.sender if f.sender != user else f.receiver for f in friends_qs]

        serializer = FriendSerializer(friends, many=True)
        return Response({"friends": serializer.data}, status=200)

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
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction
class ChatRoomListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        """Retrieve chat rooms for the authenticated user with other users."""
        chatrooms = ChatRoom.objects.filter(
            is_deleted=False,
            users=request.user
        ).prefetch_related("users")  # Prefetch users to optimize queries

        chatroom_data = []
        for chatroom in chatrooms:
            # Get other users in the chat excluding the authenticated user
            other_users = chatroom.users.exclude(id=request.user.id)
            other_users_data = UserListSerializer(other_users, many=True).data  # Serialize other users
            
            chatroom_info = ChatRoomSerializer(chatroom).data
            chatroom_info["other_users"] = other_users_data  # Add other users to response
            
            chatroom_data.append(chatroom_info)

        return Response(chatroom_data, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):
        """Create or get a chat room (DM or group based on number of users)."""
        other_user_ids = request.data.get("user_ids", [])
        group_name = request.data.get("name", "").strip()

        if not other_user_ids:
            return Response(
                {"detail": "At least one user's ID is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        friends = request.user.get_friends().filter(id__in=other_user_ids)
        if friends.count() != len(other_user_ids):
            return Response(
                {"detail": "Some users are not your friends or do not exist."},
                status=status.HTTP_400_BAD_REQUEST
            )

        user_ids = sorted([request.user.id] + list(friends.values_list("id", flat=True)))

        if len(other_user_ids) == 1:
            # If only one user, create a DM
            friend = friends.first()
            chatroom = ChatRoom.get_or_create_dm(request.user, friend)
            serializer = ChatRoomSerializer(chatroom)
            return Response(serializer.data, status=status.HTTP_200_OK)

        # ---- GROUP CHAT CREATION ----
        if not group_name:
            return Response(
                {"detail": "Group name is required for group chats."},
                status=status.HTTP_400_BAD_REQUEST
            )

        with transaction.atomic():
            existing_room = None
            candidate_rooms = ChatRoom.objects.filter(is_deleted=False)\
                .annotate(user_count=Count("users"))\
                .filter(user_count=len(user_ids))

            for room in candidate_rooms:
                room_user_ids = sorted(list(room.users.values_list("id", flat=True)))
                if room_user_ids == user_ids:
                    existing_room = room
                    break

            if existing_room:
                serializer = ChatRoomSerializer(existing_room)
                return Response(serializer.data, status=status.HTTP_200_OK)

            chatroom = ChatRoom.objects.create(
                is_group_chat=True,
                name=group_name
            )
            chatroom.users.set([request.user] + list(friends))
            chatroom.save()

        serializer = ChatRoomSerializer(chatroom)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

class ChatRoomDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get_object(self, pk):
        return get_object_or_404(ChatRoom, pk=pk, is_deleted=False, users=self.request.user)

    def get(self, request, pk, *args, **kwargs):
        """Retrieve chat room details with messages and exclude the requesting user."""
        chatroom = self.get_object(pk)
        messages = ChatMessage.objects.filter(room=chatroom).order_by('timestamp')
        other_users = chatroom.users.exclude(id=request.user.id)
        other_users_serializer = UserListSerializer(other_users, many=True)
        chatroom_serializer = ChatRoomSerializer(chatroom)
        message_serializer = ChatMessageSerializer(messages, many=True)

        return Response({
            "chat_room": chatroom_serializer.data,
            "other_users": other_users_serializer.data,  # Filtered users list
            "messages": message_serializer.data
        }, status=status.HTTP_200_OK)

    def put(self, request, pk, *args, **kwargs):
        """Update chat room details."""
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
        return Response(
            {"detail": "Chat room deleted successfully."},
            status=status.HTTP_204_NO_CONTENT
        )
import datetime
class ChatMessageListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        """Retrieve messages for a specific room."""
        room_id = request.query_params.get('room_id')
        if not room_id:
            return Response(
                {"error": "room_id is required."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        room = get_object_or_404(ChatRoom, id=room_id, is_deleted=False, users=request.user)
        # Only fetch non-deleted messages
        messages = ChatMessage.objects.filter(room=room, is_deleted=False).order_by('timestamp')
        serializer = ChatMessageSerializer(messages, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):
        room_id = request.data.get('room_id')
        if not room_id:
            return Response(
                {"error": "room_id is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        room = get_object_or_404(ChatRoom, id=room_id, is_deleted=False)
        if request.user not in room.users.all():
            return Response(
                {"error": "User is not part of this chat room."},
                status=status.HTTP_403_FORBIDDEN
            )

        # Modify request.data to include room and user
        data = request.data.copy()
        data['room'] = room_id
        data['user'] = request.user.id

        serializer = ChatMessageSerializer(data=data)
        if serializer.is_valid():
            message = serializer.save(user=request.user, room=room)
            profile_picture_url = self.get_profile_picture_url(request.user)
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                f"chat_{room_id}",
                {
                    "type": "chat_message",
                    "message": message.message,
                    "user": request.user.username,
                    "first_name": request.user.first_name,  # Added
                    "last_name": request.user.last_name,
                    "user": request.user.id,
                    "profile_picture": profile_picture_url,
                    "timestamp": str(message.timestamp)
                }
            )
            
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    def put(self, request, *args, **kwargs):
        """Edit only the message content of an existing message."""
        message_id = request.data.get('message_id')
        new_message_text = request.data.get('message')
        if not message_id or not new_message_text:
            return Response(
                {"error": "message_id and message are required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        message = get_object_or_404(ChatMessage, id=message_id, is_deleted=False)
        if message.user != request.user:
            return Response(
                {"error": "You can only edit your own messages."},
                status=status.HTTP_403_FORBIDDEN
            )
        message.message = new_message_text
        message.save(update_fields=['message'])
        serializer = ChatMessageSerializer(message)
        channel_layer = get_channel_layer()
        event = {
            "type": "chat_message",
            "message": message.message,  # Only send the updated message content
            "user": message.user.id,     # Keep user details unchanged
            "first_name": message.user.first_name,
            "last_name": message.user.last_name,
            "profile_picture": self.get_profile_picture_url(message.user),
            "timestamp": str(message.timestamp),
            "id": message.id,
            "action": "edit"
        }
        async_to_sync(channel_layer.group_send)(
            f"chat_{message.room.id}",
            event
        )
        
        return Response(serializer.data, status=status.HTTP_200_OK)

    def delete(self, request, *args, **kwargs):
        """Soft delete an existing message."""
        message_id = request.data.get('message_id')
        
        if not message_id:
            return Response(
                {"error": "message_id is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        message = get_object_or_404(ChatMessage, id=message_id, is_deleted=False)
        
        # Check if the user is the message author
        if message.user != request.user:
            return Response(
                {"error": "You can only delete your own messages."},
                status=status.HTTP_403_FORBIDDEN
            )

        # Soft delete the message
        message.is_deleted = True
        message.save(update_fields=['is_deleted'])
        
        channel_layer = get_channel_layer()
        event = {
            "type": "chat_message",
            "message": message.message,
            "first_name": request.user.first_name,
            "last_name": request.user.last_name,
            "user": request.user.id,
            "profile_picture": self.get_profile_picture_url(request.user),
            "timestamp": str(message.timestamp),
            "id": message.id,
            "action": "delete"
        }
        async_to_sync(channel_layer.group_send)(
            f"chat_{message.room.id}",
            event
        )
        
        return Response({"message": "Message deleted successfully."}, status=status.HTTP_200_OK)

    def get_profile_picture_url(self, user):
        """Get the URL of the user's profile picture if it exists."""
        if hasattr(user, 'profile_picture') and user.profile_picture:
            url = f"{user.profile_picture.url}?v={int(datetime.datetime.now().timestamp())}"
            return url
        return None
    
PEER_CONNECTIONS = {}
ICE_CANDIDATES = {}

class OfferView(APIView):
    def post(self, request):
        offer_sdp = request.data.get('sdp')
        caller = request.data.get('peer_id')  # e.g., "peer1"
        receiver = request.data.get('remote_peer_id')  # e.g., "peer4"
        
        # Store the offer under the receiver's id with the caller info.
        PEER_CONNECTIONS[receiver] = {
            'offer': offer_sdp,
            'answer': None,
            'caller': caller
        }
        ICE_CANDIDATES[receiver] = []
        print("Offer created. Current PEER_CONNECTIONS:", PEER_CONNECTIONS)  # Debug log
        return Response({'status': 'offer received'}, status=status.HTTP_201_CREATED)

class AnswerView(APIView):
    def post(self, request):
        answer_sdp = request.data.get('sdp')
        caller_peer = request.data.get('caller_peer_id')
        print("Answer SDP:", answer_sdp)
        print("Caller Peer:", caller_peer)
        print("Current PEER_CONNECTIONS:", PEER_CONNECTIONS) 
        if not caller_peer:
            return Response({'error': 'caller_peer_id is required'}, status=status.HTTP_400_BAD_REQUEST)
        if caller_peer in PEER_CONNECTIONS:
            PEER_CONNECTIONS[caller_peer]['answer'] = answer_sdp
            return Response({'status': 'answer received'}, status=status.HTTP_201_CREATED)
        return Response({'error': 'caller peer_id not found'}, status=status.HTTP_404_NOT_FOUND)


class SetOfferView(APIView):
    def post(self, request, peer_id):
        offer = request.data.get('sdp')
        caller = request.data.get('caller')
        PEER_CONNECTIONS[peer_id] = {'offer': offer, 'caller': caller}
        return Response({'message': 'Offer set successfully'}, status=status.HTTP_200_OK)

class GetOfferView(APIView):
    def get(self, request, peer_id):
        connection = PEER_CONNECTIONS.get(peer_id, {})
        offer = connection.get('offer')
        caller = connection.get('caller')
        if offer:
            return Response({'sdp': offer, 'caller': caller}, status=status.HTTP_200_OK)
        return Response({'error': 'offer not found'}, status=status.HTTP_404_NOT_FOUND)

class SetAnswerView(APIView):
    def post(self, request, peer_id):
        answer = request.data.get('sdp')
        if peer_id in PEER_CONNECTIONS:
            PEER_CONNECTIONS[peer_id]['answer'] = answer
            return Response({'message': 'Answer set successfully'}, status=status.HTTP_200_OK)
        return Response({'error': 'Offer not found'}, status=status.HTTP_404_NOT_FOUND)

class GetAnswerView(APIView):
    def get(self, request, peer_id):
        answer = PEER_CONNECTIONS.get(peer_id, {}).get('answer')
        print("Current PEER_CONNECTIONS:", PEER_CONNECTIONS)
        if answer:
            return Response({'sdp': answer}, status=status.HTTP_200_OK)
        return Response({'error': 'answer not found'}, status=status.HTTP_404_NOT_FOUND)

class IceCandidateView(APIView):
    def post(self, request):
        peer_id = request.data.get('peer_id')
        candidate = request.data.get('candidate')
        if peer_id not in ICE_CANDIDATES:
            ICE_CANDIDATES[peer_id] = []
        ICE_CANDIDATES[peer_id].append(candidate)
        return Response({'status': 'candidate received'}, status=status.HTTP_201_CREATED)

    def get(self, request, peer_id):
        candidates = ICE_CANDIDATES.get(peer_id, [])
        print("Current ICE Candidates:", ICE_CANDIDATES)
        return Response({'candidates': candidates}, status=status.HTTP_200_OK)


class ShareFilesInRoomAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        if 'files' not in request.FILES:
            return Response({"error": "No files provided. Use 'files' as the key."}, status=400)

        uploaded_files = request.FILES.getlist('files')
        if len(uploaded_files) == 0:
            return Response({"error": "Please upload at least 1 file."}, status=400)
        if len(uploaded_files) > 10:
            return Response({"error": "You cannot upload more than 10 files at once."}, status=400)

        room_id = request.data.get('room_id')
        if not room_id:
            return Response({"error": "Room ID is required."}, status=400)
        try:
            room = ChatRoom.objects.get(id=room_id)
        except ChatRoom.DoesNotExist:
            return Response({"error": "Chat room not found."}, status=404)

        if request.user not in room.users.all():
            return Response({"error": "You are not a member of this room."}, status=403)

        for file in uploaded_files:
            file_size_mb = file.size / (1024 * 1024)
            if file.name.lower().endswith(('.mp4', '.avi', '.mov', '.mkv')):
                if file_size_mb > 50:
                    return Response({"error": f"Video '{file.name}' exceeds 50MB limit."}, status=400)
            else:
                if file_size_mb > 100:
                    return Response({"error": f"File '{file.name}' exceeds 100MB limit."}, status=400)

        # Use provided message, default to "Shared some files" only if empty
        message_text = request.data.get('message', '').strip() or 'Shared some files'
        chat_message = ChatMessage.objects.create(
            room=room,
            user=request.user,
            message=message_text
        )

        saved_files = []
        total_size = 0
        for file in uploaded_files:
            total_size += file.size
            attached_file = AttachedFile(
                chat_message=chat_message,
                file=file,
                name=file.name,
                size=file.size,
                content_type=file.content_type
            )
            attached_file.save()
            saved_files.append({
                "name": attached_file.name,
                "size": attached_file.size,
                "url": attached_file.file.url
            })

        channel_layer = get_channel_layer()
        event = {
            "type": "chat_message",
            "message": message_text,
            "first_name": request.user.first_name,
            "last_name": request.user.last_name,
            "user": request.user.id,
            "timestamp": str(chat_message.timestamp),
            "files": saved_files
        }

        async_to_sync(channel_layer.group_send)(f"chat_{room_id}", event)

        return Response(
            {
                "message": f"Files shared in room '{room.name}' successfully!",
                "chat_id": chat_message.id,
                "room": room.name,
                "files": saved_files,
                "total_size": total_size
            },
            status=201
        )
class ViewChatMessageAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, token, *args, **kwargs):
        chat_message = get_object_or_404(ChatMessage, share_token=token)

        if request.user not in chat_message.room.members.all():
            return Response({"error": "You are not a member of this room."}, status=403)

        files = [
            {
                "name": f.name,
                "size": f.size,
                "url": f.file.url
            } for f in chat_message.files.all()
        ]

        return Response({
            "sender": chat_message.sender.username,
            "room": chat_message.room.name,
            "message": chat_message.message,
            "files": files,
            "timestamp": chat_message.timestamp
        })