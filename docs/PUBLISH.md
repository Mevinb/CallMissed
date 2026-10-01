# Remaining account actions

The project is implemented and tested locally. These steps finish external publication and verification.

## GitHub

The `Mevinb/CallMissed` repository was inspected and was empty. The connected GitHub tool refused writes because it requires approval and this session's approval policy is `never`. No remote changes were made.

A local source commit is prepared using `.local-git` metadata because the managed workspace's `.git` directory is read-only. From the project directory, in your own authenticated terminal:

```bash
# Refresh the Mevinb login if the existing GitHub CLI token is expired.
gh auth login --hostname github.com
gh auth setup-git
git --git-dir=.local-git --work-tree=. push -u origin main
```

Alternatively unpack `artifacts/callmissed-playground-source.zip` into a new empty directory, initialize Git there, add the intended remote and push the source. The archive excludes credentials, installed dependencies and generated builds.

After publication, check the GitHub Actions CI run. Docker build and hosted integration checks have not been executed in the managed local session.

## Vercel and live credentials

Complete Vercel CLI/device login in an account you control, or import the published repository through your dashboard. See `DEPLOYMENT.md` for production variables, Redis setup and Fluid Compute.

Place `CALLMISSED_API_KEY` in the local ignored `.env` file for live smoke checks. Enter it in Vercel's secure project environment configuration for production; do not put it in the frontend or Git. Set the reviewer code, stable session secret, exact HTTPS origin, and Redis REST credentials as documented before deployment.

Finally test chat, an image and a spoken voice exchange through the actual hosted application. Update `VERIFICATION.md` with observed results and the real hosted URL. Submission email preparation starts only after Mevin approves the completed live project.
