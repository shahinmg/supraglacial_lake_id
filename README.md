# supraglacial_lake_id


A pipeline for NDWI masking for supraglacial lakes in central-west Greenland using Sentinel-2 L2A imagery from Microsoft Planetary Computer. The final output are Zarr stores for a particular year's melt season.

## Environment

```
conda env create -f environment.yml
conda activate supraglacial-lake-id
```

## Pipeline

The pipeline scripts live in `src/`. Run them from the repo root (their input,
output, and data paths are resolved relative to the current working directory):

```
src/lake_detect_parallel.py
↓
output_dir/
↓
src/merge_daily_masks.py
↓
output_dir/
↓
src/reproject_to_3413.py ← NSIDC-0793_*.nc (ice mask)
↓
output_dir/
↓
src/create_zarr_datacube.py
↓
lake_detection_binary_masks_.zarr
```

The `reading_zarr_and_item_grab.ipynb` in the `notebooks/` dir has an example on how to read the zarr and grab one of the stac item's assets used for a single time step.

Zarr dimensions are: (time: num_of_days, x: 26088, y: 52904, stac_item: 9). The `stac_item` dim refers to the number of MRGS tiles in CW Greenland found in the `sentinel_2_tiles.csv`

## Output

The current main outputs are the NDWI mask zarrs 

lake_detection_binary_masks_2018.zarr : The 2018 NDWI masks from 2018-05-01 - 2018-09-30

lake_detection_binary_masks_2019.zarr : The 2019 NDWI masks from 2019-05-01 - 2019-09-30

