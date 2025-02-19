# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2009- Spyder Project Contributors
#
# Distributed under the terms of the MIT License
# (see spyder/__init__.py for details)
# -----------------------------------------------------------------------------


"""
Client widget for the IPython Console.

This is the widget used on all its tabs.
"""


# Standard library imports.
# Fix for spyder-ide/spyder#1356.
from __future__ import absolute_import

import codecs
import os
import os.path as osp
from string import Template
import time

# Third party imports (qtpy)
from qtpy.QtCore import QUrl, QTimer, Signal, Slot, QThread
from qtpy.QtGui import QKeySequence
from qtpy.QtWidgets import (QHBoxLayout, QLabel, QMenu, QMessageBox,
                            QToolButton, QVBoxLayout, QWidget)

# Local imports
from spyder.api.config.mixins import SpyderConfigurationAccessor
from spyder.config.base import (_, get_module_source_path,
                                running_under_pytest)
from spyder.utils.icon_manager import ima
from spyder.utils import sourcecode
from spyder.utils.image_path_manager import get_image_path
from spyder.utils.encoding import get_coding
from spyder.utils.environ import RemoteEnvDialog
from spyder.utils.palette import QStylePalette
from spyder.utils.programs import get_temp_dir
from spyder.utils.qthelpers import (add_actions, create_action,
                                    create_toolbutton, DialogManager,
                                    MENU_SEPARATOR)
from spyder.py3compat import to_text_string
from spyder.plugins.ipythonconsole.widgets import ShellWidget
from spyder.utils.stylesheet import PANES_TABBAR_STYLESHEET
from spyder.widgets.collectionseditor import CollectionsEditor
from spyder.widgets.mixins import SaveHistoryMixin


#-----------------------------------------------------------------------------
# Templates
#-----------------------------------------------------------------------------
# Using the same css file from the Help plugin for now. Maybe
# later it'll be a good idea to create a new one.
PLUGINS_PATH = get_module_source_path('spyder', 'plugins')

CSS_PATH = osp.join(PLUGINS_PATH, 'help', 'utils', 'static', 'css')
TEMPLATES_PATH = osp.join(PLUGINS_PATH, 'ipythonconsole', 'assets', 'templates')

BLANK = open(osp.join(TEMPLATES_PATH, 'blank.html')).read()
LOADING = open(osp.join(TEMPLATES_PATH, 'loading.html')).read()
KERNEL_ERROR = open(osp.join(TEMPLATES_PATH, 'kernel_error.html')).read()

try:
    time.monotonic  # time.monotonic new in 3.3
except AttributeError:
    time.monotonic = time.time


#-----------------------------------------------------------------------------
# Client widget
#-----------------------------------------------------------------------------
class ClientWidget(QWidget, SaveHistoryMixin, SpyderConfigurationAccessor):
    """
    Client widget for the IPython Console

    This widget is necessary to handle the interaction between the
    plugin and each shell widget.
    """

    sig_append_to_history_requested = Signal(str, str)

    CONF_SECTION = 'ipython_console'
    SEPARATOR = '{0}## ---({1})---'.format(os.linesep*2, time.ctime())
    INITHISTORY = ['# -*- coding: utf-8 -*-',
                   '# *** Spyder Python Console History Log ***',]

    def __init__(self, plugin, id_,
                 history_filename, config_options,
                 additional_options, interpreter_versions,
                 connection_file=None, hostname=None,
                 menu_actions=None, slave=False,
                 is_external_kernel=False,
                 is_spyder_kernel=True,
                 given_name=None,
                 options_button=None,
                 show_elapsed_time=False,
                 reset_warning=True,
                 ask_before_restart=True,
                 ask_before_closing=False,
                 css_path=None):
        super(ClientWidget, self).__init__(plugin)
        SaveHistoryMixin.__init__(self, history_filename)

        # --- Init attrs
        self.plugin = plugin
        self.id_ = id_
        self.connection_file = connection_file
        self.hostname = hostname
        self.menu_actions = menu_actions
        self.slave = slave
        self.given_name = given_name
        self.show_elapsed_time = show_elapsed_time
        self.reset_warning = reset_warning
        self.ask_before_restart = ask_before_restart
        self.ask_before_closing = ask_before_closing

        # --- Other attrs
        self.options_button = options_button
        self.stop_button = None
        self.reset_button = None
        self.stop_icon = ima.icon('stop')
        self.history = []
        self.allow_rename = True
        self.stderr_dir = None
        self.is_error_shown = False
        self.restart_thread = None
        self.give_focus = True

        if css_path is None:
            self.css_path = CSS_PATH
        else:
            self.css_path = css_path

        # --- Widgets
        self.shellwidget = ShellWidget(config=config_options,
                                       ipyclient=self,
                                       additional_options=additional_options,
                                       interpreter_versions=interpreter_versions,
                                       is_external_kernel=is_external_kernel,
                                       is_spyder_kernel=is_spyder_kernel,
                                       local_kernel=True)

        self.infowidget = plugin.infowidget
        self.blank_page = self._create_blank_page()
        self.loading_page = self._create_loading_page()
        # To keep a reference to the page to be displayed
        # in infowidget
        self.info_page = None
        self._before_prompt_is_ready()

        # Elapsed time
        self.time_label = None
        self.t0 = time.monotonic()
        self.timer = QTimer(self)
        self.show_time_action = create_action(self, _("Show elapsed time"),
                                         toggled=self.set_elapsed_time_visible)

        # --- Layout
        self.layout = QVBoxLayout()
        toolbar_buttons = self.get_toolbar_buttons()

        hlayout = QHBoxLayout()
        hlayout.addWidget(self.create_time_label())
        hlayout.addStretch(0)
        for button in toolbar_buttons:
            hlayout.addWidget(button)

        self.layout.addLayout(hlayout)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.addWidget(self.shellwidget)
        self.layout.addWidget(self.infowidget)
        self.setLayout(self.layout)

        # --- Exit function
        self.exit_callback = lambda: plugin.close_client(client=self)

        # --- Dialog manager
        self.dialog_manager = DialogManager()

        # Show timer
        self.update_time_label_visibility()

        # Poll for stderr changes
        self.stderr_mtime = 0
        self.stderr_timer = QTimer(self)
        self.stderr_timer.timeout.connect(self.poll_stderr_file_change)
        self.stderr_timer.setInterval(1000)
        self.stderr_timer.start()

    def __del__(self):
        """Close threads to avoid segfault"""
        if (self.restart_thread is not None
                and self.restart_thread.isRunning()):
            self.restart_thread.wait()

    #------ Public API --------------------------------------------------------
    @property
    def kernel_id(self):
        """Get kernel id"""
        if self.connection_file is not None:
            json_file = osp.basename(self.connection_file)
            return json_file.split('.json')[0]

    @property
    def stderr_file(self):
        """Filename to save kernel stderr output."""
        stderr_file = None
        if self.connection_file is not None:
            stderr_file = self.kernel_id + '.stderr'
            if self.stderr_dir is not None:
                stderr_file = osp.join(self.stderr_dir, stderr_file)
            else:
                try:
                    stderr_file = osp.join(get_temp_dir(), stderr_file)
                except (IOError, OSError):
                    stderr_file = None
        return stderr_file

    @property
    def stderr_handle(self):
        """Get handle to stderr_file."""
        if self.stderr_file is not None:
            # Needed to prevent any error that could appear.
            # See spyder-ide/spyder#6267.
            try:
                handle = codecs.open(self.stderr_file, 'w', encoding='utf-8')
            except Exception:
                handle = None
        else:
            handle = None

        return handle

    def remove_stderr_file(self):
        """Remove stderr_file associated with the client."""
        try:
            # Defer closing the stderr_handle until the client
            # is closed because jupyter_client needs it open
            # while it tries to restart the kernel
            self.stderr_handle.close()
            os.remove(self.stderr_file)
        except Exception:
            pass

    def get_stderr_contents(self):
        """Get the contents of the stderr kernel file."""
        try:
            stderr = self._read_stderr()
        except Exception:
            stderr = None
        return stderr

    @Slot()
    def poll_stderr_file_change(self):
        """Check if the stderr file just changed"""
        try:
            mtime = os.stat(self.stderr_file).st_mtime
        except Exception:
            return

        if mtime == self.stderr_mtime:
            return
        self.stderr_mtime = mtime
        stderr = self.get_stderr_contents()
        if stderr:
            self.shellwidget._append_plain_text(
                '\n' + stderr, before_prompt=True)

    def configure_shellwidget(self, give_focus=True):
        """Configure shellwidget after kernel is connected."""
        self.give_focus = give_focus

        # Make sure the kernel sends the comm config over
        self.shellwidget.call_kernel()._send_comm_config()

        # Set exit callback
        self.shellwidget.set_exit_callback()

        # To save history
        self.shellwidget.executing.connect(self.add_to_history)

        # For Mayavi to run correctly
        self.shellwidget.executing.connect(
            self.shellwidget.set_backend_for_mayavi)

        # To update history after execution
        self.shellwidget.executed.connect(self.update_history)

        # To update the Variable Explorer after execution
        self.shellwidget.executed.connect(
            self.shellwidget.refresh_namespacebrowser)

        # To enable the stop button when executing a process
        self.shellwidget.executing.connect(self.enable_stop_button)

        # To disable the stop button after execution stopped
        self.shellwidget.executed.connect(self.disable_stop_button)

        # To show kernel restarted/died messages
        self.shellwidget.sig_kernel_restarted_message.connect(
            self.kernel_restarted_message)
        self.shellwidget.sig_kernel_restarted.connect(
            self._finalise_restart)

        # To correctly change Matplotlib backend interactively
        self.shellwidget.executing.connect(
            self.shellwidget.change_mpl_backend)

        # To show env and sys.path contents
        self.shellwidget.sig_show_syspath.connect(self.show_syspath)
        self.shellwidget.sig_show_env.connect(self.show_env)

        # To sync with working directory toolbar
        self.shellwidget.executed.connect(self.shellwidget.update_cwd)

        # To apply style
        self.set_color_scheme(self.shellwidget.syntax_style, reset=False)

    def add_to_history(self, command):
        """Add command to history"""
        if self.shellwidget.is_debugging():
            return
        return super(ClientWidget, self).add_to_history(command)

    def _before_prompt_is_ready(self):
        """Configure shellwidget before kernel is connected."""
        self._show_loading_page()
        self.shellwidget.sig_prompt_ready.connect(
            self._when_prompt_is_ready)
        # If remote execution, the loading page should be hidden as well
        self.shellwidget.sig_remote_execute.connect(
            self._when_prompt_is_ready)

    def _when_prompt_is_ready(self):
        """Configuration after the prompt is shown."""
        # To hide the loading page
        self._hide_loading_page()

        # Show possible errors when setting Matplotlib backend
        self._show_mpl_backend_errors()

        # To show if special console is valid
        self._check_special_console_error()

        self.shellwidget.sig_prompt_ready.disconnect(
            self._when_prompt_is_ready)
        self.shellwidget.sig_remote_execute.disconnect(
            self._when_prompt_is_ready)

        # It's necessary to do this at this point to avoid giving
        # focus to _control at startup.
        self._connect_control_signals()

        if self.give_focus:
            self.shellwidget._control.setFocus()

    def enable_stop_button(self):
        self.stop_button.setEnabled(True)

    def disable_stop_button(self):
        # This avoids disabling automatically the button when
        # re-running files on dedicated consoles.
        # See spyder-ide/spyder#5958.
        if not self.shellwidget._executing:
            # This avoids disabling the button while debugging
            # see spyder-ide/spyder#13283
            if not self.shellwidget.is_waiting_pdb_input():
                self.stop_button.setDisabled(True)
            else:
                self.stop_button.setEnabled(True)

    @Slot()
    def stop_button_click_handler(self):
        """Method to handle what to do when the stop button is pressed"""
        self.stop_button.setDisabled(True)
        # Interrupt computations or stop debugging
        if not self.shellwidget.is_waiting_pdb_input():
            self.interrupt_kernel()
        else:
            self.shellwidget.pdb_execute_command('exit')

    def show_kernel_error(self, error):
        """Show kernel initialization errors in infowidget."""
        # Replace end of line chars with <br>
        eol = sourcecode.get_eol_chars(error)
        if eol:
            error = error.replace(eol, '<br>')

        # Don't break lines in hyphens
        # From https://stackoverflow.com/q/7691569/438386
        error = error.replace('-', '&#8209')

        # Create error page
        message = _("An error ocurred while starting the kernel")
        kernel_error_template = Template(KERNEL_ERROR)
        self.info_page = kernel_error_template.substitute(
            css_path=self.css_path,
            message=message,
            error=error)

        # Show error
        self.set_info_page()
        self.shellwidget.hide()
        self.infowidget.show()

        # Tell the client we're in error mode
        self.is_error_shown = True

    def get_name(self):
        """Return client name"""
        if self.given_name is None:
            # Name according to host
            if self.hostname is None:
                name = _("Console")
            else:
                name = self.hostname
            # Adding id to name
            client_id = self.id_['int_id'] + u'/' + self.id_['str_id']
            name = name + u' ' + client_id
        elif self.given_name in ["Pylab", "SymPy", "Cython"]:
            client_id = self.id_['int_id'] + u'/' + self.id_['str_id']
            name = self.given_name + u' ' + client_id
        else:
            name = self.given_name + u'/' + self.id_['str_id']
        return name

    def get_control(self):
        """Return the text widget (or similar) to give focus to"""
        # page_control is the widget used for paging
        page_control = self.shellwidget._page_control
        if page_control and page_control.isVisible():
            return page_control
        else:
            return self.shellwidget._control

    def get_kernel(self):
        """Get kernel associated with this client"""
        return self.shellwidget.kernel_manager

    def get_options_menu(self):
        """Return options menu"""
        env_action = create_action(
                        self,
                        _("Show environment variables"),
                        icon=ima.icon('environ'),
                        triggered=self.shellwidget.request_env
                     )

        syspath_action = create_action(
                            self,
                            _("Show sys.path contents"),
                            icon=ima.icon('syspath'),
                            triggered=self.shellwidget.request_syspath
                         )

        self.show_time_action.setChecked(self.show_elapsed_time)
        additional_actions = [MENU_SEPARATOR,
                              env_action,
                              syspath_action,
                              self.show_time_action]

        if self.menu_actions is not None:
            console_menu = self.menu_actions + additional_actions
            return console_menu

        else:
            return additional_actions

    def get_toolbar_buttons(self):
        """Return toolbar buttons list."""
        buttons = []

        # Code to add the stop button
        if self.stop_button is None:
            self.stop_button = create_toolbutton(
                                   self,
                                   text=_("Stop"),
                                   icon=self.stop_icon,
                                   tip=_("Stop the current command"))
            self.disable_stop_button()
            # set click event handler
            self.stop_button.clicked.connect(self.stop_button_click_handler)
        if self.stop_button is not None:
            buttons.append(self.stop_button)
        self.stop_button.setStyleSheet(str(PANES_TABBAR_STYLESHEET))

        # Reset namespace button
        if self.reset_button is None:
            self.reset_button = create_toolbutton(
                                    self,
                                    text=_("Remove"),
                                    icon=ima.icon('editdelete'),
                                    tip=_("Remove all variables"),
                                    triggered=self.reset_namespace)
        if self.reset_button is not None:
            buttons.append(self.reset_button)
        self.reset_button.setStyleSheet(str(PANES_TABBAR_STYLESHEET))
        if self.options_button is None:
            options = self.get_options_menu()
            if options:
                self.options_button = create_toolbutton(self,
                        text=_('Options'), icon=ima.icon('tooloptions'))
                self.options_button.setPopupMode(QToolButton.InstantPopup)
                menu = QMenu(self)
                add_actions(menu, options)
                self.options_button.setMenu(menu)
        if self.options_button is not None:
            buttons.append(self.options_button)

        return buttons

    def add_actions_to_context_menu(self, menu):
        """Add actions to IPython widget context menu"""
        inspect_action = create_action(
            self,
            _("Inspect current object"),
            QKeySequence(self.get_shortcut('inspect current object')),
            icon=ima.icon('MessageBoxInformation'),
            triggered=self.inspect_object)

        clear_line_action = create_action(
            self,
            _("Clear line or block"),
            QKeySequence(self.get_shortcut('clear line')),
            triggered=self.clear_line)

        reset_namespace_action = create_action(
            self,
            _("Remove all variables"),
            QKeySequence(self.get_shortcut('reset namespace')),
            icon=ima.icon('editdelete'),
            triggered=self.reset_namespace)

        clear_console_action = create_action(
            self,
            _("Clear console"),
            QKeySequence(self.get_shortcut('clear shell')),
            triggered=self.clear_console)

        quit_action = create_action(
            self,
            _("&Quit"),
            icon=ima.icon('exit'),
            triggered=self.exit_callback)

        add_actions(menu, (None, inspect_action, clear_line_action,
                           clear_console_action, reset_namespace_action,
                           None, quit_action))
        return menu

    def set_font(self, font):
        """Set IPython widget's font"""
        self.shellwidget._control.setFont(font)
        self.shellwidget.font = font

    def set_color_scheme(self, color_scheme, reset=True):
        """Set IPython color scheme."""
        # Needed to handle not initialized kernel_client
        # See spyder-ide/spyder#6996.
        try:
            self.shellwidget.set_color_scheme(color_scheme, reset)
        except AttributeError:
            pass

    def shutdown(self):
        """Shutdown kernel"""
        if self.get_kernel() is not None and not self.slave:
            self.shellwidget.shutdown()

    def close(self):
        """Close client"""
        self.shellwidget.will_close(
            self.get_kernel() is None or self.slave)
        super(ClientWidget, self).close()

    def interrupt_kernel(self):
        """Interrupt the associanted Spyder kernel if it's running"""
        # Needed to prevent a crash when a kernel is not running.
        # See spyder-ide/spyder#6299.
        try:
            self.shellwidget.request_interrupt_kernel()
        except RuntimeError:
            pass

    @Slot()
    def restart_kernel(self):
        """
        Restart the associated kernel.

        Took this code from the qtconsole project
        Licensed under the BSD license
        """
        sw = self.shellwidget

        if not running_under_pytest() and self.ask_before_restart:
            message = _('Are you sure you want to restart the kernel?')
            buttons = QMessageBox.Yes | QMessageBox.No
            result = QMessageBox.question(self, _('Restart kernel?'),
                                          message, buttons)
        else:
            result = None

        if (result == QMessageBox.Yes or
                running_under_pytest() or
                not self.ask_before_restart):
            if sw.kernel_manager:
                if self.infowidget.isVisible():
                    self.infowidget.hide()

                if self._abort_kernel_restart():
                    sw.spyder_kernel_comm.close()
                    return

                self._show_loading_page()

                # Close comm
                sw.spyder_kernel_comm.close()

                # Stop autorestart mechanism
                sw.kernel_manager.stop_restarter()
                sw.kernel_manager.autorestart = False

                # Create and run restarting thread
                if (self.restart_thread is not None
                        and self.restart_thread.isRunning()):
                    self.restart_thread.finished.disconnect()
                    self.restart_thread.terminate()
                    self.restart_thread.wait()
                self.restart_thread = QThread()
                self.restart_thread.run = self._restart_thread_main
                self.restart_thread.error = None
                self.restart_thread.finished.connect(
                    lambda: self._finalise_restart(True))
                self.restart_thread.start()

            else:
                sw._append_plain_text(
                    _('Cannot restart a kernel not started by Spyder\n'),
                    before_prompt=True
                )
                self._hide_loading_page()

    def _restart_thread_main(self):
        """Restart the kernel in a thread."""
        try:
            self.shellwidget.kernel_manager.restart_kernel(
                stderr=self.stderr_handle)
        except RuntimeError as e:
            self.restart_thread.error = e

    def _finalise_restart(self, reset=False):
        """Finishes the restarting of the kernel."""
        sw = self.shellwidget

        if self._abort_kernel_restart():
            sw.spyder_kernel_comm.close()
            return

        if self.restart_thread and self.restart_thread.error is not None:
            sw._append_plain_text(
                _('Error restarting kernel: %s\n') % self.restart_thread.error,
                before_prompt=True
            )
        else:
            # Reset Pdb state and reopen comm
            sw._pdb_in_loop = False
            sw.spyder_kernel_comm.remove()
            sw.spyder_kernel_comm.open_comm(sw.kernel_client)

            # Start autorestart mechanism
            sw.kernel_manager.autorestart = True
            sw.kernel_manager.start_restarter()

            # For spyder-ide/spyder#6235, IPython was changing the
            # setting of %colors on windows by assuming it was using a
            # dark background. This corrects it based on the scheme.
            self.set_color_scheme(sw.syntax_style, reset=reset)
            sw._append_html(_("<br>Restarting kernel...<br>"),
                            before_prompt=True)
            sw.insert_horizontal_ruler()

        self._hide_loading_page()
        self.stop_button.setDisabled(True)
        self.restart_thread = None

    @Slot(str)
    def kernel_restarted_message(self, msg):
        """Show kernel restarted/died messages."""
        if not self.is_error_shown:
            # If there are kernel creation errors, jupyter_client will
            # try to restart the kernel and qtconsole prints a
            # message about it.
            # So we read the kernel's stderr_file and display its
            # contents in the client instead of the usual message shown
            # by qtconsole.
            stderr = self.get_stderr_contents()
            if stderr:
                self.show_kernel_error('<tt>%s</tt>' % stderr)
        else:
            self.shellwidget._append_html("<br>%s<hr><br>" % msg,
                                          before_prompt=False)

    @Slot()
    def inspect_object(self):
        """Show how to inspect an object with our Help plugin"""
        self.shellwidget._control.inspect_current_object()

    @Slot()
    def clear_line(self):
        """Clear a console line"""
        self.shellwidget._keyboard_quit()

    @Slot()
    def clear_console(self):
        """Clear the whole console"""
        self.shellwidget.clear_console()

    @Slot()
    def reset_namespace(self):
        """Resets the namespace by removing all names defined by the user"""
        self.shellwidget.reset_namespace(warning=self.reset_warning,
                                         message=True)

    def update_history(self):
        self.history = self.shellwidget._history

    @Slot(object)
    def show_syspath(self, syspath):
        """Show sys.path contents."""
        if syspath is not None:
            editor = CollectionsEditor(self)
            editor.setup(syspath, title="sys.path contents", readonly=True,
                         icon=ima.icon('syspath'))
            self.dialog_manager.show(editor)
        else:
            return

    @Slot(object)
    def show_env(self, env):
        """Show environment variables."""
        self.dialog_manager.show(RemoteEnvDialog(env, parent=self))

    def create_time_label(self):
        """Create elapsed time label widget (if necessary) and return it"""
        if self.time_label is None:
            self.time_label = QLabel()
        return self.time_label

    def show_time(self, end=False):
        """Text to show in time_label."""
        if self.time_label is None:
            return

        elapsed_time = time.monotonic() - self.t0
        # System time changed to past date, so reset start.
        if elapsed_time < 0:
            self.t0 = time.monotonic()
            elapsed_time = 0
        if elapsed_time > 24 * 3600:  # More than a day...!
            fmt = "%d %H:%M:%S"
        else:
            fmt = "%H:%M:%S"
        if end:
            color = QStylePalette.COLOR_TEXT_3
        else:
            color = QStylePalette.COLOR_ACCENT_4
        text = "<span style=\'color: %s\'><b>%s" \
               "</b></span>" % (color,
                                time.strftime(fmt, time.gmtime(elapsed_time)))
        self.time_label.setText(text)

    def update_time_label_visibility(self):
        """Update elapsed time visibility."""
        self.time_label.setVisible(self.show_elapsed_time)

    @Slot(bool)
    def set_elapsed_time_visible(self, state):
        """Slot to show/hide elapsed time label."""
        self.show_elapsed_time = state
        if self.time_label is not None:
            self.time_label.setVisible(state)

    def set_info_page(self):
        """Set current info_page."""
        if self.info_page is not None:
            self.infowidget.setHtml(
                self.info_page,
                QUrl.fromLocalFile(self.css_path)
            )

    #------ Private API -------------------------------------------------------
    def _create_loading_page(self):
        """Create html page to show while the kernel is starting"""
        loading_template = Template(LOADING)
        loading_img = get_image_path('loading_sprites')
        if os.name == 'nt':
            loading_img = loading_img.replace('\\', '/')
        message = _("Connecting to kernel...")
        page = loading_template.substitute(css_path=self.css_path,
                                           loading_img=loading_img,
                                           message=message)
        return page

    def _create_blank_page(self):
        """Create html page to show while the kernel is starting"""
        loading_template = Template(BLANK)
        page = loading_template.substitute(css_path=self.css_path)
        return page

    def _show_loading_page(self):
        """Show animation while the kernel is loading."""
        self.shellwidget.hide()
        self.infowidget.show()
        self.info_page = self.loading_page
        self.set_info_page()

    def _hide_loading_page(self):
        """Hide animation shown while the kernel is loading."""
        self.infowidget.hide()
        self.info_page = self.blank_page
        self.set_info_page()
        self.shellwidget.show()

    def _read_stderr(self):
        """Read the stderr file of the kernel."""
        # We need to read stderr_file as bytes to be able to
        # detect its encoding with chardet
        f = open(self.stderr_file, 'rb')

        try:
            stderr_text = f.read()

            # This is needed to avoid showing an empty error message
            # when the kernel takes too much time to start.
            # See spyder-ide/spyder#8581.
            if not stderr_text:
                return ''

            # This is needed since the stderr file could be encoded
            # in something different to utf-8.
            # See spyder-ide/spyder#4191.
            encoding = get_coding(stderr_text)
            stderr_text = to_text_string(stderr_text, encoding)
            return stderr_text
        finally:
            f.close()

    def _show_mpl_backend_errors(self):
        """
        Show possible errors when setting the selected Matplotlib backend.
        """
        if self.shellwidget.is_spyder_kernel:
            self.shellwidget.call_kernel().show_mpl_backend_errors()

    def _check_special_console_error(self):
        """Check if the dependecies for special consoles are available."""
        self.shellwidget.call_kernel(
            callback=self._show_special_console_error
            ).is_special_kernel_valid()

    def _show_special_console_error(self, missing_dependency):
        if missing_dependency is not None:
            error_message = _(
                "Your Python environment or installation doesn't have the "
                "<tt>{missing_dependency}</tt> module installed or it "
                "occurred a problem importing it. Due to that, it is not "
                "possible for Spyder to create this special console for "
                "you."
            ).format(missing_dependency=missing_dependency)

            self.show_kernel_error(error_message)

    def _abort_kernel_restart(self):
        """
        Abort kernel restart if there are errors while starting it.

        We also ignore errors about comms, which are irrelevant.
        """
        stderr = self.get_stderr_contents()
        if stderr and 'No such comm' not in stderr:
            return True
        else:
            return False

    def _connect_control_signals(self):
        """Connect signals of control widgets."""
        control = self.shellwidget._control
        page_control = self.shellwidget._page_control

        control.sig_focus_changed.connect(
            lambda: self.plugin.sig_focus_changed.emit())
        page_control.sig_focus_changed.connect(
            lambda: self.plugin.sig_focus_changed.emit())
        control.sig_visibility_changed.connect(self.plugin.refresh_plugin)
        page_control.sig_visibility_changed.connect(self.plugin.refresh_plugin)
        page_control.sig_show_find_widget_requested.connect(
            self.plugin.find_widget.show)