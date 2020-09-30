import toml
from fabric import Connection, task

from fabfile.util import ok, log, warn, error


@task
def get_sn(c):
    c: Connection

    warn("Make sure you inserted bootstrap card to pi")

    c.run("cat /proc/cpuinfo | tail -4")
    serial_number = c.run("cat /proc/cpuinfo | grep Serial | awk -F ': ' '{print $2}' | tail -c 9", hide=True)
    ok(f"Detected serial number: {serial_number.stdout}")


@task
def setup_pxe_boot(c, file):
    c: Connection

    with open(file, "r") as f:
        piconfig_toml = "".join(f.readlines())

    config = toml.loads(piconfig_toml)
    serial = config["serial_number"]
    network = config["network"]

    nfs_server = "192.168.10.11"

    pxe_root = f"/srv/nfs/rpi4-{serial}"

    # Copy from master copy
    log("Copying files from master copy...")
    c.sudo(f"mkdir -p {pxe_root}", hide="out")
    c.sudo(f"cp -a /srv/nfs/rpi4-master/* {pxe_root}/", hide="out")
    ok("Successfully copied from master copy!")

    # Configure NFS export and TFTP boot mount
    tftp_boot_dir = f"/srv/tftpboot/{serial}"

    log("Configuring NFS export and TFTP boot mount...")
    c.sudo(f"mkdir -p {tftp_boot_dir}", hide="out")
    c.run(f"echo \"{pxe_root}/boot {tftp_boot_dir} none defaults,bind 0 0\" | sudo tee -a /etc/fstab", hide="out")
    c.run(f"echo \"{pxe_root} {network['ip']}(rw,sync,no_subtree_check,no_root_squash)\" | sudo tee -a /etc/exports", hide="out")
    c.sudo(f"mount {tftp_boot_dir}/")
    ok("NFS export and TFTP boot mount was successful!")

    # Configure cmdline for set NFS server
    log("Configuring cmdlines...")
    c.run(f"echo 'console=serial0,115200 console=tty root=/dev/nfs nfsroot={nfs_server}:/srv/nfs/rpi4-{serial},vers=3 rw ip=dhcp rootwait elevator=deadline\n"
          f"cgroup_enable=cpuset cgroup_enable=memory cgroup_memory=1' | sudo tee {pxe_root}/boot/cmdline.txt", hide="out")
    ok("Successfully configured cmdlines!")

    # Configure hostname
    log("Configuring hostname...")
    c.run(f"echo '{network['hostname']}' | sudo tee {pxe_root}/etc/hostname", hide="out")
    ok("Hostname was successfully configured!")

    # Refresh NFS export
    log("Refreshing NFS server...")
    c.sudo("exportfs -ra")
    ok("NFS server was successfully refreshed!")


@task
def join_swarm(c, leader_ip, role):
    node_state = c.sudo("docker info --format '{{.Swarm.LocalNodeState}}'", hide="out").stdout.strip()

    if node_state == "inactive":
        join_token_result = Connection(f"pi@{leader_ip}").run(f"docker swarm join-token {role} --quiet", hide="out")

        if not join_token_result.failed:
            c.sudo(f"docker swarm join --token {join_token_result.stdout.strip()} {leader_ip}:2377")
            ok(f"Successfully joined a swarm as a {role}")
        else:
            error("Error while joining swarm")
    else:
        warn("Skipping swarm join...")


@task
def update_packages(c):
    log("Upgrading system...")

    c.sudo("apt-get update -y", hide="out")
    c.sudo("apt-get upgrade -y", hide="out")
    c.sudo("apt-get dist-upgrade -y", hide="out")
    c.sudo("apt --fix-broken install -y", hide="out")

    ok("System upgrade complete!")