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


def water_occurrence_mask(s2_collection, min_fraction=config.WATER_OCCURRENCE_MIN_FRACTION):
    """Fraction of cloud-free scenes where MNDWI > 0; thresholding this
    (rather than AND-ing every scene, which only keeps permanent water)
    captures both permanent and seasonal gher/pond extent."""
    water_flags = s2_collection.map(lambda img: mndwi(img).gt(0).rename("is_water"))
    occurrence = water_flags.mean()
    mask = occurrence.gte(min_fraction)
    return mask.selfMask().focal_max(
        config.WATER_BOUNDARY_BUFFER_PX * 10, "square", "meters"
    )
