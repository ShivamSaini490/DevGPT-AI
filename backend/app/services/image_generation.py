"""Free text-to-image providers used by the image-generation tool."""

import base64
import logging
import random
import re
import time
from dataclasses import dataclass
from io import BytesIO
from uuid import uuid4

import httpx
from huggingface_hub import InferenceClient
from PIL import Image, UnidentifiedImageError

from app.core.config import (
    CLOUDFLARE_ACCOUNT_ID,
    CLOUDFLARE_API_TOKEN,
    HF_TOKEN,
)
from app.core.paths import GENERATED_IMAGES_DIR
from app.services.files import image_extension, looks_like_image


IMAGE_REQUEST_TIMEOUT_SECONDS = 60.0
HF_REQUEST_TIMEOUT_SECONDS = 60.0
IMAGE_MAX_RETRIES = 2
IMAGE_RETRY_BACKOFF_SECONDS = 1.0
IMAGE_MAX_RETRY_DELAY_SECONDS = 10.0
HF_IMAGE_MODEL = "black-forest-labs/FLUX.1-schnell"
CLOUDFLARE_IMAGE_MODEL = "@cf/black-forest-labs/flux-1-schnell"
CLOUDFLARE_FALLBACK_IMAGE_MODEL = (
    "@cf/stabilityai/stable-diffusion-xl-base-1.0"
)
CLOUDFLARE_FLUX_PROVIDER = "Cloudflare Workers AI FLUX.1-schnell"
CLOUDFLARE_SDXL_PROVIDER = "Cloudflare Workers AI SDXL"
HF_PROVIDER = "Hugging Face FLUX.1-schnell"
NEGATIVE_PROMPT = (
    "blurry, dark, low quality, deformed hands, extra fingers, bad anatomy, "
    "watermark, text, logo, low resolution, soft details, distorted face, "
    "duplicate limbs, signature"
)

logger = logging.getLogger(__name__)


class ImageGenerationError(RuntimeError):
    """No configured image provider could produce a valid image."""


@dataclass(frozen=True)
class ProviderFailure:
    """A safe, user-displayable provider failure summary."""

    provider: str
    status: int | str
    reason: str

    def __str__(self) -> str:
        return f"{self.provider} [status {self.status}]: {self.reason}"


class ProviderRequestError(ImageGenerationError):
    """One provider request failed without exposing credentials."""

    def __init__(self, failure: ProviderFailure):
        self.failure = failure
        super().__init__(str(failure))


def _provider_name(model: str) -> str:
    if model == CLOUDFLARE_IMAGE_MODEL:
        return CLOUDFLARE_FLUX_PROVIDER
    if model == CLOUDFLARE_FALLBACK_IMAGE_MODEL:
        return CLOUDFLARE_SDXL_PROVIDER
    return f"Cloudflare Workers AI {model}"


def _safe_text(value: object, limit: int = 300) -> str:
    """Return compact provider diagnostics with local credentials redacted."""
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    for secret in (
        CLOUDFLARE_API_TOKEN,
        CLOUDFLARE_ACCOUNT_ID,
        HF_TOKEN,
    ):
        if secret:
            text = text.replace(secret, "[redacted]")
    text = re.sub(
        r"(?i)(authorization\s*[:=]\s*bearer\s+)[^\s,;]+",
        r"\1[redacted]",
        text,
    )
    return text[:limit] or "empty response body"


def _log_failure(failure: ProviderFailure, attempt: int) -> None:
    logger.error(
        "Image provider failure provider=%s status=%s attempt=%d/%d reason=%s",
        failure.provider,
        failure.status,
        attempt,
        IMAGE_MAX_RETRIES + 1,
        failure.reason,
    )


def _is_valid_image(data: bytes) -> bool:
    if not looks_like_image(data):
        return False
    try:
        with Image.open(BytesIO(data)) as image:
            image.verify()
    except (UnidentifiedImageError, OSError):
        return False
    return True


def _retry_delay(response: httpx.Response | None, attempt: int) -> float:
    if response is not None:
        value = response.headers.get("Retry-After", "").strip()
        if value:
            try:
                return min(float(value), IMAGE_MAX_RETRY_DELAY_SECONDS)
            except ValueError:
                pass
    return min(
        IMAGE_RETRY_BACKOFF_SECONDS * (attempt + 1),
        IMAGE_MAX_RETRY_DELAY_SECONDS,
    )


def _cloudflare_image(
    prompt: str,
    model: str = CLOUDFLARE_IMAGE_MODEL,
) -> bytes:
    """Run one Cloudflare request using the model's documented response form."""
    provider = _provider_name(model)
    url = (
        "https://api.cloudflare.com/client/v4/accounts/"
        f"{CLOUDFLARE_ACCOUNT_ID}/ai/run/{model}"
    )
    parameters: dict[str, object] = {"prompt": prompt}
    if model == CLOUDFLARE_IMAGE_MODEL:
        parameters["steps"] = 8

    logger.info(
        "Image provider request provider=%s model=%s endpoint=/accounts/"
        "[redacted]/ai/run/%s timeout=%.0fs",
        provider,
        model,
        model,
        IMAGE_REQUEST_TIMEOUT_SECONDS,
    )
    response = httpx.post(
        url,
        headers={"Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}"},
        json=parameters,
        timeout=IMAGE_REQUEST_TIMEOUT_SECONDS,
        follow_redirects=True,
    )
    try:
        logger.info(
            "Image provider response provider=%s status=%d",
            provider,
            response.status_code,
        )
        if response.status_code != 200:
            raise ProviderRequestError(
                ProviderFailure(
                    provider,
                    response.status_code,
                    _safe_text(response.text),
                )
            )

        if model == CLOUDFLARE_FALLBACK_IMAGE_MODEL:
            data = response.content
        else:
            try:
                payload = response.json()
                result = payload.get("result", {})
                encoded = result.get("image", "")
                if encoded.startswith("data:"):
                    encoded = encoded.split(",", 1)[-1]
                data = base64.b64decode(encoded, validate=True)
            except (ValueError, TypeError, AttributeError, KeyError) as exc:
                raise ProviderRequestError(
                    ProviderFailure(
                        provider,
                        200,
                        "response JSON did not contain valid base64 image data",
                    )
                ) from exc

        if not _is_valid_image(data):
            raise ProviderRequestError(
                ProviderFailure(provider, 200, "response was not a valid image")
            )
        return data
    finally:
        response.close()


def _download_cloudflare_model(prompt: str, model: str) -> bytes:
    """Run one Cloudflare model, retrying only transient failures."""
    provider = _provider_name(model)
    last_failure = ProviderFailure(provider, "unknown", "request did not run")
    for attempt in range(IMAGE_MAX_RETRIES + 1):
        response = None
        try:
            return _cloudflare_image(prompt, model)
        except ProviderRequestError as exc:
            last_failure = exc.failure
            _log_failure(last_failure, attempt + 1)
            retryable = (
                isinstance(last_failure.status, int)
                and (
                    last_failure.status == 429
                    or 500 <= last_failure.status <= 599
                )
            )
            if not retryable or attempt >= IMAGE_MAX_RETRIES:
                break
        except httpx.RequestError as exc:
            response = getattr(exc, "response", None)
            last_failure = ProviderFailure(
                provider,
                "network-error",
                _safe_text(exc),
            )
            _log_failure(last_failure, attempt + 1)
            if attempt >= IMAGE_MAX_RETRIES:
                break

        time.sleep(_retry_delay(response, attempt))

    raise ProviderRequestError(last_failure)


def _download_cloudflare(prompt: str) -> tuple[bytes, str]:
    """Try Cloudflare FLUX first, then Cloudflare SDXL."""
    failures = []
    for model in (CLOUDFLARE_IMAGE_MODEL, CLOUDFLARE_FALLBACK_IMAGE_MODEL):
        try:
            return _download_cloudflare_model(prompt, model), model
        except ProviderRequestError as exc:
            failures.append(exc.failure)
    raise ImageGenerationError("; ".join(str(item) for item in failures))


def _hugging_face_image(prompt: str) -> bytes:
    """Run one Hugging Face FLUX request."""
    logger.info(
        "Image provider request provider=%s model=%s timeout=%.0fs",
        HF_PROVIDER,
        HF_IMAGE_MODEL,
        HF_REQUEST_TIMEOUT_SECONDS,
    )
    client = InferenceClient(
        api_key=HF_TOKEN,
        provider="auto",
        timeout=HF_REQUEST_TIMEOUT_SECONDS,
    )
    image = client.text_to_image(
        prompt,
        model=HF_IMAGE_MODEL,
        negative_prompt=NEGATIVE_PROMPT,
        width=1024,
        height=1024,
        num_inference_steps=4,
        guidance_scale=0.0,
        seed=random.randint(1, 2_000_000_000),
    )
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def _failure_from_exception(provider: str, exc: Exception) -> ProviderFailure:
    response = getattr(exc, "response", None)
    status = getattr(response, "status_code", None)
    if status is not None:
        try:
            reason = _safe_text(response.text)
        except Exception:
            reason = _safe_text(exc)
        return ProviderFailure(provider, int(status), reason)
    if isinstance(exc, (httpx.RequestError, TimeoutError, ConnectionError)):
        return ProviderFailure(provider, "network-error", _safe_text(exc))
    return ProviderFailure(provider, "error", _safe_text(exc))


def _download_hugging_face(prompt: str) -> bytes:
    last_failure = ProviderFailure(HF_PROVIDER, "unknown", "request did not run")
    for attempt in range(IMAGE_MAX_RETRIES + 1):
        response = None
        try:
            data = _hugging_face_image(prompt)
            if not _is_valid_image(data):
                raise ProviderRequestError(
                    ProviderFailure(HF_PROVIDER, 200, "response was not a valid image")
                )
            return data
        except ProviderRequestError as exc:
            last_failure = exc.failure
        except Exception as exc:
            response = getattr(exc, "response", None)
            last_failure = _failure_from_exception(HF_PROVIDER, exc)

        _log_failure(last_failure, attempt + 1)
        retryable = last_failure.status == "network-error" or (
            isinstance(last_failure.status, int)
            and (last_failure.status == 429 or 500 <= last_failure.status <= 599)
        )
        if not retryable or attempt >= IMAGE_MAX_RETRIES:
            break
        time.sleep(_retry_delay(response, attempt))

    raise ProviderRequestError(last_failure)


def _cloudflare_configuration_failure() -> ProviderFailure | None:
    missing = []
    if not CLOUDFLARE_ACCOUNT_ID:
        missing.append("CLOUDFLARE_ACCOUNT_ID")
    if not CLOUDFLARE_API_TOKEN:
        missing.append("CLOUDFLARE_API_TOKEN")
    if not missing:
        return None
    return ProviderFailure(
        "Cloudflare Workers AI",
        "not-configured",
        f"{', '.join(missing)} is missing or contains a placeholder",
    )


def _generate_image_bytes(prompt: str) -> tuple[bytes, str]:
    """Run the strict provider chain without anonymous image fallbacks."""
    failures: list[ProviderFailure] = []
    configuration_failure = _cloudflare_configuration_failure()
    if configuration_failure is None:
        for model in (CLOUDFLARE_IMAGE_MODEL, CLOUDFLARE_FALLBACK_IMAGE_MODEL):
            try:
                data = _download_cloudflare_model(prompt, model)
                provider = _provider_name(model)
                logger.info(
                    "Image generation succeeded provider=%s model=%s",
                    provider,
                    model,
                )
                return data, provider
            except ProviderRequestError as exc:
                failures.append(exc.failure)
    else:
        logger.error("Image provider unavailable: %s", configuration_failure)
        failures.extend(
            ProviderFailure(
                provider,
                configuration_failure.status,
                configuration_failure.reason,
            )
            for provider in (
                CLOUDFLARE_FLUX_PROVIDER,
                CLOUDFLARE_SDXL_PROVIDER,
            )
        )

    if HF_TOKEN:
        try:
            data = _download_hugging_face(prompt)
            logger.info("Image generation succeeded provider=%s", HF_PROVIDER)
            return data, HF_PROVIDER
        except ProviderRequestError as exc:
            failures.append(exc.failure)

    raise ImageGenerationError(
        "All image providers failed: "
        + "; ".join(str(failure) for failure in failures)
    )


def _verify_saved_image(path) -> None:
    try:
        with Image.open(path) as image:
            image.verify()
    except (UnidentifiedImageError, OSError) as exc:
        path.unlink(missing_ok=True)
        raise ImageGenerationError(
            "Generated image failed validation after it was saved."
        ) from exc


def generate_image_with_provider(prompt: str) -> tuple[str, str]:
    """Generate a validated image and return its saved path and provider name."""
    prompt = prompt.strip()
    if not prompt:
        raise ImageGenerationError("The image prompt cannot be empty.")

    data, provider = _generate_image_bytes(prompt)
    GENERATED_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    path = GENERATED_IMAGES_DIR / f"{uuid4().hex}{image_extension(data)}"
    path.write_bytes(data)
    _verify_saved_image(path)
    logger.info("Generated image validated path=%s provider=%s", path, provider)
    return str(path.resolve()), provider


def generate_image(prompt: str) -> str:
    """Generate an image, save it under outputs/images, and return its path."""
    path, _provider = generate_image_with_provider(prompt)
    return path
