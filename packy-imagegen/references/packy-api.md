# PackyAPI GPT Image Reference

Official guide (written for `gpt-image-2`): <https://docs.packyapi.com/docs/paint/GPTImage.html>

## Models

- `gpt-image-2.6-flare` — default for this skill.
- `gpt-image-2.6-sunburst` — sibling variant with the same endpoint.
- `gpt-image-2.5-flare` and `gpt-image-2.5-sunburst` — previous generation, still available.
- `gpt-image-2` — legacy model.

All of them are served from the `image` group.

## Endpoint

- Base URL: `https://cf.api.fan/v1` (production route recommended by Packy). The script also accepts `--base-url` overrides.
- Generate: `POST /images/generations`
- Authentication: bearer token from a group with access to the model
- Unsupported generation routes: Responses API and Chat Completions API

## Parameters

- `prompt`: required string
- `n`: only `1`
- `size`: `auto` or a valid custom size; `1024x1024`, `1536x1024`, `1024x1536`, `2048x2048`, and `3840x2160` work with 2.6-flare
- `quality`: `low`, `medium`, `high`, or `auto`
- `output_format`: prefer `png` or `jpeg`
- `background`: default or `opaque`; transparent is unsupported
- `moderation`: `auto` or `low`
- `response_format`: **not accepted by `gpt-image-2.6-flare`**. Sending it returns `400 unknown_parameter`. Omit it and read `data[0].b64_json` or `data[0].url`.
- `stream` and `partial_images`: not supported
- `style`: not needed

Custom sizes must have edges divisible by 16, a maximum edge of 3840, a long-to-short ratio no greater than 3:1, and 655,360 to 8,294,400 total pixels.

## Observed pricing

The Packy catalog listed `gpt-image-2.6-flare` at $0.02469-$0.71157 per image on 2026-11-22. The actual pre-charge depends on size and quality. Confirm the current price in the Packy dashboard before large runs, and choose `low`, `medium`, or `high` explicitly instead of assuming `auto` is cheaper.

## Response

`gpt-image-2.6-flare` returned Base64 data in live tests:

```json
{
  "created": 1792316791,
  "background": "opaque",
  "data": [{"b64_json": "iVBORw0KGgo...", "revised_prompt": "..."}]
}
```

The bundled script also accepts a `data[0].url` response for compatibility.

## Errors

- `401` or `403`: invalid token or wrong permissions.
- `403 insufficient_user_quota`: the prepaid balance is below the request estimate. Top up, or lower quality and size.
- `503 model_not_found`: the token's group has no distributor for that model. GPT-Image models need the `image` group.
- `400 unknown_parameter` on `response_format`: remove the field for the 2.5 models.
- Timeout near 60 seconds: bypass a local proxy for `cf.api.fan` (or `api.fan`) or increase the client timeout. Image generation can take several minutes.
- Successful response but no file: inspect `data[0]`; PackyAPI may return either `url` or `b64_json`. The bundled script handles both.
