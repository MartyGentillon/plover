#!/usr/bin/env python3
# Copyright (c) 2010 Joshua Harlan Lifton.
# See LICENSE.txt for details.

import contextlib
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import textwrap
import zipfile

from distutils import log
import pkg_resources
import setuptools
from setuptools.command.build_py import build_py

from plover import (
    __name__ as __software_name__,
    __version__,
    __description__,
    __long_description__,
    __url__,
    __download_url__,
    __license__,
    __copyright__,
)


PACKAGE = '%s-%s' % (
    __software_name__,
    __version__,
)


def get_version():
    if not os.path.exists('.git'):
        return None
    version = subprocess.check_output('git describe --tags --match=v[0-9]*'.split()).strip().decode()
    m = re.match(r'^v(\d[\d.]*(?:\.dev\d+)?)(-\d+-g[a-f0-9]*)?$', version)
    assert m is not None, version
    version = m.group(1)
    if m.group(2) is not None:
        version += '+' + m.group(2)[1:].replace('-', '.')
    return version


class Command(setuptools.Command):

    def build_in_place(self):
        self.run_command('build_py')
        self.reinitialize_command('build_ext', inplace=1)
        self.run_command('build_ext')

    @contextlib.contextmanager
    def project_on_sys_path(self):
        self.build_in_place()
        ei_cmd = self.get_finalized_command("egg_info")
        old_path = sys.path[:]
        old_modules = sys.modules.copy()
        try:
            sys.path.insert(0, pkg_resources.normalize_path(ei_cmd.egg_base))
            pkg_resources.working_set.__init__()
            pkg_resources.add_activation_listener(lambda dist: dist.activate())
            pkg_resources.require('%s==%s' % (ei_cmd.egg_name, ei_cmd.egg_version))
            yield
        finally:
            sys.path[:] = old_path
            sys.modules.clear()
            sys.modules.update(old_modules)
            pkg_resources.working_set.__init__()


class BinaryDistWin(Command):

    description = 'create distribution(s) for MS Windows'
    user_options = [
        ('trim', 't',
         'trim the resulting distribution to reduce size'),
        ('zipdir', 'z',
         'create a zip of the resulting directory'),
        ('installer', 'i',
         'create an executable installer for the resulting distribution'),
    ]
    boolean_options = ['installer', 'trim', 'zipdir']
    extra_args = []

    def initialize_options(self):
        self.installer = False
        self.trim = False
        self.zipdir = False

    def finalize_options(self):
        pass

    def run(self):
        # Download helper.
        from utils.download import download
        # Run command helper.
        def run(*args):
            if self.verbose:
                log.info('running %s', ' '.join(a for a in args))
            subprocess.check_call(args)
        # First things first: create Plover wheel.
        wheel_cmd = self.get_finalized_command('bdist_wheel')
        wheel_cmd.run()
        plover_wheel = glob.glob(os.path.join(wheel_cmd.dist_dir,
                                              wheel_cmd.wheel_dist_name)
                                 + '*.whl')[0]
        # Setup embedded Python distribution.
        # Note: python35.zip is decompressed to prevent errors when 2to3
        # is used (including indirectly by setuptools `build_py` command).
        py_embedded = download('https://www.python.org/ftp/python/3.5.2/python-3.5.2-embed-win32.zip',
                               'a62675cd88736688bb87999e8b86d13ef2656312')
        dist_dir = os.path.join(wheel_cmd.dist_dir, PACKAGE + '-win32')
        data_dir = os.path.join(dist_dir, 'data')
        stdlib = os.path.join(data_dir, 'python35.zip')
        if os.path.exists(dist_dir):
            shutil.rmtree(dist_dir)
        os.makedirs(data_dir)
        for path in (py_embedded, stdlib):
            with zipfile.ZipFile(path) as zip:
                zip.extractall(data_dir)
        os.unlink(stdlib)
        dist_py = os.path.join(data_dir, 'python.exe')
        # Install pip/wheel.
        run(dist_py, '-m', 'utils.get_pip')
        # Install Plover and dependencies.
        # Note: do not use the embedded Python executable with `setup.py
        # install` to prevent setuptools from installing extra development
        # dependencies...
        run(dist_py, '-m', 'utils.install_wheels',
            '-r', 'requirements_distribution.txt')
        run(dist_py, '-m', 'utils.install_wheels',
            '--ignore-installed', '--no-deps', plover_wheel)
        # List installed packages.
        if self.verbose:
            run(dist_py, '-m', 'pip', 'list', '--format=columns')
        # Trim the fat...
        if self.trim:
            from utils.trim import trim
            trim(data_dir, 'windows/dist_blacklist.txt', verbose=self.verbose)
        # Add miscellaneous files: icon, license, ...
        for src, target_dir in (
            ('LICENSE.txt'             , '.'   ),
            ('plover/assets/plover.ico', 'data')
        ):
            dst = os.path.join(dist_dir, target_dir, os.path.basename(src))
            shutil.copyfile(src, dst)
        # Create launchers.
        for entrypoint, gui in (
            ('plover         = plover.main:main', True ),
            ('plover_console = plover.main:main', False),
        ):
            run(dist_py, '-c', textwrap.dedent(
                '''
                from pip._vendor.distlib.scripts import ScriptMaker
                sm = ScriptMaker(source_dir='{dist_dir}', target_dir='{dist_dir}')
                sm.executable = 'data\\python.exe'
                sm.variants = set(('',))
                sm.make('{entrypoint}', options={{'gui': {gui}}})
                '''.rstrip()).format(dist_dir=dist_dir,
                                     entrypoint=entrypoint,
                                     gui=gui))
        # Make distribution source-less.
        run(dist_py, '-m', 'utils.source_less',
            # Don't touch pip._vendor.distlib sources,
            # or `pip install` will not be usable...
            data_dir, '*/pip/_vendor/distlib/*',
        )
        # Zip results.
        if self.zipdir:
            from utils.zipdir import zipdir
            if self.verbose:
                log.info('zipping %s', dist_dir)
            zipdir(dist_dir)
        # Create an installer.
        if self.installer:
            installer_exe = '%s.setup.exe' % dist_dir
            # Compute install size for "Add/Remove Programs" entry.
            install_size = sum(os.path.getsize(os.path.join(dirpath, f))
                               for dirpath, dirnames, filenames
                               in os.walk(dist_dir) for f in filenames)
            run('makensis.exe', '-NOCD',
                '-Dsrcdir=' + dist_dir,
                '-Dversion=' + __version__,
                '-Dinstall_size=' + str(install_size // 1024),
                'windows/installer.nsi',
                '-XOutFile ' + installer_exe)


class Launch(Command):

    description = 'run %s from source' % __software_name__.capitalize()
    command_consumes_arguments = True
    user_options = []

    def initialize_options(self):
        self.args = None

    def finalize_options(self):
        pass

    def run(self):
        with self.project_on_sys_path():
            os.execv(sys.executable, 'plover -m plover.main'.split() + self.args)


class PatchVersion(Command):

    description = 'patch package version from VCS'
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        version = get_version()
        if version is None:
            sys.exit(1)
        log.info('patching version to %s', version)
        version_file = os.path.join('plover', '__init__.py')
        with open(version_file, 'r') as fp:
            contents = fp.read().split('\n')
        contents = [re.sub(r'^__version__ = .*$', "__version__ = '%s'" % version, line)
                    for line in contents]
        with open(version_file, 'w') as fp:
            fp.write('\n'.join(contents))


class TagWeekly(Command):

    description = 'tag weekly version'
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        version = get_version()
        if version is None:
            sys.exit(1)
        weekly_version = 'weekly-v%s' % version
        log.info('tagging as %s', weekly_version)
        subprocess.check_call('git tag -f'.split() + [weekly_version])


class Test(Command):

    description = 'run unit tests after in-place build'
    command_consumes_arguments = True
    user_options = []

    def initialize_options(self):
        self.args = []

    def finalize_options(self):
        pass

    def run(self):
        with self.project_on_sys_path():
            self.run_tests()

    def run_tests(self):
        test_dir = os.path.join(os.path.dirname(__file__), 'test')
        # Remove __pycache__ directory so pytest does not freak out
        # when switching between the Linux/Windows versions.
        pycache = os.path.join(test_dir, '__pycache__')
        if os.path.exists(pycache):
            shutil.rmtree(pycache)
        custom_testsuite = None
        args = []
        for a in self.args:
            if '-' == a[0]:
                args.append(a)
            elif os.path.exists(a):
                custom_testsuite = a
                args.append(a)
            else:
                args.extend(('-k', a))
        if custom_testsuite is None:
            args.insert(0, test_dir)
        sys.argv[1:] = args
        main = pkg_resources.load_entry_point('pytest',
                                              'console_scripts',
                                              'py.test')
        sys.exit(main())


class BinaryDistApp(Command):
    description = 'create an application bundle for Mac'
    user_options = []
    extra_args = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        whl_cmd = self.get_finalized_command('bdist_wheel')
        whl_cmd.run()
        wheel_path = whl_cmd.get_archive_basename()
        cmd = 'bash osx/make_app.sh %s %s' % (wheel_path, PACKAGE)
        log.info('running %s', cmd)
        subprocess.check_call(cmd.split())


class BinaryDistDmg(Command):

    user_options = []
    extra_args = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        self.run_command('bdist_app')
        # Get dmgbuild
        from utils.download import download
        dmgbuild = download(
          'https://github.com/morinted/dmgbuild/releases/download/v1.2.1%2Bplover/dmgbuild-1.2.1.pex',
          '548a5c3336fd30b966060b84d86faa9a697b7f94'
        )
        dmg = 'dist/%s.dmg' % PACKAGE
        # Use Apple's built-in python2 to run dmgbuild
        cmd = '/usr/bin/python %s -s osx/dmg_resources/settings.py Plover %s' % (dmgbuild, dmg)
        log.info('running %s', cmd)
        subprocess.check_call(cmd.split())

cmdclass = {
    'launch': Launch,
    'patch_version': PatchVersion,
    'tag_weekly': TagWeekly,
    'test': Test,
}
options = {}
build_dependencies = []

if sys.platform.startswith('darwin'):
    cmdclass['bdist_app'] = BinaryDistApp
    cmdclass['bdist_dmg'] = BinaryDistDmg

if sys.platform.startswith('win32'):
    cmdclass['bdist_win'] = BinaryDistWin

try:
    import PyQt5
except ImportError:
    pass
else:
    try:
        from pyqt_distutils.build_ui import build_ui
    except ImportError:
        pass
    else:
        class BuildUi(build_ui):

            def finalize_options(self):
                # Patch-in correct Python interpreter before the call
                # to build_ui.finalize_options load the configuration.
                with open('pyuic.json.in') as fp:
                    cfg = json.load(fp)
                for opt in 'pyrcc pyuic'.split():
                    cfg[opt] = cfg[opt].replace('$PYTHON', sys.executable)
                with open('pyuic.json', 'w') as fp:
                    json.dump(cfg, fp)
                build_ui.finalize_options(self)

            def run(self):
                from utils.pyqt import fix_icons
                self._hooks['fix_icons'] = fix_icons
                build_ui.run(self)

        cmdclass['build_ui'] = BuildUi
        build_dependencies.append('build_ui')

try:
    from babel.messages import frontend as babel
except ImportError:
    pass
else:
    cmdclass.update({
        'compile_catalog': babel.compile_catalog,
        'extract_messages': babel.extract_messages,
        'init_catalog': babel.init_catalog,
        'update_catalog': babel.update_catalog
    })
    locale_dir = 'plover/gui_qt/messages'
    template = '%s/%s.pot' % (locale_dir, __software_name__)
    options['compile_catalog'] = {
        'domain': __software_name__,
        'directory': locale_dir,
    }
    options['extract_messages'] = {
        'output_file': template,
    }
    options['init_catalog'] = {
        'domain': __software_name__,
        'input_file': template,
        'output_dir': locale_dir,
    }
    options['update_catalog'] = {
        'domain': __software_name__,
        'output_dir': locale_dir,
    }
    build_dependencies.append('compile_catalog')


extras_require = {
    ':"win32" in sys_platform': [
        'PyQt5',
        'plyer==1.2.4', # For notifications.
    ],
    ':"linux" in sys_platform': [
        # Note: do not require PyQt5 on Linux, as official distribution
        # packages are missing the required Python distribution info.
        # 'PyQt5',
        'python-xlib>=0.16',
    ],
    ':"darwin" in sys_platform': [
        'PyQt5',
        'pyobjc-core==3.1.1+plover2',
        'pyobjc-framework-Cocoa==3.1.1+plover2',
        'pyobjc-framework-Quartz==3.1.1',
        'appnope>=0.1.0',
    ],
}


class CustomBuildPy(build_py):
    def run(self):
        for command in build_dependencies:
            self.run_command(command)
        build_py.run(self)

cmdclass['build_py'] = CustomBuildPy


setuptools.setup(
    name=__software_name__,
    version=__version__,
    description=__description__,
    long_description=__long_description__,
    url=__url__,
    download_url=__download_url__,
    license=__license__,
    options=options,
    cmdclass=cmdclass,
    extras_require=extras_require,
)
