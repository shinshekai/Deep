"""Agent tools for the dispatch loop — OpenAI function-calling compatible definitions."""

DEEP_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "retrieve_knowledge",
            "description": "Search the knowledge base for documents, chunks, or facts relevant to the query. Call this FIRST when you need information from the user's documents.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The search query to find relevant content"}
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "investigate",
            "description": "Analyze a question or retrieved content to identify key concepts, required knowledge domains, and complexity. Break down into sub-questions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "context": {"type": "string", "description": "The question or retrieved content to analyze"}
                },
                "required": ["context"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "plan_approach",
            "description": "Create a step-by-step plan to answer the query based on investigation findings. Decide what information is critical and what order to present it.",
            "parameters": {
                "type": "object",
                "properties": {
                    "findings": {"type": "string", "description": "The investigation results to base the plan on"}
                },
                "required": ["findings"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "produce_answer",
            "description": "Execute the plan and produce a comprehensive final answer. Be precise, cite sources, and explain reasoning clearly. Call this ONLY when you have sufficient context to answer.",
            "parameters": {
                "type": "object",
                "properties": {
                    "plan": {"type": "string", "description": "The execution plan to follow"},
                    "context": {"type": "string", "description": "The knowledge base results and investigation notes"}
                },
                "required": ["plan", "context"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "finalize_answer",
            "description": "Declare the answer complete. Returns the final response to the user. Call this when you have produced a satisfactory answer.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
]

TOOL_SYSTEM_PROMPT = (
    "You are a multi-agent document analysis system. You have access to tools "
    "that help you research, analyze, and answer questions about documents.\n\n"
    "WORKFLOW:\n"
    "1. Call retrieve_knowledge FIRST if you need document information\n"
    "2. Call investigate to analyze the query and retrieved content\n"
    "3. Call plan_approach to create an answer plan\n"
    "4. Call produce_answer to generate the final answer\n"
    "5. Call finalize_answer ONLY when the answer is complete\n\n"
    "IMPORTANT:\n"
    "- For simple questions, you may skip investigation and planning\n"
    "- NEVER call produce_answer without context\n"
    "- Call finalize_answer to end the conversation"
)
