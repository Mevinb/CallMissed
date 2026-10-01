# Deployment guide

## Vercel (preferred)

Vercel's current [WebSocket documentation](https://vercel.com/docs/functions/websockets) supports FastAPI ASGI WebSocket handlers in beta with Fluid Compute. Its [FastAPI deployment guide](https://vercel.com/docs/frameworks/backend/fastapi) documents `tool.vercel.entrypoint` and lifespan startup. This implementation uses that path, not a legacy Python serverless adapter. Verify the beta feature on your deployed project before submission.

1. Sign in to your Vercel account and import `Mevinb/CallMissed`.
2. Use the **repository root** as Root Directory. Select **FastAPI**, Python 3.12 and Node.js 22. The build command is `npm --prefix frontend ci && npm --prefix frontend run build`; the FastAPI entrypoint is `backend.app.main:app`. Do not set `frontend` as the root and do not set a static-only output directory.
3. Enable Fluid Compute. `vercel.json` sets a 300-second function duration. Voice calls stop after 240 seconds, leaving time for connection and cleanup within the [Hobby 300-second limit](https://vercel.com/docs/functions/limitations).
4. Create or connect an Upstash Redis database using an eligible free plan in the Vercel Marketplace or Upstash console. Copy its REST URL and token into the server environment variables below. [Upstash REST documentation](https://upstash.com/docs/redis/features/restapi) describes the command-array API. The app stores only hashed request counters with expiry; never conversation content.
5. Set these variables for the target deployment environment. Configure them before the production build because the framework may import the app while inspecting routes:

   ```text
   APP_ENV=production
   APP_ORIGINS=https://YOUR-PROJECT.vercel.app
   CALLMISSED_API_KEY=<private company key>
   SESSION_SECRET=<random 32+ characters>
   DEMO_ACCESS_CODE=<private reviewer code, 12+ characters>
   UPSTASH_REDIS_REST_URL=<database REST URL>
   UPSTASH_REDIS_REST_TOKEN=<database REST token>
   GLOBAL_DAILY_REQUESTS=200
   VOICE_MAX_SECONDS=240
   ```

   Put credential values in Vercel environment settings, not in command arguments or committed config. Keep Preview variables separate from Production. Add exact preview hostnames to `APP_ORIGINS` only when you intend to test them; no wildcards. For a stable production URL, using only its exact origin is enough.
6. Deploy. If the project name or domain differs, update `APP_ORIGINS` and redeploy. Keep the session secret stable across replicas and deployments.
7. Open `https://YOUR-PROJECT.vercel.app/api/health`. It should return `status:ok` and `provider_configured:true`. This tests configuration, not key validity.
8. Open the main app, unlock it with the private reviewer code and complete [acceptance testing](ACCEPTANCE.md), including a spoken reply, interruption, mute, stop, and a new call.
9. Check Vercel logs for startup/protocol errors without logging environment contents, request bodies, cookies or authorization headers. If WebSocket upgrades are unavailable in the account, retain the Python relay and use the EC2 deployment below.
10. Record the actual hosted URL in README and verification notes only after deployment succeeds. Set a suitable deployment visibility for your reviewer; do not disable a paid security product or purchase a plan automatically.

CLI alternative after authentication:

```bash
npx vercel login
npx vercel link
npx vercel deploy
# After preview acceptance and production environment configuration:
npx vercel deploy --prod
```

A CLI device sign-in must be completed by the account owner. Connecting Vercel to GitHub may require the owner to approve a repository permission screen. Neither access nor deployment success is assumed.

## AWS EC2 Free Tier-compatible fallback

This is a lightweight single-instance deployment. It does not require an ALB, NAT gateway, RDS, Kubernetes or GPUs. [AWS Free Tier eligibility](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-free-tier-usage.html) depends on account creation date, account plan, available credits and regional instance eligibility; `t3.micro` is a reasonable small x86 target when your console marks it eligible. Check the console estimate first. Public IPv4, disk, surplus CPU credits and traffic can affect cost.

1. Launch an Ubuntu x86 instance with an eligible size, 8–12 GB encrypted gp3 root volume, and IMDSv2 required. No AWS credentials are needed inside this app. Use Standard CPU credit mode for a burstable instance if available to avoid unlimited surplus-credit billing.
2. Permit inbound TCP 80/443. For administration, prefer existing Session Manager access, or allow SSH only from your current IP. Do not expose port 8000 to the Internet.
3. Install Docker Engine and its Compose plugin following the [official Ubuntu instructions](https://docs.docker.com/engine/install/ubuntu/). No AWS resource creation is performed by this repository.
4. Point a hostname you control to the instance's public address. HTTPS is required for a remote microphone. The supplied Caddy configuration obtains and renews certificates and supports [WebSocket upgrades and streaming](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy).
5. Fetch the application:

   ```bash
   git clone https://github.com/Mevinb/CallMissed.git
   cd CallMissed
   cp .env.example .env
   chmod 600 .env
   ```

6. Edit `.env` with the API key, `APP_ENV=production`, a stable `SESSION_SECRET`, `DEMO_ACCESS_CODE`, `APP_DOMAIN=your-domain.example` and `APP_ORIGINS=https://your-domain.example`. Redis can be omitted on a single worker; counters then reset on process restart. For durable shared limits, supply Redis here too.
7. Build and start:

   ```bash
   sudo docker compose -f compose.production.yaml up --build -d
   curl --fail https://your-domain.example/api/health
   ```

   The production Compose file publishes only Caddy's ports. The app is reachable on the internal Docker network. If building the frontend exhausts the micro instance's RAM, build the image locally/CI and transfer it; do not solve this by adding paid infrastructure without reviewing cost.
8. Complete browser acceptance, keep `.env` readable only by its owner, and keep the EC2 host updated. Persist Caddy's volumes so certificates survive restarts. Application conversations are kept by the browser; the server does not need a data disk for history.
9. To update, fetch the new commit and repeat the Compose build/start. To roll back, check out a known previous commit and rebuild. Stop resources you no longer need through the console; do not leave unused instances running.

## Production startup and configuration

The Docker image runs:

```bash
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --workers 1 --ws-max-size 8192 --no-access-log
```

`PORT` is honored by the container startup command. The Vercel ASGI runtime imports the same app directly. Backend CORS allows only exact configured origins and credentials; state-changing HTTP routes and voice upgrades also validate the browser Origin. This is enforced independently of CORS.

All frontend API/WebSocket connections use the current application hostname. There are no secret frontend environment variables and no need to give the browser an upstream API token.
