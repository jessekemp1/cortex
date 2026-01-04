#!/usr/bin/env python3
"""
Cortex MCP Server
Universal Model Context Protocol server for Cortex.
Bridging Antigravity, Cursor, and Claude Code.

Protocol: JSON-RPC 2.0 over Stdio
Capabilities:
- Resources: cortex://context?query=...
- Tools: inject_recommendation, trigger_action
"""
import json
import logging
import sys
import traceback
from pathlib import Path
from typing import Any, Dict, Optional

# Ensure we can import cortex modules
ROOT_DIR = Path(__file__).parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from cortex.bridge import CortexBridge

# Configure logging to stderr (stdout is for Protocol)
logging.basicConfig(
    stream=sys.stderr, level=logging.INFO, format="[CortexMCP] %(message)s"
)
logger = logging.getLogger("cortex-mcp")


class MCPServer:
    def __init__(self):
        self.bridge = CortexBridge(ROOT_DIR)
        self.tools = {
            # V1 Tools
            "inject_recommendation": self._tool_inject,
            "trigger_action": self._tool_trigger,
            # V2 Prime Tools
            "v2_status": self._tool_v2_status,
            "graph_query": self._tool_graph_query,
            "graph_add_node": self._tool_graph_add_node,
            "graph_related": self._tool_graph_related,
            "interventions_list": self._tool_interventions_list,
            "interventions_ack": self._tool_interventions_ack,
            "iap_message": self._tool_iap_message,
        }

    def run(self):
        """Main loop: Read line -> Process JSON-RPC -> Write line"""
        logger.info("Starting Cortex MCP Server...")

        while True:
            try:
                line = sys.stdin.readline()
                if not line:
                    break

                request = json.loads(line)
                response = self._handle_request(request)

                if response:
                    print(json.dumps(response), flush=True)

            except json.JSONDecodeError:
                logger.error("Invalid JSON received")
            except Exception as e:
                logger.error(f"Server Error: {e}")
                traceback.print_exc(file=sys.stderr)

    def _handle_request(self, request: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Handle JSON-RPC request."""
        req_id = request.get("id")
        method = request.get("method")
        params = request.get("params", {})

        if not method:
            return None

        try:
            result = None
            if method == "initialize":
                result = {
                    "protocolVersion": "0.1.0",
                    "serverInfo": {"name": "cortex-mcp", "version": "1.0.0"},
                    "capabilities": {"resources": {}, "tools": {}},
                }
            elif method == "notifications/initialized":
                # client acknowledging
                return None
            elif method == "resources/list":
                result = {
                    "resources": []
                }  # We use templates mostly, but could list recent?
            elif method == "resources/templates/list":
                result = {
                    "resourceTemplates": [
                        {
                            "uriTemplate": "cortex://context/{query}",
                            "name": "Cortex Context",
                            "description": "Get context from Cortex Brain (Knowledge Base + Project History)",
                            "mimeType": "application/json",
                        }
                    ]
                }
            elif method == "resources/read":
                uri = params.get("uri", "")
                result = self._handle_resource_read(uri)
            elif method == "tools/list":
                result = {
                    "tools": [
                        # V1 Tools
                        {
                            "name": "inject_recommendation",
                            "description": "Inject a strategic recommendation into Cortex.",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "title": {"type": "string"},
                                    "rationale": {"type": "string"},
                                    "priority": {
                                        "type": "string",
                                        "enum": ["high", "medium", "low"],
                                    },
                                    "related_project": {"type": "string"},
                                },
                                "required": ["title", "rationale"],
                            },
                        },
                        {
                            "name": "trigger_action",
                            "description": "Trigger an automated agent.",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "agent_id": {"type": "string"},
                                    "payload": {"type": "object"},
                                },
                                "required": ["agent_id"],
                            },
                        },
                        # V2 Prime Tools
                        {
                            "name": "v2_status",
                            "description": "Get Cortex V2 Prime system status including engines, graph stats, and interventions.",
                            "inputSchema": {"type": "object", "properties": {}},
                        },
                        {
                            "name": "graph_query",
                            "description": "Query the context graph by node type (project, pattern, lesson, goal, error).",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "node_type": {
                                        "type": "string",
                                        "description": "Type of nodes to query",
                                        "enum": ["project", "pattern", "lesson", "goal", "error", "file", "work_item"],
                                    },
                                },
                            },
                        },
                        {
                            "name": "graph_add_node",
                            "description": "Add a node to the context graph.",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "node_type": {"type": "string", "description": "Type of node"},
                                    "name": {"type": "string", "description": "Node name"},
                                    "data": {"type": "object", "description": "Node data"},
                                },
                                "required": ["node_type", "name"],
                            },
                        },
                        {
                            "name": "graph_related",
                            "description": "Get nodes related to a given node.",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "node_id": {"type": "string", "description": "Node ID to find relations for"},
                                    "edge_type": {
                                        "type": "string",
                                        "description": "Optional edge type filter",
                                        "enum": ["relates_to", "implements", "blocks", "causes", "contains", "used_in"],
                                    },
                                },
                                "required": ["node_id"],
                            },
                        },
                        {
                            "name": "interventions_list",
                            "description": "List pending interventions from the Action Broker.",
                            "inputSchema": {"type": "object", "properties": {}},
                        },
                        {
                            "name": "interventions_ack",
                            "description": "Acknowledge an intervention.",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "intervention_id": {"type": "string", "description": "ID of intervention to acknowledge"},
                                },
                                "required": ["intervention_id"],
                            },
                        },
                        {
                            "name": "iap_message",
                            "description": "Send an Inter-Agent Protocol message to Cortex.",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "message_type": {
                                        "type": "string",
                                        "enum": ["query", "handoff", "ack"],
                                        "description": "Type of IAP message",
                                    },
                                    "payload": {"type": "object", "description": "Message payload"},
                                    "context": {"type": "object", "description": "Optional context snapshot"},
                                },
                                "required": ["message_type", "payload"],
                            },
                        },
                    ]
                }
            elif method == "tools/call":
                name = params.get("name")
                args = params.get("arguments", {})
                if name in self.tools:
                    tool_result = self.tools[name](args)
                    result = {
                        "content": [
                            {"type": "text", "text": json.dumps(tool_result, indent=2)}
                        ]
                    }
                else:
                    raise ValueError(f"Unknown tool: {name}")
            else:
                # Ignore unknown methods or ping
                return None

            return {"jsonrpc": "2.0", "id": req_id, "result": result}

        except Exception as e:
            logger.error(f"Request failed: {e}")
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32000, "message": str(e)},
            }

    def _handle_resource_read(self, uri: str) -> Dict[str, Any]:
        """Handle cortex://context/{query}"""
        if not uri.startswith("cortex://context/"):
            raise ValueError("Unsupported URI scheme")

        query = uri.replace("cortex://context/", "")
        query = query.replace("%20", " ")  # Basic decoding

        items = self.bridge.get_context(query)

        return {
            "contents": [
                {
                    "uri": uri,
                    "mimeType": "application/json",
                    "text": json.dumps(items, indent=2),
                }
            ]
        }

    def _tool_inject(self, args: Dict[str, Any]) -> Dict[str, Any]:
        success = self.bridge.inject_recommendation(
            title=args["title"],
            rationale=args["rationale"],
            priority=args.get("priority", "medium"),
            related_project=args.get("related_project", ""),
        )
        return {"success": success}

    def _tool_trigger(self, args: Dict[str, Any]) -> Dict[str, Any]:
        return self.bridge.trigger_action(
            agent_id=args["agent_id"], payload=args.get("payload", {})
        )

    # V2 Prime Tool Implementations

    def _tool_v2_status(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get V2 Prime system status."""
        return self.bridge.get_v2_status()

    def _tool_graph_query(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Query context graph by node type."""
        node_type = args.get("node_type")
        if node_type:
            return {"nodes": self.bridge.query_graph(node_type)}
        else:
            return {"stats": self.bridge.get_graph_stats()}

    def _tool_graph_add_node(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Add a node to the context graph."""
        return self.bridge.add_graph_node(
            node_type=args["node_type"],
            name=args["name"],
            data=args.get("data", {}),
        )

    def _tool_graph_related(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get nodes related to a given node."""
        return {
            "related": self.bridge.get_related_nodes(
                node_id=args["node_id"],
                edge_type=args.get("edge_type"),
            )
        }

    def _tool_interventions_list(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """List pending interventions."""
        return {"interventions": self.bridge.get_pending_interventions()}

    def _tool_interventions_ack(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Acknowledge an intervention."""
        return self.bridge.acknowledge_intervention(args["intervention_id"])

    def _tool_iap_message(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle Inter-Agent Protocol message."""
        message = {
            "message_type": args["message_type"],
            "payload": args["payload"],
        }
        if args.get("context"):
            message["context_snapshot"] = args["context"]
        return self.bridge.handle_iap_message(message)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "inspector":
        print("MCP Inspector mode not implemented yet.")
        sys.exit(0)

    server = MCPServer()
    server.run()
