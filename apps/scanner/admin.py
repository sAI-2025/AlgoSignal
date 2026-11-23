from django.contrib import admin

from apps.scanner.models import ScannerSetting


@admin.register(ScannerSetting)
class ScannerSettingAdmin(admin.ModelAdmin):
    list_display = (
        "short_period",
        "long_period",
        "lookback_days",
        "max_stocks",
        "auto_run_on_open",
        "updated_at",
    )
    readonly_fields = ("updated_at",)

    def has_add_permission(self, request):
        return not ScannerSetting.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
