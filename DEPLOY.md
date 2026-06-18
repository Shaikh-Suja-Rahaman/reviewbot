# Deploying the webhook server

The container (`Dockerfile`) runs `copilot serve` as a FastAPI app on `$PORT`.
It exposes:

- `GET /` → health check (`{"status":"ok"}`)
- `POST /webhook` → GitHub PR webhook (HMAC-verified)

You need three secrets set as **environment variables** on the host (NOT baked into
the image, NOT committed):

| Var | What | Where to get it |
|---|---|---|
| `ANTHROPIC_API_KEY` | Calls Claude | https://platform.claude.com → API keys |
| `GITHUB_TOKEN` | Posts reviews | GitHub → Settings → Developer settings → fine-grained PAT: `Contents:Read` + `Pull requests:Read/Write` on the target repo |
| `GITHUB_WEBHOOK_SECRET` | Verifies webhook calls | Generate one: `python -c "import secrets; print(secrets.token_hex(32))"` |

Optional: `COPILOT_MODEL` (default `claude-opus-4-8`), `COPILOT_DB_PATH`.

> ⚠️ SQLite (`copilot.db`) is written to the container's local disk and is **ephemeral**
> on most PaaS hosts — review history resets on redeploy. Fine for a demo; attach a
> volume if you want it to persist.

---

## 0. Pre-flight (do this once, locally)

```bash
# create the real .env (gitignored) so you have the values handy
cp .env.example .env
python -c "import secrets; print('GITHUB_WEBHOOK_SECRET=' + secrets.token_hex(32))"
# paste that + your ANTHROPIC_API_KEY + GITHUB_TOKEN into .env

# sanity check the container builds and serves locally (Docker Desktop must be running)
docker build -t copilot .
docker run --rm -p 8000:8000 --env-file .env copilot
# in another shell:  curl localhost:8000/   -> {"status":"ok",...}
```

---

## Option A — Railway (simplest, recommended)

```bash
railway login
railway init                       # create a new project
railway up                         # builds the Dockerfile and deploys
# set secrets (or paste them in the Railway dashboard → Variables):
railway variables --set ANTHROPIC_API_KEY=sk-ant-... \
                  --set GITHUB_TOKEN=ghp_... \
                  --set GITHUB_WEBHOOK_SECRET=<the hex you generated>
railway domain                     # generates a public https URL
```

Your webhook URL is `https://<that-domain>/webhook`.

---

## Option B — AWS App Runner (uses the account you're already logged into)

```bash
# 1. build + push image to ECR
AWS_REGION=us-east-1
ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
aws ecr create-repository --repository-name copilot --region $AWS_REGION || true
aws ecr get-login-password --region $AWS_REGION | \
  docker login --username AWS --password-stdin $ACCOUNT.dkr.ecr.$AWS_REGION.amazonaws.com
docker build --platform linux/amd64 -t copilot .
docker tag copilot $ACCOUNT.dkr.ecr.$AWS_REGION.amazonaws.com/copilot:latest
docker push $ACCOUNT.dkr.ecr.$AWS_REGION.amazonaws.com/copilot:latest

# 2. create the App Runner service in the AWS Console:
#    - Source: the ECR image above
#    - Port: 8000
#    - Add env vars: ANTHROPIC_API_KEY, GITHUB_TOKEN, GITHUB_WEBHOOK_SECRET
#    - Health check path: /
#    App Runner gives you a public https URL.
```

> App Runner bills while running — pause/delete the service after the demo to stop cost.

---

## Final step — register the GitHub webhook (same for either host)

GitHub repo → **Settings → Webhooks → Add webhook**:

- **Payload URL:** `https://<your-host-url>/webhook`
- **Content type:** `application/json`
- **Secret:** the exact `GITHUB_WEBHOOK_SECRET` value you set on the host
- **Events:** "Let me select" → **Pull requests** only

Open or push to a PR → GitHub delivers the event → the server reviews it and posts
inline comments + a risk summary. Check **Recent Deliveries** in the webhook settings
to confirm a `202 accepted` response.
