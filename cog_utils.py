"""Shared utilities for writing Cloud-Optimized GeoTIFFs."""

import os
import tempfile

import rasterio
from rasterio.enums import Resampling
from rasterio.shutil import copy as rio_copy


COG_PROFILE = {
    "driver": "GTiff",
    "compress": "zstd",
    "zstd_level": 9,
    "tiled": True,
    "blockxsize": 512,
    "blockysize": 512,
    "interleave": "band",
    "copy_src_overviews": True,
}

# Per-tile masks don't need the coarsest overview levels
OVERVIEW_LEVELS_TILE  = [2, 4, 8, 16, 32]
OVERVIEW_LEVELS_MOSAIC = [2, 4, 8, 16, 32, 64]

# Keys that must not be passed to the intermediate temp write
_COG_ONLY_KEYS = ("compress", "zstd_level", "tiled", "blockxsize", "blockysize",
                  "interleave", "copy_src_overviews")


def write_cog(data, profile, dst_path, tags=None, overview_levels=OVERVIEW_LEVELS_TILE):
    """Write a numpy array as a COG with ZSTD compression and overviews.

    Args:
        data:            2-D numpy array (single band).
        profile:         Rasterio profile dict for the output.
        dst_path:        Output file path.
        tags:            Optional dict of dataset-level tags to embed.
        overview_levels: List of overview decimation factors.
    """
    tmp_profile = {k: v for k, v in profile.items() if k not in _COG_ONLY_KEYS}
    tmp_profile.update(driver="GTiff", count=1)

    with tempfile.NamedTemporaryFile(suffix=".tif", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        with rasterio.open(tmp_path, "w", **tmp_profile) as tmp_ds:
            tmp_ds.write(data, 1)
            if tags:
                tmp_ds.update_tags(**tags)

        with rasterio.open(tmp_path, "r+") as tmp_ds:
            tmp_ds.build_overviews(overview_levels, Resampling.nearest)
            tmp_ds.update_tags(ns="rio_overview", resampling="nearest")

        with rasterio.open(tmp_path) as tmp_ds:
            out_profile = tmp_ds.profile.copy()
            out_profile.update(COG_PROFILE)
            rio_copy(tmp_ds, dst_path, **out_profile)
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
