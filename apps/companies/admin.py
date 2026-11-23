from django.contrib import admin

from apps.companies.models import Company, CompanyProfile, IndexMembership


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ("nse_code", "company_name", "sector", "industry", "is_active")
    search_fields = ("nse_code", "company_name", "isin")
    list_filter = ("is_active", "sector")
    ordering = ("company_name",)


@admin.register(IndexMembership)
class IndexMembershipAdmin(admin.ModelAdmin):
    list_display = ("company", "index_code", "effective_from", "effective_to", "imported_at")
    search_fields = ("company__nse_code", "index_code")
    list_filter = ("index_code", "effective_to")


@admin.register(CompanyProfile)
class CompanyProfileAdmin(admin.ModelAdmin):
    list_display = ("company", "source_name", "verified_on", "updated_at")
    search_fields = ("company__nse_code", "company__company_name")
