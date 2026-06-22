"""Concrete tool implementations registered in the ToolRegistry.

Each tool inherits from BaseTool and is registered at import time.
"""

from app.services.plugin_protocol import BaseTool, ToolRegistry

# Global registries — populated at import time
tool_registry = ToolRegistry()


class NavigateTreeTool(BaseTool):
    name = "navigate_tree"
    description = "Navigate the document knowledge tree to explore sections and find detailed information. Use this for multi-hop research that requires exploring multiple document sections."
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "What specific information to search for"}
        },
        "required": ["query"],
    }

    async def execute(self, args: dict, context: dict) -> str:
        from app.services.agentic_tree_navigator import AgenticTreeNavigator

        kb_name = context.get("kb_name", "")
        if not kb_name:
            return "No knowledge base selected."
        navigator = AgenticTreeNavigator(kb_name)
        return await navigator.navigate(
            query=args.get("query", context.get("query", "")),
            lm_client=context["lm_client"],
            model_id=context["model_id"],
        )


class RetrieveKnowledgeTool(BaseTool):
    name = "retrieve_knowledge"
    description = "Search the knowledge base for documents, chunks, or facts relevant to the query. Call this FIRST when you need information from the user's documents."
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "The search query to find relevant content"}
        },
        "required": ["query"],
    }

    async def execute(self, args: dict, context: dict) -> str:
        from app.services.retrieval_service import RetrieveRequest
        from app.services.retrieval_service import retrieve as run_retrieval

        search_query = args.get("query", context.get("query", ""))
        kb_name = context.get("kb_name", "")
        pipeline = context.get("retrieval_pipeline", "hybrid")
        try:
            req = RetrieveRequest(query=search_query, kb_name=kb_name, retrieval_pipeline=pipeline, top_k=5)
            resp = await run_retrieval(req)
            results = resp.get("results", [])
            if results:
                chunks = []
                for i, r in enumerate(results):
                    content = r.get("content", "") or r.get("summary", "")
                    chunks.append(f"[{i+1}] {content[:500]}")
                return "Retrieved chunks:\n" + "\n---\n".join(chunks)
            return "No relevant documents found."
        except Exception as e:
            return f"Retrieval failed: {e}"


class InvestigateTool(BaseTool):
    name = "investigate"
    description = "Analyze a question or retrieved content to identify key concepts, required knowledge domains, and complexity. Break down into sub-questions."
    parameters = {
        "type": "object",
        "properties": {
            "context": {"type": "string", "description": "The question or retrieved content to analyze"}
        },
        "required": ["context"],
    }

    async def execute(self, args: dict, context: dict) -> str:
        lm_client = context["lm_client"]
        model_id = context["model_id"]
        system_prompt = "You are an Investigate agent. Analyze and identify key concepts. Be concise."
        result = await lm_client.stream_chat_completion(
            model=model_id,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": args.get("context", "")},
            ],
            max_tokens=1024,
        )
        return result.get("content", "Investigation unavailable.")


class PlanApproachTool(BaseTool):
    name = "plan_approach"
    description = "Create a step-by-step plan to answer the query based on investigation findings."
    parameters = {
        "type": "object",
        "properties": {
            "findings": {"type": "string", "description": "The investigation results to base the plan on"}
        },
        "required": ["findings"],
    }

    async def execute(self, args: dict, context: dict) -> str:
        lm_client = context["lm_client"]
        model_id = context["model_id"]
        query = context.get("query", "")
        system_prompt = "You are a Planning agent. Create a step-by-step plan. Be concise."
        result = await lm_client.stream_chat_completion(
            model=model_id,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Query: {query}\n\nFindings: {args.get('findings', '')}"},
            ],
            max_tokens=1024,
        )
        return result.get("content", "Planning unavailable.")


class ProduceAnswerTool(BaseTool):
    name = "produce_answer"
    description = "Execute the plan and produce a comprehensive final answer. Be precise, cite sources, and explain reasoning clearly."
    parameters = {
        "type": "object",
        "properties": {
            "plan": {"type": "string", "description": "The execution plan to follow"},
            "context": {"type": "string", "description": "The knowledge base results and investigation notes"}
        },
        "required": ["plan", "context"],
    }

    async def execute(self, args: dict, context: dict) -> str:
        lm_client = context["lm_client"]
        model_id = context["model_id"]
        query = context.get("query", "")
        system_prompt = "You are a Solve agent. Produce a comprehensive answer. Be precise, cite sources, and explain reasoning clearly."
        result = await lm_client.stream_chat_completion(
            model=model_id,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Query: {query}\n\nPlan: {args.get('plan', '')}\n\nContext: {args.get('context', '')}"},
            ],
            max_tokens=4096,
        )
        return result.get("content", "Answer generation unavailable.")


class FinalizeAnswerTool(BaseTool):
    name = "finalize_answer"
    description = "Declare the answer complete. Returns the final response to the user."
    parameters = {"type": "object", "properties": {}, "required": []}

    async def execute(self, args: dict, context: dict) -> str:
        return "Answer complete."


# Register all tools at import time
for tool_cls in [NavigateTreeTool, RetrieveKnowledgeTool, InvestigateTool, PlanApproachTool, ProduceAnswerTool, FinalizeAnswerTool]:
    tool_registry.register(tool_cls())
