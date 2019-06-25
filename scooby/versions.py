import importlib
import mock
import logging
import sys
import time
import scipy
import textwrap
import platform
import numpy as np
import multiprocessing
from types import ModuleType


from scooby.knowledge import VERSION_ATTRIBUTES


# Optional modules
try:
    import IPython
except ImportError:
    IPython = False
try:
    import matplotlib
except ImportError:
    matplotlib = False
try:
    import mkl
except ImportError:
    mkl = False

# Get mkl info, if available
if mkl:
    mklinfo = mkl.get_version_string()
else:
    mklinfo = False


class Versions:
    r"""Print date, time, and version information.

    Print date, time, and package version information in any environment
    (Jupyter notebook, IPython console, Python console, QT console), either as
    html-table (notebook) or as plain text (anywhere).

    Always shown are the OS, number of CPU(s), ``numpy``, ``scipy``,
    ``sys.version``, and time/date.

    Additionally shown are, if they can be imported, ``IPython`` and
    ``matplotlib``. It also shows MKL information, if available.

    All modules provided in ``add_pckg`` are also shown. They have to be
    imported before ``versions`` is called.

    This script was heavily inspired by:

        - ipynbtools.py from qutip https://github.com/qutip
        - watermark.py from https://github.com/rasbt/watermark


    Parameters
    ----------
    add_pckg : packages, optional
        Package or list of packages to add to output information (must be
        imported beforehand).

    ncol : int, optional
        Number of package-columns in html table; only has effect if
        ``mode='HTML'`` or ``mode='html'``. Defaults to 3.

    """

    def __init__(self, core=('numpy', 'scipy',),
                       optional=('IPython', 'matplotlib',),
                       additional=None,
                       ncol=4, text_width=54):
        """Initiate and add packages and number of columns to self."""
        self.ncol = int(ncol)
        self.text_width = text_width

        # Mandatory packages
        self._packages = {}

        # MAke sure arguments are good
        safety = lambda x: [] if x is None or len(x) < 1 else list(x)
        core = safety(core)
        optional = safety(optional)
        additional = safety(additional)

        # Update packages
        self.add_packages(core)
        # Optional packages
        self.add_packages(optional)
        # Additional packages
        self.add_packages(additional)


    @staticmethod
    def _safe_import_by_name(name):
        try:
            module = importlib.import_module(name)
        except ((ImportError, ModuleNotFoundError)):
            logging.warning('Could not import module `{}`. This will be mocked.'.format(name))
            module = mock.Mock()
            sys.modules[name] = module
        return module


    def _add_package(self, module, name=None):
        """Internal helper to update the packages dictionary with a module
        """
        if name is None or not isinstance(name, str):
            name = module.__name__
        if not isinstance(module, ModuleType):
            raise TypeError('Module passed is not a module.')
        self._packages[name] = module
        return


    def _add_package_by_name(self, name):
        """Internal helper to add a module to the internal list of packages.
        Returns True if succesful, false if unsuccesful."""
        module = Versions._safe_import_by_name(name)
        if not isinstance(module, mock.Mock):
            self._add_package(module, name)
            return True
        return False


    def add_packages(self, packages):
        if not isinstance(packages, (list, tuple)):
            raise TypeError('You must pass a list of packages or package names.')
        for pckg in packages:
            if isinstance(pckg, str):
                self._add_package_by_name(pckg)
            elif isinstance(pckg, ModuleType):
                self._add_package(pckg)
            elif pckg is None:
                pass
            else:
                raise TypeError('Cannot add package from type ({})'.format(type(pckg)))

    @property
    def platform(self):
        """Returns the system/OS name, e.g. ``'Linux'``, ``'Windows'``, or
        ``'Java'``. An empty string is returned if the value cannot be
        determined."""
        return platform.system()


    @property
    def cpu_count(self):
        """Return the number of CPUs in the system. May raise
        ``NotImplementedError``."""
        return multiprocessing.cpu_count()


    @property
    def sys_version(self):
        text = '\n'
        for txt in textwrap.wrap(sys.version, self.text_width-4):
            text += '  '+txt+'\n'
        return text


    def get_version(self, pckg):
        """Get the version of a package by passing the package or it's name"""
        # First, fetch the module and its name
        if isinstance(pckg, str):
            name = pckg
            try:
                module = self._packages[name]
            except KeyError:
                # This could raise an error if module not found
                module = Versions._safe_import_by_name(pckg)
        elif isinstance(pckg, ModuleType):
            name = pckg.__name__
            module = pckg
        else:
            raise TypeError('Cannot fetch version from type ({})'.format(type(pckg)))
        # Now get the version info from the module
        try:
            attr = VERSION_ATTRIBUTES[name]
            version = getattr(module, attr)
        except (KeyError, AttributeError):
            try:
                version = module.__version__
            except AttributeError:
                logging.warning('Varsion attribute for `{}` is unknown.'.format(name))
                version = 'unknown'
        return version


    def __repr__(self):
        r"""Plain-text version information."""

        # Width for text-version
        text = '\n' + self.text_width*'-' + '\n'

        # Date and time info as title
        text += time.strftime('  %a %b %d %H:%M:%S %Y %Z\n\n')

        # OS and CPUs
        text += '{:>15}'.format(self.platform)+' : OS\n'
        text += '{:>15}'.format(self.cpu_count)+' : CPU(s)\n'

        # Loop over packages
        for name in self._packages.keys():
            text += '{:>15} : {}\n'.format(self.get_version(name), name)

        # sys.version
        text += self.sys_version

        # mkl version
        if mklinfo:
            text += '\n'
            for txt in textwrap.wrap(mklinfo, self.text_width-4):
                text += '  '+txt+'\n'

        # Finish
        text += self.text_width*'-'

        return text

    def _repr_html_(self):
        """HTML-rendered version information."""

        # Define html-styles
        border = "border: 2px solid #fff;'"

        def colspan(html, txt, ncol, nrow):
            r"""Print txt in a row spanning whole table."""
            html += "  <tr>\n"
            html += "     <td style='text-align: center; "
            if nrow == 0:
                html += "font-weight: bold; font-size: 1.2em; "
            elif nrow % 2 == 0:
                html += "background-color: #ddd;"
            html += border + " colspan='"
            html += str(2*ncol)+"'>%s</td>\n" % txt
            html += "  </tr>\n"
            return html

        def cols(html, version, name, ncol, i):
            r"""Print package information in two cells."""

            # Check if we have to start a new row
            if i > 0 and i % ncol == 0:
                html += "  </tr>\n"
                html += "  <tr>\n"

            html += "    <td style='text-align: right; background-color: #ccc;"
            html += " " + border + ">%s</td>\n" % version

            html += "    <td style='text-align: left; "
            html += border + ">%s</td>\n" % name

            return html, i+1

        # Start html-table
        html = "<table style='border: 3px solid #ddd;'>\n"

        # Date and time info as title
        html = colspan(html, time.strftime('%a %b %d %H:%M:%S %Y %Z'),
                       self.ncol, 0)

        # OS and CPUs
        html += "  <tr>\n"
        html, i = cols(html, self.platform, 'OS', self.ncol, 0)
        html, i = cols(html, self.cpu_count, 'CPU(s)',
                       self.ncol, i)

        # Loop over packages
        for name in self._packages.keys():
            html, i = cols(html, self.get_version(name), name, self.ncol, i)
        # Fill up the row
        while i % self.ncol != 0:
            html += "    <td style= " + border + "></td>\n"
            html += "    <td style= " + border + "></td>\n"
            i += 1
        # Finish row
        html += "  </tr>\n"

        # sys.version
        html = colspan(html, sys.version, self.ncol, 1)

        # mkl version
        if mklinfo:
            html = colspan(html, mklinfo, self.ncol, 2)

        # Finish table
        html += "</table>"

        return html