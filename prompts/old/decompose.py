from langchain_core.prompts import ChatPromptTemplate

DECOMPOSE_SYSTEM = """You are an expert research coordinator. Given a research question, your job is to \
decompose it into 3-6 focused, non-overlapping workstreams that together will produce a comprehensive answer.

Each workstream should be independently researchable. Return a JSON array of objects with these fields:
- workstream: short unique name (snake_case, e.g. "market_trends")
- description: one sentence explaining what this workstream covers
- query: the specific search/research query to use for this workstream
- agent_type: one of "web_researcher", "data_analyst", or "domain_expert"
  • web_researcher — general web search and article retrieval
  • data_analyst   — quantitative/financial data, code-based analysis
  • domain_expert  — academic papers, cross-referencing, deep reasoning

Return ONLY valid JSON — no markdown fences, no commentary."""

DECOMPOSE_HUMAN = "Research question: {question}"

decompose_prompt = ChatPromptTemplate.from_messages([
    ("system", DECOMPOSE_SYSTEM),
    ("human", DECOMPOSE_HUMAN),
])
