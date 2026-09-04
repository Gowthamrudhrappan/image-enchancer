# Clarity AI restore backend

A real, self-hosted server running actual **GFPGAN** (face restoration)
and **Real-ESRGAN** (general upscale) — not a third-party demo, not a
paid third-party API. You run it, you own it, it's yours.

This is the "guaranteed to work" tier discussed throughout this
project: classical processing and the free in-browser models (MAXIM,
ESRGAN) have a real ceiling on badly degraded photos; this doesn't,
because GFPGAN is trained specifically to repaint plausible facial
detail rather than just amplify existing pixels.

## Run it locally (2 minutes)

From the project root (one level up from this folder):

```bash
docker compose up --build
```

- Frontend: http://localhost:8080
- Backend: http://localhost:8000 (health check: http://localhost:8000/health)

Then in `index.html`, temporarily set:
```js
const AI_ENDPOINT = 'http://localhost:8000/enhance-ai';
```
Reload http://localhost:8080, switch to the AI tab, and the strength
slider + face-safe toggle will appear (those are backend-mode-only
controls) — generate an image and it'll route through your local
GFPGAN/Real-ESRGAN server instead of the in-browser model.

**First request will be slow** — GFPGANer and RealESRGANer each
download their model weights (a few hundred MB total) from GitHub on
first use and cache them in `./backend/weights` (that folder is
volume-mounted in `docker-compose.yml` so weights survive restarts —
don't delete it unless you want to re-download).

## Deploying it somewhere reachable from the internet

This is a standard Docker container — any platform that runs Docker
images works. Roughly in order of "least setup":

- **Railway / Render / Fly.io** — point them at `/backend`, they build
  the Dockerfile and give you a public URL. Simplest path if you don't
  want to manage a server directly.
- **A VPS you already have** (DigitalOcean, Hetzner, etc.) — `docker
  compose up -d` on the box, put it behind a reverse proxy (Caddy or
  nginx) for HTTPS, done.

Once deployed, set `AI_ENDPOINT` in `index.html` to
`https://<your-backend-host>/enhance-ai`, and set
`CLARITY_ALLOWED_ORIGINS` (an env var on the backend) to your actual
frontend origin — e.g. `https://gowthamrudhrappan.github.io` — instead
of leaving it as `*`. `*` is fine for local testing; it's an open door
if left on in production, since it lets any website call your backend.

## Hardware / cost reality — read this before deploying

- **CPU-only works.** GFPGAN and Real-ESRGAN both run on CPU; there's
  no hard GPU requirement. On CPU, expect roughly 5–20 seconds per
  image on a small/typical source photo, depending on the server's
  CPU. Fine for occasional/personal use.
- **A GPU instance is meaningfully faster** (often under a second per
  image) if this needs to handle real traffic or multiple people using
  VIP25's tool at once. Most platforms above offer GPU tiers at extra
  cost — only worth it once there's actual usage to justify it.
  Start on CPU; upgrade if it's slow in practice.
- **Memory**: budget at least 2–4GB RAM for the container — torch plus
  both loaded models isn't tiny.
- **Model weights**: ~350MB for GFPGAN v1.3 + ~65MB for Real-ESRGAN
  x2plus, downloaded once and cached. Make sure whatever platform you
  pick either persists `/app/weights` across deploys (a volume) or
  you're fine re-downloading on every deploy — the latter is slow but
  not broken.

## Known gotcha (already handled in requirements.txt, documented so you know why)

`basicsr` 1.4.2 imports `torchvision.transforms.functional_tensor`,
which was **removed** in torchvision 0.17+. If you bump `torch`/
`torchvision` in `requirements.txt` without checking this, GFPGAN will
fail to import with `ModuleNotFoundError: functional_tensor` the
moment a request comes in. `requirements.txt` pins compatible versions
deliberately — if you need a newer torch for another reason, either
stay on this pin, or patch `basicsr`'s degradations.py to import from
`torchvision.transforms.functional` instead (a well-known, documented
one-line fix in the basicsr community, not something wrong with this
setup).

## API contract

This matches exactly what `index.html`'s `runAiEnhanceViaBackend()`
already sends — no frontend changes needed once `AI_ENDPOINT` is set.

**POST `/enhance-ai`**
```json
{
  "imageBase64": "data:image/png;base64,...",
  "strength": 60,
  "faceSafe": true
}
```
Response:
```json
{ "outputUrl": "data:image/png;base64,..." }
```

`faceSafe: true` routes through GFPGAN (with Real-ESRGAN handling the
background). `faceSafe: false` routes through Real-ESRGAN alone —
faster, but no face-specific reconstruction. `strength` (0–100) maps to
GFPGAN's blend weight between the original and fully-restored face,
so you can dial back how far it drifts from the source.

**GET `/health`** — returns `{"status": "ok"}`, for platform health
checks / uptime monitoring.
