from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from .serializers import UserRegistrationSerializer , UserLoginSerializer,  UserListSerializer, FriendRequestSerializer,FriendSerializer
from .models import User, FriendRequest
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.db.models import Q
from rest_framework_simplejwt.tokens import RefreshToken
from django.db import models
from django.db.models import Count

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
class ChatRoomListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        """Retrieve chat rooms for the authenticated user."""
        chatrooms = ChatRoom.objects.filter(
            is_deleted=False,
            users=request.user
        )
        serializer = ChatRoomSerializer(chatrooms, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):
        """
        Create or get an existing chat room.
        
        If only one friend is provided, create/get a one-on-one DM room.
        If more than one friend is provided, create a group chat room.
        """
        other_user_ids = request.data.get('users', [])

        if not other_user_ids:
            return Response(
                {"detail": "At least one user's ID is required to create a chat room."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        authenticated_user = request.user

        # Validate that all provided user IDs are friends of the authenticated user.
        friends = authenticated_user.get_friends().filter(id__in=other_user_ids)
        if friends.count() != len(other_user_ids):
            return Response(
                {"detail": "Some users are not your friends or do not exist."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if len(other_user_ids) == 1:
            # One-on-one DM using the helper method in ChatRoom
            friend = friends.first()
            chatroom = ChatRoom.get_or_create_dm(authenticated_user, friend)
            serializer = ChatRoomSerializer(chatroom)
            return Response(serializer.data, status=status.HTTP_200_OK)
        else:
            # Group chat creation
            # Combine authenticated user and friends and sort their IDs for consistency.
            user_ids = sorted([authenticated_user.id] + list(friends.values_list('id', flat=True)))

            # Attempt to find an existing group chat that exactly has these users.
            existing_room = None
            candidate_rooms = ChatRoom.objects.filter(is_deleted=False)\
                .annotate(user_count=Count('users'))\
                .filter(user_count=len(user_ids))
            for room in candidate_rooms:
                room_user_ids = sorted(list(room.users.values_list('id', flat=True)))
                if room_user_ids == user_ids:
                    existing_room = room
                    break

            if existing_room:
                serializer = ChatRoomSerializer(existing_room)
                return Response(serializer.data, status=status.HTTP_200_OK)

            # Create a new group chat room.
            chatroom = ChatRoom.objects.create()
            chatroom.users.add(authenticated_user, *friends)
            # Saving again in case the ChatRoom.save() method auto-generates the name.
            chatroom.save()

            serializer = ChatRoomSerializer(chatroom)
            return Response(serializer.data, status=status.HTTP_201_CREATED)


class ChatRoomDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get_object(self, pk):
        """Retrieve a single chat room by its primary key."""
        return get_object_or_404(ChatRoom, pk=pk, is_deleted=False)

    def get(self, request, pk, *args, **kwargs):
        """Retrieve details of a specific chat room along with its messages."""
        chatroom = self.get_object(pk)
        messages = ChatMessage.objects.filter(room=chatroom).order_by('timestamp')

        chatroom_serializer = ChatRoomSerializer(chatroom)
        message_serializer = ChatMessageSerializer(messages, many=True)
        return Response({
            "chat_room": chatroom_serializer.data,
            "messages": message_serializer.data
        }, status=status.HTTP_200_OK)

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
        return Response(
            {"detail": "Chat room deleted successfully."},
            status=status.HTTP_204_NO_CONTENT
        )


class ChatMessageListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        """Retrieve all messages for a specific room."""
        room_id = request.query_params.get('room_id')
        if not room_id:
            return Response({"error": "room_id is required."}, status=status.HTTP_400_BAD_REQUEST)
        
        room = get_object_or_404(ChatRoom, id=room_id, is_deleted=False)
        messages = ChatMessage.objects.filter(room=room).order_by('timestamp')
        serializer = ChatMessageSerializer(messages, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):
        """Create a new chat message."""
        room_id = request.data.get('room_id')
        if not room_id:
            return Response({"error": "room_id is required."}, status=status.HTTP_400_BAD_REQUEST)

        room = get_object_or_404(ChatRoom, id=room_id, is_deleted=False)

        # Ensure the user is part of the chat room.
        if request.user not in room.users.all():
            return Response({"error": "User is not part of this chat room."}, status=status.HTTP_403_FORBIDDEN)

        serializer = ChatMessageSerializer(data=request.data)
        if serializer.is_valid():
            message = serializer.save(user=request.user, room=room)

            # Send the message to WebSocket clients in real time.
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                f"chat_{room_id}",  # Group name for the chat room.
                {
                    "type": "chat_message",
                    "message": message.message,
                    "user": request.user.username
                }
            )

            return Response(serializer.data, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
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