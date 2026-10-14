import rasterio
import numpy as np
import matplotlib.pyplot as plt

IMAGE_PATH = "data/raw/flood_image.tif"


def load_image():
    with rasterio.open(IMAGE_PATH) as src:
        image = src.read(1).astype(np.float32)

        print("Image loaded successfully!")
        print("Shape:", image.shape)
        print("Minimum:", image.min())
        print("Maximum:", image.max())

        return image


def normalize_image(image):
    min_value = np.percentile(image, 2)
    max_value = np.percentile(image, 98)

    if max_value == min_value:
        return np.zeros_like(image, dtype=np.float32)

    normalized = (image - min_value) / (max_value - min_value)
    return np.clip(normalized, 0, 1)


def show_normalized_image(image):
    plt.figure(figsize=(10, 8))
    plt.imshow(image, cmap="gray")
    plt.title("FLOODRA - Normalized Sentinel-1 Image")
    plt.xlabel("Pixel")
    plt.ylabel("Pixel")
    plt.colorbar(label="Normalized Backscatter")
    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    print("FLOODRA preprocessing started...")

    image = load_image()
    normalized_image = normalize_image(image)

    print("Normalization completed!")
    show_normalized_image(normalized_image)
