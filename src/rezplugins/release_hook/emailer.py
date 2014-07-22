"""
Sends a post-release email
"""
from rez.release_hook import ReleaseHook
from email.mime.text import MIMEText
from rez.util import print_warning
import smtplib
import sys


class EmailReleaseHook(ReleaseHook):

    schema_dict = {
        "smtp_host":        basestring,
        "smtp_port":        int,
        "sender":           basestring,
        "recipients":       [basestring]}

    @classmethod
    def name(cls):
        return "emailer"

    def __init__(self, source_path):
        super(EmailReleaseHook, self).__init__(source_path)

    def post_release(self, user, install_path, release_message=None,
                     changelog=None, previous_version=None,
                     previous_revision=None):
        # construct email body
        body = []
        body.append("USER: %s" % user)
        body.append("PACKAGE: %s" % self.package.qualified_name)
        body.append("RELEASED TO: %s" % install_path)
        if previous_version:
            body.append("PREVIOUS VERSION: %s" % previous_version)
        if release_message:
            body.append("\nMESSAGE:\n%s" % release_message)
        body.append("\nCHANGELOG:\n%s" % changelog)

        # send email
        subject = "[rez] [release] %s released %s" \
            % (user, self.package.qualified_name)
        self.send_email(subject, '\n'.join(body))

    def send_email(self, subject, body):
        if not self.settings.recipients:
            return  # nothing to do, sending email to nobody
        if not self.settings.smtp_host:
            print_warning("did not send release email: "
                          "SMTP host is not specified")
            return

        print "Sending release email..."
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = self.settings.sender
        msg["To"] = str(',').join(self.settings.recipients)

        try:
            s = smtplib.SMTP(self.settings.smtp_host, self.settings.smtp_port)
            s.sendmail(from_addr=self.settings.sender,
                       to_addrs=self.settings.recipients,
                       msg=msg.as_string())
            print 'email(s) sent.'
        except Exception, e:
            print >> sys.stderr, "release email delivery failed: %s" % str(e)


def register_plugin():
    return EmailReleaseHook
