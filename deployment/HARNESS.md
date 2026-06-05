# Deploying dcc-mcp-fpt on Harness

dcc-mcp-fpt can be deployed as a Harness service or integrated into Harness
CI/CD pipelines for automated testing and deployment.

## Docker Deployment

### Image Build

```dockerfile
FROM python:3.11-slim
# ... (use the included Dockerfile)
```

Build and push to your Harness-connected registry:

```bash
docker build -t dcc-mcp-fpt .
docker tag dcc-mcp-fpt <registry>/dcc-mcp-fpt:latest
docker push <registry>/dcc-mcp-fpt:latest
```

### Harness Service Definition

```yaml
service:
  name: dcc-mcp-fpt
  type: Kubernetes
  spec:
    manifests:
      - kind: Deployment
        apiVersion: apps/v1
        metadata:
          name: dcc-mcp-fpt
        spec:
          replicas: 1
          selector:
            matchLabels:
              app: dcc-mcp-fpt
          template:
            metadata:
              labels:
                app: dcc-mcp-fpt
            spec:
              containers:
                - name: dcc-mcp-fpt
                  image: <registry>/dcc-mcp-fpt:latest
                  ports:
                    - containerPort: 8765
                      name: http
                    - containerPort: 9765
                      name: gateway
                  env:
                    - name: DCC_MCP_GATEWAY_PORT
                      value: "9765"
                    - name: DCC_MCP_FPT_CREDENTIAL_PROFILES_FILE
                      value: /etc/fpt/profiles.json
                  livenessProbe:
                    httpGet:
                      path: /health
                      port: 8765
                    initialDelaySeconds: 10
                    periodSeconds: 30
                  readinessProbe:
                    httpGet:
                      path: /health
                      port: 8765
                    initialDelaySeconds: 5
                    periodSeconds: 10
                  volumeMounts:
                    - name: profiles
                      mountPath: /etc/fpt
                      readOnly: true
              volumes:
                - name: profiles
                  secret:
                    secretName: fpt-credential-profiles
```

## Environment Variables

Same as documented in the main README. Key variables for Harness deployment:

| Variable | Purpose |
|----------|---------|
| `DCC_MCP_FPT_CREDENTIAL_PROFILES_FILE` | Path to mounted profiles secret |
| `DCC_MCP_GATEWAY_PORT` | Gateway port; set 0 to disable |
| `DCC_MCP_FPT_ENABLE_GATEWAY_FAILOVER` | Gateway election control |

## CI/CD Integration

### Harness Pipeline

The included `.github/workflows/ci.yml` can be adapted to Harness pipelines:

1. **Build stage**: Install dependencies, run tests
2. **Lint stage**: ruff check + format check
3. **Package stage**: Build wheel/sdist
4. **Docker stage**: Build and push image
5. **Smoke stage**: Run live CRUD smoke (requires Harness secrets)

### Secrets Configuration

In Harness, create the following secrets:

- `SHOTGRID_URL` — ShotGrid server URL
- `SHOTGRID_SCRIPT_NAME` — Script user name
- `SHOTGRID_SCRIPT_KEY` — Script user key
- `SHOTGRID_PROJECT` — Project for smoke tests
- `CODECOV_TOKEN` — Codecov upload token (optional)

## Health Check

The `/health` endpoint returns:

```json
{
  "status": "ok",
  "version": "dcc-mcp-fpt/0.1.2",
  "sg_configured": true
}
```

- `sg_configured: false` means ShotGrid credentials are missing — check the
  profiles file or environment variables.
- HTTP 503 means the ASGI app is still starting — wait and retry.

## Graceful Shutdown

The adapter handles SIGTERM for graceful shutdown. When Harness stops a pod,
it sends SIGTERM, and the adapter:
1. Stops accepting new connections
2. Closes the ShotGrid connection pool
3. Shuts down the MCP server
4. Exits cleanly

Set `stop_grace_period` or `terminationGracePeriodSeconds` to at least 15
seconds to allow in-flight requests to complete.
