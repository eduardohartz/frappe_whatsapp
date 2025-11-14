# Migration from Facebook WhatsApp API to WAHA

This document summarizes the complete migration of frappe_whatsapp from Facebook's WhatsApp Business API to WAHA (WhatsApp HTTP API).

## Overview

The app has been completely converted to use WAHA API instead of Facebook's official WhatsApp Business API. This provides a simpler, more flexible integration without the need for Meta Business accounts or WhatsApp Business API approval.

## Major Changes

### 1. Removed Template System

-   **Deleted**: Entire `whatsapp_templates` doctype and all related files
-   **Deleted**: `template_utils.py` utility file
-   **Removed**: Template fields from all doctypes
-   **Reason**: WAHA uses direct messaging without requiring pre-approved templates

### 2. Updated Doctypes

#### WhatsApp Settings (`whatsapp_settings.json`)

**Removed Fields:**

-   `token` - Facebook access token
-   `url` - Graph API URL
-   `version` - API version
-   `phone_id` - WhatsApp phone number ID
-   `business_id` - Meta business account ID
-   `app_id` - Facebook app ID
-   `webhook_verify_token` - Facebook webhook verification

**Added Fields:**

-   `waha_url` - WAHA server URL
-   `api_key` - WAHA API key for authentication
-   `session_name` - WAHA session name (default: "default")
-   `webhook_hmac_secret` - Secret for HMAC SHA512 webhook authentication

#### WhatsApp Message (`whatsapp_message.json`)

**Removed Fields:**

-   `use_template` - Template usage flag
-   `template` - Link to template
-   `template_parameters` - Template parameter values
-   `template_header_parameters` - Template header parameters
-   `body_param` - Body parameters

**Updated:**

-   `message_type` options changed from "Manual\nTemplate" to "Manual"

#### WhatsApp Notification (`whatsapp_notification.json`)

**Removed Fields:**

-   `template` - Link to WhatsApp Templates
-   `header_type` - Template header type

**Added Fields:**

-   `message` - Long Text field for message content with field variable support

**Updated:**

-   Help text to show direct message examples instead of template examples
-   Field descriptions to reflect WAHA usage

#### Bulk WhatsApp Message (`bulk_whatsapp_message.json`)

**Removed Fields:**

-   `use_template` - Template usage checkbox
-   `template` - Link to template
-   `variable_type` - Common/Unique variables
-   `template_variables` - JSON template variables

**Added Fields:**

-   `message_content` - Long Text field for message content with {{variable}} syntax

### 3. Core Python Files Rewritten

#### `whatsapp_message.py`

-   **Complete rewrite** for WAHA API
-   Changed from `make_post_request` to `requests` library
-   Implemented new methods:
    -   `send_text()` - Send text messages
    -   `send_image()` - Send image messages
    -   `send_video()` - Send video messages
    -   `send_voice()` - Send voice messages
    -   `send_file()` - Send file attachments
    -   `send_reaction()` - Send reactions to messages
    -   `send_location()` - Send location messages
    -   `send_contact()` - Send contact vCards
-   Added `format_number()` to convert phone numbers to WAHA format (adds @c.us)
-   Added `make_waha_request()` helper for API calls with X-Api-Key authentication
-   Removed `send_template()` method entirely

#### `webhook.py`

-   **Complete rewrite** with HMAC authentication
-   Added `verify_hmac()` function using SHA512 for webhook security
-   Changed from Facebook webhook format to WAHA event format
-   Implemented event handlers:
    -   `handle_message()` - Process incoming text messages
    -   `handle_reaction()` - Process message reactions
    -   `handle_message_ack()` - Process message acknowledgments
    -   `handle_message_revoked()` - Process message deletions
    -   `handle_session_status()` - Monitor WAHA session status
-   Added media download from WAHA with `handle_media_message()`
-   Removed Facebook-specific `update_status()` functions

#### `whatsapp_notification.py`

-   Removed template dependencies completely
-   Replaced `send_template_message()` with `send_notification_message()`
-   Added message formatting with field replacement using `{field_name}` syntax
-   Changed from `make_post_request` to `requests.post()`
-   Added `notify_waha()` method for WAHA API calls
-   Implemented file type detection for attachments
-   Updated to use WAHA message endpoints

#### `bulk_whatsapp_message.py`

-   Removed template references from `create_single_message()`
-   Simplified to use `message_content` with `{{variable}}` replacement
-   Updated variable substitution to work without templates

### 4. JavaScript Updates

#### `frappe_whatsapp.js`

-   Removed template selection UI
-   Changed to direct message input with:
    -   Message text field
    -   Content type selector
    -   Attachment field

#### `whatsapp_notification.js`

-   Removed `load_template()` function
-   Removed `template` change handler
-   Simplified attachment logic without template header types

#### `bulk_whatsapp_message.js`

-   Removed template validation check
-   Updated validation to require `message_content` only

### 5. Documentation

#### `README.md`

-   **Completely rewritten** for WAHA setup
-   Removed all Facebook API references
-   Added WAHA installation instructions
-   Updated webhook configuration with HMAC setup
-   Changed configuration section to show WAHA fields
-   Updated usage examples to show direct messaging

#### `docs/index.html`

-   Updated title and meta information
-   Changed "Template Management" feature to "WAHA Integration"
-   Updated prerequisites from Meta Business to WAHA server
-   Rewrote configuration section for WAHA settings
-   Updated API examples to show WAHA usage
-   Changed troubleshooting section for WAHA-specific issues
-   Removed all template-related examples

#### `pyproject.toml`

-   Updated description from "meta API's" to "WAHA (WhatsApp HTTP API)"

### 6. Utility Updates

#### `utils/__init__.py`

-   Changed method call from `send_template_message()` to `send_notification_message()`

## API Changes

### Authentication

**Before (Facebook):**

-   Bearer token in Authorization header
-   Phone Number ID in URL path
-   API version in URL

**After (WAHA):**

-   X-Api-Key header authentication
-   Session name in request body
-   Base URL: `{waha_url}/api/{endpoint}`

### Message Format

**Before (Facebook):**

```python
{
    "messaging_product": "whatsapp",
    "to": "+1234567890",
    "type": "template",
    "template": {
        "name": "template_name",
        "language": {"code": "en"},
        "components": [...]
    }
}
```

**After (WAHA):**

```python
{
    "session": "default",
    "chatId": "1234567890@c.us",
    "text": "Your message here"
}
```

### Webhook Format

**Before (Facebook):**

-   GET request for verification with `hub.verify_token`
-   POST with Facebook-specific event structure

**After (WAHA):**

-   No GET verification needed
-   POST with HMAC SHA512 signature in X-Hmac-Signature header
-   Event-based structure with event types: message, message.any, message.reaction, message.ack, message.revoked, session.status

## Webhook Security

### HMAC Authentication

WAHA webhooks are secured using HMAC SHA512:

1. WAHA signs webhook payload with secret key
2. Signature sent in `X-Hmac-Signature` header
3. Frappe verifies signature using same secret
4. Rejects webhooks with invalid signatures

### Setup

1. Configure same secret in both WAHA and Frappe WhatsApp Settings
2. WAHA sends signature: `hmac.new(secret, payload, hashlib.sha512).hexdigest()`
3. Frappe verifies: `hmac.compare_digest(calculated, received)`

## Phone Number Format

### Facebook Format

-   Full international format: `+1234567890`
-   Country code required with +

### WAHA Format

-   ChatId format: `1234567890@c.us`
-   Phone number without + prefix
-   Automatically appended with @c.us by `format_number()` method

## Message Types Support

### WAHA Endpoints Used

-   `/api/sendText` - Text messages
-   `/api/sendImage` - Image with caption
-   `/api/sendVideo` - Video with caption
-   `/api/sendVoice` - Audio/voice messages
-   `/api/sendFile` - Document files
-   `/api/sendLocation` - GPS coordinates
-   `/api/sendContactVcard` - Contact vCards
-   `/api/sendSeen` - Mark messages as seen
-   `/api/reaction` - React to messages

## Field Variable Replacement

### Notifications

Messages support field replacement using `{field_name}` syntax:

```
Dear {customer_name}, your order {order_id} has been confirmed.
```

### Bulk Messages

Use `{{field_name}}` syntax for recipient data:

```
Hello {{name}}, your balance is {{amount}}.
```

## Migration Checklist

-   [x] Remove WhatsApp Templates doctype
-   [x] Update WhatsApp Settings doctype
-   [x] Update WhatsApp Message doctype
-   [x] Update WhatsApp Notification doctype
-   [x] Update Bulk WhatsApp Message doctype
-   [x] Rewrite whatsapp_message.py
-   [x] Rewrite webhook.py with HMAC
-   [x] Update whatsapp_notification.py
-   [x] Update bulk_whatsapp_message.py
-   [x] Update JavaScript files
-   [x] Delete template_utils.py
-   [x] Update README.md
-   [x] Update docs/index.html
-   [x] Update pyproject.toml
-   [x] Remove all Facebook API references
-   [x] Remove all template references

## Testing Recommendations

1. **WAHA Setup**: Ensure WAHA server is running and WhatsApp account is connected
2. **Configuration**: Verify all WAHA settings in WhatsApp Settings doctype
3. **Webhook**: Test HMAC authentication with webhook endpoint
4. **Messages**: Send test messages of each type (text, image, video, etc.)
5. **Notifications**: Test automated notifications on doctype events
6. **Bulk Messages**: Test bulk messaging with variable replacement
7. **Incoming**: Verify incoming message handling via webhook

## Benefits of WAHA Migration

1. **No Template Approval**: Send any message without Meta approval
2. **Simpler Setup**: No Meta Business account required
3. **Better Control**: Self-hosted WAHA server gives full control
4. **HMAC Security**: More secure webhook authentication
5. **Flexibility**: Direct messaging without template constraints
6. **Open Source**: WAHA is open source and actively maintained
