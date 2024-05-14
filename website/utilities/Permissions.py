from rest_framework.permissions import BasePermission

from website.models import UserPerms


class AdminPerms(BasePermission):
    def has_permission(self, request, view):
        perms = UserPerms.objects.get(user=request.user)
        return (perms.admin or perms.admin) and not perms.globalLock

class CmdExecutePerms(BasePermission):
    def has_permission(self, request, view):
        perms = UserPerms.objects.get(user=request.user)
        return (perms.execute or perms.admin) and not perms.globalLock

class CreatePerms(BasePermission):
    def has_permission(self, request, view):
        perms = UserPerms.objects.get(user=request.user)
        return (perms.create or perms.admin) and not perms.globalLock

class ModifyPerms(BasePermission):
    def has_permission(self, request, view):
        perms = UserPerms.objects.get(user=request.user)
        return (perms.modify or perms.admin) and not perms.globalLock

class DeletePerms(BasePermission):
    def has_permission(self, request, view):
        perms = UserPerms.objects.get(user=request.user)
        return (perms.delete or perms.admin) and not perms.globalLock

class SharePerms(BasePermission):
    def has_permission(self, request, view):
        perms = UserPerms.objects.get(user=request.user)
        return (perms.share or perms.admin) and not perms.globalLock

class DownloadPerms(BasePermission):
    def has_permission(self, request, view):
        perms = UserPerms.objects.get(user=request.user)
        return (perms.download or perms.admin) and not perms.globalLock

class LockPerms(BasePermission):
    def has_permission(self, request, view):
        perms = UserPerms.objects.get(user=request.user)
        return (perms.lock or perms.admin) and not perms.globalLock

class ReadPerms(BasePermission):
    def has_permission(self, request, view):
        perms = UserPerms.objects.get(user=request.user)
        return (perms.read or perms.admin) and not perms.globalLock

class SettingsModifyPerms(BasePermission):
    def has_permission(self, request, view):
        perms = UserPerms.objects.get(user=request.user)
        return (perms.settings_modify or perms.admin) and not perms.globalLock