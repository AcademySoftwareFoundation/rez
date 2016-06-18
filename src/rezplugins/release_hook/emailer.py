"""
Sends a post-release email
"""
from rez.release_hook import ReleaseHook
from rez.system import system
from email.mime.text import MIMEText
from rez.utils.logging_ import print_warning
from rez.utils.scope import scoped_formatter
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

    def post_release(self, user, install_path, variants, release_message=None,
                     changelog=None, previous_version=None, **kwargs):
        if not variants:
            return  # nothing was released

        # construct email body
        release_dict = dict(path=install_path,
                            previous_version=previous_version or "None.",
                            message=release_message or "No release message.",
                            changelog=changelog or "No changelog.")

        paths_str = '\n'.join(x.root for x in variants)
        variants_dict = dict(count=len(variants),
                             paths=paths_str)

        formatter = scoped_formatter(release=release_dict,
                                     variants=variants_dict,
                                     system=system,
                                     package=self.package)

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


# Copyright 2013-2016 Allan Johns.
#
# This library is free software: you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation, either
# version 3 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library.  If not, see <http://www.gnu.org/licenses/>.
