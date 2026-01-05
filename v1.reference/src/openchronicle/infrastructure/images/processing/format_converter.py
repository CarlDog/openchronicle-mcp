"""
Image Format Converter for OpenChronicle

Handles image format conversion, optimization, and processing utilities.
Provides format standardization and optimization for generated images.
"""

import base64
import binascii
import io
import logging
from enum import Enum
from pathlib import Path
from typing import Any

from PIL import Image
from PIL import UnidentifiedImageError

from ..shared.image_models import ImageSize
from ..shared.validation_utils import ImageValidationError


logger = logging.getLogger(__name__)


class ImageFormat(Enum):
    """Supported image formats"""

    PNG = "PNG"
    JPEG = "JPEG"
    WEBP = "WEBP"
    GIF = "GIF"


class ImageQuality(Enum):
    """Image quality levels for compression"""

    LOW = 60
    MEDIUM = 80
    HIGH = 95
    MAXIMUM = 100


class ImageFormatConverter:
    """Handles image format conversion and optimization"""

    def __init__(self):
        self.supported_input_formats = {
            ".png",
            ".jpg",
            ".jpeg",
            ".webp",
            ".gif",
            ".bmp",
            ".tiff",
        }
        self.supported_output_formats = {
            ImageFormat.PNG,
            ImageFormat.JPEG,
            ImageFormat.WEBP,
            ImageFormat.GIF,
        }

    async def convert_image(
        self,
        source_path: Path,
        target_path: Path,
        target_format: str,
        optimize: bool = True,
    ) -> bool:
        """Convert an image file on disk to a target format.

        Returns True on success, False on failure. Uses existing conversion utilities.
        """
        try:
            # Read source bytes
            data = source_path.read_bytes()

            # Map string to ImageFormat enum
            fmt_str = target_format.upper()
            if fmt_str == "JPG":
                fmt_str = "JPEG"
            try:
                fmt = ImageFormat[fmt_str]
            except KeyError:
                # Fallback: try by value
                fmt = ImageFormat(fmt_str)

            # Optionally optimize size before/after conversion
            converted = self.convert_format(data, fmt)
            if optimize:
                # Keep under ~1MB by default
                converted = self.optimize_size(converted, max_size_kb=1024)

            # Ensure output directory exists
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_bytes(converted)
        except Exception:
            logger.exception("Failed to convert image on disk")
            return False
        else:
            return True

    def detect_format(self, image_data: bytes) -> ImageFormat | None:
        """Detect image format from binary data"""
        try:
            # Check magic bytes
            if image_data.startswith(b"\x89PNG\r\n\x1a\n"):
                return ImageFormat.PNG
            if image_data.startswith(b"\xff\xd8\xff"):
                return ImageFormat.JPEG
            if image_data.startswith(b"RIFF") and b"WEBP" in image_data[:20]:
                return ImageFormat.WEBP
            if image_data.startswith(b"GIF87a") or image_data.startswith(b"GIF89a"):
                return ImageFormat.GIF
            # Try to open with PIL to detect format
            with Image.open(io.BytesIO(image_data)) as img:
                format_name = img.format
                if format_name in ["PNG", "JPEG", "WEBP", "GIF"]:
                    return ImageFormat(format_name)

        except (OSError, ValueError, UnidentifiedImageError) as e:
            logger.warning(f"Could not detect image format: {e}")

        return None

    def convert_format(
        self,
        image_data: bytes,
        target_format: ImageFormat,
        quality: ImageQuality = ImageQuality.HIGH,
    ) -> bytes:
        """Convert image to target format"""
        try:
            with Image.open(io.BytesIO(image_data)) as img:
                # Convert to RGB if necessary (for JPEG)
                if target_format == ImageFormat.JPEG and img.mode in (
                    "RGBA",
                    "LA",
                    "P",
                ):
                    # Create white background for transparency
                    background = Image.new("RGB", img.size, (255, 255, 255))
                    if img.mode == "P":
                        img = img.convert("RGBA")
                    background.paste(img, mask=img.split()[-1] if "A" in img.mode else None)
                    img = background

                # Prepare save parameters
                save_kwargs: dict[str, Any] = {"format": target_format.value}

                if target_format == ImageFormat.JPEG:
                    save_kwargs["quality"] = quality.value
                    save_kwargs["optimize"] = True
                elif target_format == ImageFormat.WEBP:
                    save_kwargs["quality"] = quality.value
                    save_kwargs["method"] = 6  # Better compression
                elif target_format == ImageFormat.PNG:
                    save_kwargs["optimize"] = True

                # Convert and return
                output = io.BytesIO()
                img.save(output, **save_kwargs)
                return output.getvalue()

        except (OSError, ValueError, UnidentifiedImageError) as e:
            logger.exception("Format conversion failed")
            raise ImageValidationError(f"Could not convert to {target_format.value}: {e}") from e

    def resize_image(self, image_data: bytes, target_size: ImageSize, maintain_aspect: bool = True) -> bytes:
        """Resize image to target dimensions"""
        try:
            target_width, target_height = map(int, target_size.value.split("x"))

            with Image.open(io.BytesIO(image_data)) as img:
                if maintain_aspect:
                    # Calculate aspect ratio preserving resize
                    img.thumbnail((target_width, target_height), Image.Resampling.LANCZOS)

                    # Create new image with target size and center the resized image
                    new_img = Image.new("RGB", (target_width, target_height), (255, 255, 255))
                    paste_x = (target_width - img.width) // 2
                    paste_y = (target_height - img.height) // 2
                    new_img.paste(img, (paste_x, paste_y))
                    img = new_img
                else:
                    # Direct resize (may distort aspect ratio)
                    img = img.resize((target_width, target_height), Image.Resampling.LANCZOS)

                # Save to bytes
                output = io.BytesIO()
                img.save(output, format="PNG")
                return output.getvalue()

        except (OSError, ValueError, UnidentifiedImageError) as e:
            logger.exception("Image resize failed")
            raise ImageValidationError(f"Could not resize image: {e}") from e

    def optimize_size(self, image_data: bytes, max_size_kb: int = 1024) -> bytes:
        """Optimize image size to stay under size limit"""
        current_size = len(image_data) / 1024  # KB

        if current_size <= max_size_kb:
            return image_data

        try:
            # Try different quality levels
            quality_levels = [ImageQuality.HIGH, ImageQuality.MEDIUM, ImageQuality.LOW]

            for quality in quality_levels:
                # Try WEBP first (better compression)
                try:
                    optimized = self.convert_format(image_data, ImageFormat.WEBP, quality)
                    if len(optimized) / 1024 <= max_size_kb:
                        return optimized
                except (ImageValidationError, OSError, ValueError, UnidentifiedImageError):
                    # Continue trying other strategies
                    pass

                # Try JPEG
                try:
                    optimized = self.convert_format(image_data, ImageFormat.JPEG, quality)
                    if len(optimized) / 1024 <= max_size_kb:
                        return optimized
                except (ImageValidationError, OSError, ValueError, UnidentifiedImageError):
                    # Continue trying other strategies
                    pass

            # If still too large, try reducing dimensions
            with Image.open(io.BytesIO(image_data)) as img:
                width, height = img.size

                # Reduce by 20% each iteration
                for scale in [0.8, 0.6, 0.4]:
                    new_width = int(width * scale)
                    new_height = int(height * scale)

                    resized = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

                    output = io.BytesIO()
                    resized.save(output, format="WEBP", quality=ImageQuality.MEDIUM.value)

                    if len(output.getvalue()) / 1024 <= max_size_kb:
                        return output.getvalue()

            # Last resort: return heavily compressed version
            logger.warning(f"Could not optimize image under {max_size_kb}KB, using maximum compression")
            return self.convert_format(image_data, ImageFormat.WEBP, ImageQuality.LOW)

        except (OSError, ValueError, UnidentifiedImageError) as e:
            logger.exception("Image optimization failed")
            return image_data  # Return original if optimization fails

    def create_thumbnail(self, image_data: bytes, size: tuple[int, int] = (200, 200)) -> bytes:
        """Create a thumbnail version of the image"""
        try:
            with Image.open(io.BytesIO(image_data)) as img:
                # Create thumbnail maintaining aspect ratio
                img.thumbnail(size, Image.Resampling.LANCZOS)

                # Save as WEBP for good compression
                output = io.BytesIO()
                img.save(output, format="WEBP", quality=80)
                return output.getvalue()

        except (OSError, ValueError, UnidentifiedImageError) as e:
            logger.exception("Thumbnail creation failed")
            raise ImageValidationError(f"Could not create thumbnail: {e}") from e

    def add_watermark(
        self,
        image_data: bytes,
        watermark_text: str = "OpenChronicle",
        opacity: float = 0.3,
        position: str = "bottom-right",
    ) -> bytes:
        """Add a watermark to the image"""
        try:
            with Image.open(io.BytesIO(image_data)) as img:
                # Convert to RGBA for transparency
                if img.mode != "RGBA":
                    img = img.convert("RGBA")

                # Create watermark
                watermark = Image.new("RGBA", img.size, (0, 0, 0, 0))

                try:
                    from PIL import ImageDraw
                    from PIL import ImageFont

                    draw = ImageDraw.Draw(watermark)

                    # Try to use a nice font
                    try:
                        font_size = max(12, min(img.width, img.height) // 40)
                        font = ImageFont.truetype("arial.ttf", font_size)
                    except (OSError, ValueError):
                        font = ImageFont.load_default()

                    # Calculate text position
                    bbox = draw.textbbox((0, 0), watermark_text, font=font)
                    text_width = bbox[2] - bbox[0]
                    text_height = bbox[3] - bbox[1]

                    margin = 10
                    if position == "bottom-right":
                        x = img.width - text_width - margin
                        y = img.height - text_height - margin
                    elif position == "bottom-left":
                        x = margin
                        y = img.height - text_height - margin
                    elif position == "top-right":
                        x = img.width - text_width - margin
                        y = margin
                    elif position == "top-left":
                        x = margin
                        y = margin
                    else:  # center
                        x = (img.width - text_width) // 2
                        y = (img.height - text_height) // 2

                    # Draw watermark with transparency
                    alpha = int(255 * opacity)
                    draw.text((x, y), watermark_text, fill=(255, 255, 255, alpha), font=font)

                    # Composite watermark onto image
                    img = Image.alpha_composite(img, watermark)

                except ImportError:
                    logger.warning("PIL ImageDraw not available, skipping watermark")
                    return image_data

                # Convert back to RGB if needed and save
                if img.mode == "RGBA":
                    background = Image.new("RGB", img.size, (255, 255, 255))
                    background.paste(img, mask=img.split()[3])
                    img = background

                output = io.BytesIO()
                img.save(output, format="PNG")
                return output.getvalue()

        except (OSError, ValueError, UnidentifiedImageError) as e:
            logger.exception("Watermark addition failed")
            return image_data  # Return original if watermarking fails

    def get_image_info(self, image_data: bytes) -> dict[str, Any]:
        """Get information about an image"""
        try:
            with Image.open(io.BytesIO(image_data)) as img:
                return {
                    "format": img.format,
                    "mode": img.mode,
                    "size": img.size,
                    "width": img.width,
                    "height": img.height,
                    "has_transparency": img.mode in ("RGBA", "LA") or "transparency" in img.info,
                    "file_size_bytes": len(image_data),
                    "file_size_kb": len(image_data) / 1024,
                    "aspect_ratio": img.width / img.height if img.height > 0 else 0,
                }
        except (OSError, ValueError, UnidentifiedImageError) as e:
            logger.exception("Could not get image info")
            return {"error": str(e)}

    def validate_image_data(self, image_data: bytes) -> tuple[bool, str | None]:
        """Validate that image data is a valid image"""
        try:
            with Image.open(io.BytesIO(image_data)) as img:
                # Try to load the image
                img.load()

                # Check basic constraints
                if img.width <= 0 or img.height <= 0:
                    return False, "Invalid image dimensions"

                if img.width > 4096 or img.height > 4096:
                    return False, "Image too large (max 4096x4096)"

                if len(image_data) > 50 * 1024 * 1024:  # 50MB
                    return False, "Image file too large (max 50MB)"

                return True, None

        except (OSError, ValueError, UnidentifiedImageError) as e:
            return False, f"Invalid image data: {e}"

    def to_base64(self, image_data: bytes) -> str:
        """Convert image data to base64 string"""
        return base64.b64encode(image_data).decode("utf-8")

    def from_base64(self, base64_string: str) -> bytes:
        """Convert base64 string to image data"""
        try:
            return base64.b64decode(base64_string)
        except (binascii.Error, ValueError) as e:
            raise ImageValidationError(f"Invalid base64 image data: {e}") from e

    def batch_convert(
        self,
        image_files: list[str],
        target_format: ImageFormat,
        output_dir: str,
        quality: ImageQuality = ImageQuality.HIGH,
    ) -> dict[str, Any]:
        """Convert multiple image files to target format"""
        results = {"successful": [], "failed": [], "total_processed": 0}

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        for file_path in image_files:
            try:
                input_path = Path(file_path)
                if not input_path.exists():
                    results["failed"].append({"file": file_path, "error": "File not found"})
                    continue

                # Read input file
                with open(input_path, "rb") as f:
                    image_data = f.read()

                # Convert format
                converted_data = self.convert_format(image_data, target_format, quality)

                # Generate output filename
                output_filename = input_path.stem + f".{target_format.value.lower()}"
                output_file = output_path / output_filename

                # Write output file
                with open(output_file, "wb") as f:
                    f.write(converted_data)

                results["successful"].append(
                    {
                        "input": file_path,
                        "output": str(output_file),
                        "size_reduction": len(image_data) - len(converted_data),
                    }
                )

            except (OSError, ImageValidationError, ValueError) as e:
                results["failed"].append({"file": file_path, "error": str(e)})

            results["total_processed"] += 1

        return results
