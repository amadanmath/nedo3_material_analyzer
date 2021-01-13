from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin

from .models import Job

@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'started_at', 'action', 'state']
    fields = ['id', 'user', 'started_at', 'finished_at', 'action', 'txt', 'ann', 'state']
    readonly_fields = ['id', 'started_at']
    list_filter = ['action', 'state']


class JobInline(admin.TabularInline):
    model = Job
    fields = ['id', 'user', 'started_at', 'action', 'state']
    readonly_fields = ['id', 'started_at']
    extra = 0


admin.site.unregister(User)
@admin.register(User)
class CustomUserAdmin(UserAdmin):
    inlines = UserAdmin.inlines + [JobInline]
