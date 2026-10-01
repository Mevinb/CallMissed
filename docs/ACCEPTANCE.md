# Manual acceptance before submission

Use a real configured CallMissed key. API calls can consume company credits. Do not include the key or reviewer code in recorded evidence.

| Check | Expected result | Status |
|---|---|---|
| HTTPS deployment and health | Actual hosted page loads; health returns configured true | Hosted HTTP passed; browser rendering pending |
| Access gate | No access without code; wrong code fails; correct code unlocks | Hosted auth/cookie/logout passed; wrong-code mocked; browser pending |
| Chat answer | Ask a unique question; actual answer streams | Hosted API stream passed; browser pending |
| Chat context | Ask a follow-up referring to previous details | Pending live provider |
| Chat cancel/new conversation | Cancel mid-answer; new chat remains clear | Automated/static review |
| Image generation | Unique prompt yields a real image; no success on API failure | Hosted API image decoded; UI pending; failures mocked |
| Image download/history | Download opens as PNG/JPEG; history survives tab reload; clear removes it | Pending browser |
| Voice permission denial | Deny mic; useful error; no call or microphone stays active | Automated only |
| Voice exchange | Allow mic, speak, hear a relevant spoken response, see transcript | Hosted greeting PCM passed; spoken turn/playback/transcripts pending |
| Voice interruption | Speak during answer; queued answer stops promptly | Pending hardware/live provider |
| Voice mute/stop | Mute suppresses outgoing mic; stop removes browser mic indicator | Pending browser |
| Voice reconnect/disconnect | Network failure shows error; resources close; fresh call works | Mocked backend only |
| Responsive/keyboard review | No horizontal overflow at 390px; visible focus; controls usable | Pending browser |
| Credential boundary | DevTools source and network show no CallMissed key, no upstream host requests | Source and hosted bundle scan passed; DevTools pending |
| Error cases | Missing key, invalid key, low credits, timeout show errors without fake output | Mocked tests passed |

Only mark a pending row passed after performing the corresponding real check. Health reports process availability and key presence, not successful inference. Provider smoke checks can establish response/handshake validity but cannot establish perceptual audio quality.

After Mevin completes and approves these checks, prepare the submission email to `durvesh@callmissed.com`, subject `Backend Engineering Intern Assignment Submission - Mevin Benty`, with the actual hosted URL and GitHub URL. Do not send it automatically.
