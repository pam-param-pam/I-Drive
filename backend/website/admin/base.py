import base64

from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.template.defaultfilters import filesizeformat
from simple_history.admin import SimpleHistoryAdmin


class IDriveModelAdmin(admin.ModelAdmin):
    """Read-only admin; hex, base64 and readable_size replace named model fields.

    List displays can use the original field names and retain database sorting.
    A field may appear in multiple format lists to expose multiple encodings.
    """

    actions = None
    hex = ()
    base64 = ()
    readable_size = ()

    def __init__(self, model, admin_site):
        super().__init__(model, admin_site)
        self._formatted_fields = {}
        for fields, suffix, formatter in (
            (self.hex, "hex", lambda value: f"{value:08X}" if isinstance(value, int) else bytes(value).hex()),
            (self.base64, "base64", lambda value: base64.b64encode(value).decode("ascii")),
            (self.readable_size, "readable_size", filesizeformat),
        ):
            for field_name in fields:
                field = model._meta.get_field(field_name)
                display_name = f"{field_name}_{suffix}"
                if hasattr(self, display_name):
                    raise ValueError(f"Admin formatter conflicts with {display_name}")
                display = self._make_formatter(field_name, formatter)
                display.__name__ = display_name
                display = admin.display(
                    description=f"{field.verbose_name} ({suffix.replace('_', ' ')})",
                    ordering=field_name,
                )(display)
                setattr(self, display_name, display)
                self._formatted_fields.setdefault(field_name, []).append(display_name)

    @staticmethod
    def _make_formatter(field_name, formatter):
        def display(obj):
            value = getattr(obj, field_name)
            return None if value is None else formatter(value)
        return display

    def get_exclude(self, request, obj=None):
        return (*(super().get_exclude(request, obj) or ()), *self._formatted_fields)

    def get_readonly_fields(self, request, obj=None):
        fields = (field.name for field in (*self.model._meta.fields, *self.model._meta.many_to_many))
        return self._format_field_names((*super().get_readonly_fields(request, obj), *fields))

    def _format_field_names(self, fields):
        return tuple(dict.fromkeys(
            display for field in fields for display in self._formatted_fields.get(field, (field,))
        ))

    def get_list_display(self, request):
        return self._format_field_names(super().get_list_display(request))

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class IDriveHistoryAdmin(IDriveModelAdmin, SimpleHistoryAdmin):
    def has_change_history_permission(self, request, obj=None):
        return False

    def history_form_view(self, request, object_id, version_id, extra_context=None):
        if request.method == "POST":
            raise PermissionDenied
        return super().history_form_view(request, object_id, version_id, extra_context)
