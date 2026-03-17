"""Image Processing Module — Memory-optimized preprocessing for Render free tier."""

import gc

import numpy as np
from PIL import Image, ImageFilter, ImageOps

# Maximum image dimension to prevent memory issues on 512MB RAM
MAX_IMAGE_DIM = 1200


def preprocess_image(image_path):
    """
    Preprocess an answer script image for text extraction.
    
    Optimized pipeline for low memory:
    1. Read and resize image (limit dimensions)
    2. Convert to grayscale
    3. Light denoising
    4. Adaptive thresholding
    5. Memory cleanup

    Returns: preprocessed image as numpy array
    """
    with Image.open(image_path) as img:
        img = img.convert("L")
        img = resize_if_needed(img, MAX_IMAGE_DIM)

        # Lightweight denoise/contrast path that works reliably in Colab.
        img = img.filter(ImageFilter.MedianFilter(size=3))
        img = ImageOps.autocontrast(img)

        arr = np.array(img)

    # Simple thresholding to produce a clean grayscale/binary-like image.
    threshold = max(80, int(arr.mean()))
    binary = np.where(arr > threshold, 255, 0).astype(np.uint8)

    gc.collect()
    return binary


def resize_if_needed(image, max_dim=MAX_IMAGE_DIM):
    """Resize large images to fit within max dimension (preserves aspect ratio)."""
    width, height = image.size

    if max(height, width) <= max_dim:
        return image

    if width > height:
        scale = max_dim / width
        new_size = (max_dim, int(height * scale))
    else:
        scale = max_dim / height
        new_size = (int(width * scale), max_dim)

    return image.resize(new_size, Image.Resampling.LANCZOS)


def get_image_size_mb(image):
    """Get approximate memory size of image in MB."""
    return image.nbytes / (1024 * 1024)
