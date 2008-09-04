# $Id: $
__requires__='TurboGears[future]'

from setuptools import setup, find_packages
from turbogears.finddata import find_package_data
import os
import re
import glob
import shutil
from distutils.dep_util import newer
from distutils import log

from distutils.command.build_scripts import build_scripts as _build_scripts
from distutils.command.build import build as _build
from distutils.command.install_data import install_data as _install_data
from distutils.dep_util import newer
from setuptools.command.install import install as _install
from setuptools.command.install_lib import install_lib as _install_lib

from turbogears.finddata import find_package_data, standard_exclude, \
        standard_exclude_directories


excludeFiles = ['*.cfg.in']
excludeFiles.extend(standard_exclude)
excludeDataDirs = ['bodhi/static', 'comps']
excludeDataDirs.extend(standard_exclude_directories)

poFiles = filter(os.path.isfile, glob.glob('po/*.po'))

SUBSTFILES = ('bodhi/config/app.cfg',)

class Build(_build, object):
    '''
    Build the package, changing the directories that data files are installed.
    '''
    user_options = _build.user_options
    user_options.extend([('install-data=', None,
        'Installation directory for data files')])
    # These are set in finalize_options()
    substitutions = {'@DATADIR@': None, '@LOCALEDIR@': None}
    subRE = re.compile('(' + '|'.join(substitutions.keys()) + ')+')

    def initialize_options(self):
        self.install_data = None
        super(Build, self).initialize_options()

    def finalize_options(self):
        if self.install_data:
            self.substitutions['@DATADIR@'] = self.install_data + '/bodhi'
            self.substitutions['@LOCALEDIR@'] = self.install_data + '/locale'
        else:
            self.substitutions['@DATADIR@'] = '%(top_level_dir)s'
            self.substitutions['@LOCALEDIR@'] = '%(top_level_dir)s/../locale'
        super(Build, self).finalize_options()

    def run(self):
        '''Substitute special variables for our installation locations.'''
        for filename in SUBSTFILES:
            # Change files to reference the data directory in the proper
            # location
            infile = filename + '.in'
            if not os.path.exists(infile):
                continue
            try:
                f = file(infile, 'r')
            except IOError:
                if not self.dry_run:
                    raise
                f = None
            outf = file(filename, 'w')
            for line in f.readlines():
                matches = self.subRE.search(line)
                if matches:
                    for pattern in self.substitutions:
                        line = line.replace(pattern, self.substitutions[pattern])
                outf.writelines(line)
            outf.close()
            f.close()

        # Make empty en.po
        dirname = 'locale/'
        if not os.path.isdir(dirname):
            os.makedirs(dirname)
        #shutil.copy('po/LINGUAS', 'locale/')

        for pofile in poFiles:
            # Compile PO files
            lang = os.path.basename(pofile).rsplit('.', 1)[0]
            dirname = 'locale/%s/LC_MESSAGES/' % lang
            if not os.path.isdir(dirname):
                os.makedirs(dirname)
            # Hardcoded gettext domain: 'bodhi'
            mofile = dirname + 'bodhi' + '.mo'
            subprocess.call(['/usr/bin/msgfmt', pofile, '-o', mofile])
        super(Build, self).run()

class InstallData(_install_data, object):
    def finalize_options(self):
        '''Override to emulate setuptools in the default case.
        install_data => install_dir
        '''
        self.temp_lib = None
        self.temp_data = None
        self.temp_prefix = None
        haveInstallDir = self.install_dir
        self.set_undefined_options('install',
                ('install_data', 'temp_data'),
                ('install_lib', 'temp_lib'),
                ('prefix', 'temp_prefix'),
                ('root', 'root'),
                ('force', 'force'),
                )
        if not self.install_dir:
            if self.temp_data == self.root + self.temp_prefix:
                self.install_dir = os.path.join(self.temp_lib, 'bodhi')
            else:
                self.install_dir = self.temp_data

# bodhi/static => /usr/share/bodhi/static
data_files = [
    ('bodhi/static', filter(os.path.isfile, glob.glob('bodhi/static/*'))),
    ('bodhi/static/css', filter(os.path.isfile, glob.glob('bodhi/static/css/*'))),
    ('bodhi/static/images', filter(os.path.isfile, glob.glob('bodhi/static/images/*'))),
    ('bodhi/static/js', filter(os.path.isfile, glob.glob('bodhi/static/js/*'))),
    ('man/man1', ['docs/bodhi.1']),
]
for langfile in filter(os.path.isfile, glob.glob('locale/*/*/*')):
    data_files.append((os.path.dirname(langfile), [langfile]))

package_data = find_package_data(where='bodhi', package='bodhi', exclude=excludeFiles, exclude_directories=excludeDataDirs,)
package_data['bodhi.config'].append('app.cfg')

from bodhi.release import NAME, VERSION, DESCRIPTION, AUTHOR, EMAIL, URL, LICENSE

setup(
    name=NAME,
    version=VERSION,
    description=DESCRIPTION,
    author=AUTHOR,
    author_email=EMAIL,
    url=URL,
    license=LICENSE,
    cmdclass={
        'build': Build,
        'install_data': InstallData,
    },
    install_requires = [
        "TurboGears >= 1.0",
        "TurboMail",
        "python_fedora",
    ],
    scripts = [],
    data_files = data_files,
    zip_safe=False,
    packages=find_packages(),
    package_data = package_data,
    keywords = [
        'turbogears.app',
    ],
    classifiers = [
        'Programming Language :: Python',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Framework :: TurboGears',
        'Framework :: TurboGears :: Applications',
    ],
    test_suite = 'nose.collector',
    entry_points = {
            'console_scripts': (
                'start-bodhi = bodhi.commands:start',
                'bodhi-pickledb = bodhi.tools.pickledb:main',
                'bodhi-tagcheck = bodhi.tools.tagcheck:main',
                'bodhi-init = bodhi.tools.init:main',
                'bodhi-devinit = bodhi.tools.dev_init:main',
                'bodhi-rmrelease = bodhi.tools.rmrelease:main',
            ),
            'turbogears.extensions': (
                'masher = bodhi.masher'
            ),
    }
)
