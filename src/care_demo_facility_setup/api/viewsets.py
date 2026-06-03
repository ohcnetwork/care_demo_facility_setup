from django.db import transaction

from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework.viewsets import GenericViewSet

from care_demo_facility_setup.models import SeedRun
from care_demo_facility_setup.models import SeedRunStatus
from care_demo_facility_setup.services.seed_packs import (
    DEFAULT_PACK_SLUG,
    SeedPackError,
    list_profiles,
    list_seed_packs,
    validate_seed_request,
)
from care_demo_facility_setup.services.seed_runs import (
    create_seed_run,
    enqueue_seed_run,
    serialize_seed_run,
)


class BaseViewSet(GenericViewSet):
    permission_classes = [IsAuthenticated]

    def _current_host(self, request) -> str:
        return request.get_host().split(":", 1)[0]

    @action(detail=False, methods=["get"])
    def hello(self, request, *args, **kwargs):
        return Response({"message": "Hello from care_demo_facility_setup plugin!"})

    @action(detail=False, methods=["get"], url_path="seed-packs")
    def seed_packs(self, request, *args, **kwargs):
        return Response({"results": list_seed_packs()})

    @action(detail=False, methods=["get"], url_path="profiles")
    def profiles(self, request, *args, **kwargs):
        pack_slug = request.query_params.get("pack_slug") or DEFAULT_PACK_SLUG
        try:
            return Response({"results": list_profiles(pack_slug)})
        except SeedPackError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=False, methods=["post"], url_path="validate")
    def validate(self, request, *args, **kwargs):
        result = validate_seed_request(
            pack_slug=request.data.get("pack_slug") or DEFAULT_PACK_SLUG,
            profile_slug=request.data.get("profile_slug") or "demo",
            care_base_url=request.data.get("care_base_url"),
            current_host=self._current_host(request),
        )
        response_status = status.HTTP_200_OK if result.valid else status.HTTP_400_BAD_REQUEST
        return Response(result.to_dict(), status=response_status)

    @action(detail=False, methods=["get", "post"], url_path="runs")
    def runs(self, request, *args, **kwargs):
        if request.method == "POST":
            if not request.user.is_superuser:
                return Response(
                    {"detail": "Only superusers can create demo seed runs."},
                    status=status.HTTP_403_FORBIDDEN,
                )
            run = create_seed_run(
                request_payload=request.data,
                requested_by=request.user,
                current_host=self._current_host(request),
            )
            if run.status == SeedRunStatus.QUEUED:
                transaction.on_commit(lambda run_external_id=str(run.external_id): enqueue_seed_run(run_external_id))
                run.refresh_from_db()
            response_status = (
                status.HTTP_201_CREATED if run.status != "validation_failed" else status.HTTP_400_BAD_REQUEST
            )
            return Response(serialize_seed_run(run, include_details=True), status=response_status)

        runs = SeedRun.objects.prefetch_related("steps", "artifacts").all()[:50]
        return Response({"results": [serialize_seed_run(run) for run in runs]})

    @action(
        detail=False,
        methods=["get"],
        url_path=r"runs/(?P<external_id>[0-9a-f-]+)",
    )
    def run_detail(self, request, external_id=None, *args, **kwargs):
        try:
            run = SeedRun.objects.prefetch_related("steps", "artifacts").get(external_id=external_id)
        except SeedRun.DoesNotExist:
            return Response({"detail": "Seed run not found"}, status=status.HTTP_404_NOT_FOUND)
        return Response(serialize_seed_run(run, include_details=True))
