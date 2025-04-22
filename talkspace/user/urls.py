from django.urls import path
from .views import (
    UserRegistrationView, UserLoginView, UserListView, UserSearchView, 
    SendFriendRequestView, RespondToFriendRequestView, FriendsListView, 
    UserLogoutView, ChatRoomListCreateView, ChatRoomDetailView, 
    ChatMessageListCreateView, PendingFriendRequestsView, OfferView, 
    AnswerView, GetAnswerView, GetOfferView, IceCandidateView, 
    SetAnswerView, SetOfferView, UserDetailAPIView, ShareFilesInRoomAPIView,
    ViewChatMessageAPIView, ForgotPasswordView, ResetPasswordView
)

urlpatterns = [
    path('register/', UserRegistrationView.as_view(), name='user_register'),
    path('login/', UserLoginView.as_view(), name='user_login'),
    path('users-list/', UserListView.as_view(), name='user_list'),
    path("user-detail/", UserDetailAPIView.as_view(), name="user-detail"),
    path('user-search/<str:query>/', UserSearchView.as_view(), name='user-search'),
    path('send-friend-request/', SendFriendRequestView.as_view(), name='send-friend-request'),
    path('respond-to-friend-request/<int:request_id>/', RespondToFriendRequestView.as_view(), name='respond-to-friend-request'),
    path('pending-requests/', PendingFriendRequestsView.as_view(), name='pending_requests'),
    path('friend-list/', FriendsListView.as_view(), name='friend-list'),
    path('logout/', UserLogoutView.as_view(), name='user-logout'),
    path('chatrooms/', ChatRoomListCreateView.as_view(), name='chatroom-list-create'),
    path('chatrooms/<int:pk>/', ChatRoomDetailView.as_view(), name='chatroom-detail'),
    path('messages/', ChatMessageListCreateView.as_view(), name='chatmessage-list-create'),
    path('offer/', OfferView.as_view(), name='offer'),
    path('offer/<str:peer_id>/', GetOfferView.as_view(), name='get_offer'),
    path('offer/<str:peer_id>/set/', SetOfferView.as_view(), name='set_offer'),
    path('answer/<str:peer_id>/', GetAnswerView.as_view(), name='get_answer'),
    path('answer/<str:peer_id>/set/', SetAnswerView.as_view(), name='set_answer'),
    path('answer/', AnswerView.as_view(), name='answer'),
    path('ice_candidate/', IceCandidateView.as_view(), name='ice_candidate'),
    path('ice_candidate/<str:peer_id>/', IceCandidateView.as_view(), name='get_ice_candidates'),
    path('share-files-in-room/', ShareFilesInRoomAPIView.as_view(), name='share-files-in-room'),
    path('chat/<uuid:token>/', ViewChatMessageAPIView.as_view(), name='view_chat_message'),  # From previous response
    path('forgot-password/', ForgotPasswordView.as_view(), name='forgot-password'),
    path('reset-password/', ResetPasswordView.as_view(), name='reset-password'),
]