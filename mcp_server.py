"""
MCP Server for Compliance Analyst
Exposes the compliance audit tool via Model Context Protocol.
Run with: python mcp_server.py
"""

import json
import asyncio
from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions
import mcp.server.stdio
import mcp.types as types

# Reuse your existing agent
from agent.graph import build_compliance_graph

server = Server("compliance-analyst")
compliance_graph = build_compliance_graph()

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """List available tools for MCP clients."""
    return [
        types.Tool(
            name="audit_document",
            description="Audit a document for compliance and return a structured report with risk score and recommendations.",
            inputSchema={
                "type": "object",
                "properties": {
                    "document_text": {
                        "type": "string",
                        "description": "Full text of the document to audit (contract, policy, resume, etc.)"
                    }
                },
                "required": ["document_text"]
            }
        )
    ]

@server.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    """Execute the requested tool."""
    if name == "audit_document":
        document_text = arguments.get("document_text", "")
        if not document_text:
            return [types.TextContent(type="text", text="Error: document_text is required.")]
        
        # Run the compliance agent
        result = compliance_graph.invoke({
            "document_text": document_text,
            "doc_id": "mcp-request"
        })
        
        # Format the response
        response = {
            "plan": result.get("plan", []),
            "final_report": result.get("final_report", ""),
            "passes_validation": result.get("passes_validation", True),
            "critique": result.get("critique", "")
        }
        
        return [types.TextContent(type="text", text=json.dumps(response, indent=2))]
    
    raise ValueError(f"Unknown tool: {name}")

async def run():
    """Start the MCP server using stdio transport."""
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="compliance-analyst",
                server_version="1.0.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={}
                )
            )
        )

if __name__ == "__main__":
    asyncio.run(run())