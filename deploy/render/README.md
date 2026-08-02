# Render Free deployment

Deploy `../huggingface/media-bridge` as a free Docker Web Service. The service
uses Render's generated `onrender.com` HTTPS origin and a generated
`MEDIA_BRIDGE_KEY`. Copy those two values into the GitHub Actions secrets
`MYCODEXAI_MEDIA_BRIDGE_URL` and `MYCODEXAI_MEDIA_BRIDGE_KEY`.

Free Render services sleep after 15 idle minutes and wake on the next request.
MyCodexAI retries a bridge request for up to one minute to cover a normal cold
start. No source audio is persisted by the bridge.
