from django.urls import path
from .views import UserRegistrationView, UserLoginView, UserListView, UserSearchView, SendFriendRequestView, RespondToFriendRequestView, FriendsListView, UserLogoutView, ChatRoomListCreateView, ChatRoomDetailView, ChatMessageListCreateView


urlpatterns = [
    path('register/', UserRegistrationView.as_view(), name='user_register'),
    path('login/', UserLoginView.as_view(), name='user_login'),
    path('users-list/', UserListView.as_view(), name='user_list'),
    path('user-search/<str:username>/', UserSearchView.as_view(), name='user-search'),
    path('send-friend-request/', SendFriendRequestView.as_view(), name='send-friend-request'),
    path('respond-to-friend-request/<int:request_id>/', RespondToFriendRequestView.as_view(), name='respond-to-friend-request'),
    path('friend-list/', FriendsListView.as_view(), name='friend-list'),
    path('logout/', UserLogoutView.as_view(), name='user-logout'),
    path('chatrooms/', ChatRoomListCreateView.as_view(), name='chatroom-list-create'),
    path('chatrooms/<int:pk>/', ChatRoomDetailView.as_view(), name='chatroom-detail'),
    path('messages/', ChatMessageListCreateView.as_view(), name='chatmessage-list-create'),
]