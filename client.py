import asyncio
from typing import Optional
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()  # load environment variables from .env

class MCPClient:
    def __init__(self):
        # Initialize session and client objects
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self.openai = OpenAI()

    async def connect_to_server(self, server_script_path: str):
        """Connect to an MCP server
        
        Args:
            server_script_path: Path to the server script (.py or .js)
        """
        is_python = server_script_path.endswith('.py')
        is_js = server_script_path.endswith('.js')
        if not (is_python or is_js):
            raise ValueError("Server script must be a .py or .js file")
            
        command = "python" if is_python else "node"
        server_params = StdioServerParameters(
            command=command,
            args=[server_script_path],
            env=None
        )
        
        stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
        self.stdio, self.write = stdio_transport
        self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.write))
        
        await self.session.initialize()
        
        # List available tools
        response = await self.session.list_tools()
        tools = response.tools
        print("\nConnected to server with tools:", [tool.name for tool in tools])

    async def process_query(self, query: str, prev_query: str, prev_response: str) -> str:
        """Process a query using OpenAI and available tools"""
        
        # Format chat history as alternating list of queries and responses
        chat_history = []
        if prev_query and prev_response:
            chat_history.append(f"Query: {prev_query}")
            chat_history.append(f"Response: {prev_response}")
        
        # Create the formatted context for the LLM
        context_parts = []
        if chat_history:
            context_parts.append("=== CHAT HISTORY ===")
            context_parts.extend(chat_history)
            context_parts.append("=== END CHAT HISTORY ===")
            context_parts.append("")  # Empty line for separation
        
        context_parts.append("=== CURRENT QUERY ===")
        context_parts.append(query)
        context_parts.append("=== END CURRENT QUERY ===")
        
        # Join all parts with newlines
        formatted_context = "\n".join(context_parts)
        
        messages = [
            {
                "role": "user",
                "content": formatted_context
            }
        ]

        response = await self.session.list_tools()
        available_tools = [{ 
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.inputSchema
            }
        } for tool in response.tools]

        # Initial OpenAI API call
        response = self.openai.chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=1000,
            messages=messages,
            tools=available_tools,
            tool_choice="auto"
        )

        # Process response and handle tool calls
        final_text = []
        assistant_message = response.choices[0].message

        if assistant_message.content:
            final_text.append(assistant_message.content)

        if assistant_message.tool_calls:
            for tool_call in assistant_message.tool_calls:
                tool_name = tool_call.function.name
                tool_args = tool_call.function.arguments
                
                # Execute tool call
                # Parse the JSON string arguments into a dictionary
                import json
                try:
                    parsed_args = json.loads(tool_args) if isinstance(tool_args, str) else tool_args
                    result = await self.session.call_tool(tool_name, parsed_args)
                    final_text.append(f"[Calling tool {tool_name} with args {parsed_args}]")
                except json.JSONDecodeError as e:
                    final_text.append(f"Error parsing tool arguments: {e}")
                    continue

                # Continue conversation with tool results
                messages.append({
                    "role": "assistant",
                    "content": assistant_message.content,
                    "tool_calls": [tool_call]
                })
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result.content
                })

                # Get next response from OpenAI
                response = self.openai.chat.completions.create(
                    model="gpt-4o-mini",
                    max_tokens=1000,
                    messages=messages,
                )

                final_text.append(response.choices[0].message.content)

        return "\n".join(final_text)

    async def chat_loop(self):
        """Run an interactive chat loop"""
        print("\nMCP Client Started!")
        print("Type your queries or 'quit' to exit.")
        
        conversation_history = []  # List to store alternating queries and responses
        
        while True:
            try:
                query = input("\nQuery: ").strip()
                if query.lower() == 'quit':
                    break
                
                # Build context from conversation history
                prev_query = ""
                prev_response = ""
                if len(conversation_history) >= 2:
                    # Get the last query and response from history
                    prev_query = conversation_history[-2]  # Second to last item
                    prev_response = conversation_history[-1]  # Last item
                
                response = await self.process_query(query, prev_query, prev_response)
                print("\n" + response)
                
                # Add current query and response to history
                conversation_history.append(query)
                conversation_history.append(response)
                    
            except Exception as e:
                print(f"\nError: {str(e)}")
    
    async def cleanup(self):
        """Clean up resources"""
        await self.exit_stack.aclose()

async def main():
    import sys
    if len(sys.argv) < 2:
        print("Usage: mcp-client <path_to_server_script>")
        sys.exit(1)
        
    client = MCPClient()
    try:
        await client.connect_to_server(sys.argv[1])
        await client.chat_loop()
    finally:
        await client.cleanup()

def main_sync():
    """Synchronous entry point for the client"""
    asyncio.run(main())

if __name__ == "__main__":
    import sys
    main_sync()