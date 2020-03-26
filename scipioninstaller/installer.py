# !/usr/bin/env python
import os
import argparse
import sys

from scipioninstaller import INSTALL_ENTRY
# Virtual env programs
from scipioninstaller.launchers import LAUNCHER_TEMPLATE, VIRTUAL_ENV_VAR, ACTIVATE_ENV_CMD

CMD_SEP = " &&\n"
CONDA = 'conda'
SCIPION_ENV = '.scipion3env'
GIT = 'git'
LAUNCHER_NAME = "scipion3"
XMIPP_DEVEL_BRANCH = "python3_migration"

# User answers
YES = "y"
NO = "n"

# Python 2 vs 3 differences
try:
    # Python 2 methods
    ask = raw_input
except:
    # Python 3 methods
    ask = input


def askForInput(message):

    return ask(message)


def getEnvironmentCreationCmd(conda, scipionHome):
    if conda:
        cmd = getCondaCmd()
    else:
        cmd = getVirtualenvCmd(scipionHome)

    return cmd


class InstallationError(Exception):
    pass


def getCondaCmd():

    checkProgram(CONDA)
    cmd = cmdfy(getCondaInitCmd())
    cmd += cmdfy("%s create -n %s python=3" % (CONDA, SCIPION_ENV))
    cmd += cmdfy(getCondaenvActivationCmd())
    return cmd


def getCondaInitCmd():
    shell = os.environ.get("SHELL")
    return 'eval "$(conda shell.%s hook)"' % os.path.basename(shell)


def getCondaenvActivationCmd():
    return "conda activate %s" % SCIPION_ENV


def cmdfy(cmd, sep=CMD_SEP):
    """ Add a command separator like &&\n """
    return cmd + sep


def getVirtualenvCmd(scipionHome):

    cmd = cmdfy("cd %s" % scipionHome)
    cmd += cmdfy("%s -m virtualenv --python=python3 %s" % (sys.executable, SCIPION_ENV))
    cmd += cmdfy(getVirtualenvActivationCmd(scipionHome))
    return cmd


def getVirtualenvActivationCmd(scipionHome):
    return ". %s" % os.path.join(scipionHome, SCIPION_ENV, "bin", "activate")


def checkProgram(program):
    """Check whether `name` is on PATH."""

    from distutils.spawn import find_executable

    if find_executable(program) is None:
        raise InstallationError("%s command not found." % program)


def solveScipionHome(scipionHome, dry):
    # Check folder exists
    if not os.path.exists(scipionHome):

        answer = askForInput("path %s does not exists. Shall I create it? (%s/%s): " % (scipionHome, YES, NO))

        if answer != YES:
            raise InstallationError("Cannot continue without creating %s" % scipionHome)
        else:
            try:
                if not dry:
                    os.mkdir(scipionHome)
                else:
                    print ("%s would have been created." % scipionHome)
            except OSError as e:
                print (e)
                raise InstallationError("Please, verify that you have permissions to create %s" % scipionHome)


def getRepoInstallCommand(scipionHome, repoName, useHttps, organization='scipion-em', branch='devel', pipInstall=True, cloneFolder=''):
    
    # Choose url type: ssh or https
    cloneUrl= 'git@github.com:%s/%s.git' if not useHttps else 'https://github.com/%s/%s.git'

    # replace the repository name
    cloneUrl = cloneUrl % (organization, repoName)
    
    if not os.path.exists(os.path.join(scipionHome, repoName if cloneFolder == '' else cloneFolder)):
        cmd = cmdfy("git clone --branch %s %s %s" % (branch, cloneUrl, cloneFolder))
    else:
        cmd = ""
        print("Print %s repository detected, skipping clone." % repoName)

    if pipInstall:
        cmd += cmdfy("pip install -e %s" % repoName)

    return cmd


def getInstallationCmd(scipionHome, dev, useHttps, noXmipp):
    if dev:
        cmd = cmdfy("cd %s" % scipionHome)
        # Scipion repos
        cmd += getRepoInstallCommand(scipionHome, "scipion-pyworkflow", useHttps)
        cmd += getRepoInstallCommand(scipionHome, "scipion-em", useHttps)
        cmd += getRepoInstallCommand(scipionHome, "scipion-app", useHttps)

        cmd += cmdfy("mkdir -p software/lib")
        cmd += cmdfy("mkdir -p software/bindings")
        cmd += cmdfy("mkdir -p software/em")

        if not noXmipp:
            #Xmipp repos
            cmd += cmdfy("echo '\033[1m\033[95m > Installing Xmipp-dev ...\033[0m'")
            cmd += getRepoInstallCommand(scipionHome, "xmipp", useHttps,
                                         organization='i2pc', branch=XMIPP_DEVEL_BRANCH,
                                         pipInstall=False, cloneFolder='xmipp-bundle')

            cmd += cmdfy("(cd xmipp-bundle && ./xmipp get_devel_sources %s)" % XMIPP_DEVEL_BRANCH)
            cmd += cmdfy("pip install -e xmipp-bundle/src/scipion-em-xmipp")
            cmd += cmdfy("export SCIPION_HOME=%s" % scipionHome)
            cmd += cmdfy("python -m scipion installb xmippDev")
            cmd += cmdfy("rm -rf software/em/xmipp && "
                         "ln -s $PWD/xmipp-bundle/build software/em/xmipp")

    else:
        cmd = cmdfy("pip install scipion-app")
    return cmd


def createLauncher(scipionHome, conda, dry, devel=False):

    if devel:
        # TODO: Contemplate different launcher template (ex: scipion3 git [options])
        content = LAUNCHER_TEMPLATE
    else:
        content = LAUNCHER_TEMPLATE

    if conda:
        replaceDict = {VIRTUAL_ENV_VAR: "CONDA_DEFAULT_ENV",
                        ACTIVATE_ENV_CMD: getCondaInitCmd() + " && " + getCondaenvActivationCmd()}
    else:
        replaceDict = {VIRTUAL_ENV_VAR: "VIRTUAL_ENV",
                        ACTIVATE_ENV_CMD: getVirtualenvActivationCmd(scipionHome)}

    # Replace values
    content = content % replaceDict

    launcherFn = os.path.join(scipionHome, LAUNCHER_NAME)
    if dry:
        print("A python executable script would've been created at %s with the following content:" % launcherFn)
        print("_" * 40)
        print(content)
        print("_" * 40)
    else:
        fh = open(launcherFn, "w")
        fh.write(content)
        fh.close()

    runCmd("chmod +x %s" % launcherFn, dry)

    return launcherFn


def main():
    try:
        # Arg parser configuration
        parser = argparse.ArgumentParser(prog=INSTALL_ENTRY, epilog="Happy Scipioning!")
        parser.add_argument('path',
                            help='Location where you want scipion to be installed.')
        parser.add_argument('-conda',
                            help='Use conda environments, otherwise will use virtualenv',
                            action='store_true')
        parser.add_argument('-dev', help='installs components in devel mode',
                            action='store_true')
        parser.add_argument('-noXmipp', help='Xmipp is installed in devel mode '
                                             'under xmipp-bundle dir by default. '
                                             'This flag skips the Xmipp installation.',
                            action='store_true')
        parser.add_argument('-dry', help='Just shows the commands without running them.',
                            action='store_true')
        
        parser.add_argument('-httpsClone', help='Only when -dev is active, '
                                                'makes git clones using https '
                                                'instead of ssh',
                            action='store_true')
        

        # Parse and fill args
        args = parser.parse_args()
        scipionHome = os.path.abspath(args.path)
        conda = args.conda
         # Warn about conda fonts...
        if conda and askForInput("Conda installations will have a poor font and may"
            " affect your user experience. Are you sure you want to continue? (%s/%s): " % (YES, NO)) !=YES:
            raise InstallationError("Cancelling installation with conda.")

        dev = args.dev
        # TODO: Remove this when releasing scipion3 on pypi.
        dev = True
        if askForInput("This is an early version of the installer. "
                       "So far only works for developers installing an unstable version."
                       "Are you sure you want to continue? (%s/%s): " % (
                                 YES, NO)) != YES:
            raise InstallationError("User cancelled development/unstable installation.")

        dry = args.dry
        checkProgram(GIT) if dev else None
        # Check Scipion home folder and create it if apply.
        solveScipionHome(scipionHome, dry)
        cmd = getEnvironmentCreationCmd(conda, scipionHome)
        cmd += getInstallationCmd(scipionHome, dev, args.httpsClone, args.noXmipp)
        runCmd(cmd, dry)

        launcher = createLauncher(scipionHome, conda, dry, dev)
        if not dry:
            print("\n\nScipion has been successfully installed!! Happy EM processing!!\n\n")
            print("You can launch Scipion using the launcher at %s\n" % launcher )


    except InstallationError as e:
        print (str(e))
        print ("Installation cancelled.")
    except KeyboardInterrupt as e:
        print("\nInstallation cancelled, probably by pressing \"Ctrl + c\".")


def runCmd(cmd, dry):

    # remove last CMD_SEP
    if cmd.endswith(CMD_SEP):
        cmd = cmd[:-len(CMD_SEP)]

    if dry:
        print (cmd)
    else:
        val = os.system(cmd)
        if val != 0:
            raise InstallationError("Something went wrong running: \n %s" % cmd)


if __name__ == '__main__':
    main()


