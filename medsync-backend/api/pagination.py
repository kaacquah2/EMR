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

    cursor = request.GET.get("cursor")
    
    if use_cursor and cursor:
        # Assuming queryset is ordered by -created_at or -id
        queryset = queryset.filter(id__lt=cursor)
    
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
        items = list(queryset[:size + 1])
        has_more = len(items) > size
        if has_more:
            items = items[:size]
            next_cursor = str(items[-1].id)
        else:
            next_cursor = None
        return items, next_cursor, has_more
