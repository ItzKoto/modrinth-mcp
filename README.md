# Modrinth MCP

A small [MCP](https://modelcontextprotocol.io) server that lets Claude manage your [Modrinth](https://modrinth.com) projects: create projects, publish new versions, and edit existing ones. It's a single Python file that runs locally over stdio.

## Tools

| Tool | What it does |
| --- | --- |
| `modrinth_create_project` | Create a new project as a private draft (optional icon upload) |
| `modrinth_update_project` | Edit a project's title, short description, or long Markdown body |
| `modrinth_create_version` | Upload files and publish a new version to a project |
| `modrinth_update_version` | Edit a version's name, changelog, version number, type, or featured flag |
| `modrinth_list_versions` | List a project's versions (id, name, number, type, date) |

Errors from the Modrinth API are returned as text, so Claude can see the real message instead of a generic tool failure.

## Setup

1. Install dependencies (Python 3.10+):

   ```bash
   pip install -r requirements.txt
   ```

2. Create a personal access token at <https://modrinth.com/settings/pats> with these scopes:
   - Create projects
   - Create versions
   - Write projects
   - Write versions

3. Set the token as an environment variable:

   ```bash
   # macOS / Linux
   export MODRINTH_TOKEN=mrp_xxxxxxxx

   # Windows (PowerShell)
   $env:MODRINTH_TOKEN = "mrp_xxxxxxxx"
   ```

4. Run it (stdio transport):

   ```bash
   python modrinth_mcp.py
   ```

## Claude Desktop

Add this to `claude_desktop_config.json` (Settings → Developer → Edit Config), then restart Claude Desktop:

```json
{
  "mcpServers": {
    "modrinth": {
      "command": "python",
      "args": ["/path/to/modrinth_mcp.py"],
      "env": { "MODRINTH_TOKEN": "mrp_xxxxxxxx" }
    }
  }
}
```

On Windows, use a full path with escaped backslashes, e.g. `"C:\\Users\\you\\modrinth-mcp\\modrinth_mcp.py"`.

## Usage notes

- New projects are created as **drafts**. They stay private until you upload a version and submit the project for review on Modrinth.
- `modrinth_create_version` takes local file paths; the first file is the primary one.
- `project_type` is one of `mod`, `modpack`, `resourcepack`, `shader`, `plugin`, `datapack`.
- `license_id` takes an SPDX id such as `MIT` or `Apache-2.0`.

## Security

Never commit your token. Keep `MODRINTH_TOKEN` in your environment or in your Claude Desktop config, and revoke it from the Modrinth settings page if it leaks.

## License

MIT, see [LICENSE](LICENSE).
