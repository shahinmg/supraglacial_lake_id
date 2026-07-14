"""
Sentinel-2 L2A NDWI for supraglacial lake detection

"""

import os
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
import pandas as pd
import planetary_computer
import rasterio
from pystac_client import Client
from pystac_client.exceptions import APIError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential
from tqdm import tqdm

API_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"
TILE_LIST_PATH = "./sentinel_2_tiles.csv"
DATE_RANGE = "2021-05-01/2021-08-31"
CLOUD_COVER_MAX = 10

NDWI_MIN = 0.3  # Dunmire 2021 uses 0.5; 0.3 bc we clip to ice sheet extents from Greene 2024

OUT_ROOT = "./lake_detection_binary_masks_parallel_v2"

# GDAL tuning for reading remote COGs from Planetary Computer (Azure blob).
GDAL_ENV = dict(
    GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
    CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif",
    GDAL_HTTP_MULTIPLEX="YES",
    GDAL_HTTP_VERSION="2",
    VSI_CACHE="TRUE",
    VSI_CACHE_SIZE=str(64 * 1024 * 1024),
)


def _boa_offset(item):
    """BOA_ADD_OFFSET introduced in processing baseline 04.00 (Jan 2022)."""
    baseline = float(item.properties.get("s2:processing_baseline", "0"))
    return -1000.0 if baseline >= 4.0 else 0.0


def lake_detect(args):
    item, tile = args

    item = planetary_computer.sign(item)  # fresh SAS tokens inside the worker
    item_id = item.id

    out_dir = os.path.join(OUT_ROOT, tile)
    os.makedirs(out_dir, exist_ok=True)
    out_file = os.path.join(out_dir, f"{item_id}_lake_pixels.tif")

    if os.path.exists(out_file):
        tqdm.write(f"  skip (exists): {item_id}")
        return

    offset = _boa_offset(item)
    DN_offset = 10000.0 # try 2**14 https://github.com/Clay-foundation/model/issues/94

    try:
        with rasterio.open(item.assets["B02"].href) as src:
            blue = (src.read(1).astype(np.float32) + offset) / DN_offset
            profile = src.profile

        with rasterio.open(item.assets["B04"].href) as src:
            red = (src.read(1).astype(np.float32) + offset) / DN_offset

    except Exception as e:
        tqdm.write(f"  FAILED {item_id}: {e}")
        return

    # Compute NDWI with minimal peak memory
    num = blue - red #numerator
    den = blue + red #denominator
    del blue, red
    with np.errstate(divide="ignore", invalid="ignore"):
        num /= den  # in place; num now holds NDWI
    del den
    mask = (num > NDWI_MIN).astype(np.int8)

    # Per-tile intermediate: valid COG, no overviews
    for k in ("tiled", "blockxsize", "blockysize", "interleave", "compress", "zstd_level", "predictor"):
        profile.pop(k, None)
    profile.update(driver="COG", dtype="int8", count=1,
                   compress="ZSTD", level=1, blocksize=512, overviews="NONE")  
    with rasterio.open(out_file, "w", **profile) as dst:
        dst.write(mask, 1)
        dst.update_tags(source_items=item_id)


@retry(
    retry=retry_if_exception_type(APIError),
    wait=wait_exponential(multiplier=2, min=4, max=60),
    stop=stop_after_attempt(5),
    reraise=True,
)
def search_tile(client, tile):
    search = client.search(
        collections=["sentinel-2-l2a"],
        datetime=DATE_RANGE,
        query={
            "eo:cloud_cover": {"lt": CLOUD_COVER_MAX},
            "s2:mgrs_tile": {"eq": tile},
        },
        sortby=["-properties.datetime", "+id"],
    )
    return list(search.items())


def main():
    client = Client.open(API_URL, modifier=planetary_computer.sign_inplace)
    tiles = pd.read_csv(TILE_LIST_PATH)["tile"]
    # Capped by memory, not CPU: each worker peaks at ~1.4 GB on a full S2 tile.
    max_workers = min(10, os.cpu_count())

    with rasterio.Env(**GDAL_ENV):
        for tile in tiles:
            items = search_tile(client, tile)
            print(f"Tile {tile}: found {len(items)} datasets")
            if not items:
                continue

            with ThreadPoolExecutor(max_workers=max_workers) as ex:
                futures = [ex.submit(lake_detect, (item, tile)) for item in items]
                for fut in tqdm(as_completed(futures), total=len(futures),
                                desc=tile, unit="scene"):
                    fut.result()  # re-raise any worker exception instead of swallowing it


if __name__ == "__main__":
    main()
