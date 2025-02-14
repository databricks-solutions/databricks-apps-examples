import logging
from pydantic import BaseModel
from locust import HttpUser, task, between
from locust.env import Environment
import asyncio
import os
from fastapi import APIRouter, Request, Query

# Initialize router
router = APIRouter()

# Set up logging
logger = logging.getLogger(__name__)

class LoadTestConfig(BaseModel):
    users: int = 10
    spawn_rate: int = 2
    test_time: int = 30  # seconds

class WebsiteUser(HttpUser):
    wait_time = between(1, 2)
    
    @task
    def get_endpoint(self):
        self.client.get("/api/")

@router.get("/load-test")
async def run_load_test(
    request: Request,
    users: int = Query(default=10, gt=0, description="Number of users to simulate"),
    spawn_rate: int = Query(default=2, gt=0, description="Users to spawn per second"),
    test_time: int = Query(default=30, gt=0, description="Test duration in seconds")
):
    user_info = {
        "user_id": request.headers.get("X-Forwarded-User"),
        "username": request.headers.get("X-Forwarded-Preferred-Username"),
        "email": request.headers.get("X-Forwarded-Email"),
        "request_id": request.headers.get("X-Request-Id"),
        "client_ip": request.headers.get("X-Real-Ip")
    }
    
    logger.info(f"Load test initiated by user: {user_info}")
    env = Environment(
        user_classes=[WebsiteUser],
        host=f"http://localhost:{os.getenv('DATABRICKS_APP_PORT', 8000)}"
    )
    env.create_local_runner()
    env.runner.start(users, spawn_rate=spawn_rate)
    
    await asyncio.sleep(test_time)
    
    env.runner.quit()
    stats = env.runner.stats
    
    return {
        "test_duration": test_time,
        "total_requests": stats.total.num_requests,
        "successful_requests": stats.total.num_requests - stats.total.num_failures,
        "failed_requests": stats.total.num_failures,
        "requests_per_second": stats.total.current_rps,
        "concurrent_users": users,
        "response_time": {
            "min": stats.total.min_response_time,
            "max": stats.total.max_response_time,
            "mean": stats.total.avg_response_time,
            "median": stats.total.median_response_time,
            "p95": stats.total.get_response_time_percentile(0.95)
        },
        "errors": [{
            "name": name,
            "count": error.occurrences,
            "error_type": error.error,
            "exception": str(error.exception),
            "traceback": error.traceback
        } for name, error in stats.errors.items()]
    }
            
   