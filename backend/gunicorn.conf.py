import os

bind = f"0.0.0.0:{os.getenv('PORT', '8000')}"
workers = int(os.getenv("WEB_CONCURRENCY", "2"))
timeout = 60            # analysis fans out to external APIs; each has its own 10 s timeout
accesslog = "-"
errorlog = "-"          # error logs also to stdout for platform log aggregation
forwarded_allow_ips = os.getenv("FORWARDED_ALLOW_IPS", "127.0.0.1")

max_requests = 1000          # recycle workers after N requests (prevents memory growth)
max_requests_jitter = 100   # randomise recycling to avoid thundering herd
worker_class = "sync"       # explicit: sync workers suit I/O-bound external API calls
