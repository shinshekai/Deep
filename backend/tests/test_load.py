"""Load testing with Locust for UDIP backend.

Run with: locust -f backend/tests/test_load.py --host=http://localhost:8001
"""

from locust import HttpUser, between, tag, task


class HealthUser(HttpUser):
    """Simulate users hitting health endpoints."""

    wait_time = between(0.1, 0.5)

    @task(5)
    @tag("health")
    def health_check(self):
        self.client.get("/api/v1/health")

    @task(3)
    @tag("config")
    def get_config(self):
        self.client.get("/api/v1/config")

    @task(2)
    @tag("models")
    def discover_models(self):
        self.client.get("/api/v1/models/discover")


class QueryUser(HttpUser):
    """Simulate users making queries."""

    wait_time = between(0.5, 2.0)

    @task(3)
    @tag("query")
    def simple_query(self):
        self.client.post(
            "/api/v1/query",
            json={
                "query": "What is machine learning?",
                "device_id": "load-test-user",
            },
        )

    @task(2)
    @tag("query")
    def complex_query(self):
        self.client.post(
            "/api/v1/query",
            json={
                "query": "Explain the differences between supervised and unsupervised learning",
                "device_id": "load-test-user",
            },
        )

    @task(1)
    @tag("memory")
    def recall_memory(self):
        self.client.get(
            "/api/v1/memory/recall",
            params={
                "query": "machine learning",
                "device_id": "load-test-user",
            },
        )


class ModelManagementUser(HttpUser):
    """Simulate users managing models."""

    wait_time = between(1, 5)

    @task(2)
    @tag("models")
    def select_model(self):
        self.client.post(
            "/api/v1/models/select",
            json={
                "provider_type": "local",
                "provider_id": "lm_studio",
                "model_id": "google/gemma-4-e2b",
                "load": False,
            },
        )

    @task(1)
    @tag("models")
    def get_model_status(self):
        self.client.get("/api/v1/models/status")
