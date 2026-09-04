from types import MethodType

from django.contrib import admin


ADMIN_MENU = (
    (
        "core",
        "Core",
        "core",
        (
            ("core", "ServerSetting", "Server Settings"),
            ("auth", "User", "Users"),
            ("accounts", "UserWebSession", "Web Session Management"),
            ("accounts", "UserClientSession", "Client Session Management"),
            ("accounts", "ClientLoginRequest", "Client Login Request"),
        ),
    ),
    (
        "library",
        "Library",
        "library",
        (
            ("library", "CatalogTag", "Catalog Tags"),
            ("library", "LibraryGroup", "Library Groups"),
            ("library", "Book", "Books"),
            ("library", "Author", "Authors"),
            ("library", "Series", "Series"),
        ),
    ),
    (
        "userdata",
        "UserData",
        "shelves",
        (
            ("shelves", "Shelf", "Shelves"),
            ("marginalia", "ReadingSession", "Reading Sessions"),
            ("marginalia", "ImportStage", "Import Stage Management"),
        ),
    ),
    (
        "maintenance",
        "Maintenance",
        "maintenance",
        (
            ("maintenance", "MaintenanceTaskConfig", "Tasks"),
            ("maintenance", "MaintenanceTaskRun", "Run Log"),
        ),
    ),
)

MENU_GROUP_BY_APP = {
    "accounts": "core",
    "auth": "core",
    "core": "core",
    "library": "library",
    "marginalia": "userdata",
    "shelves": "userdata",
    "maintenance": "maintenance",
}


def _arrange_admin_menu(app_list):
    apps = {app["app_label"]: app for app in app_list}
    models = {
        (app["app_label"], model["object_name"]): model
        for app in app_list
        for model in app["models"]
    }
    arranged = []
    for group_key, group_name, link_app_label, definitions in ADMIN_MENU:
        group_models = []
        for app_label, object_name, display_name in definitions:
            model = models.get((app_label, object_name))
            if model is None:
                continue
            item = dict(model)
            item["name"] = display_name
            group_models.append(item)
        if not group_models:
            continue
        link_app = apps.get(link_app_label)
        if link_app is None:
            link_app = next(
                apps[app_label]
                for app_label, object_name, _display_name in definitions
                if (app_label, object_name) in models
            )
        arranged.append(
            {
                "name": group_name,
                "app_label": group_key,
                "app_url": link_app["app_url"],
                "has_module_perms": True,
                "models": group_models,
            }
        )
    return arranged


def install_admin_menu():
    if hasattr(admin.site, "_secondpass_unarranged_get_app_list"):
        return

    admin.site._secondpass_unarranged_get_app_list = admin.site.get_app_list

    def get_app_list(self, request, app_label=None):
        app_list = self._secondpass_unarranged_get_app_list(request, None)
        arranged = _arrange_admin_menu(app_list)
        if app_label is None:
            return arranged
        group_key = MENU_GROUP_BY_APP.get(app_label, app_label)
        return [app for app in arranged if app["app_label"] == group_key]

    admin.site.get_app_list = MethodType(get_app_list, admin.site)
