# web/ — hosted demo

Static page (no build step, no dependencies) that replays the two real runs:

- `data/index.json` — run list
- `data/<slug>.json` — script + measured timeline for one run (captions, narration, bpy code, t_start/t_end)
- `media/<slug>.mp4` — the rendered short (H.264 + faststart, so metadata loads without a Range-capable server)
- `media/poster_<slug>.jpg` — still extracted from a mid-run frame

## What it does on purpose

The demo **does not call any API**. A public demo page can't hold an API key, so instead it
replays runs that were actually produced, and highlights the step whose recorded time range
contains the current playback position. Honesty over a fake "generate" button.

## Publishing

The site is served from the **`gh-pages` branch** of this repository, at
<https://unotchi.com/blender-dekisou/> (GitHub Pages under the account's custom domain).

```bash
# rebuild the gh-pages branch from web/ (video and poster files are gitignored on main)
tmp=$(mktemp -d)
cp -r web/. "$tmp"/
cd "$tmp" && git init -q -b gh-pages && git add -A \
  && git commit -q -m "demo: rebuild" \
  && git push --force https://github.com/sanpeita/blender-dekisou.git gh-pages
```

Videos are excluded from `main` by `.gitignore` (`*.mp4`), so the copy above is what carries
them to the published branch.
