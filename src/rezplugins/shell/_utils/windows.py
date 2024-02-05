# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


import os
import re
import subprocess
from rez.utils.execution import Popen


def get_syspaths_from_registry():

    def gen_expected_regex(parts):
        whitespace = r"[\s]+"
        return whitespace.join(parts)

    entries = (
        # local machine
        dict(
            cmd=[
                "REG",
                "QUERY",
                "HKLM\\SYSTEM\\CurrentControlSet\\Control\\Session Manager\\Environment",
                "/v",
                "PATH"
            ],
            expected=gen_expected_regex([
                "HKEY_LOCAL_MACHINE\\\\SYSTEM\\\\CurrentControlSet\\\\Control\\\\Session Manager\\\\Environment",
                "PATH",
                "REG_(EXPAND_)?SZ",
                "(.*)"
            ])
        ),
        # current user
        dict(
            cmd=[
                "REG",
                "QUERY",
                "HKCU\\Environment",
                "/v",
                "PATH"
            ],
            expected=gen_expected_regex([
                "HKEY_CURRENT_USER\\\\Environment",
                "PATH",
                "REG_(EXPAND_)?SZ",
                "(.*)"
            ])
        )
    )

    paths = []

    for entry in entries:
        p = Popen(
            entry["cmd"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=True,
            text=True
        )

        out_, _ = p.communicate()
        out_ = out_.strip()

        if p.returncode == 0:
            match = re.match(entry["expected"], out_)
            if match:
                paths.extend(match.group(2).split(os.pathsep))

    return [x for x in paths if x]
