$(document).on("app_ready", function () {
    frappe.router.on("change", () => {
        var route = frappe.get_route()
        if (route && route[0] == "Form") {
            frappe.ui.form.on(route[1], {
                refresh: function (frm) {
                    frm.page.add_menu_item(__("Send To WhatsApp"), function () {
                        var user_name = frappe.user.name
                        var user_full_name = frappe.session.user_fullname
                        var reference_doctype = frm.doctype
                        var reference_name = frm.docname
                        var dialog = new frappe.ui.Dialog({
                            fields: [
                                { fieldname: "ht", fieldtype: "HTML" },
                                {
                                    label: "Send to",
                                    fieldname: "contact",
                                    reqd: 1,
                                    fieldtype: "Link",
                                    options: "Contact",
                                    change() {
                                        let contact_name = dialog.get_value("contact")
                                        if (contact_name) {
                                            frappe.call({
                                                method: "frappe.client.get_value",
                                                args: {
                                                    doctype: "Contact",
                                                    filters: { name: contact_name },
                                                    fieldname: ["mobile_no"],
                                                },
                                                callback: function (r) {
                                                    if (r.message) {
                                                        dialog.set_value("mobile_no", r.message.mobile_no)
                                                    } else {
                                                        dialog.set_value("mobile_no", "")
                                                        frappe.msgprint("Mobile number not found for the selected contact.")
                                                    }
                                                },
                                            })
                                        } else {
                                            dialog.set_value("mobile_no", "")
                                        }
                                    },
                                },
                                { label: "Mobile no", fieldname: "mobile_no", fieldtype: "Data", reqd: 1 },
                                { label: "Message", fieldname: "message", fieldtype: "Small Text", reqd: 1 },
                                { label: "Content Type", fieldname: "content_type", fieldtype: "Select", options: "text\nimage\nvideo\ndocument\naudio", default: "text" },
                                { label: "Attachment", fieldname: "attach", fieldtype: "Attach" },
                            ],
                            primary_action_label: "Send",
                            title: "Send a WhatsApp Message",
                            primary_action: function () {
                                var values = dialog.get_values()
                                if (values) {
                                    frappe.call({
                                        method: "frappe_whatsapp.frappe_whatsapp.doctype.whatsapp_message.whatsapp_message.send_message",
                                        args: {
                                            to: values.mobile_no,
                                            message: values.message,
                                            content_type: values.content_type || "text",
                                            attach: values.attach,
                                            reference_doctype: frm.doc.doctype,
                                            reference_name: frm.doc.name,
                                        },
                                        freeze: true,
                                        callback: (r) => {
                                            frappe.msgprint(__("Successfully Sent to: " + values.mobile_no))
                                            dialog.hide()
                                        },
                                        error: (r) => {
                                            frappe.msgprint(__("Failed to send message. Check the error log."))
                                        },
                                    })

                                    var comment_message = "To : " + values.mobile_no + "\n\nWhatsApp Message: " + values.message
                                    frappe.call({
                                        method: "frappe.desk.form.utils.add_comment",
                                        args: {
                                            reference_doctype: reference_doctype,
                                            reference_name: reference_name,
                                            content: comment_message,
                                            comment_by: frappe.session.user_fullname,
                                            comment_email: frappe.session.user,
                                        },
                                    })
                                }
                            },
                            no_submit_on_enter: true,
                        })
                        dialog.show()
                    })
                },
            })
        }
    })
})
