#!/usr/bin/python
# -*- coding: utf-8 -*-

# (c) 2015, Matt Schreiber <schreibah () gmail.com>,
# <https://github.com/BaxterStockman>
#
# Based substantially on ini_file.py, (c) 2012, Jan-Piet Mens
# <jpmens () gmail.com>.
#
# Released under the same terms as Ansible itself, as reproduced below:
#
#   'Ansible is free software: you can redistribute it and/or modify it under
#   the terms of the GNU General Public License as published by the Free
#   Software Foundation, either version 3 of the License, or (at your option)
#   any later version.
#
#   You should have received a copy of the GNU General Public License along
#   with Ansible.  If not, see <http://www.gnu.org/licenses/>.'
#

DOCUMENTATION = '''
---
module: sabnzbd_config
short_description: Manage C(sabnzbd.ini)
extends_documentation_fragment: files
description:
     - Add, remove or update settings in the SABnzbd configuration file
       C(sabnzbd.ini) without needing to manage the whole shebang.
     - Supports a I(batch) mode for making multiple configuration changes in
       one go.
version_added: "1.9"
options:
  dest:
    description:
      - Path to C(sabnzbd.ini).
      - If this file does not already exist, it will be created.
    required: no
    default: C(/opt/sabnzbd/sabnzbd.ini)
  libdir:
    description:
      - Path to the SABnzbd Python libraries.
    required: no
    default: C(os.path.basename(/opt/sabnzbd))
  section:
    description:
      - The name of a C([section]) in C(sabnzbd.ini).
      - Will be ignored in batch mode.
    required: no
    default: null
  option:
    description:
      - The left side of an C(option = value) pair.
      - Will be ignored in batch mode and when deleting a whole section.
    required: no
    default: null
  value:
    description:
      - The right side of an C(option = value) pair
      - Will be ignored in batch mode and when deleting a whole section.
    required: no
    default: null
  settings:
    description:
      - A hash of settings that will be merged into C(sabnzbd.ini).
      - Top-level keys are section names, (almost) everything else is a
        C(option = value) pair (see the 'Notes' section for the exception).
  state:
    description:
      - The desired state of the section, option, or hash of settings.
      - If I(state) is I(absent) and I(option) is not defined, the entire
        I(section) will be removed.
      - In batch mode, the I(settings) hash is merged recursively into any
        existing SABnzbd options.  No state concerning I(settings) is
        maintained between plays, so if you accidentally included C(frob=nozzle)
        somewhere in your I(settings) hash, it's going to stay in
        C(sabnzbd.ini) until you remove it with C(state=absent), or manually.
    required: no
    default: "batch"
    choices: [ "present", "absent", "batch" ]
  backup:
    description:
      - Create a timestamped backup of the original C(sabnzbd.ini).
    required: no
    default: "no"
    choices: [ "yes", "no" ]
notes:
  - This module uses SABnzbd's library code for manipulating the
    configuration file, so SABnzbd must be installed and its libraries must
    be readable or the module will fail to run.
  - SABnzbd does a fair bit of internal twiddling between (1) loading the
    configuration file into a ConfigObj object, (2) translating configuration
    file settings into its own internal database settings, and (3) merging that
    database back into the ConfigObj object prior to writing out a new
    configuration file.  This twiddling includes, but is far from limited to,
    adding default values for the various C([categories]).  Rather than try to
    re-implement SABnzbd's internal logic, this module instead tries its
    hardest to rely on SABnzbd's own library routines.  But because so much of
    the munging logic just described occurs within subroutines that
    inextricably involve reading from and writing to disk, this module is very
    heavy on the I/O -- every C(sabnzbd_config) task involves at least two
    reads and two writes of C(sabnzbd.ini).  Batch mode helps cut down on this.
  - Final caution: this module does not preserve comments in the configuration
    file.

requirements: [ sabnzbd ]

author: Matt Schreiber U(https://github.com/BaxterStockman), based on Jan-Piet
        Miens' work on the M(ini_file) module.
'''

EXAMPLES = '''
# Change value of port and https_port in the [misc] section
- sabnzbd_config:
    dest: "/opt/sabnzbd/sabnzbd.ini"
    settings:
      misc:
        port: 9090
        https_port: 9095

# Delete the [growl] section
- sabnzbd_config:
    dest: "/opt/sabnzbd/sabnzbd.ini"
    section: growl
    ensure: absent

# Delete the 'priority' key from the [categories][[tv]] section
- sabnzbd_config:
    dest: "/opt/sabnzbd/sabnzbd.ini"
    section: categories
    option:
      tv: priority
    ensure: absent
'''

import os
import sys
import shutil
import tempfile

# ==============================================================
# SABnzbdConfigWrapper

class SABnzbdConfigWrapper(object):
    def __init__(self, module, filename, state='batch', libdir=None,
                 settings=None, section=None, option=None, value=None,
                 backup=False):
        self.module = module
        self.filename = filename
        self.state = state
        self.settings = settings
        self.option = option
        self.value = value
        self.section = section
        self.backup = backup

        # Backup filename for restoration in case of error
        self.temp_filename = tempfile.mktemp()

        # Try to create a backup file, ignoring errors errors, since the source
        # file might not exist yet.
        if not os.path.exists(self.temp_filename):
            try:
                shutil.copy2(filename, self.temp_filename)
            except (OSError, IOError):
                pass
            except Exception as err:
                self.module.fail_json(msg="Error backing up SABnzbd configuration %s: %s"
                                 % (filename, str(err)))

        self.set_operation(state)
        self.set_libdir(libdir)

        self.validate()

        try:
            sys.path.append(self.libdir)
            import sabnzbd.config
        except Exception as err:
            self.module.fail_json(msg="Can't load SABnzbd python libraries from %s: %s"
                                  % (libdir, str(err)))
        else:
            self.sabconfig = sabnzbd.config

        # Some versions of SABnzbd (e.g. the one available through jcfp's
        # Ubuntu PPA) don't fatpack configobj with the sabnzbd python
        # libraries.  These versions load configobj from the existing sys.path,
        # so we try that if the first import fails.
        try:
            import sabnzbd.utils.configobj
        except Exception:
            try:
                import configobj
            except Exception as err:
                self.module.fail_json(msg="Can't load the configobj python library: %s" % str(err))
            else:
                self.configobj = configobj
        else:
            self.configobj = sabnzbd.utils.configobj

    def cleanup(self, changed):
        if self.module.check_mode:
            # Try to restore backup file
            try:
                shutil.move(self.temp_filename, self.filename)
            except:
                # Assume that failure to restore the file indicates that no
                # backup was made because no file existed at the start of the
                # run.
                try:
                    os.remove(filename)
                except Exception as err:
                    self.module.fail_json(msg="Can't remove SABnzbd config file %s: %s"
                                          % (self.filename, str(err)))
            return changed
        else:
            if changed:
                if self.backup:
                    self.module.backup_local(filename)

                self.write_config()

            file_args = self.module.load_file_common_arguments(self.module.params)
            return self.module.set_fs_attributes_if_different(file_args, changed)

    def set_operation(self, state=None):
        if state is None:
            state = self.state

        if state == 'batch':
            self.operation = self.do_batch
        elif state == 'present':
            self.operation = self.do_present
        elif state == 'absent':
            self.operation = self.do_absent

    def set_libdir(self, libdir=None):
        if libdir is None:
            libdir = os.path.dirname(self.filename)
        self.libdir = libdir

    def validate(self):
        missing = []

        if self.state == 'batch':
            if not isinstance(self.settings, dict):
                missing.append('settings')
        elif self.state == 'present':
            if self.section is None:
                missing.append('section')
            if self.option is None:
                missing.append('option')
        elif self.state == 'absent':
            if self.section is None:
                missing.append('section')

        if missing:
            self.module.fail_json(msg="Missing required arguments: %s" %
                                  ','.join(missing))

    def run(self, *args, **kwargs):
        # Store initial config
        init_config_dict = self.get_config().dict()

        # Execute the operation.  Write out the configuration file, then
        # reload.  This is so that SABnzbd can do its internal twiddling with
        # configuration values, rather than reimplement all that here.
        self.operation(*args, **kwargs)
        self.write_config()
        new_config_dict = self.get_config(reload=True).dict()

        # Determine whether a change occurred
        changed = self.is_changed(init_config_dict, new_config_dict)

        # Write out the configuration, if not in check_mode
        return self.cleanup(changed)

    def read_config(self, filename=None, reload=False):
        if filename is None:
            filename = self.filename

        read_res = True
        read_msg = ''
        try:
            if reload:
                self.sabconfig.CFG.clear()

            read_res, read_msg = self.sabconfig.read_config(filename)

            if not read_res:
                raise IOError(filename)
        except Exception as err:
            self.module.fail_json(msg="Can't read SABnzbd config file %s: %s" %
                                (filename, str(err)))

        # Annoying, but probably better than trying to reimplement the
        # merging logic from sabnzbd.config.save_config()...
        self.save_config()

        return self.sabconfig.CFG

    def get_config(self, filename=None, reload=False):
        if filename is None:
            filename = self.filename

        if (not hasattr(self, 'config')) or reload:
            self.config = self.read_config(filename, reload)

        return self.config

    def write_config(self):
        try:
            self.config.write()
        except IOError as err:
            self.module.fail_json(msg="Failed to write SABnzbd configuration file %s: %s"
                             % (filename, str(err)))

    def save_config(self):
        """ Wrapper for sabnzbd.config.save_config().  Forces saving by setting
            sabnzbd.config.modified to True
        """

        # Do this or sabnzbd.config.save_config() method will exit immediately
        self.sabconfig.modified = True

        if not self.sabconfig.save_config():
            self.module.fail_json(msg="Can't save SABnzbd config file %s" %
                                  self.filename)

        return True

    def is_changed(self, left, right):
        """ Nothing more complicated ATM
        """
        return (cmp(left, right) != 0)

    def do_present(self, settings=None, section=None, option=None, value=None, config=None):
        if config is None:
            config = self.get_config()

        try:
            config[section].merge({option: value})
        except KeyError:
            config[section] = {option: value}

    def do_absent(self, settings=None, section=None, option=None, value=None, config=None):
        if config is None:
            config = self.get_config()

        section_obj = None
        try:
            section_obj = config[section]
        except KeyError:
            return

        if option is None:
            del config[section]
        else:
            if isinstance(option, dict):
                for key, value in option.iteritems():
                    self.do_absent(section=key, option=value, config=section_obj)
            elif hasattr(option, '__iter__'):
                for key in option:
                    self.do_absent(section=key, option=value, config=section_obj)
            elif isinstance(option, basestring):
                self.do_absent(section=option, config=section_obj)
            else:
                self.module.fail_json(msg="Don't understand how to handle option type: %s" %
                                      option.__class__.__name__)

    def do_batch(self, settings=None, section=None, option=None, value=None, config=None):
        if settings is None:
            settings = self.settings

        # Now merge the wanted settings and compare
        self.get_config().merge(self.settings)


# ==============================================================
# main

def main():
    module = AnsibleModule(
        argument_spec = dict(
            dest     = dict(required=True),
            libdir   = dict(required=False),
            settings = dict(required=False, type='dict'),
            section  = dict(required=False, type='str'),
            option   = dict(required=False),
            value    = dict(required=False),
            backup   = dict(default='no', type='bool'),
            state    = dict(default='batch', choices=['batch', 'absent', 'present'])
        ),
        add_file_common_args = True,
        supports_check_mode = True
    )

    dest = os.path.expanduser(module.params['dest'])
    libdir = None
    if module.params['libdir'] is not None:
        libdir = os.path.expanduser(module.params['libdir'])
    section = module.params['section']
    option = module.params['option']
    value = module.params['value']
    settings = module.params['settings']
    state = module.params['state']
    backup = module.params['backup']

    config = SABnzbdConfigWrapper(module, dest, libdir=libdir, section=section,
                                  option=option, value=value,
                                  settings=settings, state=state,
                                  backup=backup)

    changed = config.run(section=section, option=option, value=value, settings=settings)

    module.exit_json(dest=dest, changed=changed, msg="OK")

# import module snippets
from ansible.module_utils.basic import *

if __name__ == '__main__':
    main()
