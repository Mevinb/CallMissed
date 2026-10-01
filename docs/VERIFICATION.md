# Verification report — October 1, 2026

## Implemented

- React/Vite/TypeScript frontend with Chat, Image Studio and Voice Agent workspaces.
- FastAPI routes, validated request models, HTTPX chat/image integration, SSE streaming, WebSocket voice relay and health/session endpoints.
- Browser microphone AudioWorklet, PCM16 resampling, voice playback scheduling, interruption flush, mute/stop lifecycle and provider transcript events.
- Server-only API credentials, private reviewer access, signed HttpOnly cookies, explicit origin checks, request/input limits, production startup validation, shared Redis limits and atomic voice concurrency leases for Vercel.
- Docker/Compose/Caddy, Vercel configuration, CI workflow, local launcher and real provider smoke-check script.
- README, deployment instructions and manual acceptance checklist.

## Executed and passed locally

- **69 Pytest tests:** health, validation, missing key, HTTP errors, timeout/network failures, successful mocked chat/image responses, malformed streams/images, nullable content frames, key redaction across stream chunks, cookies, origin enforcement, body limits, shared rate counters and fail-closed Redis behavior, voice settings/audio relay/cleanup, missing key/auth denial, connection timeout, cross-worker concurrency, owned lease release and failed browser-accept cleanup. One upstream Starlette TestClient deprecation warning is emitted; tests pass.
- **13 Vitest tests:** workspace navigation, prompt input, streamed chat and conversation context, cancel/new-chat race, failure display, access gate, microphone denial cleanup, SSE decoding, interrupted streams, image generation/download/reuse/clear, prompt-edit races, late history load, and request cancellation on unmount. DOM and browser APIs are mocked; this is not proof of a real browser download.
- **4 Node audio tests:** encoding/resampling 24 kHz, 44.1 kHz and 48 kHz input to 24 kHz mono PCM16, and signed clipping.
- **Real local Redis 7.0.15:** repeated all 10 voice-slot tests with admission/release Lua evaluated by an isolated Redis process over a Unix socket. Separately checked a 300-second lease TTL, expired-slot reclamation and stale-owner protection. This validates Redis script execution; the Upstash HTTP transport and deployed multi-instance behavior remain unverified.
- TypeScript and Vite production build.
- Ruff lint and formatting.
- Clean `npm ci` and npm audit: no reported vulnerabilities at verification time.
- Actual local Uvicorn HTTP checks: `/`, `/api/health`, `/pcm-capture.js`, and `/favicon.svg` return 200 with expected content types; a session can be created; a chat request with the unconfigured key returns 503 `not_configured`.
- **Live CallMissed:** after the user's `.env.txt` was renamed to the expected `.env` with mode 600, `python -m scripts.smoke_provider --image --voice` passed. Actual nonempty chat text, a decodable 512 × 512 JPEG image, accepted voice settings and raw greeting audio were received. The actual API key was checked as absent from frontend source, public assets and the built bundle; `.env` is ignored by Git.
- **Live local backend:** authenticated streaming chat returned actual answer tokens and a completion event; authenticated `/api/voice` returned accepted settings and real greeting PCM. Testing exposed nullable `delta.content` frames in the actual provider stream; the parser was corrected to skip them without forwarding reasoning fields. Five regression cases were added. No microphone audio was sent by these checks, so they do not prove a spoken user turn or browser playback. The provider's greeting sequence emitted `Welcome`, `SettingsApplied`, audio and `AgentAudioDone`; no transcript event was observed for that greeting.
- Docker base tags were checked as available in the official registry. No Docker image was built locally because Docker is not installed in this session.

## Still unverified / pending

- **Microphone and playback:** mocked permission/PCM/relay checks do not establish actual microphone capture, audible agent responses or perceptual interruption timing.
- **Live spoken turns and transcripts:** greeting audio and session initialization passed, but microphone input, recognition of a spoken user turn, its reply and transcript events need browser acceptance testing.
- **Browser visual review and screenshots:** no browser surface is available in the computer-use tool. DOM tests run in jsdom; no screenshots were captured and no responsive rendering claim is made from them.
- **Docker runtime:** provided and statically inspected; local execution pending a Docker environment. CI includes a build check.
- **Vercel hosting:** CLI installed/available, but the account is signed out and device login has not completed. The user deferred account sign-in on October 1; the local API key is now configured. Production deployment still requires its server-side environment configuration, exact app origin, reviewer access/session secrets and persistent Upstash Redis REST configuration. No hosted URL has been invented.
- **GitHub Actions:** workflow included; remote run must be checked after publication.
- **GitHub publication:** the existing destination repository was inspected and was empty. The connector rejected the write because it requires approval and this session uses approval policy `never`. No remote files were created. Local source commit and a source archive are prepared for owner-controlled publication.
- **Submission:** user review and approval pending. No email has been sent or staged for automatic sending.

## Completion boundary

This is an implemented project with local automated and live provider checks, not yet a completed hosted submission. Configure production credentials, deploy, then run `docs/ACCEPTANCE.md` and record the actual browser results before describing the entire application as working end to end.
