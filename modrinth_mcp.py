"""Modrinth MCP server.

Setup:
    pip install "mcp[cli]" httpx
    export MODRINTH_TOKEN=mrp_xxxxxxxx   # Personal access token from modrinth.com/settings/pats
                                         # (needs Create projects, Create versions,
                                         #  Write projects, Write versions scopes)
    python modrinth_mcp.py               # stdio transport

Claude Desktop config (claude_desktop_config.json):
    {
      "mcpServers": {
        "modrinth": {
          "command": "python",
          "args": ["/path/to/modrinth_mcp.py"],
          "env": { "MODRINTH_TOKEN": "mrp_xxxxxxxx" }
        }
      }
    }
"""
import functools
import inspect
import json
import os
from pathlib import Path

import httpx
from mcp.server.mcpserver import MCPServer

API = "https://api.modrinth.com/v2"
UA = "modrinth-mcp/0.1 (personal MCP server)"

mcp = MCPServer("modrinth")


def safe(fn):
    """Return errors as text (so Claude can see Modrinth's real message) and
    always return a string, instead of the generic 'Error executing tool'."""

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            result = fn(*args, **kwargs)
        except Exception as e:  # noqa: BLE001
            return f"ERROR ({type(e).__name__}): {e}"
        return result if isinstance(result, str) else json.dumps(result, indent=2)

    wrapper.__signature__ = inspect.signature(fn).replace(return_annotation=str)
    wrapper.__annotations__ = {**fn.__annotations__, "return": str}
    return wrapper


def _headers() -> dict:
    token = os.environ.get("MODRINTH_TOKEN")
    if not token:
        raise RuntimeError("MODRINTH_TOKEN environment variable is not set")
    return {"Authorization": token, "User-Agent": UA}


def _check(r: httpx.Response) -> dict | list | str:
    if r.status_code >= 400:
        raise RuntimeError(f"Modrinth API error {r.status_code}: {r.text}")
    return r.json() if r.content else "OK"


@mcp.tool()
@safe
def modrinth_create_project(
    title: str,
    slug: str,
    summary: str,
    body: str,
    project_type: str = "mod",
    categories: list[str] | None = None,
    additional_categories: list[str] | None = None,
    client_side: str = "unknown",
    server_side: str = "unknown",
    license_id: str = "LicenseRef-All-Rights-Reserved",
    icon_path: str | None = None,
) -> dict:
    """Create a new Modrinth project as a private draft.

    project_type: mod | modpack | resourcepack | shader | plugin | datapack.
    summary: short description (max 256 chars). body: long Markdown description.
    client_side / server_side: required | optional | unsupported | unknown.
    license_id: SPDX id such as "MIT", "Apache-2.0", "LGPL-3.0-only".
    icon_path: optional local png/jpg/gif/webp file (max 256 KiB).
    The project stays a draft until you upload a version and submit it for review.
    """
    payload = {
        "slug": slug,
        "title": title,
        "description": summary,
        "body": body,
        "project_type": project_type,
        "categories": categories or [],
        "additional_categories": additional_categories or [],
        "client_side": client_side,
        "server_side": server_side,
        "license_id": license_id,
        "is_draft": True,
        "initial_versions": [],
    }
    files = [("data", (None, json.dumps(payload), "application/json"))]
    icon_fh = None
    try:
        if icon_path:
            p = Path(icon_path).expanduser()
            if not p.is_file():
                raise FileNotFoundError(f"Icon not found: {p}")
            icon_fh = open(p, "rb")
            files.append(("icon", (p.name, icon_fh, "application/octet-stream")))
        with httpx.Client(timeout=60) as c:
            return _check(c.post(f"{API}/project", headers=_headers(), files=files))
    finally:
        if icon_fh:
            icon_fh.close()


@mcp.tool()
@safe
def modrinth_list_versions(project_id: str) -> list:
    """List versions of a project (id or slug). Returns id, name, version_number, type, date."""
    with httpx.Client(timeout=30) as c:
        data = _check(c.get(f"{API}/project/{project_id}/version", headers=_headers()))
    return [
        {
            "id": v["id"],
            "name": v["name"],
            "version_number": v["version_number"],
            "version_type": v["version_type"],
            "date_published": v["date_published"],
        }
        for v in data
    ]


@mcp.tool()
@safe
def modrinth_create_version(
    project_id: str,
    name: str,
    version_number: str,
    changelog: str,
    game_versions: list[str],
    loaders: list[str],
    file_paths: list[str],
    version_type: str = "release",
    featured: bool = False,
    dependencies: list[dict] | None = None,
) -> dict:
    """Publish a new version (an 'update') to a Modrinth project.

    game_versions: e.g. ["1.21.1"]. loaders: e.g. ["fabric", "neoforge"].
    file_paths: local paths to the jar/zip files; the first is the primary file.
    version_type: release | beta | alpha.
    dependencies: optional list like [{"project_id": "...", "dependency_type": "required"}].
    """
    paths = [Path(p).expanduser() for p in file_paths]
    for p in paths:
        if not p.is_file():
            raise FileNotFoundError(f"File not found: {p}")

    part_names = [f"file{i}" for i in range(len(paths))]
    payload = {
        "project_id": project_id,
        "name": name,
        "version_number": version_number,
        "changelog": changelog,
        "dependencies": dependencies or [],
        "game_versions": game_versions,
        "version_type": version_type,
        "loaders": loaders,
        "featured": featured,
        "status": "listed",
        "file_parts": part_names,
        "primary_file": part_names[0],
    }
    files = [("data", (None, json.dumps(payload), "application/json"))]
    handles = []
    try:
        for part, p in zip(part_names, paths):
            fh = open(p, "rb")
            handles.append(fh)
            files.append((part, (p.name, fh, "application/octet-stream")))
        with httpx.Client(timeout=300) as c:
            return _check(c.post(f"{API}/version", headers=_headers(), files=files))
    finally:
        for fh in handles:
            fh.close()


@mcp.tool()
@safe
def modrinth_update_version(
    version_id: str,
    name: str | None = None,
    changelog: str | None = None,
    version_number: str | None = None,
    version_type: str | None = None,
    featured: bool | None = None,
) -> str:
    """Edit an existing version (e.g. fix its changelog). Only provided fields change."""
    body = {
        k: v
        for k, v in {
            "name": name,
            "changelog": changelog,
            "version_number": version_number,
            "version_type": version_type,
            "featured": featured,
        }.items()
        if v is not None
    }
    if not body:
        return "Nothing to update."
    with httpx.Client(timeout=30) as c:
        r = c.patch(f"{API}/version/{version_id}", headers=_headers(), json=body)
    return _check(r)


@mcp.tool()
@safe
def modrinth_update_project(
    project_id: str,
    body: str | None = None,
    description: str | None = None,
    title: str | None = None,
) -> str:
    """Edit a project page. body = long Markdown description, description = short summary."""
    patch = {
        k: v
        for k, v in {"body": body, "description": description, "title": title}.items()
        if v is not None
    }
    if not patch:
        return "Nothing to update."
    with httpx.Client(timeout=30) as c:
        r = c.patch(f"{API}/project/{project_id}", headers=_headers(), json=patch)
    return _check(r)


if __name__ == "__main__":
    mcp.run()
