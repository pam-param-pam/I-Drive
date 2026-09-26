from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch
from urllib.parse import parse_qs

from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import User
from django.test import TestCase as DjangoTestCase

from website.core.errors import BadRequestError, ResourceNotFoundError, ResourcePermissionError
from website.core.crypto.signer import sign_resource, verify_signed_resource_request
from website.models import DeletionScope, File, Folder, FolderLockPolicy, TrashRoot

from .actions import ResourceAction
from .authorizer import Authorizer
from .contexts import ContextSet, ResourceContext, ResourceContextResolver, ShareContext
from .credentials import CredentialSet
from .errors import PermissionPasswordError
from .policies import POLICIES, PolicyRegistry, ResourceRole, ResourceType
from .principals import PrincipalFactory, UserPrincipal


class _User:
    id = 7
    is_authenticated = True


class _AnonymousUser:
    is_authenticated = False


def _request(user=None):
    return SimpleNamespace(
        user=user or _User(),
        auth=SimpleNamespace(device_id="device-1"),
        context=SimpleNamespace(device_id="device-1", request_id="request-1"),
        META={"REMOTE_ADDR": "127.0.0.1"},
    )


def _context(**overrides):
    values = {
        "resource_type": ResourceType.FILE,
        "resource_id": "file-1",
        "role": ResourceRole.TARGET,
        "owner_id": 7,
        "parent_id": "folder-1",
        "direct_state": "active",
        "is_root_folder": False,
        "explicit_trash_root": False,
        "effective_trash_root_id": None,
        "effective_deletion_scope_id": None,
        "effective_lock_policy_id": None,
        "effective_lock_policy_name": None,
        "effective_lock_password_verifier": None,
        "resource_version": 3,
    }
    values.update(overrides)
    return ResourceContext(**values)


def _permissions(**overrides):
    values = {
        "globalLock": False,
        "admin": False,
        "read": True,
        "create": True,
        "modify": True,
        "delete": True,
        "share": True,
        "download": True,
        "lock": True,
        "reset_lock": True,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class PermissionApiTests(TestCase):
    def setUp(self):
        self.user_principal = PrincipalFactory.from_authenticated_request(_request())

    def test_principals_cannot_be_constructed_directly(self):
        with self.assertRaises(TypeError):
            UserPrincipal(7, "device", "request", "127.0.0.1")

    def test_policy_registry_is_complete(self):
        PolicyRegistry.validate_complete()
        self.assertEqual(set(ResourceAction), set(POLICIES))

    @patch("website.auth.permissions.authorizer.UserPerms.objects.get", return_value=_permissions())
    def test_authorization_result_does_not_expose_verifier(self, _get_permissions):
        context = _context(
            effective_lock_policy_id="folder-1",
            effective_lock_policy_name="Private",
            effective_lock_password_verifier=make_password("secret"),
        )
        result = Authorizer().authorize_user_action(
            self.user_principal,
            ResourceAction.READ,
            ContextSet((context,)),
            CredentialSet({"folder-1": "secret"}),
        )
        self.assertEqual(result.resources[0].effective_lock_policy_id, "folder-1")
        self.assertFalse(hasattr(result.resources[0], "password_verifier"))

    @patch("website.auth.permissions.authorizer.UserPerms.objects.get", return_value=_permissions())
    def test_bulk_lock_failures_are_deduplicated(self, _get_permissions):
        verifier = make_password("secret")
        contexts = ContextSet((
            _context(effective_lock_policy_id="folder-1", effective_lock_policy_name="Private", effective_lock_password_verifier=verifier),
            _context(resource_id="file-2", effective_lock_policy_id="folder-1", effective_lock_policy_name="Private", effective_lock_password_verifier=verifier),
        ))
        with self.assertRaises(PermissionPasswordError) as raised:
            Authorizer().authorize_user_action(self.user_principal, ResourceAction.READ, contexts)
        self.assertEqual(len(raised.exception.challenges), 1)

    @patch("website.auth.permissions.authorizer.UserPerms.objects.get", return_value=_permissions(read=False))
    def test_account_capability_is_enforced(self, _get_permissions):
        with self.assertRaises(ResourcePermissionError):
            Authorizer().authorize_user_action(
                self.user_principal,
                ResourceAction.READ,
                ContextSet((_context(),)),
            )
    def test_public_share_requires_matching_root_context(self):
        principal = PrincipalFactory.from_share_request(_request(_AnonymousUser()), "token")
        share = ShareContext(
            share_id="share-1",
            share_token="token",
            owner_id=7,
            root_type=ResourceType.FOLDER,
            root_id="folder-1",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            password_verifier=None,
        )
        wrong_root = _context(role=ResourceRole.SHARE_ROOT)
        with self.assertRaises(ResourceNotFoundError):
            Authorizer().authorize_share_action(
                principal,
                ResourceAction.READ_SHARE,
                share,
                ContextSet((wrong_root,)),
            )

    @patch("website.auth.permissions.authorizer.UserPerms.objects.get", return_value=_permissions())
    def test_search_can_authorize_account_before_candidates_are_loaded(self, _get_permissions):
        result = Authorizer().authorize_user_action(self.user_principal, ResourceAction.SEARCH)
        self.assertEqual(result.resources, ())

    @patch(
        "website.auth.permissions.authorizer.UserPerms.objects.get",
        return_value=_permissions(globalLock=True, change_password=True),
    )
    def test_change_password_remains_available_during_global_lock(self, _get_permissions):
        result = Authorizer().authorize_user_action(
            self.user_principal, ResourceAction.CHANGE_PASSWORD,
        )
        self.assertEqual(result.resources, ())

    @patch(
        "website.auth.permissions.authorizer.UserPerms.objects.get",
        return_value=_permissions(globalLock=True, settings_modify=True),
    )
    def test_global_lock_denies_normal_account_actions(self, _get_permissions):
        with self.assertRaises(ResourcePermissionError):
            Authorizer().authorize_user_action(
                self.user_principal, ResourceAction.MODIFY_SETTINGS,
            )

    @patch("website.auth.permissions.authorizer.UserPerms.objects.get", return_value=_permissions())
    def test_non_resource_action_rejects_contexts(self, _get_permissions):
        with self.assertRaises(BadRequestError):
            Authorizer().authorize_user_action(
                self.user_principal,
                ResourceAction.LIST_SHARES,
                ContextSet((_context(),)),
            )

    @patch("website.auth.permissions.authorizer.UserPerms.objects.get", return_value=_permissions())
    def test_restore_allows_an_explicit_trash_marker(self, _get_permissions):
        context = _context(
            explicit_trash_root=True,
            effective_trash_root_id="file-1",
        )
        result = Authorizer().authorize_user_action(
            self.user_principal,
            ResourceAction.RESTORE,
            ContextSet((context,)),
        )
        self.assertEqual(result.resources[0].resource_id, "file-1")

    @patch("website.auth.permissions.authorizer.UserPerms.objects.get", return_value=_permissions())
    def test_restore_rejects_an_inherited_trashed_descendant(self, _get_permissions):
        context = _context(
            explicit_trash_root=False,
            effective_trash_root_id="folder-1",
        )
        with self.assertRaises(ResourcePermissionError):
            Authorizer().authorize_user_action(
                self.user_principal,
                ResourceAction.RESTORE,
                ContextSet((context,)),
            )

    @patch("website.auth.permissions.authorizer.UserPerms.objects.get", return_value=_permissions())
    def test_list_trash_accepts_only_explicit_trash_roots(self, _get_permissions):
        explicit = _context(explicit_trash_root=True, effective_trash_root_id="file-1")
        Authorizer().authorize_user_action(
            self.user_principal, ResourceAction.LIST_TRASH, ContextSet((explicit,)),
        )
        inherited = _context(explicit_trash_root=False, effective_trash_root_id="folder-1")
        with self.assertRaises(ResourcePermissionError):
            Authorizer().authorize_user_action(
                self.user_principal, ResourceAction.LIST_TRASH, ContextSet((inherited,)),
            )


class SignedCapabilityTests(TestCase):
    def test_signature_is_bound_to_resource_version_and_purpose(self):
        path = "/files/file-1/thumbnail/thumb-1/stream"
        query = parse_qs(sign_resource(
            path,
            resource_id="file-1",
            resource_version=7,
            purpose="thumbnail",
        ).removeprefix("?"))
        request = SimpleNamespace(
            path_info=path,
            GET={key: values[0] for key, values in query.items()},
            META={"REMOTE_ADDR": "127.0.0.1"},
        )
        claims = verify_signed_resource_request(request, "file-1", "thumbnail")
        self.assertEqual(claims["resource_version"], 7)
        self.assertEqual(claims["purpose"], "thumbnail")

    def test_signature_cannot_be_reused_for_another_purpose(self):
        path = "/files/file-1/stream"
        query = parse_qs(sign_resource(
            path,
            resource_id="file-1",
            resource_version=7,
            purpose="file_download",
        ).removeprefix("?"))
        request = SimpleNamespace(
            path_info=path,
            GET={key: values[0] for key, values in query.items()},
            META={"REMOTE_ADDR": "127.0.0.1"},
        )
        from website.core.errors import URLInvalidOrExpired
        with self.assertRaises(URLInvalidOrExpired):
            verify_signed_resource_request(request, "file-1", "thumbnail")


class ResourceContextResolverTests(DjangoTestCase):
    def test_file_context_contains_inherited_namespace_facts(self):
        owner = User.objects.create_user(username="owner")
        root = Folder.objects.create(name="root", owner=owner)
        locked_folder = Folder.objects.create(name="locked", owner=owner, parent=root)
        file_obj = File.objects.create(
            name="document.txt",
            extension=".txt",
            size=1,
            type="Text",
            parent=locked_folder,
            owner=owner,
            encryption_method=0,
            frontend_id="frontend-1",
        )
        FolderLockPolicy.objects.create(
            folder=locked_folder,
            owner=owner,
            password_verifier=make_password("secret"),
        )
        TrashRoot.objects.create(folder=locked_folder, owner=owner)
        deletion_scope = DeletionScope.objects.create(owner=owner, root_folder=locked_folder)

        context = ResourceContextResolver().resolve_file(file_obj.id, owner.id)

        self.assertEqual(context.resource_id, str(file_obj.id))
        self.assertEqual(context.effective_lock_policy_id, str(locked_folder.id))
        self.assertEqual(context.effective_trash_root_id, str(locked_folder.id))
        self.assertEqual(context.effective_deletion_scope_id, str(deletion_scope.id))
        self.assertFalse(context.explicit_trash_root)
        self.assertEqual(context.resource_version, file_obj.resource_version)
