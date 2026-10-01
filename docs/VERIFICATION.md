# Verification report — October 1, 2026

## Implemented

- React/Vite/TypeScript frontend with Chat, Image Studio and Voice Agent workspaces.
- FastAPI routes, validated request models, HTTPX chat/image integration, SSE streaming, WebSocket voice relay and health/session endpoints.
- Browser microphone AudioWorklet, PCM16 resampling, voice playback scheduling, interruption flush, mute/stop lifecycle and provider transcript events.
- Server-only API credentials, private reviewer access, signed HttpOnly cookies, explicit origin checks, request/input limits, production startup validation, shared Redis limits and atomic voice concurrency leases for Vercel.
- Docker/Compose/Caddy, Vercel configuration, CI workflow, local launcher and real provider smoke-check script.
- README, deployment instructions and manual acceptance checklist.

## Executed and passed locally

- **71 Pytest tests:** health, validation, missing key, HTTP errors, timeout/network failures, successful mocked chat/image responses, malformed streams/images, nullable content frames, key redaction across stream chunks, private startup-validation inputs, cookies, origin enforcement, body limits, shared rate counters and fail-closed Redis behavior, voice settings/audio relay/cleanup, missing key/auth denial, connection timeout, cross-worker concurrency, owned lease release and failed browser-accept cleanup. One upstream Starlette TestClient deprecation warning is emitted; tests pass.
- **13 Vitest tests:** workspace navigation, prompt input, streamed chat and conversation context, cancel/new-chat race, failure display, access gate, microphone denial cleanup, SSE decoding, interrupted streams, image generation/download/reuse/clear, prompt-edit races, late history load, and request cancellation on unmount. DOM and browser APIs are mocked; this is not proof of a real browser download.
- **4 Node audio tests:** encoding/resampling 24 kHz, 44.1 kHz and 48 kHz input to 24 kHz mono PCM16, and signed clipping.
- **Real local Redis 7.0.15:** repeated all 10 voice-slot tests with admission/release Lua evaluated by an isolated Redis process over a Unix socket. Separately checked a 300-second lease TTL, expired-slot reclamation and stale-owner protection. This validates Redis script execution; routing concurrent calls to multiple actual Vercel instances remains unverified.
- TypeScript and Vite production build.
- Ruff lint and formatting.
- Clean `npm ci` and npm audit: no reported vulnerabilities at verification time.
- Actual local Uvicorn HTTP checks: `/`, `/api/health`, `/pcm-capture.js`, and `/favicon.svg` return 200 with expected content types; a session can be created; a chat request with the unconfigured key returns 503 `not_configured`.
- **Live CallMissed:** after the user's `.env.txt` was renamed to the expected `.env` with mode 600, `python -m scripts.smoke_provider --image --voice` passed. Actual nonempty chat text, a decodable 512 × 512 JPEG image, accepted voice settings and raw greeting audio were received. The actual API key was checked as absent from frontend source, public assets and the built bundle; `.env` is ignored by Git.
- **Live local backend:** authenticated streaming chat returned actual answer tokens and a completion event; authenticated `/api/voice` returned accepted settings and real greeting PCM. Testing exposed nullable `delta.content` frames in the actual provider stream; the parser was corrected to skip them without forwarding reasoning fields. Five regression cases were added. No microphone audio was sent by these checks, so they do not prove a spoken user turn or browser playback. The provider's greeting sequence emitted `Welcome`, `SettingsApplied`, audio and `AgentAudioDone`; no transcript event was observed for that greeting.
- Docker base tags were checked as available in the official registry. No Docker image was built locally because Docker is not installed in this session.
- GitHub CI for published commit `019d164e2903` completed successfully: https://github.com/Mevinb/CallMissed/actions/runs/36895488487. That workflow includes the Docker image build. The newer local startup-validation change has passed local tests but has not yet run in remote CI.

## Executed on the hosted application

Production URL: **https://callmissed-playground.vercel.app**. Deployment `dpl_5bzbKiUkLpdfPMeAZScxQezHKFdq` completed with status `READY` on October 1, 2026. The Vercel cloud build installed Python dependencies, compiled TypeScript/Vite and deployed the FastAPI app successfully; its npm audit reported no vulnerabilities.

- `/`, `/api/health`, `/pcm-capture.js` and `/favicon.svg` return 200 over HTTPS without a Vercel account login. Health reports `provider_configured:true`.
- Actual Upstash REST checks passed: counters shared by two limiter objects, atomic duplicate voice-session denial, release and reacquisition. The owner accepted marketplace terms; Redis was provisioned on the Free plan with automatic upgrades disabled and connected to the production project.
- Unauthenticated inference returns 401. The reviewer code creates a Secure, HttpOnly, SameSite=Lax cookie. Logout clears authorized access.
- Public JavaScript/CSS assets load successfully and do not contain the actual CallMissed key. Content Security Policy is present.
- Streaming chat through the hosted FastAPI backend returns actual answer tokens followed by completion.
- Hosted image generation returns actual JPEG bytes, saved privately to `artifacts/callmissed-hosted-image.jpg`; the image decoded successfully for visual inspection.
- The hosted authenticated voice WebSocket accepts settings, returns 24 kHz greeting PCM and `AgentAudioDone`, accepts KeepAlive and stops on request. This checks the deployed ASGI WebSocket path and provider relay, not browser microphone capture or a spoken user turn.
- Vercel login is verified as `mevinbenty507-9965`. `callmissed-playground` uses FastAPI, Node.js 22 and Fluid Compute. Server credentials are configured in production; local copies remain in ignored files with owner-only permissions. The separate reviewer-access artifact contains no provider API key.

## Still unverified / pending

- **Microphone and playback:** mocked permission/PCM/relay checks do not establish actual microphone capture, audible agent responses or perceptual interruption timing.
- **Live spoken turns and transcripts:** greeting audio and session initialization passed, but microphone input, recognition of a spoken user turn, its reply and transcript events need browser acceptance testing.
- **Browser visual review and screenshots:** no browser surface is available in the computer-use tool. DOM tests run in jsdom; no screenshots were captured and no responsive rendering claim is made from them.
- **Docker container runtime:** the published commit's CI Docker build passed; launching the container, production Compose/Caddy and EC2 execution remain unverified.
- **Latest GitHub Actions:** published commit `019d164e2903` passed CI; the latest local changes need a push and a new CI run.
- **Latest GitHub update:** the public repository now contains commit `019d164e2903`, verified after deployment. The newer startup-validation security change and deployment notes are committed locally and still need a push. The connector rejected writes because it requires approval and this session uses approval policy `never`; no remote writes were made through that connector. An updated source archive is also prepared.
- **Submission:** user review and approval pending. No email has been sent or staged for automatic sending.

## Completion boundary

The app is hosted and its inference/voice relay paths passed live protocol checks. Complete `docs/ACCEPTANCE.md` in a real browser, push the latest GitHub changes and inspect CI before submission. Do not describe microphone conversations, audible playback or visual behavior as verified until those corresponding checks have been performed.
