"""
Push Notification API Endpoints.

Handles Web Push subscription management.
"""

import logging
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.models import UserPushSubscription
from api.utils import audit_log

logger = logging.getLogger(__name__)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def push_subscribe(request):
    """
    Subscribe to push notifications.
    
    Request body:
    {
        "endpoint": "https://fcm.googleapis.com/...",
        "keys": {
            "p256dh": "...",
            "auth": "..."
        }
    }
    """
    endpoint = request.data.get('endpoint')
    keys = request.data.get('keys', {})
    p256dh = keys.get('p256dh')
    auth = keys.get('auth')
    
    if not endpoint or not p256dh or not auth:
        return Response(
            {'message': 'Missing required subscription data'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Upsert subscription
    subscription, created = UserPushSubscription.objects.update_or_create(
        endpoint=endpoint,
        defaults={
            'user': request.user,
            'p256dh': p256dh,
            'auth': auth,
            'user_agent': request.META.get('HTTP_USER_AGENT', '')[:255],
            'is_active': True,
        }
    )
    
    audit_log(
        request.user,
        'PUSH_SUBSCRIBE' if created else 'PUSH_RESUBSCRIBE',
        'UserPushSubscription',
        str(subscription.id),
        request=request
    )
    
    return Response({
        'message': 'Subscribed successfully',
        'subscription_id': str(subscription.id),
    }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def push_unsubscribe(request):
    """
    Unsubscribe from push notifications.
    
    Request body:
    {
        "endpoint": "https://fcm.googleapis.com/..."
    }
    """
    endpoint = request.data.get('endpoint')
    
    if not endpoint:
        return Response(
            {'message': 'Endpoint required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    deleted_count, _ = UserPushSubscription.objects.filter(
        user=request.user,
        endpoint=endpoint,
    ).delete()
    
    if deleted_count == 0:
        return Response(
            {'message': 'Subscription not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    audit_log(
        request.user,
        'PUSH_UNSUBSCRIBE',
        'UserPushSubscription',
        endpoint[:100],
        request=request
    )
    
    return Response({'message': 'Unsubscribed successfully'})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def push_status(request):
    """
    Get push notification subscription status for current user.
    """
    subscriptions = UserPushSubscription.objects.filter(
        user=request.user,
        is_active=True,
    ).count()
    
    return Response({
        'subscribed': subscriptions > 0,
        'subscription_count': subscriptions,
    })
