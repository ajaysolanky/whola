import requests

# BASE_URL = "http://127.0.0.1:8000"
BASE_URL = "https://d299-2603-7000-5100-74-515c-23b7-c690-87b9.ngrok-free.app"

def chat_with_server():
    convo_id = None
    while True:
        user_message = input("You: ")
        if user_message.lower() == "exit":
            print("Exiting chat...")
            break

        payload = {
            "message": user_message,
            "convo_id": convo_id,
            "auth": "Pv7!n7h3W0rk"  # Replace with your actual hardcoded auth key
        }

        response = requests.post(f"{BASE_URL}/ganggang", json=payload)
        if response.status_code == 200:
            data = response.json()
            server_response = data.get('response')
            convo_id = data.get('convo_id')
            print(f"Server: {server_response}")
        else:
            print(f"Failed to communicate with the server. Status code: {response.status_code}")
            break

if __name__ == "__main__":
    print("Chat with the server. Type 'exit' to end the chat.")
    chat_with_server()
