# todo rewrite svn/git rez-release and move reused code into this file

import os
import sys
import smtplib
from email.mime.text import MIMEText


def send_release_email(subject, body):
    from_ = os.getenv("REZ_RELEASE_EMAIL_FROM", "rez")
    to_ = os.getenv("REZ_RELEASE_EMAIL_TO")
    if not to_:
        return
    recipients = to_.replace(':',' ').replace(';',' ').replace(',',' ')
    recipients = recipients.strip().split()
    if not recipients:
        return

    print
    print("---------------------------------------------------------")
    print("rez-release: sending notification emails...")
    print("---------------------------------------------------------")
    print
    print "sending to:\n%s" % str('\n').join(recipients)

    smtphost = os.getenv("REZ_RELEASE_EMAIL_SMTP_HOST", "localhost")
    smtpport = os.getenv("REZ_RELEASE_EMAIL_SMTP_PORT")

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = from_
    msg["To"] = str(',').join(recipients)

    try:
        s = smtplib.SMTP(smtphost, smtpport)
        s.sendmail(from_, recipients, msg.as_string())
        print 'email(s) sent.'
    except Exception as e:
        print  >> sys.stderr, "Emailing failed: %s" % str(e)
