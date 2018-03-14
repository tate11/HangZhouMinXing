# -*- coding: utf-8 -*-
import logging
import poplib
from imaplib import IMAP4, IMAP4_SSL
from poplib import POP3, POP3_SSL
from odoo import api, fields, models, tools, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)
MAX_POP_MESSAGES = 50
MAIL_TIMEOUT = 60

# Workaround for Python 2.7.8 bug https://bugs.python.org/issue23906
poplib._MAXLINE = 65536

class vieterp_fetchmail_server(models.Model):
    _inherit = 'fetchmail.server'
    _name = 'fetchmail.server.inbox'

    @api.model
    def _def_object_id(self):
        model_obj = self.env['ir.model']
        model = model_obj.search([('model', '=', 'mail.inbox')], limit = 1)
        if model:
            return model[0].id
        return False

    source_id = fields.Many2one('mail.server.source', string=u'邮件来源')
    object_id = fields.Many2one('ir.model', string=u"创建新的记录", default=_def_object_id)

    @api.multi
    def fetch_mail(self):
        print 'fetch_mail'
        """ WARNING: meant for cron usage only - will commit() after each email! """
        additionnal_context = {
            'fetchmail_cron_running': True
        }
        MailThread = self.env['mail.thread']
        for server in self:
            _logger.info('start checking for new emails on %s server %s', server.type, server.name)
            additionnal_context['fetchmail_server_id'] = server.id
            additionnal_context['server_type'] = server.type
            count, failed = 0, 0
            imap_server = None
            pop_server = None
            if server.type == 'imap':
                print 'imap 协议'
                try:
                    imap_server = server.connect()
                    imap_server.select()
                    result, data = imap_server.search(None, '(UNSEEN)')
                    for num in data[0].split():
                        res_id = None
                        result, data = imap_server.fetch(num, '(RFC822)')
                        imap_server.store(num, '-FLAGS', '\\Seen')
                        try:
                            res_id = MailThread.with_context(**additionnal_context).message_process(
                                server.object_id.model, data[0][1], save_original=server.original,
                                strip_attachments=(not server.attach))
                        except Exception:
                            _logger.info('Failed to process mail from %s server %s.', server.type, server.name,
                                         exc_info=True)
                            failed += 1
                        if res_id and server.action_id:
                            server.action_id.with_context({
                                'active_id': res_id,
                                'active_ids': [res_id],
                                'active_model': self.env.context.get("thread_model", server.object_id.model)
                            }).run()
                        imap_server.store(num, '+FLAGS', '\\Seen')
                        self._cr.commit()
                        count += 1
                    _logger.info("Fetched %d email(s) on %s server %s; %d succeeded, %d failed.", count,
                                 server.type, server.name, (count - failed), failed)
                except Exception:
                    _logger.info("General failure when trying to fetch mail from %s server %s.", server.type,
                                 server.name, exc_info=True)
                finally:
                    if imap_server:
                        imap_server.close()
                        imap_server.logout()
            elif server.type == 'pop':
                print 'pop 协议'
                try:
                    while True:
                        pop_server = server.connect()
                        (num_messages, total_size) = pop_server.stat()
                        pop_server.list()
                        for num in range(1, min(MAX_POP_MESSAGES, num_messages) + 1):
                            (header, messages, octets) = pop_server.retr(num)
                            message = '\n'.join(messages)
                            # print 'message',message
                            res_id = None
                            try:
                                res_id = MailThread.with_context(**additionnal_context).message_process(
                                    server.object_id.model, message, save_original=server.original,
                                    strip_attachments=(not server.attach))
                                # pop_server.dele(num)
                            except Exception:
                                _logger.info('Failed to process mail from %s server %s.', server.type, server.name,
                                             exc_info=True)
                                failed += 1
                            if res_id and server.action_id:
                                server.action_id.with_context({
                                    'active_id': res_id,
                                    'active_ids': [res_id],
                                    'active_model': self.env.context.get("thread_model", server.object_id.model)
                                }).run()
                            self.env.cr.commit()
                        if num_messages < MAX_POP_MESSAGES:
                            break
                        pop_server.quit()
                        _logger.info("Fetched %d email(s) on %s server %s; %d succeeded, %d failed.", num_messages,
                                     server.type, server.name, (num_messages - failed), failed)
                except Exception:
                    _logger.info("General failure when trying to fetch mail from %s server %s.", server.type,
                                 server.name, exc_info=True)
                finally:
                    if pop_server:
                        pop_server.quit()
            server.write({'date': fields.Datetime.now()})
        return True

    @api.multi
    def connect(self):
        if self.source_id and self.source_id.id:
            self.ensure_one()
            if self.source_id.type == 'imap':
                if self.source_id.is_ssl:
                    connection = IMAP4_SSL(self.source_id.server, int(self.source_id.port))
                else:
                    connection = IMAP4(self.source_id.server, int(self.source_id.port))
                connection.login(self.user, self.password)
            elif self.type == 'pop':
                if self.source_id.is_ssl:
                    connection = POP3_SSL(self.source_id.server, int(self.source_id.port))
                else:
                    connection = POP3(self.source_id.server, int(self.source_id.port))
                # TODO: use this to remove only unread messages
                # connection.user("recent:"+server.user)
                connection.user(self.user)
                connection.pass_(self.password)
            # Add timeout on socket
            connection.sock.settimeout(MAIL_TIMEOUT)
            return connection
        return super(vieterp_fetchmail_server, self).connect()