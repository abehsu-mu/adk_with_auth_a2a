### Create virtual env & install packages
```cmd
uv venv --python=3.12.10
source .venv/bin/activate
uv sync
```

### Launc A2A server
- setup env
```cmd
export GOOGLE_GENAI_USE_VERTEXAI=TRUE
export GOOGLE_CLOUD_PROJECT=xxxxxx
export GOOGLE_CLOUD_LOCATION=us-west1
```
- launch server
```cmd
cd a2a_auth_server
uv run .
```

### Launc A2A client
```
cp adk_a2a_client/.env_example adk_a2a_client/.env
modify .env file to fill out project & token information
adk web
ask quesiton: Use transfer_to_agent to ask qna_agent what is the current stock price of Google.
```




### Example by using curl
```
curl -X POST http://localhost:10007 \
  -H "Authorization: Bearer <AAD token>" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": "1",
    "method": "message/send",
    "params": {
        "id": "2",
        "message": {
            "messageId": "msg-1",
            "role": "user",
            "parts": [
                {
                    "type": "text",
                    "text": "What is current stock price of Google"
                }
            ]
        }
    }
}' | jq .
```