from __future__ import annotations

import json
from importlib import resources

PACKAGE = "care_demo_facility_setup.seed_packs"
DEFAULT_PACK_SLUG = "generic_hospital_v1"


class SeedPackError(ValueError):
    pass


def _pack_root(pack_slug: str):
    try:
        return resources.files(PACKAGE).joinpath(pack_slug)
    except ModuleNotFoundError as exc:
        raise SeedPackError("Seed pack package data is not available") from exc


def _load_json(path) -> dict | list:
    if not path.is_file():
        raise SeedPackError(f"Missing seed pack file: {path.name}")
    return json.loads(path.read_text(encoding="utf-8"))


def list_seed_packs() -> list[dict]:
    package_root = resources.files(PACKAGE)
    packs = []
    for pack_dir in package_root.iterdir():
        if not pack_dir.is_dir():
            continue
        manifest_path = pack_dir.joinpath("manifest.json")
        if not manifest_path.is_file():
            continue
        manifest = _load_json(manifest_path)
        packs.append(
            {
                "slug": manifest["slug"],
                "name": manifest["name"],
                "version": manifest["version"],
                "description": manifest.get("description", ""),
                "counts": manifest.get("counts", {}),
            }
        )
    return sorted(packs, key=lambda pack: pack["slug"])


def load_seed_pack(pack_slug: str = DEFAULT_PACK_SLUG) -> dict:
    pack_root = _pack_root(pack_slug)
    manifest = _load_json(pack_root.joinpath("manifest.json"))
    resources_config = manifest.get("resources", {})
    pack = {"manifest": manifest}
    for resource_key, resource_path in resources_config.items():
        pack[resource_key] = _load_json(pack_root.joinpath(resource_path))
    return pack


def list_profiles(pack_slug: str = DEFAULT_PACK_SLUG) -> list[dict]:
    pack_root = _pack_root(pack_slug)
    manifest = _load_json(pack_root.joinpath("manifest.json"))
    profiles_dir = pack_root.joinpath(manifest.get("profiles_dir", "profiles"))
    profiles = []
    if not profiles_dir.is_dir():
        return profiles
    for profile_path in profiles_dir.iterdir():
        if profile_path.name.endswith(".json"):
            profile = _load_json(profile_path)
            profiles.append(
                {
                    "slug": profile["slug"],
                    "name": profile["name"],
                    "description": profile.get("description", ""),
                    "allowed_hosts": profile.get("allowed_hosts", []),
                }
            )
    return sorted(profiles, key=lambda profile: profile["slug"])


def load_profile(pack_slug: str, profile_slug: str) -> dict:
    pack_root = _pack_root(pack_slug)
    manifest = _load_json(pack_root.joinpath("manifest.json"))
    profile_path = pack_root.joinpath(
        manifest.get("profiles_dir", "profiles"),
        f"{profile_slug}.json",
    )
    profile = _load_json(profile_path)
    if profile.get("slug") != profile_slug:
        raise SeedPackError("Profile slug does not match the requested profile")
    return profile
