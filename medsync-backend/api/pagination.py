"""
Reusable pagination for list APIs that return { data, next_cursor, has_more }.
Uses offset/limit; cursor can be the next offset for consistency with existing clients.
"""
from django.core.paginator import Paginator


def paginate_queryset(queryset, request, page_size=20, max_page_size=100, use_cursor=False):
    """
    Slice queryset by page/limit or cursor.
    Returns (page_queryset, next_cursor, has_more).
    """
    try:
        raw_size = request.GET.get("limit") or request.GET.get("page_size") or page_size
        size = min(max_page_size, max(1, int(raw_size)))
    except (ValueError, TypeError):
        size = min(max_page_size, page_size)

    if not use_cursor:
        try:
            page_num = max(1, int(request.GET.get("page", 1)))
        except (ValueError, TypeError):
            page_num = 1
        
        paginator = Paginator(queryset, size)
        page = paginator.get_page(page_num)
        items = list(page.object_list)
        has_more = page.has_next()
        next_cursor = page.next_page_number() if has_more else None
        return items, next_cursor, has_more
    else:
        # Cursor-based implementation
        cursor = request.GET.get("cursor")
        
        if cursor:
            # Detect cursor type
            if "-" in cursor and ":" in cursor: # ISO Timestamp
                 # We need to know if we are ordering by encounter_date or created_at
                 # For simplicity, we'll try to filter by the most likely fields
                 if "encounter_date" in str(queryset.query.order_by):
                     queryset = queryset.filter(encounter_date__lt=cursor)
                 else:
                     queryset = queryset.filter(created_at__lt=cursor)
            else:
                 queryset = queryset.filter(id__lt=cursor)

        items = list(queryset[:size + 1])
        has_more = len(items) > size
        if has_more:
            items = items[:size]
            # Determine which field to use for next_cursor
            if "encounter_date" in str(queryset.query.order_by):
                next_cursor = items[-1].encounter_date.isoformat() if items[-1].encounter_date else str(items[-1].id)
            elif "created_at" in str(queryset.query.order_by):
                next_cursor = items[-1].created_at.isoformat() if items[-1].created_at else str(items[-1].id)
            else:
                next_cursor = str(items[-1].id)
        else:
            next_cursor = None
        return items, next_cursor, has_more
