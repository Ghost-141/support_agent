import os
from dotenv import load_dotenv
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage
from schemas import ChatbotState
from tools.qa import TOOLS
from prompts import system_prompt


load_dotenv(".env")


def build_graph(checkpointer=None):
    llm = ChatOllama(
        model=os.getenv("OLLAMA_MODEL"),
        base_url=os.getenv("OLLAMA_BASE_URL"),
        temperature=os.getenv("OLLAMA_TEMPERATURE"),
        num_predict=os.getenv("OLLAMA_NUM_PREDICT"),
        num_ctx=os.getenv("OLLAMA_NUM_CTX"),
        streaming=True,
    )
    llm_with_tools = llm.bind_tools(TOOLS)

    async def assistant(state: ChatbotState) -> dict:
        print("--- Assistant thinking... ---")
        messages = [SystemMessage(content=system_prompt)] + state["messages"]
        response = await llm_with_tools.ainvoke(messages)
        return {"messages": [response]}

    tool_node = ToolNode(TOOLS)

    async def debug_tool_node(state: ChatbotState) -> dict:
        print("--- Executing tools... ---")
        return await tool_node.ainvoke(state)

    graph_builder = StateGraph(ChatbotState)
    graph_builder.add_node("assistant", assistant)
    graph_builder.add_node("tools", debug_tool_node)
    graph_builder.add_edge(START, "assistant")
    graph_builder.add_conditional_edges(
        "assistant", tools_condition, {"tools": "tools", "__end__": END}
    )
    graph_builder.add_edge("tools", "assistant")

    return graph_builder.compile(checkpointer=checkpointer)
