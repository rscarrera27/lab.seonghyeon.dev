from fabric import Connection, task


class TermColors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def warn(t):
    print(TermColors.WARNING + t + TermColors.ENDC)


def error(t):
    print(TermColors.FAIL + t + TermColors.ENDC)


def ok(t):
    print(TermColors.OKGREEN + t + TermColors.ENDC)


def log(t):
    print(TermColors.OKBLUE + t + TermColors.ENDC)


@task
def whoami(c):
    c: Connection

    c.run("echo $(whoami)@$(hostname)")