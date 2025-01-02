from django.contrib import admin
from .models import User

class UserAdmin(admin.ModelAdmin):
    list_display = ('email', 'username', 'first_name', 'last_name', 'is_staff', 'is_active', 'date_joined')
    search_fields = ('email', 'username', 'first_name', 'last_name')
    list_filter = ('is_staff', 'is_active', 'gender')
    ordering = ('-date_joined',)
    
admin.site.register(User, UserAdmin)
