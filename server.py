from flask import Flask, request, jsonify, make_response
import requests
import uuid
from flask_cors import CORS, cross_origin

app = Flask(__name__)

CORS(app)

# Replace 'YOUR_HARD_CODED_AUTH_KEY' with your actual hardcoded auth key
HARD_CODED_AUTH_KEY = 'Pv7!n7h3W0rk'
# Replace 'OPENAI_API_KEY' with your actual OpenAI API key
OPENAI_API_KEY = 'openai_key_here'

conversations = {}

@app.route('/ganggang', methods=['POST'])
@cross_origin(headers=['Content-Type', 'Authorization'])
def ganggang():
    print("REQUEST:\n")
    # import pdb; pdb.set_trace()
    content_type = request.headers.get('Content-Type')
    
    if content_type.startswith('application/json'):
        data = request.get_json()
    elif content_type.startswith('multipart/form-data'):
        data = request.form
    else:
        return jsonify({"error": "Unsupported Media Type"}), 415
    
    print(data)
    print()

    message = data.get('message')
    convo_id = data.get('convo_id')
    auth_key = data.get('auth')

    # Validate auth key
    if auth_key != HARD_CODED_AUTH_KEY:
        return jsonify({"error": "Unauthorized"}), 401

    # Generate a new convo_id if empty
    if not convo_id:
        convo_id = str(uuid.uuid4())

    # Fetch or initialize conversation history
    convo_history = conversations.get(convo_id, [])

    # Add new message to the conversation history
    convo_history.append({"role": "user", "content": message})
    conversations[convo_id] = convo_history

    # Prepare request to OpenAI API
    headers = {
        'Authorization': f'Bearer {OPENAI_API_KEY}',
        'Content-Type': 'application/json',
    }

    data = {
        'model': 'gpt-3.5-turbo',  # or any other compatible model
        'messages': convo_history,
    }

    print(f"data:\n{data}\n\nfetching response...")

    response = requests.post('https://api.openai.com/v1/chat/completions', headers=headers, json=data)
    
    if response.status_code == 200:
        openai_response = response.json()
        server_response = openai_response.get('choices')[0].get('message').get('content')
        
        # Add OpenAI's response to the conversation history
        conversations[convo_id].append({"role": "assistant", "content": server_response})
        
        print(f"response:\n{server_response}\n")
        # return jsonify({"response": server_response, "convo_id": convo_id})
        response_data = jsonify({"response": server_response, "convo_id": convo_id})
    else:
        print(f"OpenAI error\n")
        # return jsonify({"error": "Failed to fetch response from OpenAI"}), 500
        response_data = jsonify({"error": "Failed to fetch response from OpenAI"}), 500
    
    response = make_response(response_data)
    response.headers['Access-Control-Allow-Origin'] = request.headers.get('Origin')
    response.headers['AMP-Email-Allow-Sender'] = request.headers.get('AMP-Email-Sender', '*')
    response.headers['Access-Control-Expose-Headers'] = 'AMP-Access-Control-Allow-Source-Origin'
    response.headers['AMP-Access-Control-Allow-Source-Origin'] = request.args.get('__amp_source_origin')
    print(response)
    return response

if __name__ == '__main__':
    app.run(port=8000, debug=True)
