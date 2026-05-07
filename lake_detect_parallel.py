"""
Sentinel-2 L2A NDWI for supraglacial lake detection via Planetary Computer.

"""

import os
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd
import planetary_computer
import rasterio
from pystac_client import Client
from pystac_client.exceptions import APIError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from cog_utils import write_cog, OVERVIEW_LEVELS_TILE

API_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"
TILE_LIST_PATH = "./sentinel_2_tiles.csv"
DATE_RANGE = "2021-05-01/2021-08-31"
CLOUD_COVER_MAX = 10

NDWI_MIN = 0.3  # Dunmire 2021 uses 0.5; 0.3 is more permissive

OUT_ROOT = "./lake_detection_binary_masks_parallel_v2"


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
        print(f"  skip (exists): {item_id}")
        return

    print(f"  reading: {item_id}")
    offset = _boa_offset(item)
    DN_offset = 10000.0 # try 2**14 https://github.com/Clay-foundation/model/issues/94

    try:
        with rasterio.open(item.assets["B02"].href) as src:
            blue = (src.read(1).astype(np.float32) + offset) / DN_offset
            profile = src.profile

        with rasterio.open(item.assets["B04"].href) as src:
            red = (src.read(1).astype(np.float32) + offset) / DN_offset

    except Exception as e:
        print(f"  FAILED {item_id}: {e}")
        return

    ndwi = (blue - red) / (blue + red)
    mask = (ndwi > NDWI_MIN).astype(np.int8)

    profile.update(dtype="int8")
    write_cog(mask, profile, out_file,
              tags={"source_items": item_id},
              overview_levels=OVERVIEW_LEVELS_TILE)

    print(f"  wrote: {item_id}")


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

    for tile in tiles:
        items = search_tile(client, tile)
        print(f"Tile {tile}: found {len(items)} datasets")
        if not items:
            continue

        max_workers = min(32, os.cpu_count() * 4)
        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            ex.map(lake_detect, [(item, tile) for item in items])


if __name__ == "__main__":
    main()
