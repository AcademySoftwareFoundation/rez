
import re

class AnimalLogicGitReleaseVCSMixin(object):

    def get_releaselog(self, previous_revision=None):
        releaselog = []
        prev_commit = (previous_revision or {}).get("commit")

        if prev_commit:
            hashes = self.git("log", "%s.." % prev_commit, "--no-merges", "--reverse",  "--pretty=%H", ".")

            for hash_ in hashes:
                log = self.git("log", hash_, "--no-merges", "-1", "--pretty=format:%an: %s")

                author = self._get_author_from_log(log[0])
                message = self._get_release_message_from_log(log[0])

                if message:
                    releaselog.append("%s: %s" % (author, message))

            return releaselog

        else:
            return releaselog

    def _get_release_message_from_log(self, log):
        """
        Extract the release message from a single commit log string.  This 
        assumes that the incoming log represents a single commit and is 
        formatted to match the regular expression which is currently:
        
            Firstname Lastname: commit log message <release>release message</release>
        """

        return "\n".join(re.findall("(?s)<release>(.*?)</release>", log))

    def _get_author_from_log(self, log):
        """
        Extract the author from a single commit log string.  This assumes that  
        the incoming log represents a single commit and is formatted to match
        the regular expression which is currently:
        
            Firstname Lastname: commit log message
        """

        return re.search('^(.*?): ', log).group(1)

    def commit(add=True, message="Auto Commit from Rez Git VCS plugin."):
        """
        """

        self.git("commit", "-a" if add else "", "-m", message)

