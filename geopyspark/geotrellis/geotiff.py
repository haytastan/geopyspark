"""This module contains functions that create ``RasterLayer`` from files."""

from geopyspark import get_spark_context
from geopyspark.geotrellis.constants import (LayerType,
                                             DEFAULT_MAX_TILE_SIZE,
                                             DEFAULT_PARTITION_BYTES,
                                             DEFAULT_CHUNK_SIZE,
                                             DEFAULT_GEOTIFF_TIME_TAG,
                                             DEFAULT_GEOTIFF_TIME_FORMAT,
                                             DEFAULT_S3_CLIENT)
from geopyspark.geotrellis.layer import RasterLayer
from geopyspark.geotrellis.s3 import Credentials, is_s3_uri, set_s3_credentials


__all__ = ['get']


def get(layer_type,
        uri,
        crs=None,
        max_tile_size=DEFAULT_MAX_TILE_SIZE,
        num_partitions=None,
        chunk_size=DEFAULT_CHUNK_SIZE,
        partition_bytes=DEFAULT_PARTITION_BYTES,
        time_tag=DEFAULT_GEOTIFF_TIME_TAG,
        time_format=DEFAULT_GEOTIFF_TIME_FORMAT,
        delimiter=None,
        s3_client=DEFAULT_S3_CLIENT,
        s3_credentials=None):
    """Creates a ``RasterLayer`` from GeoTiffs that are located on the local file system, ``HDFS``,
    or ``S3``.

    Args:
        layer_type (str or :class:`~geopyspark.geotrellis.constants.LayerType`): What the layer type
            of the geotiffs are. This is represented by either constants within ``LayerType`` or by
            a string.

            Note:
                All of the GeoTiffs must have the same saptial type.

        uri (str or [str]): The path or list of paths to the desired tile(s)/directory(ies).
        crs (str or int, optional): The CRS that the output tiles should be
            in. If ``None``, then the CRS that the tiles were originally in
            will be used.
        max_tile_size (int or None, optional): The max size of each tile in the
            resulting Layer. If the size is smaller than the read in tile,
            then that tile will be broken into smaller sections of the given
            size. Defaults to :const:`~geopyspark.geotrellis.constants.DEFAULT_MAX_TILE_SIZE`.
            If ``None``, then the whole tile will be read in.
        num_partitions (int, optional): The number of partitions Spark
            will make when the data is repartitioned. If ``None``, then the
            data will not be repartitioned.

            Note:
                If ``max_tile_size`` is also specified then this parameter
                will be ignored.

        partition_bytes (int, optional): The desired number of bytes per
            partition. This is will ensure that at least one item is assigned for
            each partition. Defaults to :const:`~geopyspark.geotrellis.constants.DEFAULT_PARTITION_BYTES`.
        chunk_size (int, optional): How many bytes of the file should be
            read in at a time. Defaults to :const:`~geopyspark.geotrellis.constants.DEFAULT_CHUNK_SIZE`.
        time_tag (str, optional): The name of the tiff tag that contains
            the time stamp for the tile.
            Defaults to :const:`~geopyspark.geotrellis.constants.DEFAULT_GEOTIFF_TIME_TAG`.
        time_format (str, optional): The pattern of the time stamp to be parsed.
            Defaults to :const:`~geopyspark.geotrellis.constants.DEFAULT_GEOTIFF_TIME_FORMAT`.
        delimiter (str, optional): The delimiter to use for S3 object listings.

            Note:
                This parameter will only be used when reading from S3.

        s3_client (str, optional): Which ``S3Client`` to use when reading
            GeoTiffs from S3. There are currently two options: ``default`` and
            ``mock``. Defaults to :const:`~geopyspark.geotrellis.constants.DEFAULT_S3_CLIENT`.

            Note:
                ``mock`` should only be used in unit tests and debugging.

        s3_credentials(:class:`~geopyspark.geotrellis.s3.Credentials`, optional): Alternative Amazon S3
            credentials to use when accessing the tile(s).

    Returns:
        :class:`~geopyspark.geotrellis.layer.RasterLayer`

    Raises:
        RuntimeError: ``s3_credentials`` were specified but the specified ``uri`` was not S3-based.
    """
    inputs = {k:v for k, v in locals().items() if v is not None}

    pysc = get_spark_context()
    geotiff_rdd = pysc._gateway.jvm.geopyspark.geotrellis.io.geotiff.GeoTiffRDD

    key = LayerType(inputs.pop('layer_type'))._key_name(False)
    partition_bytes = str(inputs.pop('partition_bytes'))

    uri = inputs.pop('uri')
    uris = (uri if isinstance(uri, list) else [uri])

    try:
        s3_credentials = inputs.pop('s3_credentials')
    except KeyError:
        s3_credentials = None
    else:
        _validate_s3_credentials(uri, s3_credentials)

    uri_type = uri.split(":")[0]

    with set_s3_credentials(s3_credentials, uri_type):
        srdd = geotiff_rdd.get(
            pysc._jsc.sc(),
            key,
            uris,
            inputs,
            partition_bytes
        )

    return RasterLayer(layer_type, srdd)


def _validate_s3_credentials(uri, credentials):
    if credentials and not is_s3_uri(uri):
        raise RuntimeError(
            'S3 credentials were provided to geotiff.get, but an AWS S3 URI '
            'was not specified (URI: {})'.format(uri)
        )
