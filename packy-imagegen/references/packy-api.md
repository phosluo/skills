# PackyAPI GPT Image Reference

Official guide (written for `gpt-image-2`): <https://docs.packyapi.com/docs/paint/GPTImage.html>

## Models

- `gpt-image-2.5-flare` — default for this skill, served from the `image` group.
- `gpt-image-2.5-sunburst` — sibling variant with the same endpoint and pricing.
- `gpt-image-2` — legacy model served from the `sora` group.

## Endpoint

- Base URL: `https://www.packyapi.com/v1`
- Generate: `POST /images/generations`
- Authentication: bearer token from a group with access to the model
- Unsupported generation routes: Responses API and Chat Completions API

## Parameters

- `prompt`: required string
- `n`: only `1`
- `size`: `auto` or a valid custom size; `1024x1024`, `1536x1024`, `1024x1536`, `2048x2048`, and `3840x2160` work
- `quality`: `low`, `medium`, `high`, or `auto`
- `output_format`: prefer `png` or `jpeg`
- `background`: default or `opaque`; transparent is unsupported
- `moderation`: `auto` or `low`
- `response_format`: **not accepted by `gpt-image-2.5-flare`**. Sending it returns `400 unknown_parameter`. Omit it and read `data[0].b64_json`.
- `stream` and `partial_images`: not supported
- `style`: not needed

Custom sizes must have edges divisible by 16, a maximum edge of 3840, a long-to-short ratio no greater than 3:1, and 655,360 to 8,294,400 total pixels.

## Observed pricing

Measured on 2026-10-18 in USD per image; prices can change, so confirm in the Packy dashboard.

| Size | low | medium | high | auto |
|------|-----|--------|------|------|
| 1024x1024 | 0.0294 | 0.06585 | 0.2634 | 1.0536 |
| 1536x1024 | 0.0237 | 0.05145 | 0.2058 | 0.8232 |
| 2048x2048 | 0.05955 | 0.1338 | 0.5352 | 2.1408 |
| 3840x2160 | 0.05565 | 0.12975 | 0.5004 | 2.0013 |

`auto` is about four times the `high` price at the same size, so choose `low`, `medium`, or `high` explicitly.

## Response

`gpt-image-2.5-flare` returns Base64 data by default:

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
- `503 model_not_found`: the token's group has no distributor for that model. `gpt-image-2.5-flare` needs the `image` group.
- `400 unknown_parameter` on `response_format`: remove the field for the 2.5 models.
- Timeout near 60 seconds: bypass a local proxy for `packyapi.com` or increase the client timeout. Image generation can take several minutes.
- Successful response but no file: inspect `data[0]`; PackyAPI may return either `url` or `b64_json`. The bundled script handles both.
