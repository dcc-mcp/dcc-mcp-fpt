# Install dcc-mcp-fpt

This adapter is a standalone service. It does not install anything into a DCC
application. The Python wheel owns the MCP server; a version-pinned `fpt`
binary owns bounded ShotGrid API commands.

## Requirements

- Python 3.8 or newer.
- `dcc-mcp-core` 0.19.45 or newer and below 1.0.
- Network access to the operator's Autodesk Flow Production Tracking endpoint.
- One operator-owned authentication mode: an `fpt` profile, script user,
  user/password, or session token.
- A `SHOTGRID_PERMISSION_LEVEL` policy ceiling of `read`, `write`, or `admin`.

Secrets belong in the OS credential store, a local secret manager, or process
environment. Never put passwords, API keys, or session tokens in MCP arguments,
repository files, logs, or receipts.

## Supported versions and platforms

| Platform | Python | Pinned `fpt` asset |
| --- | --- | --- |
| Windows x86-64 | 3.8-3.12 | `x86_64-pc-windows-msvc` |
| macOS Apple silicon | 3.8-3.12 | `aarch64-apple-darwin` |
| macOS Intel | 3.8-3.12 | `x86_64-apple-darwin` |
| Linux x86-64 | 3.8-3.12 | `x86_64-unknown-linux-gnu` |

The adapter currently pins `fpt` 0.2.25. Unsupported architectures must use an
operator-managed binary through `DCC_MCP_FPT_CLI_PATH`; the adapter never
scrapes a mutable "latest" download.

## Agent quick path

Install the published wheel into the Python environment that will own the
standalone service:

```bash
python -m pip install "dcc-mcp-fpt"
dcc-mcp-fpt doctor --json
```

`doctor` is read-only. It reports binary provenance, checksum state, Core and
`fpt` versions, configuration and credential-presence booleans, the effective
permission ceiling, connectivity, `directly_usable`, and machine-executable
`next_steps`.

After configuring credentials, run the usable-state check:

```bash
dcc-mcp-fpt verify --json
```

`verify` may populate or repair only the immutable pinned `fpt` cache. It
downloads the exact release asset and its release checksum manifest, verifies
SHA-256 before extraction, stages the executable and digest record in the same
directory, and atomically replaces the cache entry. It never provisions an
explicit `DCC_MCP_FPT_CLI_PATH` override.

Exit codes are stable:

| Code | Meaning |
| --- | --- |
| `0` | Versions, configuration, permission policy, and connectivity passed |
| `10` | Local preflight failed: binary, checksum, version, or configuration |
| `40` | Preflight passed but the bounded authentication/connectivity check failed |

The JSON output never returns credential values or raw child-process output.

## Manual path

Prefer a secure local profile because `fpt` stores its secret in the operating
system credential store:

```bash
fpt auth login --profile example-profile \
  --site https://example.shotgrid.autodesk.com \
  --auth-mode user-password \
  --username artist@example.com \
  --open-browser
```

Configure only the profile reference and bounded policy in the adapter process:

```bash
export SHOTGRID_URL="https://example.shotgrid.autodesk.com"
export SHOTGRID_FPT_PROFILE="example-profile"
export SHOTGRID_PERMISSION_LEVEL="read"
dcc-mcp-fpt verify --json
```

On Windows PowerShell, use `$env:NAME = "value"`. A script-user deployment can
instead set `SHOTGRID_SCRIPT_NAME` and `SHOTGRID_SCRIPT_KEY`; user/password and
session-token modes use the variables documented in the main README. Diagnostics
report only whether the required values are present.

An operator-managed binary is an explicit trust boundary:

```bash
export DCC_MCP_FPT_CLI_PATH="/opt/studio/bin/fpt"
dcc-mcp-fpt verify --json
```

The JSON report marks this provenance as `explicit_override` and does not claim
the adapter verified its checksum. The executable must still satisfy the `fpt`
version floor and the typed authentication check.

## Run modes

Start the default HTTP service and local gateway:

```bash
dcc-mcp-fpt http
```

Run without gateway registration or use stdio:

```bash
dcc-mcp-fpt http --no-gateway
dcc-mcp-fpt stdio --no-gateway
```

ASGI remains available for an operator-managed process server:

```bash
uvicorn dcc_mcp_fpt.asgi:app --host 127.0.0.1 --port 8000
```

For Docker, build the repository image and inject configuration at runtime:

```bash
docker build -t dcc-mcp-fpt .
docker run --rm -p 9765:9765 --env-file .env dcc-mcp-fpt
```

Do not bake secrets into an image. Mount credential/profile stores using the
platform's secret mechanism when profile authentication is required.

The adapter invokes `fpt` as a bounded synchronous child for one typed command
at a time. It does not own a resident binary daemon, generic child supervisor,
thread pump, or job registry. Core sidecar launch/wait helpers therefore do not
match this process lifetime; the MCP server and gateway continue to use Core's
public lifecycle.

## Verify

Run both surfaces after installation or configuration changes:

```bash
dcc-mcp-fpt doctor --json
dcc-mcp-fpt verify --json
```

`directly_usable: true` requires all of the following:

1. Compatible Core and `fpt` versions.
2. A present executable with acceptable provenance; pinned cache entries must
   match their local digest record.
3. An endpoint and complete selected credential mode.
4. A valid permission ceiling.
5. A successful bounded `fpt auth test --output json` call.

No real ShotGrid CRUD is performed by doctor or verify.

## Cache and integrity

Pinned entries use these per-user roots:

- Windows: `%LOCALAPPDATA%\dcc-mcp-fpt\fpt\0.2.25\<asset>\`
- Linux/macOS: `${XDG_CACHE_HOME:-~/.cache}/dcc-mcp-fpt/fpt/0.2.25/<asset>/`

The executable is accompanied by `<executable>.sha256`. A missing or mismatched
record makes the cache unusable. `verify` re-downloads only the fixed versioned
asset and checks the upstream `fpt-checksums.txt` entry before replacement.
Checksum mismatch, missing manifest entry, download failure, and unsupported
platform all fail closed; no unverified payload is executed.

## Upgrade

Stop the adapter process, upgrade the wheel, and verify again:

```bash
python -m pip install --upgrade "dcc-mcp-fpt"
dcc-mcp-fpt verify --json
```

An adapter release changes `FPT_VERSION` only alongside reviewed asset names and
the immutable release checksum manifest. A new pin uses a new version directory;
it never overwrites the previous version with a mutable CDN or "latest" URL.
After successful verification, old version directories may be removed manually.

## Uninstall and cleanup

Stop all `dcc-mcp-fpt` processes before cleanup. Remove the Python wheel:

```bash
python -m pip uninstall dcc-mcp-fpt
```

The `fpt` cache is adapter-owned and contains executables, not credentials. To
reclaim space, delete the exact version directory shown above, or the enclosing
`dcc-mcp-fpt/fpt` directory after confirming no installed adapter uses it.

Credential profiles are separate. Remove one explicitly through the OS-backed
credential command before deleting local profile metadata:

```bash
fpt auth logout --profile example-profile
```

Uninstall never scans for or deletes unrelated Python environments, credential
stores, Docker volumes, or operator-managed binaries.

## Troubleshooting

### Exit 10: binary missing or checksum failed

- If `provenance` is `explicit_override`, confirm the configured file exists
  and is executable, or unset `DCC_MCP_FPT_CLI_PATH`.
- For `pinned_cache`, run `verify` to perform a fixed-version, checksum-verified
  repair. If the cache remains invalid, remove only the reported version
  directory and retry.
- A checksum mismatch is not a reason to disable validation or fetch "latest".

### Exit 10: version floor failed

Upgrade the wheel/Core environment. For an operator-managed `fpt`, install a
compatible release and rerun `doctor`. The report includes detected and minimum
versions without including local secrets.

### Exit 10: configuration or permission failed

Confirm `SHOTGRID_URL` and every variable required by the selected auth mode.
Set `SHOTGRID_PERMISSION_LEVEL` to `read`, `write`, or `admin`; begin with
`read`. A permission hint may reduce this ceiling but cannot elevate it.

### Exit 40: authentication or connectivity failed

- Refresh a profile with `fpt auth login --profile <name>` and complete any
  browser/PAT step as the human operator.
- Confirm DNS, TLS, proxy/firewall policy, and endpoint reachability.
- Confirm the FPT account is active and has permission for the target project.
- Run `fpt auth test --output json` locally. Do not paste its raw output into a
  public issue if it contains endpoint, identity, or credential details.

No live service verification is performed in CI because credentials and an FPT
tenant are not available there. CI uses deterministic process-boundary fakes to
prove schema, exit codes, checksum/cache integrity, and secret redaction.

## Catalog handoff

The Core catalog should point `instructions_url` at:

`https://raw.githubusercontent.com/dcc-mcp/dcc-mcp-fpt/main/install.md`

That catalog change is owned by the Core repository and is intentionally not
claimed by this adapter change.
