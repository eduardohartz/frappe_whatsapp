# Copyright (c) 2022, Shridhar Patil and contributors
# For license information, please see license.txt
import json
import frappe
from frappe.model.document import Document
import requests


class WhatsAppMessage(Document):
    """Send WhatsApp messages using WAHA API."""

    def before_insert(self):
        """Send message."""
        if self.type == "Outgoing":
            if self.attach and not self.attach.startswith("http"):
                link = frappe.utils.get_url() + "/" + self.attach
            else:
                link = self.attach

            data = {
                "session": self.get_session_name(),
                "chatId": self.format_number(self.to),
            }
            
            if self.is_reply and self.reply_to_message_id:
                data["reply_to"] = self.reply_to_message_id
            
            if self.content_type == "text":
                data["text"] = self.message
                self.send_text(data)
            elif self.content_type == "image":
                data["file"] = {
                    "mimetype": "image/jpeg",
                    "url": link,
                    "filename": "image.jpeg"
                }
                if self.message:
                    data["caption"] = self.message
                self.send_image(data)
            elif self.content_type == "video":
                data["file"] = {
                    "mimetype": "video/mp4",
                    "url": link,
                    "filename": "video.mp4"
                }
                if self.message:
                    data["caption"] = self.message
                self.send_video(data)
            elif self.content_type == "audio":
                data["file"] = {
                    "mimetype": "audio/ogg; codecs=opus",
                    "url": link
                }
                self.send_voice(data)
            elif self.content_type == "document":
                data["file"] = {
                    "url": link,
                    "filename": "document.pdf"
                }
                if self.message:
                    data["caption"] = self.message
                self.send_file(data)
            elif self.content_type == "reaction":
                data["messageId"] = self.reply_to_message_id
                data["reaction"] = self.message
                self.send_reaction(data)
            elif self.content_type == "location":
                location_data = json.loads(self.message) if isinstance(self.message, str) else self.message
                data["latitude"] = location_data.get("latitude")
                data["longitude"] = location_data.get("longitude")
                data["title"] = location_data.get("title", "")
                self.send_location(data)
            elif self.content_type == "contact":
                contact_data = json.loads(self.message) if isinstance(self.message, str) else self.message
                data["contacts"] = contact_data if isinstance(contact_data, list) else [contact_data]
                self.send_contact(data)

    def send_text(self, data):
        """Send text message."""
        try:
            response = self.make_waha_request("/api/sendText", data)
            if response and response.get("id"):
                self.message_id = response["id"]
            self.status = "Success"
        except Exception as e:
            self.status = "Failed"
            frappe.throw(f"Failed to send message: {str(e)}")

    def send_image(self, data):
        """Send image message."""
        try:
            response = self.make_waha_request("/api/sendImage", data)
            if response and response.get("id"):
                self.message_id = response["id"]
            self.status = "Success"
        except Exception as e:
            self.status = "Failed"
            frappe.throw(f"Failed to send image: {str(e)}")

    def send_video(self, data):
        """Send video message."""
        try:
            response = self.make_waha_request("/api/sendVideo", data)
            if response and response.get("id"):
                self.message_id = response["id"]
            self.status = "Success"
        except Exception as e:
            self.status = "Failed"
            frappe.throw(f"Failed to send video: {str(e)}")

    def send_voice(self, data):
        """Send voice message."""
        try:
            response = self.make_waha_request("/api/sendVoice", data)
            if response and response.get("id"):
                self.message_id = response["id"]
            self.status = "Success"
        except Exception as e:
            self.status = "Failed"
            frappe.throw(f"Failed to send voice: {str(e)}")

    def send_file(self, data):
        """Send file message."""
        try:
            response = self.make_waha_request("/api/sendFile", data)
            if response and response.get("id"):
                self.message_id = response["id"]
            self.status = "Success"
        except Exception as e:
            self.status = "Failed"
            frappe.throw(f"Failed to send file: {str(e)}")

    def send_reaction(self, data):
        """Send reaction to a message."""
        try:
            response = self.make_waha_request("/api/reaction", data, method="PUT")
            self.status = "Success"
        except Exception as e:
            self.status = "Failed"
            frappe.throw(f"Failed to send reaction: {str(e)}")

    def send_location(self, data):
        """Send location message."""
        try:
            response = self.make_waha_request("/api/sendLocation", data)
            if response and response.get("id"):
                self.message_id = response["id"]
            self.status = "Success"
        except Exception as e:
            self.status = "Failed"
            frappe.throw(f"Failed to send location: {str(e)}")

    def send_contact(self, data):
        """Send contact vcard."""
        try:
            response = self.make_waha_request("/api/sendContactVcard", data)
            if response and response.get("id"):
                self.message_id = response["id"]
            self.status = "Success"
        except Exception as e:
            self.status = "Failed"
            frappe.throw(f"Failed to send contact: {str(e)}")

    def make_waha_request(self, endpoint, data, method="POST"):
        """Make request to WAHA API."""
        settings = frappe.get_doc("WhatsApp Settings", "WhatsApp Settings")
        
        if not settings.waha_url:
            frappe.throw("WAHA URL not configured in WhatsApp Settings")
        
        api_key = settings.get_password("api_key")
        url = f"{settings.waha_url.rstrip('/')}{endpoint}"
        
        headers = {
            "Content-Type": "application/json"
        }
        
        if api_key:
            headers["X-Api-Key"] = api_key
        
        try:
            if method == "POST":
                response = requests.post(url, headers=headers, json=data, timeout=30)
            elif method == "PUT":
                response = requests.put(url, headers=headers, json=data, timeout=30)
            
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            error_msg = str(e)
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_data = e.response.json()
                    error_msg = error_data.get("message", error_msg)
                except:
                    error_msg = e.response.text or error_msg
            
            frappe.get_doc({
                "doctype": "WhatsApp Notification Log",
                "template": "Text Message",
                "meta_data": json.dumps({"error": error_msg, "data": data})
            }).insert(ignore_permissions=True)
            
            raise Exception(error_msg)

    def format_number(self, number):
        """Format number to WAHA chatId format (add @c.us suffix)."""
        if number.startswith("+"):
            number = number[1:]
        
        number = number.replace(" ", "").replace("-", "")
        
        if not number.endswith("@c.us") and not number.endswith("@g.us"):
            number = f"{number}@c.us"
        
        return number

    def get_session_name(self):
        """Get session name from settings."""
        settings = frappe.get_doc("WhatsApp Settings", "WhatsApp Settings")
        return settings.session_name or "default"

    @frappe.whitelist()
    def send_read_receipt(self):
        """Mark message as seen/read."""
        if not self.message_id:
            frappe.throw("Message ID is required to send read receipt")
        
        data = {
            "session": self.get_session_name(),
            "chatId": self.format_number(self.get("from") or self.to)
        }
        
        try:
            response = self.make_waha_request("/api/sendSeen", data)
            self.status = "marked as read"
            self.save()
            return True
        except Exception as e:
            frappe.log_error("WhatsApp API Error", f"Failed to send read receipt: {str(e)}")
            return False


def on_doctype_update():
    frappe.db.add_index("WhatsApp Message", ["reference_doctype", "reference_name"])


@frappe.whitelist()
def send_message(to, message, content_type="text", attach=None, reference_doctype=None, reference_name=None):
    """Helper function to send WhatsApp message."""
    try:
        doc = frappe.get_doc({
            "doctype": "WhatsApp Message",
            "to": to,
            "type": "Outgoing",
            "message_type": "Manual",
            "message": message,
            "content_type": content_type,
            "attach": attach,
            "reference_doctype": reference_doctype,
            "reference_name": reference_name
        })
        doc.save()
        return doc
    except Exception as e:
        frappe.log_error("WhatsApp Send Message Error", str(e))
        raise e
