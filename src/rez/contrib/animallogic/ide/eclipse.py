
from rez.packages import load_developer_package
from rez.resolved_context import ResolvedContext
from rez.rex import RexExecutor, Python
import logging
import os
import re
import xml.etree.cElementTree as etree


logger = logging.getLogger(__name__)


class EclipseProjectBuilder(object):

    include_path_start_regex = re.compile('CMAKE_C_TARGET_INCLUDE_PATH')
    end_section_regex = re.compile('\)')

    def __init__(self, working_directory):

        self.working_directory = working_directory
        self.package = load_developer_package(self.working_directory)

        self.name = self.package.name
        self.dependencies = self.package.requires
        self.variants = list(self.package.iter_variants())
        self.local_dependencies = self._get_local_dependencies()

    def _get_local_dependencies(self):

        local_dependencies = []
        package_dependencies = [dependency.name for dependency in self.dependencies]

        for sibling in os.listdir('..'):
            if not os.path.isdir(os.path.join('..', sibling)):
                continue

            if sibling == self.name:
                continue

            if sibling not in package_dependencies:
                continue

            logger.info('Found local dependency: %s' % sibling)
            local_dependencies.append(sibling)

        return local_dependencies
      
    def find_src_python_paths(self):

        paths = []
        for path in ['src', 'python/src']:
            if os.path.exists(path):
                paths.append('/${PROJECT_DIR_NAME}/%s' % path)

        return paths

    def find_ext_python_paths(self, variant):

        resolved_context_file = os.path.join('build', variant.subpath, 'build.rxt')
        resolved_context = ResolvedContext.load(resolved_context_file)

        target_environ = {}
        interpreter = Python(target_environ=target_environ)
        executor = resolved_context._create_executor(interpreter, None)
        resolved_context._execute(executor)
        executor.get_output()

        return target_environ.get("PYTHONPATH", "").split(os.pathsep)

    def find_include_paths(self, variant):

        paths = []
        in_include_section = False
        target_directories = os.path.join('build', variant.subpath, 'CMakeFiles/TargetDirectories.txt')

        for target_directory in open(target_directories):
            depend_info = os.path.join(target_directory.strip(), 'DependInfo.cmake')

            for line in open(depend_info):
                if self.include_path_start_regex.search(line):
                    in_include_section = True
                    continue

                if self.end_section_regex.search(line):
                    in_include_section = False
                    continue

                if in_include_section:
                    paths.append(self.parse_include_path_from_line(line))

        return paths

    def parse_include_path_from_line(self, line):

        path = line.strip()[1:-1]

        if path[0:5] == '../..':
            # replace the 5 chars '../..' by local workspace keyword
            path = '${workspace_loc:/%s%s}'%(self.name, path[5:])

        for dependency in self.local_dependencies:
            if path.find('/%s/' % dependency) != -1:
                path = '${workspace_loc:/%s/include}' % dependency

        return path

    def make_scanner_config(self, storage_module, instance_id):

        scanner_config_build_info = etree.SubElement(storage_module, "scannerConfigBuildInfo")
        scanner_config_build_info.set('instanceId', instance_id)

        autodiscovery = etree.SubElement(scanner_config_build_info, "autodiscovery")
        autodiscovery.set('enabled', 'true')
        autodiscovery.set('problemReportingEnabled', 'true')
        autodiscovery.set('selectedProfileId', '')

    def find_target_directories(self, variant, variant_index):

        paths = []
        names = set()
        variant_name = variant.subpath
        target_directories = os.path.join('build', variant_name, 'CMakeFiles/TargetDirectories.txt')

        paths.append(('%s' % variant_name, os.path.join('build', variant_name)))

        for line in open(target_directories):
            path = line.strip().replace(self.working_directory, '')[1:]
            steps = path.split('/')
            steps[-1] = steps[-1].replace('.dir', '')

            if steps[-1] in ('package-yaml', 'cmake'):
                continue

            name = steps[-1] + '_%d' % variant_index

            paths.append((name, path))
            for i in range(len(steps)-5):
                substeps = steps[2:-i-3]

                if not substeps:
                    continue

                name = '_'.join(substeps) + '_%d' % variant_index
                path = os.path.join(*steps[:-3-i])
                path = path.replace('/%i' % variant_index, '/%s' % variant_name)

                if name not in names:
                    paths.append((name, path))
                    names.add(name)

        return paths

    def add_make_target(self, build_targets, name, path, cmd):

        target = etree.SubElement(build_targets, "target")
        target.set('name', name)
        target.set('path', path)
        target.set('targetID', 'org.eclipse.cdt.build.MakeTargetBuilder')

        etree.SubElement(target, "buildCommand").text = 'make'
        etree.SubElement(target, "buildTarget").text = cmd
        etree.SubElement(target, "stopOnError").text = 'true'
        etree.SubElement(target, "useDefaultCommand").text = 'true'
        etree.SubElement(target, "runAllBuilders").text = 'true'

    @staticmethod
    def pretty_print(element, path, prefix=None):

        with open(path, 'w') as fd:
            fd.write('<?xml version="1.0" encoding="UTF-8"?>\n')

            if prefix:
                fd.write(prefix)

            txt = etree.tostring(element)
            fd.write(txt)

    def build_project(self):

        project_description = etree.Element("projectDescription")
        etree.SubElement(project_description, "name").text = self.name

        build_spec = etree.SubElement(project_description, "buildSpec")
        build_command = etree.SubElement(build_spec, "buildCommand")
        etree.SubElement(build_command, "name").text = 'org.python.pydev.PyDevBuilder'
         
        build_command = etree.SubElement(build_spec, "buildCommand")
        etree.SubElement(build_command, "name").text = 'org.eclipse.cdt.managedbuilder.core.genmakebuilder'
        etree.SubElement(build_command, "triggers").text = 'full,incremental,'
         
        build_command = etree.SubElement(build_spec, "buildCommand")
        etree.SubElement(build_command, "name").text = 'org.eclipse.cdt.managedbuilder.core.ScannerConfigBuilder'
        etree.SubElement(build_command, "triggers").text = 'full,incremental,'
         
        projects = etree.SubElement(project_description, "projects")
        for dependency in self.dependencies:
            etree.SubElement(projects, "project").text = dependency.name
         
        natures = etree.SubElement(project_description, "natures")
        etree.SubElement(natures, "nature").text = 'org.eclipse.cdt.core.cnature'
        etree.SubElement(natures, "nature").text = 'org.eclipse.cdt.core.ccnature'
        etree.SubElement(natures, "nature").text = 'org.eclipse.cdt.managedbuilder.core.managedBuildNature'
        etree.SubElement(natures, "nature").text = 'org.eclipse.cdt.managedbuilder.core.ScannerConfigNature'
        etree.SubElement(natures, "nature").text = 'org.python.pydev.pythonNature'
         
        self.pretty_print(project_description, '.project')
        logger.info('Built .project file for %r' % self.name)

    def build_cproject(self):

        def make_extension(extensions, id_, point):
            extension = etree.SubElement(extensions, "extension")
            extension.set('id', id_)
            extension.set('point', point)

        cproject = etree.Element("cproject")
        cproject.set('storage_type_id', 'org.eclipse.cdt.core.XmlProjectDescriptionStorage')
          
        storage_module = etree.SubElement(cproject, "storageModule")
        storage_module.set('moduleId', 'org.eclipse.cdt.core.settings')
          
        j = 99 # Need a random id that's not i
        for i, variant in enumerate(self.variants):
            j += 1
            variant_name = variant.subpath

            cconfiguration = etree.SubElement(storage_module, "cconfiguration")
            cconfiguration.set('id', 'cdt.managedbuild.toolchain.gnu.base.%d' % i)

            storage_module_2 = etree.SubElement(cconfiguration, "storageModule")
            storage_module_2.set('buildSystemId', 'org.eclipse.cdt.managedbuilder.core.configurationDataProvider')
            storage_module_2.set('id', 'cdt.managedbuild.toolchain.gnu.base.%d' % i)
            storage_module_2.set('moduleId', 'org.eclipse.cdt.core.settings')
            storage_module_2.set('name', variant_name)

            extensions = etree.SubElement(storage_module_2, "extensions")

            make_extension(extensions, 'org.eclipse.cdt.core.GmakeErrorParser', 'org.eclipse.cdt.core.ErrorParser')
            make_extension(extensions, 'org.eclipse.cdt.core.CWDLocator', 'org.eclipse.cdt.core.ErrorParser')
            make_extension(extensions, 'org.eclipse.cdt.core.GCCErrorParser', 'org.eclipse.cdt.core.ErrorParser')
            make_extension(extensions, 'org.eclipse.cdt.core.GASErrorParser', 'org.eclipse.cdt.core.ErrorParser')
            make_extension(extensions, 'org.eclipse.cdt.core.GLDErrorParser', 'org.eclipse.cdt.core.ErrorParser')
            make_extension(extensions, 'org.eclipse.cdt.core.ELF', 'org.eclipse.cdt.core.BinaryParser')

            storage_module_3 = etree.SubElement(cconfiguration, "storageModule")
            storage_module_3.set('moduleId', 'cdtBuildSystem')
            storage_module_3.set('version', '4.0.0')

            configuration = etree.SubElement(storage_module_3, "configuration")
            configuration.set('artifactName', self.name)
            configuration.set('id', 'cdt.managedbuild.toolchain.gnu.base.%d' % i)
            configuration.set('name', variant_name)
            configuration.set('parent', 'org.eclipse.cdt.build.core.emptycfg')

            folder_info = etree.SubElement(configuration, "folderInfo")
            folder_info.set('id', 'cdt.managedbuild.toolchain.gnu.base.%d.%d' % (i, j))
            folder_info.set('name', '/')
            folder_info.set('resourcePath', '')

            tool_chain = etree.SubElement(folder_info, "toolChain")
            tool_chain.set('id', 'cdt.managedbuild.toolchain.gnu.base.%d' % i)
            tool_chain.set('name', 'cdt.managedbuild.toolchain.gnu.base')
            tool_chain.set('superClass', 'cdt.managedbuild.toolchain.gnu.base')

            target_platform = etree.SubElement(tool_chain, "targetPlatform")
            target_platform.set('archList', 'all')
            target_platform.set('binaryParser', 'org.eclipse.cdt.core.ELF')
            target_platform.set('id', 'cdt.managedbuild.target.gnu.platform.base.%d' % i)
            target_platform.set('name', 'Debug Platform')
            target_platform.set('osList', 'linux,hpux,aix,qnx')
            target_platform.set('superClass', 'cdt.managedbuild.target.gnu.platform.base')

            builder = etree.SubElement(target_platform, "builder")
            builder.set('buildPath', '${workspace_loc:/%s}/build/%d' % (self.name, i))
            builder.set('id', 'cdt.managedbuild.target.gnu.builder.base.%d' % i)
            builder.set('keepEnvironmentInBuildfile', 'false')
            builder.set('managedBuildOn', 'false')
            builder.set('name', 'Gnu Make Builder')
            builder.set('parallelBuildOn', 'true')
            builder.set('parallelizationNumber', 'optimal')
            builder.set('superClass', 'cdt.managedbuild.target.gnu.builder.base')

            tool = etree.SubElement(tool_chain, "tool")
            tool.set('id', 'cdt.managedbuild.tool.gnu.archiver.base.%d' % i)
            tool.set('name', 'GCC Archiver')
            tool.set('superClass', 'cdt.managedbuild.tool.gnu.archiver.base')

            tool = etree.SubElement(tool_chain, "tool")
            tool.set('id', 'cdt.managedbuild.tool.gnu.cpp.compiler.base.%i')
            tool.set('name', 'GCC C++ Compiler')
            tool.set('superClass', 'cdt.managedbuild.tool.gnu.cpp.compiler.base')

            option = etree.SubElement(tool, "option")
            option.set('id', 'gnu.cpp.compiler.option.include.paths.%d' % i)
            option.set('name', 'Include paths (-I)')
            option.set('superClass', 'gnu.cpp.compiler.option.include.paths')
            option.set('valueType', 'includePath')

            for path in self.find_include_paths(variant):
                listOptionValue = etree.SubElement(option, "listOptionValue")
                listOptionValue.set('builtIn', 'false')
                listOptionValue.set('value', path)

            input_type = etree.SubElement(tool, "inputType")
            input_type.set('id', 'cdt.managedbuild.tool.gnu.cpp.compiler.input.%d' % i)
            input_type.set('superClass', 'cdt.managedbuild.tool.gnu.cpp.compiler.input')

            tool = etree.SubElement(tool_chain, "tool")
            tool.set('id', 'cdt.managedbuild.tool.gnu.c.compiler.base.%d' % i)
            tool.set('name', 'GCC C Compiler')
            tool.set('superClass', 'cdt.managedbuild.tool.gnu.c.compiler.base')

            input_type = etree.SubElement(tool, "inputType")
            input_type.set('id', 'cdt.managedbuild.tool.gnu.c.compiler.input.%d' % i)
            input_type.set('superClass', 'cdt.managedbuild.tool.gnu.c.compiler.input')

            tool = etree.SubElement(tool_chain, "tool")
            tool.set('id', 'cdt.managedbuild.tool.gnu.c.linker.base.%d' % i)
            tool.set('name', 'GCC C Linker')
            tool.set('superClass', 'cdt.managedbuild.tool.gnu.c.linker.base')

            tool = etree.SubElement(tool_chain, "tool")
            tool.set('id', 'cdt.managedbuild.tool.gnu.cpp.linker.base.%d' % i)
            tool.set('name', 'GCC C++ Linker')
            tool.set('superClass', 'cdt.managedbuild.tool.gnu.cpp.linker.base')

            input_type = etree.SubElement(tool, "inputType")
            input_type.set('id', 'cdt.managedbuild.tool.gnu.cpp.linker.input.%d' % i)
            input_type.set('superClass', 'cdt.managedbuild.tool.gnu.cpp.linker.input')

            additional_input = etree.SubElement(input_type, "additionalInput")
            additional_input.set('kind', 'additionalinputdependency')
            additional_input.set('paths', '$(USER_OBJS)')

            additional_input = etree.SubElement(input_type, "additionalInput")
            additional_input.set('kind', 'additionalinput')
            additional_input.set('paths', '$(LIBS)')

            tool = etree.SubElement(tool_chain, "tool")
            tool.set('id', 'cdt.managedbuild.tool.gnu.assembler.base.%d' % i)
            tool.set('name', 'GCC Assembler')
            tool.set('superClass', 'cdt.managedbuild.tool.gnu.assembler.base')

            input_type = etree.SubElement(tool, "inputType")
            input_type.set('id', 'cdt.managedbuild.tool.gnu.assembler.input.%d' % i)
            input_type.set('superClass', 'cdt.managedbuild.tool.gnu.assembler.input')

        storage_module = etree.SubElement(cproject, "storageModule")
        storage_module.set('moduleId', 'cdtBuildSystem')
        storage_module.set('version', '4.0.0')

        project = etree.SubElement(storage_module, "project")
        project.set('id', '%s.null.%d' % (self.name, i))
        project.set('name', self.name)

        storage_module = etree.SubElement(cproject, "storageModule")
        storage_module.set('moduleId', 'org.eclipse.cdt.core.LanguageSettingsProviders')

        storage_module = etree.SubElement(cproject, "storageModule")
        storage_module.set('moduleId', 'refreshScope')
        storage_module.set('versionNumber', '2')

        configuration = etree.SubElement(storage_module, "configuration")
        configuration.set('configurationName', 'Default')

        resource = etree.SubElement(configuration, "resource")
        resource.set('resourceType', 'PROJECT')
        resource.set('workspacePath', '/%s/' % self.name)

        for variant in self.variants:
            configuration = etree.SubElement(storage_module, "configuration")
            configuration.set('configurationName', variant.subpath)

        storage_module = etree.SubElement(cproject, "storageModule")
        storage_module.set('moduleId', 'scannerConfiguration')
          
        autodiscovery = etree.SubElement(storage_module, "autodiscovery")
        autodiscovery.set('enabled', 'true')
        autodiscovery.set('problemReportingEnabled', 'true')
        autodiscovery.set('selectedProfileId', '')

        j = 99
        for i, variant in enumerate(self.variants): 
            j += 1

            self.make_scanner_config(storage_module, 'cdt.managedbuild.toolchain.gnu.base.%d;cdt.managedbuild.toolchain.gnu.base.%d.%d;cdt.managedbuild.tool.gnu.cpp.compiler.base.%d;cdt.managedbuild.tool.gnu.cpp.compiler.input.%d' % (i, i, j, i, i))
            self.make_scanner_config(storage_module, 'cdt.managedbuild.toolchain.gnu.base.%d;cdt.managedbuild.toolchain.gnu.base.%d.%d;cdt.managedbuild.tool.gnu.c.compiler.base.%d;cdt.managedbuild.tool.gnu.c.compiler.input.%d' % (i, i, j, i, i))

        storage_module = etree.SubElement(cproject, "storageModule")
        storage_module.set('moduleId', 'org.eclipse.cdt.make.core.buildtargets')

        build_targets = etree.SubElement(storage_module, "buildTargets")

        for i, variant in enumerate(self.variants):
            for name, path in self.find_target_directories(variant, i):
                self.add_make_target(build_targets, name, path, 'install')
                self.add_make_target(build_targets, name + '_clean', path, 'clean')

        self.pretty_print(cproject, '.cproject', prefix='<?fileVersion 4.0.0?>\n')
        logger.info('Build .cproject file for %r and %d variants.' % (self.name, len(self.variants)))

    def build_pydevproject(self):

        pydev_project = etree.Element("pydev_project")
          
        pydev_property = etree.SubElement(pydev_project, "pydev_property")
        pydev_property.set('name', 'org.python.pydev.PYTHON_PROJECT_VERSION')
        pydev_property.text = 'python 2.7'
  
        pydev_property = etree.SubElement(pydev_project, "pydev_property")
        pydev_property.set('name', 'org.python.pydev.PYTHON_PROJECT_INTERPRETER')
        pydev_property.text = 'Default'
          
        pydev_pathproperty = etree.SubElement(pydev_project, "pydev_pathproperty")
        pydev_pathproperty.set('name', 'org.python.pydev.PROJECT_SOURCE_PATH')
        for path in self.find_src_python_paths():
            etree.SubElement(pydev_pathproperty, "path").text = path
          
        pydev_pathproperty = etree.SubElement(pydev_project, "pydev_pathproperty")
        pydev_pathproperty.set('name', 'org.python.pydev.PROJECT_EXTERNAL_SOURCE_PATH')
        for path in self.find_ext_python_paths(self.variants[0]):
            etree.SubElement(pydev_pathproperty, "path").text = path
          
        self.pretty_print(pydev_project, '.pydevproject', prefix='<?eclipse-pydev version="1.0"?>\n')
        logger.info('Build .pydevproject file for %r and variant 0 (%s).' % (self.name, self.variants[0].subpath))

    def build_cproject_settings(self):

        settings = 'eclipse.preferences.version=1\n'

        for i, variant in enumerate(self.variants):
            resolved_context_file = os.path.join('build', variant.subpath, 'build.rxt')
            resolved_context = ResolvedContext.load(resolved_context_file)

            target_environ = {}
            interpreter = Python(target_environ=target_environ)
            executor = resolved_context._create_executor(interpreter, None)
            resolved_context._execute(executor)
            executor.get_output()

            for key, value in target_environ.items():
                settings += '''
environment/project/cdt.managedbuild.toolchain.gnu.base.%(i)s/%(key)s/delimiter=\:
environment/project/cdt.managedbuild.toolchain.gnu.base.%(i)s/%(key)s/operation=replace
environment/project/cdt.managedbuild.toolchain.gnu.base.%(i)s/%(key)s/value=%(value)s''' % dict(i=i, key=key, value=value)

            settings += '''
environment/project/cdt.managedbuild.toolchain.gnu.base.%(i)s/append=true'
environment/project/cdt.managedbuild.toolchain.gnu.base.%(i)s/appendContributed=true''' % dict(i=i)

        if not os.path.exists('.settings'):
            os.makedirs('.settings')

        with open('.settings/org.eclipse.cdt.core.prefs', 'w') as fd:
            fd.write(settings)

        logger.info('Build .settings/org.eclipse.cdt.core.prefs file for %r and %d variants.' % (self.name, len(self.variants)))







