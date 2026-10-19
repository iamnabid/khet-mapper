import ee

import config
from core.mosaic import daily_mosaic


def _mask_clouds(image, cloud_prob_max):
    prob = ee.Image(image.get("cloud_probability")).select("probability")
    prob_mask = prob.lt(cloud_prob_max)

    # QA60 bits 10/11 flag opaque/cirrus clouds; the band is unmasked (not
    # spectral-band thresholded). It reads as fully masked for scenes between
    # 2022 and Feb 2024, so unmask(0) treats "no data" as "no flag" instead of
    # discarding every scene in that window.
    qa60 = image.select("QA60").unmask(0)
    opaque = qa60.bitwiseAnd(1 << 10).eq(0)
    cirrus = qa60.bitwiseAnd(1 << 11).eq(0)

    return image.updateMask(prob_mask.And(opaque).And(cirrus))


def get_s2_composite(aoi, start, end, cloud_prob_max=config.CLOUD_PROB_MAX):
    s2 = (
        ee.ImageCollection(config.S2_COLLECTION)
        .filterBounds(aoi)
        .filterDate(start, end)
        .select(config.S2_BANDS + ["QA60"])
    )
    cloud_prob = (
        ee.ImageCollection(config.S2_CLOUD_PROB_COLLECTION)
        .filterBounds(aoi)
        .filterDate(start, end)
    )

    joined = ee.Join.saveFirst("cloud_probability").apply(
        primary=s2,
        secondary=cloud_prob,
        condition=ee.Filter.equals(leftField="system:index", rightField="system:index"),
    )
    masked = daily_mosaic(ee.ImageCollection(joined).map(lambda img: _mask_clouds(img, cloud_prob_max)))
    return masked, masked.median().clip(aoi)


def with_clear_fraction(collection, aoi, scale=10):
    """Set each image's `clear_fraction`: the share of the AOI's area left
    unmasked after cloud masking."""
    total = ee.Number(ee.Image.pixelArea().reduceRegion(
        ee.Reducer.sum(), aoi, scale, maxPixels=1e10, tileScale=4
    ).get("area"))

    def tag(img):
        clear = (
            img.select("B3").mask().gt(0).multiply(ee.Image.pixelArea())
            .reduceRegion(ee.Reducer.sum(), aoi, scale, maxPixels=1e10, tileScale=4).get("B3")
        )
        return img.set("clear_fraction", ee.Number(clear).divide(total))

    return collection.map(tag)


def mostly_clear(collection, aoi, min_fraction=config.OPTICAL_MIN_CLEAR_FRACTION, scale=10):
    return with_clear_fraction(collection, aoi, scale).filter(ee.Filter.gte("clear_fraction", min_fraction))
