# Clarity — Image Enhancer

A browser-based photo enhancer built for VIP25. It sharpens, denoises, and
corrects contrast on soft/noisy photos using classical image processing —
no AI model, no upload to any server, no identity-altering changes to
faces, bodies, or backgrounds. Everything runs client-side in the browser.

## What's in this folder

```
clarity-image-enhancer/
├── index.html   ← the entire product (HTML + CSS + JS, single file)
└── README.md    ← this file
```

That's it. No build step, no dependencies, no `npm install`. It's plain
HTML/CSS/JavaScript using the Canvas API.

## Run it locally

Just open `index.html` directly in any modern browser (Chrome, Safari,
Firefox, Edge) — double-click the file, or drag it into a browser tab.

Upload/drag-and-drop won't work if you view this file inside a **sandboxed
preview pane** (e.g. embedded inside another app's UI) — those environments
often block the native file dialog for security. Opening the file as its
own page (as above), or hosting it (below), avoids that entirely.

## Deploy it (GitHub Pages — free, 2 minutes)

1. Create a new GitHub repo (or use an existing one, e.g. your portfolio repo).
2. Upload `index.html` to the **root** of that repo — filename must stay
   exactly `index.html`, lowercase.
3. In the repo: **Settings → Pages** → under "Build and deployment", set
   Source to **"Deploy from a branch"**, branch **main**, folder **/ (root)**,
   then Save.
4. Wait ~1–2 minutes. Your live URL will be:
   `https://<your-username>.github.io/<repo-name>/`
5. Open that URL in a normal browser tab — upload and drag-and-drop work
   normally here, since it's a real hosted page, not an embedded preview.

If it 404s: open the repo's file list and confirm `index.html` is sitting
at the repo root (not nested in a folder), and check the **Actions** tab
to confirm the Pages build finished (green check).

## How it works

Pipeline, run in this order when you click **Generate enhanced image**:

1. **Denoise** — 3×3 median filter (found via an optimal 19-step
   sorting network, not a per-pixel array sort — faster, same result),
   blended by strength, sampling edge pixels with clamped coordinates
   instead of skipping them. Reduces grain/compression noise *before*
   sharpening, so sharpening doesn't amplify it.
2. **Sharpen** — unsharp mask applied to **luminance only** (blur a
   luminance copy via a 3-pass box blur that approximates a Gaussian,
   then push the original luminance away from the blur, and apply that
   same delta equally to R/G/B). Sharpening each color channel
   independently causes color fringing/blotching on compressed sources;
   luminance-only sharpening avoids that. It only reacts to local
   contrast that already exists — it can't invent detail, which is why
   identity/features aren't altered.
3. **Levels** — a single contrast bound derived from luminance, applied
   identically to all three channels (not computed separately per
   channel — that was causing a color cast/tint on compressed sources).
   0.6% clip on each end so a few outlier pixels can't wreck the mapping.

All three are global, uniform operations — there's no face detection or
region-specific processing. Default slider values are deliberately
conservative (Denoise 35 / Sharpen 20 / Levels 20): classical processing
amplifies whatever's already in the pixels, so on a small or heavily
compressed source, pushing these higher mostly amplifies JPEG blocking
artifacts, not real sharpness. There's a hard ceiling here — a badly
degraded source will never look truly sharp through classical methods
alone, only "less bad." That's what the AI tab is for.

Images are downscaled to a 1800px long edge before processing, for speed.

## The AI engine tab

**Default: free, runs entirely in the browser, no setup required.**
UpscalerJS (open-source, MIT-licensed, built on TensorFlow.js) runs a
real ESRGAN super-resolution model on-device — nothing is uploaded
anywhere, no account or key needed. The library (~a few MB) is fetched
lazily from jsDelivr the first time you switch to the AI tab, so
classical-only users never pay that cost. Unlike classical sharpening,
this can genuinely reconstruct plausible texture — but on very degraded
sources it's making an informed guess, not reading back your camera's
original pixels. The model outputs at a higher resolution than the
input; the compare view shows it scaled to match, but **Download PNG**
saves the true full-resolution result.

**Optional/advanced: bring your own hosted model.** If you want stronger
restoration (e.g. GFPGAN for faces, or Real-ESRGAN at higher settings)
than a browser can run, you can point the AI tab at your own backend
instead. In `index.html`, find:
```js
const AI_ENDPOINT = ''; // e.g. '/api/enhance-ai' — empty = use the free local model
```
Setting this to a deployed route switches the AI tab to call it instead
of the local model, and reveals a strength slider + face-safe toggle in
the UI. A full example backend route (Node, calling Replicate, with your
API key kept server-side) is written out as a comment directly above the
`AI_ENDPOINT` declaration in the code — copy it, deploy it, point
`AI_ENDPOINT` at it.

**Note for that path specifically:** GFPGAN/CodeFormer-style models
*reconstruct* facial detail generatively — that's how they recover
strong results from real blur, but it also means they can subtly change
how a face looks if pushed too hard. Real-ESRGAN alone (texture/
upscaling only, no facial reconstruction) is the safer default if
identity fidelity is a hard requirement for a client.

## License / ownership

Built for VIP25. No telemetry, no tracking. Two outbound network
dependencies, both optional to remove: the Google Fonts stylesheet link
in `<head>`, and — only if you ever open the AI tab — the TensorFlow.js/
UpscalerJS libraries fetched from jsDelivr. The classical engine works
fully offline once the page itself is loaded.
