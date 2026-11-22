"""Run a direct Cloudflare Workers AI image-generation smoke test."""

import sys
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from PIL import Image


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from app.core.config import (  # noqa: E402
    CLOUDFLARE_ACCOUNT_ID,
    CLOUDFLARE_API_TOKEN,
    IMAGE_CREDENTIAL_STATUS,
)
from app.core.paths import GENERATED_IMAGES_DIR  # noqa: E402
from app.services.image_generation import (  # noqa: E402
    CLOUDFLARE_IMAGE_MODEL,
    CloudflareAPIError,
    _cloudflare_image,
    _is_valid_image,
)
from app.services.files import image_extension  # noqa: E402


PROMPT = "a red apple on a wooden table"


def main() -> None:
    for name in ("CLOUDFLARE_ACCOUNT_ID", "CLOUDFLARE_API_TOKEN"):
        status = IMAGE_CREDENTIAL_STATUS[name]
        print(
            f"{name}: set={status['set']} length={status['length']} "
            f"usable={status['usable']}"
        )

    if not CLOUDFLARE_ACCOUNT_ID or not CLOUDFLARE_API_TOKEN:
        raise RuntimeError(
            "Cloudflare credentials are missing or contain placeholder values."
        )

    print(f"provider=Cloudflare Workers AI")
    print(f"model={CLOUDFLARE_IMAGE_MODEL}")
    print(f"prompt={PROMPT}")
    try:
        data = _cloudflare_image(PROMPT, CLOUDFLARE_IMAGE_MODEL)
    except CloudflareAPIError as exc:
        print(f"http_status={exc.status_code}")
        print(f"response_body={exc.response_body[:500]}")
        raise

    print("http_status=200")
    if not _is_valid_image(data):
        raise RuntimeError("Cloudflare returned HTTP 200 but not a valid image.")

    GENERATED_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    output_path = GENERATED_IMAGES_DIR / (
        f"cloudflare-red-apple-{uuid4().hex}{image_extension(data)}"
    )
    output_path.write_bytes(data)
    with Image.open(BytesIO(data)) as image:
        image.verify()
    with Image.open(output_path) as image:
        print(f"image_format={image.format}")
        print(f"image_size={image.width}x{image.height}")
    print("valid_image=True")
    print(f"saved_path={output_path.resolve()}")


if __name__ == "__main__":
    main()
