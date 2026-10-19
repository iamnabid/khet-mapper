import ee

import config


def ndvi(image):
    return image.normalizedDifference(["B8", "B4"]).rename("NDVI")


def ndre(image):
    return image.normalizedDifference(["B8", "B5"]).rename("NDRE")


def ndwi(image):
    return image.normalizedDifference(["B3", "B8"]).rename("NDWI")


def mndwi(image):
    return image.normalizedDifference(["B3", "B11"]).rename("MNDWI")


def optical_water(image):
    return mndwi(image).gt(0).rename("is_water")


def sar_water(image, vv_db_max=config.SAR_WATER_VV_DB_MAX):
    # S1_GRD is already in dB (see s1_sar_fusion.py), so threshold directly.
    return image.select("VV").lt(vv_db_max).rename("is_water")


def awei_nsh(image):
    # Feyisa et al. 2014, no-shadow variant: 4*(green-SWIR1) - (0.25*NIR + 2.75*SWIR2)
    green, swir1, nir, swir2 = (
        image.select("B3"),
        image.select("B11"),
        image.select("B8"),
        image.select("B12"),
    )
    return (
        green.subtract(swir1)
        .multiply(4)
        .subtract(nir.multiply(0.25).add(swir2.multiply(2.75)))
        .rename("AWEI_nsh")
    )


def lai_proxy(ndvi_image):
    # Empirical NDVI->LAI curve (common in crop-monitoring literature); a
    # proxy, not a calibrated biophysical retrieval — do not present as a
    # validated LAI measurement.
    ratio = ee.Image(0.69).subtract(ndvi_image).divide(0.59)
    return ratio.log().multiply(-1 / 0.91).rename("LAI_proxy")


def water_occurrence_mask(collection, classify=optical_water, min_fraction=config.WATER_OCCURRENCE_MIN_FRACTION):
    """Fraction of scenes classified as water (MNDWI > 0 on cloud-free S2 by
    default, or sar_water on S1); thresholding this (rather than AND-ing every
    scene, which only keeps permanent water) captures both permanent and
    seasonal gher/pond extent."""
    water_flags = collection.map(classify)
    occurrence = water_flags.mean()
    mask = occurrence.gte(min_fraction)
    return mask.selfMask().focal_max(
        config.WATER_BOUNDARY_BUFFER_PX * 10, "square", "meters"
    )
