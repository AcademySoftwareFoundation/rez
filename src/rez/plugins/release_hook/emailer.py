from rez.release_hook import ReleaseHook
from rez import plugin_factory
from rez.resources import load_package_metadata, load_package_settings
from email.mime.text import MIMEText
import smtplib
import sys



class EmailReleaseHook(ReleaseHook):
    @classmethod
    def name(cls):
        return "emailer"

    def __init__(self, source_path):
        super(EmailReleaseHook,self).__init__(source_path)
        metadata,_ = load_package_metadata(source_path)
        self.settings = load_package_settings(metadata)

    def post_release(self, package, user, install_path, release_message=None,
                     changelog=None, previous_version=None, previous_revision=None):
        # construct email body
        body = []
        body.append("USER: %s" % user)
        body.append("PACKAGE: %s" % package)
        body.append("RELEASED TO: %s" % install_path)
        if previous_version:
            body.append("PREVIOUS VERSION: %s" % previous_version)
        if release_message:
            body.append("\nMESSAGE:\n%s" % release_message)
        body.append("\nCHANGELOG:\n%s" % '\n'.join(changelog))

        # send email
        subject = "[rez] [release] %s released %s" % (user, package)
        self.send_email(subject, '\n'.join(body))

    def send_email(self, subject, body):
        smtp_host = self.settings.release_email_smtp_host
        from_ = self.settings.release_email_from
        to_ = self.settings.release_email_to
        if not (smtp_host and from_ and to_):
            return

        print "Sending release email..."
        smtp_port = self.settings.release_email_smtp_port
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = from_
        msg["To"] = str(',').join(to_)

        try:
            s = smtplib.SMTP(smtp_host, smtp_port)
            s.sendmail(from_, to_, msg.as_string())
            print 'email(s) sent.'
        except Exception, e:
            print >> sys.stderr, "release email delivery failed: %s" % str(e)



class EmailReleaseHookFactory(plugin_factory.RezPluginFactory):
    def target_type(self):
        return EmailReleaseHook
