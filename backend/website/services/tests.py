from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase

from website.core.errors import ResourceNotFoundError, ResourcePermissionError
from website.models import Folder, TrashRoot, UserPerms
from website.auth.permissions import CredentialSet, PrincipalFactory
from website.services.folder_service import FolderService
from website.services import namespace_service


def _principal(user: User):
    request = SimpleNamespace(
        user=user,
        auth=SimpleNamespace(device_id="device-1"),
        context=SimpleNamespace(device_id="device-1", request_id="request-1"),
        META={"REMOTE_ADDR": "127.0.0.1"},
    )
    return PrincipalFactory.from_authenticated_request(request)


class FolderServicePermissionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="owner")
        self.permissions = UserPerms.objects.create(user=self.user)
        self.principal = _principal(self.user)
        self.root = Folder.objects.create(name="root", owner=self.user)

    @patch("website.services.folder_service.namespace_lock_service.lock_owner_scope_shared")
    def test_create_authorizes_inside_the_locked_command(self, _lock_scope):
        result = FolderService.create(
            self.principal,
            str(self.root.id),
            "child",
            CredentialSet.empty(),
        )
        self.assertTrue(Folder.objects.filter(id=result.folder_id, parent=self.root).exists())

    @patch("website.services.folder_service.namespace_lock_service.lock_owner_scope_shared")
    def test_create_denies_missing_account_capability_before_mutation(self, _lock_scope):
        self.permissions.create = False
        self.permissions.save(update_fields=["create"])
        with self.assertRaises(ResourcePermissionError):
            FolderService.create(
                self.principal,
                str(self.root.id),
                "child",
                CredentialSet.empty(),
            )
        self.assertFalse(Folder.objects.filter(parent=self.root, name="child").exists())

    @patch("website.services.folder_service.namespace_lock_service.lock_owner_scope_shared")
    def test_restore_accepts_only_the_explicit_trash_root(self, _lock_scope):
        trashed = Folder.objects.create(name="trashed", owner=self.user, parent=self.root)
        descendant = Folder.objects.create(name="descendant", owner=self.user, parent=trashed)
        TrashRoot.objects.create(folder=trashed, owner=self.user)

        with self.assertRaises(ResourcePermissionError):
            FolderService.restore(
                self.principal,
                str(descendant.id),
                CredentialSet.empty(),
            )

        FolderService.restore(
            self.principal,
            str(trashed.id),
            CredentialSet.empty(),
        )
        self.assertFalse(TrashRoot.objects.filter(folder=trashed).exists())


class NamespaceClassificationTests(TestCase):
    @patch("website.services.folder_service.namespace_lock_service.lock_owner_scope_shared")
    def test_classification_does_not_replace_command_ownership_check(self, _lock_scope):
        owner = User.objects.create_user(username="owner")
        other = User.objects.create_user(username="other")
        folder = Folder.objects.create(name="private", owner=other)

        refs = namespace_service.classify_item_ids([str(folder.id)])
        self.assertEqual(refs[0].type, "folder")

        with self.assertRaises(ResourceNotFoundError):
            namespace_service.rename(_principal(owner), str(folder.id), "changed", CredentialSet.empty())
        folder.refresh_from_db()
        self.assertEqual(folder.name, "private")
