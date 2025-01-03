from django.contrib import admin
from .models import User, FriendRequest

class UserAdmin(admin.ModelAdmin):
    list_display = ('id','email', 'username', 'first_name', 'last_name', 'is_staff', 'is_active', 'date_joined')
    search_fields = ('email', 'username', 'first_name', 'last_name')
    list_filter = ('is_staff', 'is_active', 'gender')
    ordering = ('-date_joined',)

class FriendRequestAdmin(admin.ModelAdmin):
    list_display = ('id', 'sender', 'receiver', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('sender__username', 'receiver__username')
    ordering = ('-created_at',)
    
admin.site.register(FriendRequest, FriendRequestAdmin)
admin.site.register(User, UserAdmin)
