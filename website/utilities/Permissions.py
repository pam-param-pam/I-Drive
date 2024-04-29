from rest_framework.permissions import BasePermission

from website.models import UserPerms


class AdminPerms(BasePermission):
    def has_permission(self, request, view):
        perms = UserPerms.objects.get(user=request.user)
        return perms.admin or perms.admin

class CmdExecutePerms(BasePermission):
    def has_permission(self, request, view):
        perms = UserPerms.objects.get(user=request.user)
        return perms.execute or perms.admin

class CreatePerms(BasePermission):
    def has_permission(self, request, view):
        perms = UserPerms.objects.get(user=request.user)
        return perms.create or perms.admin

class ModifyPerms(BasePermission):
    def has_permission(self, request, view):
        perms = UserPerms.objects.get(user=request.user)
        return perms.modify or perms.admin

class DeletePerms(BasePermission):
    def has_permission(self, request, view):
        perms = UserPerms.objects.get(user=request.user)
        return perms.delete or perms.admin

class SharePerms(BasePermission):
    def has_permission(self, request, view):
        perms = UserPerms.objects.get(user=request.user)
        return perms.share or perms.admin

class DownloadPerms(BasePermission):
    def has_permission(self, request, view):
        perms = UserPerms.objects.get(user=request.user)
        return perms.download or perms.admin

class LockPerms(BasePermission):
    def has_permission(self, request, view):
        perms = UserPerms.objects.get(user=request.user)
        return perms.lock or perms.admin
