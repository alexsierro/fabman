# Deployment: one-time setup

### 1. Deploy key

Generate a key used only by GitHub Actions:

```bash
ssh-keygen -t ed25519 -f fabman_deploy -C "github-actions-deploy" -N ""
```

On the server, add the public key to `~/.ssh/authorized_keys` of `alex`, locked to the deploy script:

```
command="/home/alex/fablab-manager-django/fabman/scripts/deploy.sh",no-port-forwarding,no-agent-forwarding,no-X11-forwarding,no-pty ssh-ed25519 AAAA... github-actions-deploy
```

With this restriction, the key can only trigger a deploy; it can't open a shell.

### 2. Host key

Get the server's host key so GitHub Actions can verify it:

```bash
ssh-keyscan -t ed25519 <server-host>
```

### 3. GitHub secrets

In **Settings → Environments**, create an environment named `production` and add:

| Secret               | Value                                       |
|----------------------|---------------------------------------------|
| `DEPLOY_SSH_KEY`     | contents of the private key `fabman_deploy` |
| `DEPLOY_KNOWN_HOSTS` | output of `ssh-keyscan`                     |
| `DEPLOY_HOST`        | server hostname or IP                       |
| `DEPLOY_USER`        | `alex`                                      |

Then delete the private key from your machine.

### 4. Server checks

- `docker compose version` works (Compose v2).
- `git pull` in the checkout works without prompting for credentials.
- The image can be pulled: `docker pull ghcr.io/alexsierro/fabman:latest`.
  If the package is private, run `docker login ghcr.io` once.
- The checkout already contains `scripts/deploy.sh` (run `git pull` manually once after this was merged).

### 5. Branch protection (recommended)

In **Settings → Branches**, protect `main`: require a pull request and require the `test` check to pass.
