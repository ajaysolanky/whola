import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

def send_email(target_email, html_content):
    sender_email = "ajsolanky@gmail.com"
    receiver_email = target_email
    password = "app_pass_here"

    # Create the MIME message
    message = MIMEMultipart("alternative")
    message["Subject"] = "Your AMP Email Test"
    message["From"] = sender_email
    message["To"] = receiver_email

    # Add HTML content
    html_part = MIMEText(html_content, "html")
    message.attach(html_part)

    # Send the email
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:  # Use your SMTP server details
        server.login(sender_email, password)
        server.sendmail(sender_email, receiver_email, message.as_string())

# Example usage
html_content = """\
<!DOCTYPE html>
<html ⚡4email data-css-strict>
<head>
  <meta charset="utf-8" />
  <script async src="https://cdn.ampproject.org/v0.js"></script>
  <script async custom-element="amp-form" src="https://cdn.ampproject.org/v0/amp-form-0.1.js"></script>
  <script async custom-template="amp-mustache" src="https://cdn.ampproject.org/v0/amp-mustache-0.2.js"></script>
  <script async custom-element="amp-bind" src="https://cdn.ampproject.org/v0/amp-bind-0.1.js"></script>
  <style amp4email-boilerplate>
    body {
      visibility: hidden;
    }
  </style>
  <style amp-custom>
    /* Add your custom styles here */
    .response-container {
      margin-top: 10px;
    }
  </style>
</head>
<body>
  <amp-state id="chatHistory">
    <script type="application/json">
      {
        "messages": ""
      }
    </script>
  </amp-state>

  <amp-state id="chatState">
    <script type="application/json">
      {
        "convoId": ""
      }
    </script>
  </amp-state>

  <form method="post" action-xhr="https://d299-2603-7000-5100-74-515c-23b7-c690-87b9.ngrok-free.app/ganggang" id="chat-form" 
      on="submit-success:AMP.setState({
          chatHistory: {
            messages: (chatHistory.messages || '') + 'You: ' + event.target[0].value + '\n\n' + event.response.response + '\n\n'
          }, 
          chatState: {
            convoId: event.response.convo_id
          }
        })">
  <input type="text" name="message" placeholder="Type your message here" required />
  <input type="hidden" name="convo_id" [value]="chatState.convoId" value="" />
  <input type="hidden" name="auth" value="Pv7!n7h3W0rk" />
  <button type="submit">Send</button>
  <p [text]="chatHistory.messages"></p>
  <div submit-error>
    <template type="amp-mustache">
      <div class="response-container">Error: {{error}}</div>
    </template>
  </div>
</form>
</body>
</html>
"""
send_email("ajsolanky@gmail.com", html_content)
