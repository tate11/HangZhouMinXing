# -*- coding: utf-8 -*-
from odoo import tools, models, fields, api
from odoo.exceptions import UserError
from odoo.tools.translate import _

class MailInbox(models.Model):
    _inherit = 'mail.inbox'

    shop_id = fields.Many2one('amazon.shop', default=lambda self: self._default_shop_id(),string=u'店铺')

    @api.model
    def _default_shop_id(self):
        return 

    @api.model
    def message_new(self, msg_dict, custom_values=None):
        self = self.with_context(default_user_id=False)
        mail_data = {
            'subject': msg_dict.get('subject') or _(u"无主题"),
            'email_from': msg_dict.get('from'),
            'email_to': msg_dict.get('to'),
            'email_cc': msg_dict.get('cc'),
            'partner_id': msg_dict.get('author_id', False),
            'body_html': msg_dict.get('body', ''),
            'attachment_ids': msg_dict.get('attachments', []),
            'state': 'inbox',
            # 'shop_id': 1,
        }
        result = self.create(mail_data)
        return result
