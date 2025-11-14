Frappe WhatsApp

[Docs](https://shridarpatil.github.io/frappe_whatsapp/)

WhatsApp integration for Frappe using WAHA (WhatsApp HTTP API).

[![Whatsapp Video](https://img.youtube.com/vi/nq5Kcc5e1oc/0.jpg)](https://www.youtube.com/watch?v=nq5Kcc5e1oc)

[![YouTube](http://i.ytimg.com/vi/TncXQ0UW5UM/hqdefault.jpg)](https://www.youtube.com/watch?v=TncXQ0UW5UM)

![whatsapp](https://user-images.githubusercontent.com/11792643/203741234-29edeb1b-e2f9-4072-98c4-d73a84b48743.gif)

### Chat app

You can also install [whatsapp_chat](https://frappecloud.com/marketplace/apps/whatsapp_chat) along with this app to send and receive messages like a messenger.

## Installation Steps

### Step 1) Get the app

```bash
bench get-app https://github.com/shridarpatil/frappe_whatsapp
```

### Step 2) Install app on any instance/site

```bash
bench --site [sitename] install-app frappe_whatsapp
```

## Configuration

### Set up WAHA Server

1. Install and run WAHA server (https://waha.devlike.pro/)
2. Start a WhatsApp session in WAHA
3. Scan QR code to authenticate

### Enter WAHA Credentials in Frappe

Navigate to **WhatsApp Settings** and configure:

-   **WAHA URL**: Your WAHA server URL (e.g., `http://localhost:3000`)
-   **API Key**: Your WAHA X-Api-Key (if authentication is enabled)
-   **Session Name**: WAHA session name (default: `default`)
-   **Webhook HMAC Secret**: Secret key for webhook authentication (optional but recommended)

## Features

### Send WhatsApp Notifications

Create notifications based on DocType events to automatically send WhatsApp messages.

### Send Text Messages

Create an entry in the WhatsApp Message doctype. On save, it will trigger the WAHA API to send a message.

### Receive Messages

Messages are received via WAHA webhooks and automatically created in the WhatsApp Message doctype.

### Bulk Messaging

Send bulk WhatsApp messages to multiple recipients using the Bulk WhatsApp Message doctype.

## Webhook Setup

### Configure Webhook in WAHA

When starting your WAHA session, configure the webhook URL in the session config:

```json
{
    "name": "default",
    "config": {
        "webhooks": [
            {
                "url": "https://yourdomain.com/api/method/frappe_whatsapp.utils.webhook.webhook",
                "events": ["message", "message.any", "message.reaction", "message.ack", "message.revoked", "session.status"],
                "hmac": {
                    "key": "your-secret-key-from-whatsapp-settings"
                }
            }
        ]
    }
}
```

**Webhook URL**: `https://yourdomain.com/api/method/frappe_whatsapp.utils.webhook.webhook`

**Important**:

-   Use the same HMAC secret key in both WAHA config and WhatsApp Settings
-   Make sure your domain is accessible from the WAHA server
-   Configure the webhook when creating/starting the session in WAHA

### Webhook Events

The following events are supported:

-   `message` - Incoming messages
-   `message.any` - All messages (including outgoing)
-   `message.reaction` - Message reactions
-   `message.ack` - Message acknowledgments
-   `message.revoked` - Deleted messages
-   `session.status` - Session status changes

## Usage Examples

### Send a Simple Message

```python
frappe.get_doc({
    "doctype": "WhatsApp Message",
    "to": "+1234567890",
    "type": "Outgoing",
    "message_type": "Manual",
    "message": "Hello from Frappe!",
    "content_type": "text"
}).insert()
```

### Send an Image

```python
frappe.get_doc({
    "doctype": "WhatsApp Message",
    "to": "+1234567890",
    "type": "Outgoing",
    "message_type": "Manual",
    "message": "Check this out!",
    "content_type": "image",
    "attach": "/files/image.jpg"
}).insert()
```

#### License

MIT
