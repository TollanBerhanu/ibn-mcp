# IBN MCP - Model Context Protocol Client and Server

A unified repository containing both an MCP (Model Context Protocol) client and server implementation with weather API integration.

## Overview

This project demonstrates the Model Context Protocol with:
- **MCP Client**: Connects to MCP servers and uses OpenAI's API for reasoning and tool calling
- **MCP Server**: Provides weather-related tools including forecasts and alerts
- **Weather Integration**: Uses the National Weather Service API for real-time weather data

## Features

### MCP Client
- Connects to MCP servers over stdio transport
- Integrates with OpenAI's GPT models for intelligent reasoning
- Maps MCP tools to OpenAI function-calling schema
- Interactive chat interface for querying tools

### MCP Server
- Weather forecast tool with latitude/longitude coordinates
- Weather alerts tool for US states
- GNS3 network topology creation and management with complete workflows
- Environment variable support for easy configuration
- FastMCP implementation for easy tool development
- National Weather Service API integration

## Prerequisites

- Python 3.12+
- OpenAI API key (set as `OPENAI_API_KEY` environment variable)
- Dependencies managed with `uv` (recommended) or pip

## Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd ibn-mcp
   ```

2. Install dependencies:
   ```bash
   uv sync
   ```

3. Set up your OpenAI API key:
   ```bash
   export OPENAI_API_KEY="your-api-key-here"
   # Or create a .env file with: OPENAI_API_KEY=your-api-key-here
   ```

4. (Optional) Set up your GNS3 server:
   ```bash
   export GNS3_SERVER="http://your-gns3-server:port"
   ```

## Usage

### Running the MCP Client

The client can connect to any MCP server script:

```bash
# Using the included weather server
uv run mcp-client server/weather.py

# Or using the demo server
uv run mcp-client server/server.py

# Or using the GNS3 server
uv run mcp-client server/gns3_mcp.py
```

### Running the MCP Server

```bash
# Run the weather server
uv run mcp-server weather

# Run the demo server
uv run mcp-server demo

# Run the GNS3 server
uv run mcp-server gns3

# Test the fix
uv run test_fix.py
```

### Example Queries

Once connected, you can ask questions like:
- "What is the weather in Rexburg, Idaho?"
- "Get weather alerts for California"
- "What's the forecast for Washington DC?"
- "Create a topology with 2 firewalls and 4 workstations in project 'My Network'"
- "Create a VPCS topology with 3 nodes in project 'test-gns3-api'"
- "List all available GNS3 templates"
- "Start all nodes in project 'My Network'"
- "Connect to GNS3 server"

## Project Structure

```
ibn-mcp/
├── client.py                 # MCP client implementation
├── server/
│   ├── __init__.py
│   ├── __main__.py           # Server entry point
│   ├── weather.py            # Weather API server
│   ├── server.py             # Demo server
│   └── gns3_mcp.py           # GNS3 network topology server
├── __init__.py               # Package initialization
├── pyproject.toml            # Project configuration
├── README.md                 # This file
└── .gitignore
```

## Development

### Setting up development environment

```bash
# Install with development dependencies
uv sync --extra dev

# Run tests
uv run pytest

# Format code
uv run black src/ tests/
uv run isort src/ tests/

# Lint code
uv run flake8 src/ tests/
```

### Adding New Tools

To add new tools to the server:

1. Create a new function in the appropriate server file
2. Decorate it with `@mcp.tool()`
3. Add proper type hints and docstrings
4. The client will automatically discover and use the new tool

## API Reference

### Weather Tools

#### `get_forecast(latitude: float, longitude: float) -> str`
Get weather forecast for a specific location using coordinates.

#### `get_alerts(state: str) -> str`
Get active weather alerts for a US state (two-letter code).

### GNS3 Tools

#### `connect_to_gns3(server_url: str, username: str, password: str) -> str`
Connect to a GNS3 server with optional authentication.

#### `list_projects(server_url: str) -> str`
List all available projects on the GNS3 server.

#### `list_templates(server_url: str) -> str`
List all available templates on the GNS3 server.

#### `create_simple_topology(project_name: str, firewalls: int, workstations: int, ...) -> str`
Create a complete network topology with firewalls, workstations, and a switch.
This tool handles the entire workflow: connection, node creation, linking, and starting.

#### `create_vpcs_topology(project_name: str, vpcs_count: int, vpcs_template: str) -> str`
Create a simple topology with VPCS nodes connected to a switch.
Specialized tool for creating VPCS-based networks.

#### `create_vpcs_network(project_name: str, vpcs_count: int) -> str`
Create a VPCS network with the specified number of VPCS nodes connected to a switch.
Simplified tool specifically designed for VPCS networks.

#### `create_custom_topology(project_name: str, topology_description: str) -> str`
Create a custom topology based on natural language description.

#### `start_project_nodes(project_name: str) -> str`
Start all nodes in a project.

#### `stop_project_nodes(project_name: str) -> str`
Stop all nodes in a project.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Run the test suite
6. Submit a pull request

## License

[Add your license here]

## Acknowledgments

- Model Context Protocol (MCP) specification
- National Weather Service API
- OpenAI API
