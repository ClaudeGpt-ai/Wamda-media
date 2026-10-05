---
name: free-image
description: Free image generation with no paid API. Plans a visual brief, writes a strong prompt, generates variants through free providers (Pollinations with no key, or the Hugging Face free tier), then reviews the result and iterates. Use for interior design renders, hero images, social posts, product shots, concept art, mood boards and any "make me an image" request where the user does not want to pay.
---

# Free Image

A free alternative to paid image skills. The workflow is brief, then prompt, then generate, then review, then refine.

## Providers

| Provider | Cost | Setup | Notes |
|---|---|---|---|
| `pollinations` | Free | None | Default. Uses the FLUX model, rate limited, may be slow at busy times. |
| `hf` | Free tier | Set `HF_TOKEN` from a free huggingface.co account (Settings → Access Tokens, read only) | FLUX.1-schnell. Used as the fallback in `auto` mode. |

The script needs outbound access to `image.pollinations.ai` and, for the fallback, `router.huggingface.co`. In a Claude Code cloud environment, add both under **Network access → Allowed domains**.

## Workflow

### 1. Brief

Turn the request into a short brief before writing any prompt. Fill in what the user gave you and choose sensible defaults for the rest:

- **Subject**: what is in the frame
- **Setting**: where it is, time of day
- **Style**: photo, 3D render, illustration, watercolour…
- **Lighting**: soft daylight, golden hour, warm 2700K lamps, studio…
- **Camera**: eye-level wide 24mm, top-down, close-up 85mm…
- **Composition**: what goes where, and any empty space left for text
- **Palette and materials**: named colours and textures
- **Aspect**: 16:9 hero, 1:1 post, 9:16 story, 4:3 room render
- **Avoid**: things that must not appear

Show the brief and the final prompt to the user in a few lines. Generation is free, so you don't need their approval to run it.

### 2. Prompt

Write one paragraph in this order: **subject → setting → materials and colours → lighting → camera and composition → style and quality**. Use concrete nouns and real materials. "Fluted walnut panel" works better than "nice wood".

- Name the medium first, for example "Photorealistic interior photograph of…" or "Flat vector illustration of…".
- Give positions: "on the left", "in the foreground", "against the back wall".
- Write the quality cues for the medium: "architectural digest photo, natural light, sharp focus, 8k" or "clean vector, no gradients".
- These models render text badly. Never ask for words, logos or numbers in the image. Leave empty space instead and add the text afterwards (see step 5).
- Keep the prompt under about 120 words, because longer prompts get partly ignored.

### 3. Generate

```bash
python3 .claude/skills/free-image/scripts/generate.py \
  --prompt "…" --aspect 16:9 --count 2 --out generated-images --name living-room
```

- `--count 2` gives two variants with different seeds. Use 1 to 4.
- `--seed N` reproduces a result. The seed is saved in each image's `.json` sidecar.
- `--provider pollinations|hf|auto` sets the provider. The default `auto` tries Pollinations, then Hugging Face.
- `--model turbo` gives faster, lower-quality Pollinations drafts.

If every provider fails, report the actual error. For a network or proxy error, tell the user which domain to allow. Do not make up a result.

### 4. Review

Open every saved image with the Read tool and check it against the brief:

- Is the subject correct and complete?
- Do the layout and camera angle match?
- Are the colours and materials as specified?
- Are there artefacts such as warped hands, melted furniture, extra legs or garbled text?
- Was the empty space for text actually left?

Tell the user plainly which variant is best and why, and point out any flaws. Send the best image or images with SendUserFile.

### 5. Refine

- **Wrong content**: change the prompt, not the seed.
- **Right idea, bad details**: keep the prompt and try new seeds.
- **Nearly perfect**: keep the seed and make one small prompt change.
- **Exact text, logo or brand mark needed**: generate without text, then add it locally with HTML or SVG rendered by Playwright, or with Python Pillow if it is installed.

## Presets

Start from these and fill in the details.

**Interior render**
> Photorealistic interior design photograph of a {room} in a {size} apartment, {style} style. {key furniture with materials and colours, with positions}. {floor}, {walls}. {lighting}. Eye-level wide-angle shot from {position}, 24mm lens. Architectural Digest editorial photo, natural soft shadows, high detail.

**Hero or banner** (16:9)
> {medium} of {subject}, placed on the right third of the frame, with clean empty {colour} space on the left for headline text. {palette}. {lighting}. Minimal, premium, high detail.

**Product shot** (1:1 or 4:5)
> Studio product photograph of {product} on {surface}, {background}. {lighting, e.g. soft key light from the left with a gentle reflection}. 85mm, shallow depth of field, commercial catalogue quality.

**Social post** (1:1 or 9:16)
> {style} image of {subject}, bold simple composition, {palette}, eye-catching, with space at the {top/bottom} for a caption.

## Honest limits

- Free providers can be slow, rate limited or briefly unavailable. Retry once later and then say so.
- Results are not consistent from one generation to the next. The same sofa won't look identical across rooms, so for a series, reuse the exact material wording.
- Generated images are concepts. Check them before using them for anything official.
