# Verification report — October 1, 2026

## Implemented

- React/Vite/TypeScript frontend with Chat, Image Studio and Voice Agent workspaces.
- FastAPI routes, validated request models, HTTPX chat/image integration, SSE streaming, WebSocket voice relay and health/session endpoints.
- Browser microphone AudioWorklet, PCM16 resampling, voice playback scheduling, interruption flush, mute/stop lifecycle and provider transcript events.
- Server-only API credentials, private reviewer access, signed HttpOnly cookies, explicit origin checks, request/input limits, production startup validation and shared Redis limits for Vercel.
- Docker/Compose/Caddy, Vercel configuration, CI workflow, local launcher and real provider smoke-check script.
- README, deployment instructions and manual acceptance checklist.

## Executed and passed locally

- **54 Pytest tests:** health, validation, missing key, HTTP errors, timeout/network failures, successful mocked chat/image responses, malformed streams/images, key redaction across stream chunks, cookies, origin enforcement, body limits, shared rate counters and fail-closed Redis behavior, voice settings/audio relay/cleanup, missing key/auth denial and connection timeout. One upstream Starlette TestClient deprecation warning is emitted; tests pass.
- **9 Vitest tests:** workspace navigation, prompt input, streamed chat and conversation context, cancel/new-chat race, failure display, access gate, microphone denial cleanup, SSE decoding and interrupted streams.
- **4 Node audio tests:** encoding/resampling 24 kHz, 44.1 kHz and 48 kHz input to 24 kHz mono PCM16, and signed clipping.
- TypeScript and Vite production build.
- Ruff lint and formatting.
- Clean `npm ci` and npm audit: no reported vulnerabilities at verification time.
- Actual local Uvicorn HTTP checks: `/`, `/api/health`, `/pcm-capture.js`, and `/favicon.svg` return 200 with expected content types; a session can be created; a chat request with the unconfigured key returns 503 `not_configured`.
- Docker base tags were checked as available in the official registry. No Docker image was built locally because Docker is not installed in this session.

## Still unverified / pending

- **Live provider:** the company key has not been supplied in `.env`. The live smoke script correctly reports missing configuration without making a paid inference request. Real chat answers, image generation and voice model eligibility have not been established.
- **Microphone and playback:** mocked permission/PCM/relay checks do not establish actual microphone capture, audible agent responses or perceptual interruption timing.
- **Browser visual review and screenshots:** no browser surface is available in the computer-use tool. DOM tests run in jsdom; no screenshots were captured and no responsive rendering claim is made from them.
- **Docker runtime:** provided and statically inspected; local execution pending a Docker environment. CI includes a build check.
- **Vercel hosting:** CLI installed/available, but the account is signed out and device login has not completed. Production deployment also requires secrets, exact app origin and Upstash Redis REST configuration. No hosted URL has been invented.
- **GitHub Actions:** workflow included; remote run must be checked after publication.
- **GitHub publication:** the existing destination repository was inspected and was empty. The connector rejected the write because it requires approval and this session uses approval policy `never`. No remote files were created. Local source commit and a source archive are prepared for owner-controlled publication.
- **Submission:** user review and approval pending. No email has been sent or staged for automatic sending.

## Completion boundary

This is an implemented, locally tested project, not yet a completed live submission. Configure credentials, deploy, then run `docs/ACCEPTANCE.md` and record the actual results before describing all three integrations as working.
