"""
Centralized multi-tenancy (hospital-scoping) for MedSync.

Usage on a model:
    class MyModel(models.Model):
        tenant_field = "hospital"        # or "registered_at", "record__hospital", "facility"
        tenant_objects = TenantManager()
        ...

    # In a view:
    MyModel.tenant_objects.for_request(request)         # auto view-as-aware
    MyModel.tenant_objects.for_user(user, hospital)     # explicit hospital

The manager is a *second* (non-default) manager; `objects` is unchanged, so
Django generates no migrations for adding it.

Super-admin scoping matrix (preserved from existing helpers):
  role == super_admin AND no hospital AND no view-as  →  unfiltered
  role == super_admin AND view-as header              →  scoped to the granted hospital
  role == super_admin WITH own hospital               →  treated as a normal user
  any other role                                      →  own hospital, else .none()
"""

from django.db import models


class TenantQuerySet(models.QuerySet):
    def for_request(self, request):
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return self.none()
        # Lazy import avoids circular imports (api.utils imports from models).
        from api.utils import get_effective_hospital
        effective_hospital = get_effective_hospital(request)
        return self.for_user(user, effective_hospital)

    def for_user(self, user, effective_hospital=None):
        from api.utils import _scope_hospital
        hospital = _scope_hospital(user, effective_hospital)
        if user.role == "super_admin" and user.hospital_id is None and hospital is None:
            return self
        if hospital is None:
            return self.none()
        tenant_field = getattr(self.model, "tenant_field", "hospital")
        return self.filter(**{tenant_field: hospital})


class TenantManager(models.Manager):
    use_in_migrations = False  # no schema change — pure Python addition

    def get_queryset(self):
        return TenantQuerySet(self.model, using=self._db)

    def for_request(self, request):
        return self.get_queryset().for_request(request)

    def for_user(self, user, effective_hospital=None):
        return self.get_queryset().for_user(user, effective_hospital)
