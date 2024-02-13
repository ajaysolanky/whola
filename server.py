import os
from flask import Flask, request, jsonify, make_response
import requests
import uuid
from flask_cors import CORS

app = Flask(__name__)

# Enable CORS for all domains on all routes. Adjust accordingly for production.
CORS(app, supports_credentials=True)

HARD_CODED_AUTH_KEY = 'Pv7!n7h3W0rk'
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

conversations = {}

@app.route('/ganggang', methods=['POST'])
def ganggang():
    content_type = request.headers.get('Content-Type')
    
    if content_type and content_type.startswith('application/json'):
        data = request.get_json()
    else:
        # Default to form data if content type is not application/json
        data = request.form
    
    message = data.get('message')
    convo_id = data.get('convo_id')
    auth_key = data.get('auth')

    if auth_key != HARD_CODED_AUTH_KEY:
        return jsonify({"error": "Unauthorized"}), 401

    if not convo_id:
        convo_id = str(uuid.uuid4())

    convo_history = conversations.get(convo_id, [])
    convo_history.append({"role": "user", "content": message})
    conversations[convo_id] = convo_history

    headers = {
        'Authorization': f'Bearer {OPENAI_API_KEY}',
        'Content-Type': 'application/json',
    }

    data = {
        'model': 'gpt-3.5-turbo',
        'messages': convo_history,
    }

    print("REQUEST:\n")
    print(data)

    response = requests.post('https://api.openai.com/v1/chat/completions', headers=headers, json=data)
    
    if response.status_code == 200:
        openai_response = response.json()
        server_response = openai_response['choices'][0]['message']['content']
        conversations[convo_id].append({"role": "assistant", "content": server_response})
        response_data = {"response": server_response, "convo_id": convo_id}
    else:
        response_data = {"response": "Failed to fetch response from OpenAI"}, 500
    
    print("RESPONSE:\n")
    print(response_data)

    # Set required AMP for Email headers
    amp_headers = {
        'AMP-Email-Allow-Sender': request.headers.get('AMP-Email-Sender', '*'),
        'Access-Control-Allow-Origin': request.headers.get('Origin'),
        'Access-Control-Allow-Credentials': 'true',
        'Access-Control-Expose-Headers': 'AMP-Access-Control-Allow-Source-Origin, AMP-Email-Allow-Sender',
        'AMP-Access-Control-Allow-Source-Origin': request.args.get('__amp_source_origin'),
    }

    response = make_response(jsonify(response_data), response_data[1] if isinstance(response_data, tuple) else 200)
    for header, value in amp_headers.items():
        response.headers[header] = value
    
    return response

if __name__ == '__main__':
    app.run(port=8000, debug=True)
