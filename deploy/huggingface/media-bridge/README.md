---
title: MyCodexAI Media Bridge
emoji: 🎵
colorFrom: gray
colorTo: green
sdk: docker
app_port: 7860
---

# MyCodexAI Media Bridge

A private-key-protected, single-video audio bridge for MyCodexAI Music Lab.
It accepts only canonical public YouTube video URLs, limits clips to six minutes,
serializes extraction, and never uses a YouTube account or browser cookies.

The container includes yt-dlp and the pinned bgutil Proof-of-Origin provider.
Set the Hugging Face Space secret `MEDIA_BRIDGE_KEY` before use.
