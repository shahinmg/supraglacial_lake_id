# supraglacial_lake_id


A pipeline for NDWI masking for supraglacial lakes in central-west Greenland using Sentinel-2 L2A imagery from Microsoft Planetary Computer. The final output are Zarr stores for a particular year's melt season.

## Installation

The heavy geospatial stack (rasterio/GDAL) installs most reliably from conda-forge:

```bash
conda env create -f environment.yml
conda activate supraglacial-lake-id
pip install --no-deps -e .        # add the package + CLI entry points
```

Or install everything from PyPI-style wheels (rasterio ships bundled GDAL):

```bash
pip install -e .                  # editable, from a clone
# or
pip install .
```

## Usage

Installing exposes one console command per pipeline stage. Each stage reads its
configuration (date range, input/output directories, thresholds) from constants
at the top of its module — edit those to point at your data, then run:

```bash
slake-detect           # STAC query + per-tile NDWI lake detection
slake-merge-daily      # merge per-tile masks by date
slake-reproject-3413   # reproject/clip to EPSG:3413 (needs NSIDC-0793_*.nc ice mask)
slake-build-zarr       # assemble the melt-season Zarr datacube
```

The tile list defaults to the `sentinel_2_tiles.csv` packaged with the module;
override it with the `SENTINEL2_TILE_LIST` environment variable.

## Pipeline

The pipeline works as follows
```
slake-detect (lake_detect_parallel.py)
↓
output_dir/
↓
slake-merge-daily (merge_daily_masks.py)
↓
output_dir/
↓
slake-reproject-3413 (reproject_to_3413.py) ← NSIDC-0793_*.nc (ice mask)
↓
output_dir/
↓
slake-build-zarr (create_zarr_datacube.py)
↓
lake_detection_binary_masks_.zarr
```

The `reading_zarr_and_item_grab.ipynb` in the `notebooks/` dir has an example on how to read the zarr and grab one of the stac item's assets used for a single time step.

Zarr dimensions are: (time: num_of_days, x: 26088, y: 52904, stac_item: 9). The `stac_item` dim refers to the number of MRGS tiles in CW Greenland found in the `sentinel_2_tiles.csv`

## Output

The current main outputs are the NDWI mask zarrs 

lake_detection_binary_masks_2018.zarr : The 2018 NDWI masks from 2018-05-01 - 2018-09-30

lake_detection_binary_masks_2019.zarr : The 2019 NDWI masks from 2019-05-01 - 2019-09-30

