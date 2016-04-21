##
# The MIT License (MIT)
#
# Copyright (c) 2016 Stefan Wendler
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
##

"""
2016-03-16, sw@kaltpost.de

Simple file shell for Micropython.

For usage details see the README.md
"""

import io
import cmd
import os
import sys
import argparse
import colorama

from serial.tools.miniterm import Miniterm, console, CONVERT_CRLF, NEWLINE_CONVERISON_MAP
from mp.mpfexp import MpFileExplorer
from mp.mpfexp import RemoteIOError
from mp.pyboard import PyboardError


class MpTerminal(Miniterm):

    def __init__(self, serial):

        self.serial = serial
        self.echo = False
        self.repr_mode = 0
        self.convert_outgoing = CONVERT_CRLF
        self.newline = NEWLINE_CONVERISON_MAP[self.convert_outgoing]
        self.dtr_state = True
        self.rts_state = True
        self.break_state = False


class MpFileShell(cmd.Cmd):

    intro = '\n' + colorama.Fore.GREEN + \
            '** Micropython File Shell v0.2, 2016 sw@kaltpost.de ** ' + \
            colorama.Fore.RESET + '\n'

    prompt = colorama.Fore.BLUE + "mpfs [" + \
             colorama.Fore.YELLOW + "/" + \
             colorama.Fore.BLUE + "]> " + colorama.Fore.RESET

    def __init__(self):

        cmd.Cmd.__init__(self)
        self.fe = None

    def __del__(self):

        self.__disconnect()

    def __set_prompt_path(self):

        self.prompt = colorama.Fore.BLUE + "mpfs [" + \
                      colorama.Fore.YELLOW + self.fe.pwd() + \
                      colorama.Fore.BLUE + "]> " + colorama.Fore.RESET

    def __error(self, msg):

        print('\n' + colorama.Fore.RED + msg + colorama.Fore.RESET + '\n')
        # sys.stderr.write("\n" + msg + "\n\n")

    def __connect(self, port):

        try:
            self.__disconnect()
            self.fe = MpFileExplorer(port)
        except PyboardError as e:
            self.__error(str(e[-1]))

    def __disconnect(self):

        if self.fe is not None:
            try:
                self.fe.close()
                self.fe = None
            except RemoteIOError as e:
                self.__error(str(e))

    def __is_open(self):

        if self.fe is None:
            self.__error("Not connected to device. Use 'open' first.")
            return False

        return True

    def do_exit(self, args):
        """exit
        Exit this shell.
        """

        return True

    do_EOF = do_exit

    def do_open(self, args):
        """open <PORT>
        Open connection to device with given serial port.
        """

        if not len(args):
            self.__error("Missing argument: <PORT>")
        else:
            self.__connect(args)

    def do_close(self, args):
        """close
        Close connection to device.
        """

        self.__disconnect()

    def do_ls(self, args):
        """ls
        List remote files.
        """

        if self.__is_open():
            try:
                files = self.fe.ls(add_details=True)

                print("\nRemote files in '%s':\n" % self.fe.pwd())

                for elem, type in files:
                    if type == 'F':
                        print(colorama.Fore.CYAN + (" [%s] %s" % (type, elem)) + colorama.Fore.RESET)
                    else:
                        print(colorama.Fore.MAGENTA + (" [%s] %s" % (type, elem)) + colorama.Fore.RESET)

                print("")

            except IOError as e:
                self.__error(str(e))

    def do_pwd(self, args):
        """pwd
         Print current remote directory.
         """

        print(self.fe.pwd())

    def do_cd(self, args):
        """cd <TARGET DIR>
        Change current remote directory to given target.
        """
        if not len(args):
            self.__error("Missing argument: <REMOTE DIR>")
        elif self.__is_open():
            try:
                self.fe.cd(args)
                self.__set_prompt_path()
            except IOError as e:
                self.__error(str(e))

    def complete_cd(self, *args):

        try:
            files = self.fe.ls(add_files=False)
        except Exception:
            files = []

        return [i for i in files if i.startswith(args[0])]

    def do_md(self, args):
        """md <TARGET DIR>
        Create new remote directory.
        """
        if not len(args):
            self.__error("Missing argument: <REMOTE DIR>")
        elif self.__is_open():
            try:
                self.fe.md(args)
            except IOError as e:
                self.__error(str(e))

    def do_lls(self, args):
        """lls
        List files in current local directory.
        """

        files = os.listdir(".")

        print("\nLocal files:\n")

        for f in files:
            print(" %s" % f)

        print("")

    def do_lcd(self, args):
        """lcd <TARGET DIR>
        Change current local directory to given target.
        """

        if not len(args):
            self.__error("Missing argument: <TARGET DIR>")
        else:
            try:
                os.chdir(args)
            except OSError as e:
                self.__error(str(e).split("] ")[-1])

    def complete_lcd(self, *args):
        dirs = [o for o in os.listdir(".") if os.path.isdir(os.path.join(".", o))]
        return [i for i in dirs if i.startswith(args[0])]

    def do_lpwd(self, args):
        """lpwd
        Print current local directory.
        """

        print(os.getcwd())

    def do_put(self, args):
        """put <LOCAL FILE> [<REMOTE FILE>]
        Upload local file. If the second parameter is given,
        its value is used for the remote file name. Otherwise the
        remote file will be named the same as the local file.
        """

        if not len(args):
            self.__error("Missing arguments: <LOCAL FILE> [<REMOTE FILE>]")

        elif self.__is_open():
            s_args = args.split(" ")

            lfile_name = s_args[0]

            if len(s_args) > 1:
                rfile_name = s_args[1]
            else:
                rfile_name = lfile_name

            try:
                self.fe.put(lfile_name, rfile_name)
            except IOError as e:
                self.__error(str(e))

    def complete_put(self, *args):
        files = [o for o in os.listdir(".") if os.path.isfile(os.path.join(".", o))]
        return [i for i in files if i.startswith(args[0])]

    def do_get(self, args):
        """get <REMOTE FILE> [<LOCAL FILE>]
        Download remote file. If the second parameter is given,
        its value is used for the local file name. Otherwise the
        locale file will be named the same as the remote file.
        """

        if not len(args):
            self.__error("Missing arguments: <REMOTE FILE> [<LOCAL FILE>]")
        elif self.__is_open():

            s_args = args.split(" ")

            rfile_name = s_args[0]

            if len(s_args) > 1:
                lfile_name = s_args[1]
            else:
                lfile_name = rfile_name

            try:
                self.fe.get(rfile_name, lfile_name)
            except IOError as e:
                self.__error(str(e))

    def complete_get(self, *args):

        try:
            files = self.fe.ls(add_dirs=False)
        except Exception:
            files = []

        return [i for i in files if i.startswith(args[0])]

    def do_rm(self, args):
        """rm <REMOTE FILE or DIR>
        Delete a remote file or directory.

        Note: only empty directories could be removed.
        """

        if not len(args):
            self.__error("Missing argument: <REMOTE FILE>")
        elif self.__is_open():

            try:
                self.fe.rm(args)
            except IOError as e:
                self.__error(str(e))

    def complete_rm(self, *args):

        try:
            files = self.fe.ls()
        except Exception:
            files = []

        return [i for i in files if i.startswith(args[0])]

    def do_cat(self, args):
        """cat <REMOTE FILE>
        Print the contents of a remote file.
        """

        if not len(args):
            self.__error("Missing argument: <REMOTE FILE>")
        elif self.__is_open():

            try:
                print(self.fe.gets(args))
            except IOError as e:
                self.__error(str(e))

    complete_cat = complete_get

    def do_exec(self, args):
        """exec <STATEMENT>
        Execute a Python statement on remote.
        """

        def data_consumer(data):
            sys.stdout.write(data.strip("\x04"))

        if not len(args):
            self.__error("Missing argument: <STATEMENT>")
        elif self.__is_open():

            try:
                self.fe.exec_raw_no_follow(args + "\n")
                ret = self.fe.follow(None, data_consumer)

                if len(ret[-1]):
                    self.__error(ret[-1])

            except IOError as e:
                self.__error(str(e))
            except PyboardError as e:
                self.__error(str(e[-1]))

    def do_repl(self, args):
        """repl
        Enter Micropython REPL.
        """

        if self.__is_open():

            miniterm = MpTerminal(self.fe.serial)

            self.fe.teardown()

            console.setup()
            miniterm.start()

            print("\n*** Exit REPL with Ctrl+] ***")

            try:
                miniterm.join(True)
            except KeyboardInterrupt:
                pass

            console.cleanup()
            self.fe.setup()
            print("")


def main():

    colorama.init()

    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--command", help="execute given commands (separated by ;)", default=None, nargs="*")
    parser.add_argument("-s", "--script", help="execute commands from file", default=None)
    parser.add_argument("-n", "--noninteractive", help="non interactive mode (don't enter shell)",
                        action="store_true", default=False)

    args = parser.parse_args()

    mpfs = MpFileShell()

    if args.command is not None:

        for cmd in ' '.join(args.command).split(';'):
            scmd = cmd.strip()
            if len(scmd) > 0 and not scmd.startswith('#'):
                mpfs.onecmd(scmd)

    elif args.script is not None:

        f = open(args.script, 'r')
        script = ""

        for line in f:

            sline = line.strip()

            if len(sline) > 0 and not sline.startswith('#'):
                script += sline + '\n'

        sys.stdin = io.StringIO(unicode(script))
        mpfs.intro = ''
        mpfs.prompt = ''

    if not args.noninteractive:

        try:
            mpfs.cmdloop()
        except KeyboardInterrupt:
            print("")


if __name__ == '__main__':

    main()
    '''
    try:
        main()
    except Exception as e:
        sys.stderr.write(str(e) + "\n")
        exit(1)
    '''