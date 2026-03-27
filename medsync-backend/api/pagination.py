"""
Reusable pagination for list APIs that return { data, next_cursor, has_more }.
Uses offset/limit; cursor can be the next offset for consistency with existing clients.
"""
from django.core.paginator import Paginator


def paginate_queryset(queryset, request, page_size=20, max_page_size=100):
    """
    Slice queryset by page/limit from request. Returns (page_queryset, next_cursor, has_more).
    next_cursor is the next offset (integer) or None if no more pages.
    """
    try:
        page_num = max(1, int(request.GET.get("page", 1)))
    except (ValueError, TypeError):
        page_num = 1
    try:
        raw_size = request.GET.get("limit") or request.GET.get("page_size") or page_size
        size = min(max_page_size, max(1, int(raw_size)))
    except (ValueError, TypeError):
        size = min(max_page_size, page_size)
    paginator = Paginator(queryset, size)
    page = paginator.get_page(page_num)
    items = list(page.object_list)
    has_more = page.has_next()
    next_cursor = page.next_page_number() if has_more else None
    return items, next_cursor, has_more
