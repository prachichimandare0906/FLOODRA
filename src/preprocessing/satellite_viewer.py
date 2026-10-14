import rasterio
import matplotlib.pyplot as plt

IMAGE_PATH = "data/raw/flood_image.tif"


def show_satellite_image():
    print("Opening Sentinel-1 image...")

    with rasterio.open(IMAGE_PATH) as src:
        print("\n--- Satellite Image Information ---")
        print("Width:", src.width)
        print("Height:", src.height)
        print("Number of bands:", src.count)
        print("CRS:", src.crs)
        print("Data type:", src.dtypes)

        image = src.read(1)

        print("First band loaded successfully!")
        print("Minimum value:", image.min())
        print("Maximum value:", image.max())

        plt.figure(figsize=(10, 8))
        plt.imshow(image, cmap="gray")
        plt.title("FLOODRA - Sentinel-1 Satellite Image")
        plt.xlabel("Pixel")
        plt.ylabel("Pixel")
        plt.colorbar(label="Backscatter")
        plt.tight_layout()
        plt.show()


if __name__ == "__main__":
    print("FLOODRA satellite viewer is ready.")
    show_satellite_image()
