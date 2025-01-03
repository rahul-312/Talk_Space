from django.urls import path
from .views import UserRegistrationView, UserLoginView, UserListView, UserSearchView, SendFriendRequestView, RespondToFriendRequestView

urlpatterns = [
    path('register/', UserRegistrationView.as_view(), name='user_register'),
    path('login/', UserLoginView.as_view(), name='user_login'),
    path('users-list/', UserListView.as_view(), name='user_list'),
    path('user-search/<str:username>/', UserSearchView.as_view(), name='user-search'),
    path('send-friend-request/', SendFriendRequestView.as_view(), name='send-friend-request'),
    path('respond-to-friend-request/<int:request_id>/', RespondToFriendRequestView.as_view(), name='respond-to-friend-request')
]