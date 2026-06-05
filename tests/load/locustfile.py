from locust import HttpUser, task, between
import os

API_KEY = os.getenv("WS_AUTH_TOKEN", "test-token")


class DeepAPIUser(HttpUser):
    wait_time = between(1, 3)
    host = os.getenv("LOCUST_HOST", "http://localhost:8000")

    def on_start(self):
        self.headers = {"X-DEEP-API-KEY": API_KEY}

    @task(10)
    def health_check(self):
        self.client.get("/health", headers=self.headers)

    @task(5)
    def list_knowledge_bases(self):
        self.client.get("/api/v1/knowledge/", headers=self.headers)

    @task(3)
    def chat_query(self):
        self.client.post(
            "/api/v1/chat/",
            json={
                "query": "What is machine learning?",
                "mode": "hybrid",
            },
            headers=self.headers,
        )

    @task(2)
    def solve_query(self):
        self.client.post(
            "/api/v1/solve/",
            json={
                "query": "Explain neural networks",
                "mode": "hybrid",
                "retrieval_pipeline": "standard",
            },
            headers=self.headers,
        )

    @task(1)
    def list_notebooks(self):
        self.client.get("/api/v1/notebooks/", headers=self.headers)

    @task(1)
    def get_metrics(self):
        self.client.get("/metrics", headers=self.headers)
