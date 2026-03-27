# Daphne Shutdown Timeout Fix for MedSync Backend

## Problem

When running the MedSync backend development server, you may see warnings like:

```
Application instance <Task pending ...> took too long to shut down and was killed.
Application instance <Task cancelling ...> took too long to shut down and was killed.
```

These occur frequently during rapid file changes (e.g., editing `ai_views.py`) because:

1. **Daphne (the ASGI server) has a default 2-second shutdown timeout**
2. When the file reloader triggers, it kills the old Daphne process
3. Pending requests don't complete in time before the 2-second timeout
4. Daphne forcefully terminates the application instances, showing the warning

This is **not a bug** — it's a configuration issue. Daphne's 2-second timeout is designed for production where short response times are expected. For development with longer-running operations (like AI analysis), we need a longer timeout.

## Solution

Three files implement the permanent fix:

### 1. **medsync_backend/settings.py** (Configuration)

Added Daphne timeout configuration:

```python
# ============================================================================
# DAPHNE ASGI SERVER CONFIGURATION (Development & Production)
# ============================================================================
if DEBUG:
    # Development: longer timeout to allow requests to finish during reload
    DAPHNE_APPLICATION_CLOSE_TIMEOUT = 5
else:
    # Production: shorter timeout (hard kill after 2 seconds if not graceful)
    DAPHNE_APPLICATION_CLOSE_TIMEOUT = 2
```

- **Development**: 5 seconds (allows pending requests to complete gracefully)
- **Production**: 2 seconds (strict timeout for responsiveness)

### 2. **dev_server.py** (Development Server Launcher)

A new helper script that starts Daphne with proper timeout configuration:

```bash
# From medsync-backend/ directory:
python dev_server.py              # Start on 127.0.0.1:8000
python dev_server.py 8001         # Start on 127.0.0.1:8001
python dev_server.py 0.0.0.0:8000 # Start on custom host:port
```

**What it does:**
- Sets `--application-close-timeout 5` (the critical fix)
- Configures WebSocket ping intervals for stable connections during dev
- Enables access logging for debugging
- Automatically detects Python environment and ASGI app

### 3. **api/management/commands/runserver.py** (Django Management Command)

A custom `manage.py runserver` wrapper that applies the timeout configuration from settings.py.

## How to Use

### Option A: Use dev_server.py (Recommended for Development)

```bash
cd medsync-backend
python dev_server.py              # Starts on 127.0.0.1:8000
```

This is the easiest and most explicit approach. The script outputs the configuration being used.

### Option B: Use manage.py runserver

```bash
cd medsync-backend
python manage.py runserver        # Uses DAPHNE_APPLICATION_CLOSE_TIMEOUT from settings.py
```

This uses the custom runserver command that respects the settings configuration.

### Option C: Direct Daphne Command (for Advanced Users)

If you want to run Daphne directly with custom settings:

```bash
daphne -b 127.0.0.1 -p 8000 --application-close-timeout 5 medsync_backend.asgi:application
```

## What Changed

### Files Added:
- `medsync-backend/dev_server.py` — Development server launcher
- `medsync-backend/api/management/__init__.py` — Django management module
- `medsync-backend/api/management/commands/__init__.py` — Django commands module
- `medsync-backend/api/management/commands/runserver.py` — Custom runserver
- `medsync-backend/daphne.conf.json` — Daphne configuration reference (informational)

### Files Modified:
- `medsync-backend/medsync_backend/settings.py` — Added DAPHNE configuration
- `medsync-backend/README.md` — Added development server documentation

## Technical Details

### Why 5 Seconds?

The timeout is the time Daphne waits for an ASGI application instance to shut down gracefully before forcefully terminating it. 

- **2 seconds** (default): Good for production where requests should complete quickly
- **5 seconds** (development): Allows longer-running operations like AI analysis, data processing, and complex queries to finish cleanly

During file reload, Python's autoreloader gracefully shuts down the old process. With 5 seconds:
1. Pending requests have time to complete
2. Database connections can close properly
3. Cleanup code can execute without interruption
4. No warning messages in logs

### Why WebSocket Configuration?

The dev_server.py also configures WebSocket parameters:
- `--ping-interval 20` — Send ping every 20 seconds
- `--ping-timeout 20` — Wait 20 seconds for pong response

This keeps WebSocket connections stable during development and prevents false disconnects.

## Verification

To verify the fix is working:

1. Start the server with `python dev_server.py`
2. Make rapid edits to `api/views/ai_views.py` (or any file)
3. Watch the server console
4. **No more** "took too long to shut down" warnings should appear

## Production Considerations

**In production**, set `DEBUG=False` in your `.env`:

```bash
DEBUG=False
```

With `DEBUG=False`, the timeout automatically reverts to 2 seconds (from settings.py). The default Daphne timeout of 2 seconds is appropriate for production.

For production servers, you typically run Daphne directly or via a process manager (gunicorn+daphne, supervisor, systemd) without the file reloader, so the timeout is less critical.

## References

- [Daphne Documentation](https://daphne.readthedocs.io/)
- [Django ASGI Deployment](https://docs.djangoproject.com/en/4.2/howto/deployment/asgi/)
- [Django Channels](https://channels.readthedocs.io/)

## FAQ

**Q: Will this hurt production performance?**
A: No. In production (`DEBUG=False`), the timeout is 2 seconds (the Daphne default). Development uses 5 seconds only when `DEBUG=True`.

**Q: Can I customize the timeout further?**
A: Yes. Edit `DAPHNE_APPLICATION_CLOSE_TIMEOUT` in `medsync_backend/settings.py`. The `dev_server.py` script respects this setting.

**Q: Do I need to restart after editing ai_views.py?**
A: No. The file reloader will reload the module automatically. With the 5-second timeout, you should see no warnings about slow shutdown.

**Q: What if I'm still seeing warnings?**
A: You may have a request that takes longer than 5 seconds. Consider:
1. Increasing the timeout further (e.g., to 10 seconds)
2. Moving long-running operations to Celery background tasks
3. Profiling your slowest endpoints with Django Debug Toolbar

