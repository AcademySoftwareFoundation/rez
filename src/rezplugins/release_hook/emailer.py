"""
Sends a post-release email
"""
from rez.release_hook import ReleaseHook
from rez.system import system
from email.mime.text import MIMEText
from rez.util import AttrDictWrapper
from rez.utils.logging_ import print_warning
from rez.utils.data_utils import ObjectStringFormatter
import smtplib
import sys


class EmailReleaseHook(ReleaseHook):

    schema_dict = {
        "subject":          basestring,
        "body":             basestring,
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
        release_dict = dict(path=install_path,
                            previous_version=previous_version or "None.",
                            message=release_message or "No release message.",
                            changelog=changelog or "No changelog.")
        release_namespace = AttrDictWrapper(release_dict)
        namespace = dict(release=release_namespace,
                         system=system,
                         package=self.package)

        formatter = ObjectStringFormatter(namespace, pretty=True,
                                          expand=ObjectStringFormatter.empty)
        body = formatter.format(self.settings.body)
        body = body.strip()
        body = body.replace("\n\n\n", "\n\n")

        # construct subject line, send email
        subject = formatter.format(self.settings.subject)
        self.send_email(subject, body)

    def send_email(self, subject, body):
        if not self.settings.recipients:
            return  # nothing to do, sending email to nobody
        if not self.settings.smtp_host:
            print_warning("did not send release email: "
                          "SMTP host is not specified")
            return

        print "Sending release email to:"
        print '\n'.join("- %s" % x for x in self.settings.recipients)

        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = self.settings.sender
        msg["To"] = str(',').join(self.settings.recipients)

        try:
            s = smtplib.SMTP(self.settings.smtp_host, self.settings.smtp_port)
            s.sendmail(from_addr=self.settings.sender,
                       to_addrs=self.settings.recipients,
                       msg=msg.as_string())
            print 'Email(s) sent.'
        except Exception, e:
            print >> sys.stderr, "release email delivery failed: %s" % str(e)


def register_plugin():
    return EmailReleaseHook
