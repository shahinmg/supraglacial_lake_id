# -*- coding: utf-8 -*-
"""
Created on Thu Jul  9 11:17:55 2026

@author: m337l400
"""

import geopandas as gpd
import rasterio
from rasterio.features import shapes
from shapely.geometry import shape

# # 1. Open the raster dataset
# raster_path = "F:/surface_lakes/supraglacial_lake_id/lake_detection_binary_masks_merged_daily_v2_3413_clipped/20190810_merged_lake_pixels.tif"
# with rasterio.open(raster_path) as src:
#     # Read the first band as a numpy array
#     image = src.read(1)

#     # Use the dataset's native mask or filter out background/NoData values
#     mask = image != 0

#     # 2. Extract shapes from the raster band
#     # This generates (geojson_geometry, raster_value) pairs
#     shape_generator = shapes(
#         image, mask=mask, transform=src.transform, connectivity=4
#     )

#     # 3. Parse geometries and values into lists
#     records = []
#     for geojson_geom, value in shape_generator:
#         records.append({"geometry": shape(geojson_geom), "raster_val": value})

# # 4. Convert to a GeoDataFrame and assign the original CRS
# gdf = gpd.GeoDataFrame(records, crs=src.crs)

# gdf.to_file("output_polygons.gpkg", driver="GPKG")


#%%

import os
import glob
import rasterio
from rasterio import features
import geopandas as gpd
from shapely.geometry import shape
import concurrent.futures

def polygonize_raster(tif_path):
    """Reads a single .tif and converts contiguous pixel groups to polygons."""
    print(f"Processing: {os.path.basename(tif_path)}")
    
    with rasterio.open(tif_path) as src:
        # Read the first band
        image = src.read(1)
        # # Generate GeoJSON-like features (geometries and pixel values)
        # results = (
        #     {'properties': {'raster_val': v}, 'geometry': s}
        #     for i, (s, v) in enumerate(features.dataset_features(src, bidx=1, as_mask=False))
        # )
        mask = image != 0

        # Extract shapes from the raster band
        # This generates (geojson_geometry, raster_value) pairs
        shape_generator = shapes(
            image, mask=mask, transform=src.transform, connectivity=4
        )

        # Parse geometries and values into lists
        records = []
        for geojson_geom, value in shape_generator:
            records.append({"geometry": shape(geojson_geom), "raster_val": value})
    
        # Convert to GeoDataFrame
        gdf = gpd.GeoDataFrame(records, crs=src.crs)
        
        # Save each raster's polygons to a corresponding GeoJSON (or append to a list)
        output_path = tif_path.replace('.tif', '.gpkg')
        gdf.to_file(output_path, driver='GPKG')
        return output_path

def batch_process_tifs(input_directory):
    tif_files = glob.glob(os.path.join(input_directory, '*.tif'))
    
    # Run in parallel using a ThreadPoolExecutor
    # Use ProcessPoolExecutor if your polygonization is highly CPU-bound rather than I/O-bound
    with concurrent.futures.ThreadPoolExecutor() as executor:
        results = executor.map(polygonize_raster, tif_files)
        
    return list(results)

# --- Usage ---
tif_folder = "C:/Users/m337l400/Documents/surface_lakes/supraglacial_lake_id/lake_detection_binary_masks_merged_daily_v2_3413_clipped/"
processed_files = batch_process_tifs(tif_folder)
print(f"Completed processing {len(processed_files)} files.")