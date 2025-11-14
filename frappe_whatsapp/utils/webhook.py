"""Webhook for WAHA API."""
import frappe
import json
import requests
import hmac
import hashlib
from werkzeug.wrappers import Response
import frappe.utils


@frappe.whitelist(allow_guest=True)
def webhook():
	"""WAHA webhook handler."""
	if frappe.request.method == "GET":
		return Response("WAHA webhook endpoint", status=200)
	return post()


def verify_hmac():
	"""Verify HMAC signature from WAHA webhook."""
	settings = frappe.get_doc("WhatsApp Settings", "WhatsApp Settings")
	hmac_secret = settings.get_password("webhook_hmac_secret")
	
	if not hmac_secret:
		return True
	
	received_hmac = frappe.request.headers.get("X-Webhook-Hmac")
	if not received_hmac:
		frappe.throw("Missing HMAC signature", frappe.AuthenticationError)
	
	body = frappe.request.get_data()
	expected_hmac = hmac.new(
		hmac_secret.encode(),
		body,
		hashlib.sha512
	).hexdigest()
	
	if not hmac.compare_digest(received_hmac, expected_hmac):
		frappe.throw("Invalid HMAC signature", frappe.AuthenticationError)
	
	return True


def post():
	"""Handle POST webhook from WAHA."""
	verify_hmac()
	
	data = frappe.local.form_dict
	
	frappe.get_doc({
		"doctype": "WhatsApp Notification Log",
		"template": "Webhook",
		"meta_data": json.dumps(data)
	}).insert(ignore_permissions=True)
	
	event = data.get("event")
	payload = data.get("payload", {})
	session = data.get("session")
	
	if event == "message":
		handle_message(payload, session)
	elif event == "message.any":
		handle_message(payload, session)
	elif event == "message.reaction":
		handle_reaction(payload, session)
	elif event == "message.ack":
		handle_message_ack(payload, session)
	elif event == "message.revoked":
		handle_message_revoked(payload, session)
	elif event == "session.status":
		handle_session_status(payload, session)
	
	return Response("OK", status=200)


def handle_message(message, session):
	"""Handle incoming message event."""
	if message.get("fromMe"):
		return
	
	message_type = get_message_type(message)
	message_body = get_message_body(message, message_type)
	
	is_reply = bool(message.get("replyTo"))
	reply_to_message_id = message.get("replyTo")
	
	from_number = message.get("from", "")
	if from_number.endswith("@c.us"):
		from_number = from_number.replace("@c.us", "")
	
	message_doc = frappe.get_doc({
		"doctype": "WhatsApp Message",
		"type": "Incoming",
		"from": from_number,
		"message": message_body,
		"message_id": message.get("id"),
		"reply_to_message_id": reply_to_message_id,
		"is_reply": is_reply,
		"content_type": message_type,
		"profile_name": message.get("_data", {}).get("notifyName", "")
	})
	
	try:
		if message_type in ["image", "audio", "video", "document"]:
			handle_media_message(message, message_doc, message_type)
		else:
			message_doc.insert(ignore_permissions=True)
			if should_send_read_receipt():
				message_doc.send_read_receipt()
	except Exception as e:
		frappe.log_error(
			"WhatsApp Message Insert Failed",
			f"Error inserting WhatsApp Message from {from_number}: {str(e)}\n\nTraceback:\n{frappe.get_traceback()}\n\nMessage Data: {json.dumps(message, indent=2)}"
		)


def get_message_type(message):
	"""Determine message type from WAHA message payload."""
	if message.get("body"):
		return "text"
	elif message.get("_data", {}).get("type") == "image":
		return "image"
	elif message.get("_data", {}).get("type") == "video":
		return "video"
	elif message.get("_data", {}).get("type") == "audio" or message.get("_data", {}).get("type") == "ptt":
		return "audio"
	elif message.get("_data", {}).get("type") == "document":
		return "document"
	elif message.get("reaction"):
		return "reaction"
	elif message.get("location"):
		return "location"
	elif message.get("vCards"):
		return "contact"
	
	return "text"


def get_message_body(message, message_type):
	"""Extract message body based on type."""
	if message_type == "text":
		return message.get("body", "")
	elif message_type == "reaction":
		return message.get("reaction", {}).get("text", "")
	elif message_type == "location":
		location = message.get("location", {})
		return json.dumps(location)
	elif message_type == "contact":
		return json.dumps(message.get("vCards", []))
	elif message_type in ["image", "video", "document", "audio"]:
		return message.get("caption", "")
	
	return ""


def handle_media_message(message, message_doc, message_type):
	"""Download and attach media from WAHA message."""
	media_url = message.get("media", {}).get("url")
	
	if not media_url:
		message_doc.insert(ignore_permissions=True)
		return
	
	settings = frappe.get_doc("WhatsApp Settings", "WhatsApp Settings")
	api_key = settings.get_password("api_key")
	
	headers = {}
	if api_key:
		headers["X-Api-Key"] = api_key
	
	try:
		response = requests.get(media_url, headers=headers, timeout=30)
		response.raise_for_status()
		
		file_data = response.content
		mime_type = message.get("media", {}).get("mimetype", "")
		
		file_extension = get_file_extension(mime_type, message_type)
		file_name = f"{frappe.generate_hash(length=10)}.{file_extension}"
		
		message_doc.insert(ignore_permissions=True)
		
		file_doc = frappe.get_doc({
			"doctype": "File",
			"file_name": file_name,
			"attached_to_doctype": "WhatsApp Message",
			"attached_to_name": message_doc.name,
			"content": file_data,
			"attached_to_field": "attach"
		}).save(ignore_permissions=True)
		
		message_doc.attach = file_doc.file_url
		message_doc.message = message_doc.message or f"/files/{file_name}"
		message_doc.save()
		
		if should_send_read_receipt():
			message_doc.send_read_receipt()
	
	except Exception as e:
		frappe.log_error("WAHA Media Download Error", str(e))
		message_doc.insert(ignore_permissions=True)


def get_file_extension(mime_type, message_type):
	"""Get file extension from mime type."""
	mime_map = {
		"image/jpeg": "jpg",
		"image/jpg": "jpg",
		"image/png": "png",
		"image/webp": "webp",
		"video/mp4": "mp4",
		"audio/ogg": "ogg",
		"audio/mpeg": "mp3",
		"application/pdf": "pdf",
		"application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
		"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
	}
	
	extension = mime_map.get(mime_type)
	if extension:
		return extension
	
	if "/" in mime_type:
		return mime_type.split("/")[1].split(";")[0]
	
	type_map = {
		"image": "jpg",
		"video": "mp4",
		"audio": "ogg",
		"document": "pdf"
	}
	return type_map.get(message_type, "bin")


def handle_reaction(payload, session):
	"""Handle reaction event."""
	reaction = payload.get("reaction", {})
	from_number = payload.get("from", "").replace("@c.us", "")
	
	frappe.get_doc({
		"doctype": "WhatsApp Message",
		"type": "Incoming",
		"from": from_number,
		"message": reaction.get("text", ""),
		"reply_to_message_id": reaction.get("messageId"),
		"message_id": payload.get("id"),
		"content_type": "reaction"
	}).insert(ignore_permissions=True)


def handle_message_ack(payload, session):
	"""Update message status based on ack."""
	message_id = payload.get("id")
	ack = payload.get("ack")
	ack_name = payload.get("ackName")
	
	if message_id:
		messages = frappe.get_all(
			"WhatsApp Message",
			filters={"message_id": message_id},
			limit=1
		)
		
		if messages:
			message_doc = frappe.get_doc("WhatsApp Message", messages[0].name)
			message_doc.status = ack_name or f"ACK {ack}"
			message_doc.save(ignore_permissions=True)


def handle_message_revoked(payload, session):
	"""Handle message revoked event."""
	revoked_message_id = payload.get("revokedMessageId")
	
	if revoked_message_id:
		messages = frappe.get_all(
			"WhatsApp Message",
			filters={"message_id": revoked_message_id},
			limit=1
		)
		
		if messages:
			message_doc = frappe.get_doc("WhatsApp Message", messages[0].name)
			message_doc.status = "Revoked"
			message_doc.message = "[Message deleted]"
			message_doc.save(ignore_permissions=True)


def handle_session_status(payload, session):
	"""Log session status changes."""
	status = payload.get("status")
	frappe.log_error("WAHA Session Status", f"Session {session}: {status}")


def should_send_read_receipt():
	"""Check if auto read receipt is enabled."""
	settings = frappe.get_doc("WhatsApp Settings", "WhatsApp Settings")
	return settings.allow_auto_read_receipt