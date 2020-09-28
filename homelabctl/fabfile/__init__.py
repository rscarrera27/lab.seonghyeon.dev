from invoke import Collection

from fabfile import pi, util


ns = Collection()
ns.add_collection(pi)
ns.add_collection(util)
