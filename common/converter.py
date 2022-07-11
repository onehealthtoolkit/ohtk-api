import json


from django.contrib.gis.geos import GEOSGeometry
from graphene.types.generic import GenericScalar


class GeoJSON(GenericScalar):
    @staticmethod
    def geos_to_json(value):
        return json.loads(GEOSGeometry(value).geojson)

    @staticmethod
    def json_to_geos(value):
        return GEOSGeometry(value)

    serialize = geos_to_json
    deserialize = json_to_geos
