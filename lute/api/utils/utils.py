import json


def parse_url_params(request):
    """
    parse table url params
    """
    # Pagination
    start = int(request.args.get("start", 0))  # Starting index
    size = int(request.args.get("size", -1))  # Page size
    # Filters
    global_filter = request.args.get("globalFilter", "").strip()
    # [{"id": "title", "value": "Book"}]
    filters = json.loads(request.args.get("filters", "[]"))
    # {"title": "contains"}
    filter_modes = json.loads(request.args.get("filterModes", "{}"))
    # Sorting [{"id": "WordCount", "desc": True}]
    sorting = json.loads(request.args.get("sorting", "[]"))

    return start, size, filters, filter_modes, global_filter, sorting


def get_filter(typ, item, value, num=False):
    """
    map filter type to sql condition
    """
    if num:
        value = int(value)

    flt = {
        "contains": f" AND {item} LIKE '%{value}%'",
        "startsWith": f" AND {item} LIKE '{value}%'",
        "endsWith": f" AND {item} LIKE '%{value}'",
        "equalsStr": f" AND {item} = '{value}'",
        "equalsNum": f" AND {item} = {value}",
        "greaterThan": f" AND {item} > {value}",
        "lessThan": f" AND {item} < {value}",
        "notEquals": f" AND {item} != {value}",
    }

    if typ == "equals" and num:
        typ = "equalsNum"
    if typ == "equals" and not num:
        typ = "equalsStr"

    return flt[typ]
