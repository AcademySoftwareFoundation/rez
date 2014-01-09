"""
Utility functions for building an external package, ie a rez-install 'formula'.
"""
from __future__ import with_statement
from source_retrieval import get_source, SourceRetrieverError
from plugin_managers import source_retriever_plugin_manager
from rez.cli import error, output
from rez.util import render_template
import traceback
import os.path
import sys


# where pkg source is downloaded to by default
SOURCE_ROOT = 'src'


def get_source(metadata, dest_path=SOURCE_ROOT):
    def _get_urls(doc):
        urls = []
        if "urls" in doc:
            for d in doc["urls"]:
                urls += _get_urls(d)
        if "url" in doc:
            urls.append((doc.get("url"), doc.get("type"), doc.get("revision")))
        return urls

    build_data = metadata.get('external_build')
    if build_data:
        urls = _get_urls(build_data)
        cache_path = _get_cache_path(metadata)

        try:
            for url,src_type,rev in urls:
                try:
                    return get_source(url, dest_path,
                                      type=src_type,
                                      revision=rev,
                                      cache_path=cache_path)
                except Exception, e:
                    err_msg = traceback.format_exc()
                    error("Error retrieving source from %s: %s"
                          % (url, err_msg.rstrip()))
                error("Failed to retrieve source from any url")
                sys.exit(1)
        except SourceRetrieverError, e:
            error(str(e))
            sys.exit(1)

def patch_source(metadata, srcdir):
    build_data = metadata.get('external_build')
    for patch in build_data.get('patches', []):
        _apply_patch(metadata, patch, srcdir)

def write_build_script(metadata, srcdir):
    build_data = metadata.get('external_build')
    if 'commands' in build_data:
        # cleanup prevous runs
        if os.path.exists('CMakeLists.txt'):
            os.remove('CMakeLists.txt')
        install_commands = build_data['commands']
        assert isinstance(install_commands, list)
        working_dir = build_data.get('working_dir', 'source')
        _write_cmakelist(install_commands, srcdir, working_dir)

def get_patched_source(metadata):
    '''
    Main entry point for retrieving source code and patching it
    '''
    srcdir = get_source(metadata)
    if srcdir:
        patch_source(metadata, srcdir)
        write_build_script(metadata, srcdir)
        return srcdir

def _get_cache_path(metadata):
    cache_path = os.path.expanduser('~/.rez/downloads')
    cache_path = os.path.join(cache_path, metadata["name"])
    ver = metadata.get("version")
    if ver is not None:
        cache_path += "-%s" % str(ver)
    return cache_path

def _write_cmakelist(install_commands, srcdir, working_dir_mode):
    assert not os.path.isabs(srcdir), "source dir must not be an absolute path: %s" % srcdir
    # there are different modes available for the current working directory
    working_dir_mode = working_dir_mode.lower()
    if working_dir_mode == 'source':
        working_dir = "${REZ_SOURCE_DIR}"
    elif working_dir_mode == 'source_root':
        working_dir = "${REZ_SOURCE_ROOT}"
    elif working_dir_mode == 'build':
        working_dir = "${REZ_BUILD_DIR}"
    else:
        error("Invalid option for 'working_dir': provide one of 'source', 'source_root', or 'build'")
        sys.exit(1)

    lines = ['custom_build ALL ' + install_commands[0]]
    for line in install_commands[1:]:
        if line.strip():
            lines.append('  COMMAND ' + line)

    variables = set([])
    for line in install_commands:
        variables.update(re.findall('\$\{([a-zA-Z_][a-zA-Z0-9_]*)\}', line))

    extra_cmake_commands = []
    if variables:
        extra_cmake_commands.append('message("")')
        extra_cmake_commands.append('message("External build cmake variables:")')
        for cmake_var in sorted(variables):
            extra_cmake_commands.append('message("    ${%s}")' % (cmake_var))

    env_variables = set([])
    for line in install_commands:
        env_variables.update(re.findall('\$ENV\{([a-zA-Z_][a-zA-Z0-9_]*)\}', line))

    if env_variables:
        extra_cmake_commands.append('message("")')
        extra_cmake_commands.append('message("External build environment variables:")')
        for cmake_var in sorted(env_variables):
            extra_cmake_commands.append('message("    $ENV{%s}")' % (cmake_var))

    if variables or env_variables:
        extra_cmake_commands.append('message("")')

    content = render_template("external_build.cmake", \
        source_dir=srcdir,
        source_root=SOURCE_ROOT,
        extra_cmake_commands='\n'.join(extra_cmake_commands),
        target_commands='\n'.join(lines),
        working_dir=working_dir)

    print "Writing CMakeLists.txt"
    with open('CMakeLists.txt', 'w') as f:
        f.write(content)

def _apply_patch(metadata, patch_info, source_path):
    action = patch_info['type']
    if action == 'patch':
        patch = patch_info['file']
        print "applying patch %s" % patch
        patch = os.path.abspath(patch)
        # TODO: handle urls. for now, assume relative
        result = subprocess.call(['patch', '-p1', '-i', patch],
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE,
                                 cwd=source_path)
        if result:
            error("Failed to apply patch: %s" % patch)
            sys.exit(1)
    elif action == 'append':
        path = patch_info['file']
        text = patch_info['text']
        path = os.path.join(source_path, path)
        print "appending %r to %s" % (text, path)
        with open(path, 'a') as f:
            f.write(text)
    elif action == 'prepend':
        path = patch_info['file']
        text = patch_info['text']
        path = os.path.join(source_path, path)
        print "prepending %r to %s" % (text, path)
        with open(path, 'r') as f:
            curr_text = f.read()
        with open(path, 'w') as f:
            f.write(text + curr_text)
    elif action == 'replace':
        path = patch_info['file']
        find = patch_info['find']
        replace = patch_info['replace']
        path = os.path.join(source_path, path)
        print "replacing %r with %r in %s" % (find, replace, path)
        with open(path, 'r') as f:
            curr_text = f.read()
        curr_text = curr_text.replace(find, replace)
        with open(path, 'w') as f:
            f.write(curr_text)
    elif action == 'mq':
        print "using mercurial patch queue..."
        url = patch_info['url']
        rev = patch_info['revision']
        cache_path = _get_cache_path(metadata)
        dest_path = os.path.join(SOURCE_ROOT, '.hg', 'patches')

        cloner = source_retriever_plugin_manager.create_instance(url,
            type="hg", cache_path=cache_path, revision=rev)
        cloner.get_source(dest_path)

        print "applying patches"
        cloner.hg(SOURCE_ROOT, ['qpop', '--all'], check_return=False)
        guards = patch_info.get('guards')
        if guards:
            if not isinstance(guards, list):
                guards = [guards]
            print "applying patch guards: " + ' '.join(guards)
            cloner.hg(SOURCE_ROOT, ['qselect'] + guards)
        cloner.hg(SOURCE_ROOT, ['qpush', '--exact', '--all'],
                  check_return=False)
    else:
        error("Unknown patch action: %s" % action)
        sys.exit(1)
