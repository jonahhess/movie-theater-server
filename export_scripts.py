import json

from admin.main import admin
from main_site.main import app as main_site_app
from tickets.main import tickets


def export_all_specs():
    apps = {
        "main_openapi.json": main_site_app,
        "admin_openapi.json": admin,
        "tickets_openapi.json": tickets,
    }
    
    for filename, app_instance in apps.items():
        with open(filename, "w", encoding="utf-8") as f:
            # Generate and dump the schema for each specific app
            json.dump(app_instance.openapi(), f, indent=2)
        print(f"Exported {filename}")


if __name__ == "__main__":
    export_all_specs()
