"""Notification."""

import json
import frappe
import datetime

from frappe import _dict, _
from frappe.model.document import Document
from frappe.utils.safe_exec import get_safe_globals, safe_exec
from frappe.desk.form.utils import get_pdf_link
from frappe.utils import add_to_date, nowdate
import requests


class WhatsAppNotification(Document):
    """Notification."""

    def validate(self):
        """Validate."""
        if self.notification_type == "DocType Event":
            fields = frappe.get_doc("DocType", self.reference_doctype).fields
            fields += frappe.get_all(
                "Custom Field",
                filters={"dt": self.reference_doctype},
                fields=["fieldname"]
            )
            if not any(field.fieldname == self.field_name for field in fields):
                frappe.throw(_("Field name {0} does not exists").format(self.field_name))
        
        if self.custom_attachment:
            if not self.attach and not self.attach_from_field:
                frappe.throw(_("Either {0} a file or add a {1} to send attachment").format(
                    frappe.bold(_("Attach")),
                    frappe.bold(_("Attach from field")),
                ))

        if self.set_property_after_alert:
            meta = frappe.get_meta(self.reference_doctype)
            if not meta.get_field(self.set_property_after_alert):
                frappe.throw(_("Field {0} not found on DocType {1}").format(
                    self.set_property_after_alert,
                    self.reference_doctype,
                ))


    def send_scheduled_message(self) -> dict:
        """Specific to API endpoint Server Scripts."""
        safe_exec(
            self.condition, get_safe_globals(), dict(doc=self)
        )

        if self.get("_contact_list"):
            for contact in self._contact_list:
                self.send_simple_message(contact, None)
        elif self.get("_data_list"):
            for data in self._data_list:
                doc = frappe.get_doc(self.reference_doctype, data.get("name"))
                self.send_notification_message(doc, data.get("phone_no"), True)


    def send_simple_message(self, phone_no, message=None):
        """Send simple text message without a doc."""
        msg = message or self.message
        
        if not msg:
            frappe.throw(_("Message content is required"))
        
        data = {
            "session": self.get_session_name(),
            "chatId": self.format_number(phone_no),
            "text": msg
        }
        
        self.notify_waha(data, "/api/sendText")


    def send_notification_message(self, doc: Document, phone_no=None, ignore_condition=False):
        """Specific to Document Event triggered Server Scripts."""
        if self.disabled:
            return

        doc_data = doc.as_dict()
        if self.condition and not ignore_condition:
            if not frappe.safe_eval(
                self.condition, get_safe_globals(), dict(doc=doc_data)
            ):
                return

        if self.field_name:
            phone_number = phone_no or doc_data[self.field_name]
        else:
            phone_number = phone_no

        if not phone_number:
            return

        message_text = self.message
        
        if self.fields:
            for field in self.fields:
                if isinstance(doc, Document):
                    value = doc.get_formatted(field.field_name)
                else:
                    value = doc_data[field.field_name]
                    if isinstance(doc_data[field.field_name], (datetime.date, datetime.datetime)):
                        value = str(doc_data[field.field_name])
                
                message_text = message_text.replace(f"{{{{{field.field_name}}}}}", str(value))

        data = {
            "session": self.get_session_name(),
            "chatId": self.format_number(phone_number),
        }

        if self.attach_document_print or self.custom_attachment:
            file_url = self.get_attachment_url(doc, doc_data)
            
            if self.attach_document_print:
                data["file"] = {
                    "url": file_url,
                    "filename": f'{doc_data["name"]}.pdf'
                }
                if message_text:
                    data["caption"] = message_text
                self.notify_waha(data, "/api/sendFile", doc_data)
            elif self.custom_attachment:
                mimetype = self.get_mimetype_from_url(file_url)
                
                if mimetype.startswith("image/"):
                    data["file"] = {
                        "url": file_url,
                        "mimetype": mimetype,
                        "filename": self.file_name or "image.jpg"
                    }
                    if message_text:
                        data["caption"] = message_text
                    self.notify_waha(data, "/api/sendImage", doc_data)
                elif mimetype.startswith("video/"):
                    data["file"] = {
                        "url": file_url,
                        "mimetype": mimetype,
                        "filename": self.file_name or "video.mp4"
                    }
                    if message_text:
                        data["caption"] = message_text
                    self.notify_waha(data, "/api/sendVideo", doc_data)
                else:
                    data["file"] = {
                        "url": file_url,
                        "filename": self.file_name or "document.pdf"
                    }
                    if message_text:
                        data["caption"] = message_text
                    self.notify_waha(data, "/api/sendFile", doc_data)
        else:
            data["text"] = message_text
            self.notify_waha(data, "/api/sendText", doc_data)


    def get_attachment_url(self, doc, doc_data):
        """Get attachment URL."""
        if self.attach_document_print:
            key = doc.get_document_share_key()
            frappe.db.commit()
            print_format = "Standard"
            doctype = frappe.get_doc("DocType", doc_data['doctype'])
            if doctype.custom:
                if doctype.default_print_format:
                    print_format = doctype.default_print_format
            else:
                default_print_format = frappe.db.get_value(
                    "Property Setter",
                    filters={
                        "doc_type": doc_data['doctype'],
                        "property": "default_print_format"
                    },
                    fieldname="value"
                )
                print_format = default_print_format if default_print_format else print_format
            
            link = get_pdf_link(
                doc_data['doctype'],
                doc_data['name'],
                print_format=print_format
            )
            return f'{frappe.utils.get_url()}{link}&key={key}'
        
        elif self.custom_attachment:
            if self.attach_from_field:
                file_url = doc_data[self.attach_from_field]
                if not file_url.startswith("http"):
                    key = doc.get_document_share_key()
                    file_url = f'{frappe.utils.get_url()}{file_url}&key={key}'
                return file_url
            else:
                if self.attach.startswith("http"):
                    return self.attach
                else:
                    return f'{frappe.utils.get_url()}{self.attach}'
        
        return None


    def get_mimetype_from_url(self, url):
        """Determine mimetype from file extension."""
        ext = url.split('.')[-1].lower()
        mime_map = {
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg',
            'png': 'image/png',
            'gif': 'image/gif',
            'webp': 'image/webp',
            'mp4': 'video/mp4',
            'pdf': 'application/pdf',
            'doc': 'application/msword',
            'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'xls': 'application/vnd.ms-excel',
            'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        }
        return mime_map.get(ext, 'application/octet-stream')


    def notify_waha(self, data, endpoint, doc_data=None):
        """Send notification via WAHA API."""
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
            success = False
            response = requests.post(url, headers=headers, json=data, timeout=30)
            response.raise_for_status()
            response_data = response.json()

            new_doc = {
                "doctype": "WhatsApp Message",
                "type": "Outgoing",
                "message": data.get("text") or data.get("caption", ""),
                "to": data["chatId"].replace("@c.us", ""),
                "message_type": "Manual",
                "message_id": response_data.get("id"),
                "content_type": self.get_content_type(endpoint),
            }

            if doc_data:
                new_doc.update({
                    "reference_doctype": doc_data.doctype,
                    "reference_name": doc_data.name,
                })

            frappe.get_doc(new_doc).save(ignore_permissions=True)

            if doc_data and self.set_property_after_alert and self.property_value:
                if doc_data.doctype and doc_data.name:
                    fieldname = self.set_property_after_alert
                    value = self.property_value
                    meta = frappe.get_meta(doc_data.get("doctype"))
                    df = meta.get_field(fieldname)
                    if df:
                        if df.fieldtype in frappe.model.numeric_fieldtypes:
                            value = frappe.utils.cint(value)
                        frappe.db.set_value(doc_data.get("doctype"), doc_data.get("name"), fieldname, value)

            frappe.msgprint("WhatsApp Message Triggered", indicator="green", alert=True)
            success = True

        except Exception as e:
            error_message = str(e)
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_data = e.response.json()
                    error_message = error_data.get("message", error_message)
                except:
                    error_message = e.response.text or error_message

            frappe.msgprint(
                f"Failed to trigger WhatsApp message: {error_message}",
                indicator="red",
                alert=True
            )
        finally:
            if not success:
                meta = {"error": error_message}
            else:
                meta = response_data
            
            frappe.get_doc({
                "doctype": "WhatsApp Notification Log",
                "template": "Notification",
                "meta_data": json.dumps(meta)
            }).insert(ignore_permissions=True)


    def get_content_type(self, endpoint):
        """Get content type based on endpoint."""
        endpoint_map = {
            "/api/sendText": "text",
            "/api/sendImage": "image",
            "/api/sendVideo": "video",
            "/api/sendFile": "document",
            "/api/sendVoice": "audio",
        }
        return endpoint_map.get(endpoint, "text")


    def get_session_name(self):
        """Get session name from settings."""
        settings = frappe.get_doc("WhatsApp Settings", "WhatsApp Settings")
        return settings.session_name or "default"


    def on_trash(self):
        """On delete remove from schedule."""
        frappe.cache().delete_value("whatsapp_notification_map")


    def format_number(self, number):
        """Format number to WAHA chatId format."""
        if number.startswith("+"):
            number = number[1:]
        
        number = number.replace(" ", "").replace("-", "")
        
        if not number.endswith("@c.us") and not number.endswith("@g.us"):
            number = f"{number}@c.us"
        
        return number


    def get_documents_for_today(self):
        """Get list of documents that will be triggered today."""
        docs = []

        diff_days = self.days_in_advance
        if self.doctype_event == "Days After":
            diff_days = -diff_days

        reference_date = add_to_date(nowdate(), days=diff_days)
        reference_date_start = reference_date + " 00:00:00.000000"
        reference_date_end = reference_date + " 23:59:59.000000"

        doc_list = frappe.get_all(
            self.reference_doctype,
            fields="name",
            filters=[
                {self.date_changed: (">=", reference_date_start)},
                {self.date_changed: ("<=", reference_date_end)},
            ],
        )

        for d in doc_list:
            doc = frappe.get_doc(self.reference_doctype, d.name)
            self.send_notification_message(doc)


@frappe.whitelist()
def call_trigger_notifications():
    """Trigger notifications."""
    try:
        trigger_notifications()
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Error in call_trigger_notifications")
        raise e


def trigger_notifications(method="daily"):
    if frappe.flags.in_import or frappe.flags.in_patch:
        return

    if method == "daily":
        doc_list = frappe.get_all(
            "WhatsApp Notification", filters={"doctype_event": ("in", ("Days Before", "Days After")), "disabled": 0}
        )
        for d in doc_list:
            alert = frappe.get_doc("WhatsApp Notification", d.name)
            alert.get_documents_for_today()

