# Telex Country Info A2A Agent

A Python-based A2A (Agent-to-Agent) service that provides country information with cultural facts through the Telex platform. Built with FastAPI and integrated with RestCountries API and Anthropic Claude.

## Features

- 🌍 **Country Information**: Retrieves detailed data about any country (capital, population, languages, currencies, timezones)
- 🎭 **Cultural Facts**: Generates unique cultural insights using Claude AI
- ⚡ **Dual Mode Support**:
  - **Blocking mode**: Synchronous responses
  - **Non-blocking mode**: Asynchronous processing with webhook callbacks
- 🔌 **A2A Protocol**: Full JSON-RPC 2.0 compliance for Telex integration
- 📊 **Validated**: Passes Telex A2A endpoint validation

## Architecture

```
┌─────────────┐          ┌──────────────┐          ┌─────────────┐
│   Telex     │  A2A     │   FastAPI    │   API    │ RestCountries│
│  Platform   │ ───────> │   Service    │ ───────> │     API      │
└─────────────┘          └──────────────┘          └─────────────┘
                                │
                                │ AI
                                ▼
                         ┌─────────────┐
                         │  Anthropic  │
                         │   Claude    │
                         └─────────────┘
```

## Prerequisites

- Python 3.11+
- Anthropic API key
- Railway account (for deployment)
- Telex platform access

## Installation

1. **Clone the repository**

   ```bash
   git clone https://github.com/Fritz-nvm/Telex-AI-agent
   cd Telex-AI-agent
   ```

2. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

3. **Set environment variables**
   ```bash
   export ANTHROPIC_API_KEY="your-api-key-here"
   export PORT=8080
   ```

## Configuration

### Environment Variables

| Variable            | Description                  | Required | Default |
| ------------------- | ---------------------------- | -------- | ------- |
| `ANTHROPIC_API_KEY` | Anthropic API key for Claude | Yes      | -       |
| `PORT`              | Server port                  | No       | 8080    |

## API Endpoints

### A2A Endpoint

```
POST /v1/a2a/country_info
```

**Request Format** (JSON-RPC 2.0):

```json
{
  "jsonrpc": "2.0",
  "id": "request-id",
  "method": "message/send",
  "params": {
    "message": {
      "kind": "message",
      "role": "user",
      "parts": [
        {
          "kind": "text",
          "text": "tell me about Japan"
        }
      ],
      "messageId": "msg-id",
      "metadata": {
        "telex_user_id": "user-id",
        "telex_channel_id": "channel-id",
        "org_id": "org-id"
      }
    },
    "contextId": "context-id",
    "configuration": {
      "blocking": false,
      "pushNotificationConfig": {
        "url": "https://ping.telex.im/v1/a2a/webhooks/webhook-id",
        "token": "bearer-token"
      }
    }
  }
}
```

**Response Format** (Blocking Mode):

```json
{
  "jsonrpc": "2.0",
  "id": "request-id",
  "result": {
    "id": "task-id",
    "contextId": "context-id",
    "status": {
      "state": "completed",
      "timestamp": "2025-11-03T19:31:22.605544",
      "message": {
        "kind": "message",
        "role": "agent",
        "parts": [
          {
            "kind": "text",
            "text": "Japan [JP]\n- Capital: Tokyo\n- Population: 126M\n..."
          }
        ],
        "messageId": "msg-id",
        "taskId": "task-id"
      }
    },
    "artifacts": [],
    "history": [],
    "kind": "task"
  }
}
```

**Response Format** (Non-blocking Mode):

```json
{
  "jsonrpc": "2.0",
  "id": "request-id",
  "result": {
    "id": "task-id",
    "contextId": "context-id",
    "status": {
      "state": "running",
      "timestamp": "2025-11-03T19:31:22.605544"
    },
    "artifacts": [],
    "history": [],
    "kind": "task"
  }
}
```

_Note: In non-blocking mode, the final result is sent to the webhook URL_

### Health Check

```
GET /v1/a2a/country_info/health
```

Returns service status and capabilities.

## Usage Examples

### Query a Country

```
User: "tell me about Brazil"
Agent: "Brazil [BR]
- Capital: Brasília
- Region: South America
- Population: 212,559,417
- Languages: Portuguese
- Currencies: Brazilian real
- Timezones: UTC-5, UTC-4, UTC-3, UTC-2

Cultural fact: In Brazil, the 'Festa Junina' celebrates..."
```

### Supported Queries

- "tell me about [country]"
- "[country]"
- "information on [country]"
- "what about [country]"

## Development

### Run Locally

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
```

### Project Structure

```
telex-country-agent/
├── app/
│   ├── main.py                 # FastAPI application entry
│   ├── api/
│   │   └── v1/
│   │       └── countries.py    # Country info endpoint
│   └── schemas/
│       └── a2a.py              # Pydantic models for A2A protocol
├── requirements.txt
├── Procfile                    # Railway deployment config
└── README.md
```

### Key Components

**Country Extraction** (`extract_country`):

- Parses user input to identify country names
- Handles various formats and common phrases

**Country Data Fetching** (`country_summary_with_fact`):

- Fetches data from RestCountries API
- Generates cultural facts using Claude AI
- Formats response in readable format

**Push Notifications** (`push_to_telex`):

- Sends async results to Telex webhook
- Matches exact structure required by Telex
- Includes user and agent message history

## Deployment

### Railway Deployment

1. **Connect Repository**

   ```bash
   railway link
   ```

2. **Set Environment Variables**

   ```bash
   railway variables set ANTHROPIC_API_KEY=your-key
   ```

3. **Deploy**

   ```bash
   railway up
   ```

4. **Get URL**
   ```bash
   railway domain
   ```

### Telex Integration

1. Create an A2A workflow in Telex
2. Add your Railway URL as the agent endpoint:
   ```
   https://your-app.railway.app/v1/a2a/country_info
   ```
3. Configure webhook settings for non-blocking mode
4. Test the integration

## Error Handling

The service returns JSON-RPC 2.0 compliant errors:

| Code   | Message          | Description                |
| ------ | ---------------- | -------------------------- |
| -32700 | Parse error      | Invalid JSON               |
| -32600 | Invalid Request  | Malformed JSON-RPC         |
| -32601 | Method not found | Unsupported method         |
| -32602 | Invalid params   | Missing/invalid parameters |
| -32603 | Internal error   | Server error               |

## Performance

- **Blocking mode**: ~2-5 seconds response time
- **Non-blocking mode**: Immediate 202 response, result delivered via webhook in ~3-6 seconds
- **Timeout**: 25 seconds for country data + AI generation
- **Rate limits**: Depends on Anthropic API tier

## Limitations

- Country names must be recognizable (common names or official names)
- Cultural facts are AI-generated and may vary
- Requires internet connectivity for external APIs
- Non-blocking mode requires valid webhook configuration

## Troubleshooting

### "Country not found"

- Check spelling
- Try official country name (e.g., "United States" not "USA")
- Some territories may not be in RestCountries database

### Webhook not receiving responses

- Verify webhook URL is accessible
- Check bearer token is valid
- Ensure webhook accepts JSON-RPC format
- Check Railway logs for push errors

### Validation failing

- Ensure all JSON-RPC fields are present
- Verify message structure matches schema
- Check that HTTP status is 200 even for errors

## License

MIT License - see LICENSE file for details

**Built with ❤️ for the Telex A2A ecosystem**
