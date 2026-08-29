from __future__ import annotations

from dataclasses import dataclass

from care_demo_facility_setup.models import SeedRun
from care_demo_facility_setup.services.care_seed_client import CareSeedClient
from care_demo_facility_setup.services.seed_artifacts import SeedArtifactStore


@dataclass(frozen=True)
class SeedContext:
    """Read-only inputs shared by every seed step executor.

    The runner builds one context per run and injects it into each executor, so
    seeders depend on these capabilities/data instead of the runner itself.
    """

    client: CareSeedClient
    artifacts: SeedArtifactStore
    geo_organization: str
    run: SeedRun
    pack: dict
    profile: dict


@dataclass(frozen=True)
class SeedResult:
    """The outcome of a single seed step: a human-readable message plus stats."""

    message: str
    stats: dict
