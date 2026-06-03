from django.contrib import admin

from care_demo_facility_setup.models import SeedRun, SeedRunArtifact, SeedRunStep


class SeedRunStepInline(admin.TabularInline):
    model = SeedRunStep
    extra = 0
    readonly_fields = ("external_id", "created_date", "modified_date")


class SeedRunArtifactInline(admin.TabularInline):
    model = SeedRunArtifact
    extra = 0
    readonly_fields = ("external_id", "created_date", "modified_date")


@admin.register(SeedRun)
class SeedRunAdmin(admin.ModelAdmin):
    list_display = ("external_id", "pack_slug", "profile_slug", "status", "dry_run", "created_date")
    list_filter = ("status", "dry_run", "pack_slug", "profile_slug")
    search_fields = ("external_id", "pack_slug", "profile_slug", "error")
    readonly_fields = ("external_id", "created_date", "modified_date")
    inlines = (SeedRunStepInline, SeedRunArtifactInline)


@admin.register(SeedRunStep)
class SeedRunStepAdmin(admin.ModelAdmin):
    list_display = ("external_id", "run", "order", "key", "status")
    list_filter = ("status", "key")
    search_fields = ("external_id", "key", "title", "message")
    readonly_fields = ("external_id", "created_date", "modified_date")


@admin.register(SeedRunArtifact)
class SeedRunArtifactAdmin(admin.ModelAdmin):
    list_display = ("external_id", "run", "ref", "resource_type", "resource_external_id", "slug")
    list_filter = ("resource_type",)
    search_fields = ("external_id", "ref", "resource_type", "resource_external_id", "slug")
    readonly_fields = ("external_id", "created_date", "modified_date")
