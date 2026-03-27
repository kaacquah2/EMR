"""
Task status and result endpoints for async Celery task monitoring.
Allows users to check task status and retrieve results.
"""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from celery.result import AsyncResult

from core.models import TaskSubmission
from api.serializers import TaskStatusSerializer, TaskResultSerializer
from api.utils import audit_log, sanitize_audit_resource_id


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def task_status(request, task_id):
    """
    Get status of a Celery task.
    
    Returns:
        - status: PENDING, STARTED, SUCCESS, FAILURE, RETRY
        - result: Task result if available (null if not ready)
        - error_message: Error message if failed
        - task_type: Type of task (export_pdf, ai_analysis, etc.)
        - resource_type: Type of resource (patient, encounter, etc.)
        - resource_id: ID of the resource
    
    Permissions:
        - User can only view their own tasks
        - Super admin can view all tasks
    
    Returns:
        200: Task status retrieved
        403: Permission denied (task belongs to another user)
        404: Task not found in TaskSubmission table
    """
    user = request.user
    
    # Get task submission record
    try:
        task_submission = TaskSubmission.objects.get(celery_task_id=task_id)
    except TaskSubmission.DoesNotExist:
        return Response(
            {"message": "Task not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    
    # Permission check: only task owner or super_admin can view
    if user.role != "super_admin" and task_submission.user_id != user.id:
        return Response(
            {"message": "Permission denied"},
            status=status.HTTP_403_FORBIDDEN,
        )
    
    # Get task result from Celery
    async_result = AsyncResult(task_id)
    
    # Build response
    response_data = {
        "task_id": task_id,
        "status": async_result.status,
        "created_at": task_submission.submitted_at,
        "expires_at": task_submission.expires_at,
        "task_type": task_submission.get_task_type_display(),
        "resource_type": task_submission.resource_type,
        "resource_id": task_submission.resource_id,
    }
    
    # Add result if task completed successfully
    if async_result.status == "SUCCESS":
        response_data["result"] = async_result.result
    
    # Add error info if task failed
    elif async_result.status == "FAILURE":
        response_data["error_message"] = str(async_result.info) if async_result.info else "Unknown error"
        if hasattr(async_result, "traceback"):
            response_data["traceback"] = async_result.traceback
    
    # Log task status check
    audit_log(
        request=request,
        action="VIEW",
        resource_type="task",
        resource_id=sanitize_audit_resource_id(task_id),
        hospital=task_submission.hospital,
    )
    
    serializer = TaskStatusSerializer(response_data)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def task_result(request, task_id):
    """
    Get full task result data.
    
    Returns only if task is completed successfully.
    Returns 404 if task not found, not completed, or result has expired.
    
    Permissions:
        - User can only view results of their own tasks
        - Super admin can view results of all tasks
    
    Returns:
        200: Task result retrieved
        403: Permission denied (task belongs to another user)
        404: Task not found, not completed, or result expired
    """
    user = request.user
    
    # Get task submission record
    try:
        task_submission = TaskSubmission.objects.get(celery_task_id=task_id)
    except TaskSubmission.DoesNotExist:
        return Response(
            {"message": "Task not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    
    # Permission check: only task owner or super_admin can view
    if user.role != "super_admin" and task_submission.user_id != user.id:
        return Response(
            {"message": "Permission denied"},
            status=status.HTTP_403_FORBIDDEN,
        )
    
    # Check if result has expired
    from django.utils import timezone
    if timezone.now() > task_submission.expires_at:
        return Response(
            {"message": "Task result has expired"},
            status=status.HTTP_404_NOT_FOUND,
        )
    
    # Get task result from Celery
    async_result = AsyncResult(task_id)
    
    # Only return result if task completed successfully
    if async_result.status != "SUCCESS":
        return Response(
            {"message": f"Task is {async_result.status.lower()}, result not available"},
            status=status.HTTP_404_NOT_FOUND,
        )
    
    # Log result retrieval
    audit_log(
        request=request,
        action="VIEW",
        resource_type="task_result",
        resource_id=sanitize_audit_resource_id(task_id),
        hospital=task_submission.hospital,
    )
    
    response_data = {
        "task_id": task_id,
        "status": async_result.status,
        "result": async_result.result,
        "created_at": task_submission.submitted_at,
        "expires_at": task_submission.expires_at,
    }
    
    serializer = TaskResultSerializer(response_data)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def task_list(request):
    """
    List tasks submitted by the current user (or all if super_admin).
    
    Query parameters:
        - task_type: Filter by task type (export_pdf, ai_analysis, etc.)
        - resource_type: Filter by resource type (patient, encounter, etc.)
        - status: Filter by status (PENDING, STARTED, SUCCESS, FAILURE, RETRY)
        - limit: Limit results (default: 20, max: 100)
    
    Returns:
        200: List of tasks with basic info
    """
    user = request.user
    
    # Get user's tasks or all tasks if super_admin
    if user.role == "super_admin":
        tasks = TaskSubmission.objects.all()
    else:
        tasks = TaskSubmission.objects.filter(user=user)
    
    # Apply filters
    task_type = request.GET.get("task_type")
    if task_type:
        tasks = tasks.filter(task_type=task_type)
    
    resource_type = request.GET.get("resource_type")
    if resource_type:
        tasks = tasks.filter(resource_type=resource_type)
    
    # Limit results
    try:
        limit = int(request.GET.get("limit", 20))
        limit = min(limit, 100)  # Cap at 100
    except ValueError:
        limit = 20
    
    tasks = tasks.order_by("-submitted_at")[:limit]
    
    # Enrich with Celery status
    response_data = []
    for task_submission in tasks:
        async_result = AsyncResult(task_submission.celery_task_id)
        response_data.append({
            "task_id": task_submission.celery_task_id,
            "task_submission_id": str(task_submission.id),
            "status": async_result.status,
            "task_type": task_submission.get_task_type_display(),
            "resource_type": task_submission.resource_type,
            "resource_id": task_submission.resource_id,
            "submitted_at": task_submission.submitted_at,
            "expires_at": task_submission.expires_at,
        })
    
    return Response({
        "data": response_data,
        "total": len(response_data),
    }, status=status.HTTP_200_OK)
