from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _

PLUGIN_NAME = "care_demo_facility_setup"


class CareDemoFacilitySetupConfig(AppConfig):
    name = PLUGIN_NAME
    verbose_name = _("Care demo facility setup")

    def ready(self):
        import care_demo_facility_setup.signals  # noqa F401
