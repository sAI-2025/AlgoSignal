from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.core.models import TimeStampedModel


class Company(TimeStampedModel):
    company_name = models.CharField(max_length=200, db_index=True)
    nse_code = models.CharField(max_length=20, unique=True, db_index=True)
    bse_code = models.CharField(max_length=10, null=True, blank=True)
    isin = models.CharField(max_length=12, null=True, blank=True, unique=True)
    sector = models.CharField(max_length=100, null=True, blank=True)
    industry = models.CharField(max_length=150, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ["company_name"]

    def __str__(self) -> str:
        return f"{self.nse_code} - {self.company_name}"


class IndexMembership(models.Model):
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="index_memberships",
    )
    index_code = models.CharField(max_length=30)
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    source_url = models.URLField(max_length=500, blank=True)
    source_sha256 = models.CharField(max_length=64, blank=True)
    imported_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["company", "index_code", "effective_from"],
                name="uq_index_membership_snapshot",
            ),
            models.UniqueConstraint(
                fields=["company", "index_code"],
                condition=Q(effective_to__isnull=True),
                name="uq_index_membership_current_only",
            ),
        ]
        indexes = [
            models.Index(fields=["index_code", "effective_to"]),
        ]

    def __str__(self) -> str:
        return f"{self.company.nse_code} in {self.index_code}"


class CompanyProfile(TimeStampedModel):
    company = models.OneToOneField(
        Company,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    business_summary = models.TextField(null=True, blank=True)
    products = models.TextField(null=True, blank=True)
    services = models.TextField(null=True, blank=True)
    website = models.URLField(max_length=500, null=True, blank=True)
    source_name = models.CharField(max_length=100, null=True, blank=True)
    source_url = models.URLField(max_length=500, null=True, blank=True)
    verified_on = models.DateField(null=True, blank=True)

    def __str__(self) -> str:
        return f"Profile for {self.company.nse_code}"
