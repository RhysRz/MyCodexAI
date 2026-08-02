"""Preflight a social-video source before the heavy Music AI setup."""

from cloud.runner.run_music_job import (
    RetryableMediaError,
    STARTED_MARKER,
    callback,
    prepare_media_source,
)


def main() -> int:
    STARTED_MARKER.write_text("started\n", encoding="utf-8")
    callback("running")
    try:
        metadata = prepare_media_source()
        print(f"Prepared {metadata.get('type', 'media')} source with {metadata.get('extraction_strategy', 'default')}")
        return 0
    except Exception as error:
        callback("failed", error_detail=str(error)[:3_000], retryable=isinstance(error, RetryableMediaError))
        print(f"::error::{error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
