from langchain_core.messages import SystemMessage
from langchain_openai import ChatOpenAI

REWRITE_PROMPT = """你是一个电商客服查询优化专家。请将用户的口语化问题改写成一个更适合文档检索的查询。
要求：
1. 消除口语歧义，使用更正式、更具体的表达
2. 保留原意，不要添加文档中没有的信息
3. 只返回改写后的查询文本，不要解释

用户问题：{question}
改写后的查询："""


class QueryRewriter:
    def __init__(self, llm: ChatOpenAI):
        self.llm = llm

    async def rewrite(self, query: str) -> str:
        response = await self.llm.ainvoke(
            [SystemMessage(content=REWRITE_PROMPT.format(question=query))]
        )
        text = str(response.content).strip()
        for line in text.splitlines():
            line = line.strip()
            if line:
                return line
        raise RuntimeError("Query rewriter returned empty response")
