import django_filters


class EmptyListInsensitiveFilterSet(django_filters.FilterSet):
    """FilterSet base that ignores empty-list arguments.

    With graphene-django 3.x + django-filter 23.x an empty list passed to an
    ``__in`` filter is treated as "match nothing" rather than "no filter",
    silently collapsing the whole result set to empty. Clients routinely send
    ``[]`` for an unselected multi-value filter (e.g. an empty authority /
    report-type picker), so strip empty lists/tuples from the bound data before
    validation. An absent key is correctly treated as "no filter".
    """

    def __init__(self, data=None, *args, **kwargs):
        if data:
            data = {
                key: value
                for key, value in data.items()
                if not (isinstance(value, (list, tuple)) and len(value) == 0)
            }
        super().__init__(data=data, *args, **kwargs)
