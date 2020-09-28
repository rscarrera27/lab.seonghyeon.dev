import toml
from fabric import Connection, task

from fabfile.util import ok, log, warn, error


@task
def set_network(c, hostname, ip, gateway_ip):
    if c.run("hostname").stdout.strip() != hostname:
        c.sudo(f"hostnamectl set-hostname {hostname}")
        c.sudo("dhclient -r eth0")
        c.sudo("dhclient eth0")
    else:
        warn("Skipping hostname setup...")

    if f"static ip_address={ip}" not in c.run(f"cat /etc/dhcpcd.conf", hide=True).stdout:
        c.sudo("cp /etc/dhcpcd.conf /etc/dhcpcd.conf.bak")
        c.run(f"echo 'interface eth0\n"
              f"static ip_address={ip}\n"
              f"static routers={gateway_ip}\n"
              f"static domain_name_servers={gateway_ip}' | sudo cat >> /etc/dhcpcd.conf")
    else:
        warn("Skipping static ip setup...")


@task
def set_cmdline_and_config(c):
    if "cgroup" not in c.sudo("cat /boot/cmdline.txt", hide=True).stdout:
        c.run("echo 'cgroup_enable=cpuset cgroup_enable=memory cgroup_memory=1' | sudo tee -a /boot/cmdline.txt")
    else:
        warn("Skipping cgroup setup...")

    if "gpu_mem=16" not in c.sudo("cat /boot/config.txt", hide=True).stdout:
        c.run("echo 'gpu_mem=16' | sudo tee -a /boot/config.txt")
    else:
        warn("Skipping memory split...")


@task
def set_timezone(c, timezone="Asia/Seoul"):
    c.sudo(f"timedatectl set-timezone {timezone}")


@task
def change_password(c, pw):
    c.run(f"echo 'pi:{pw}' | sudo chpasswd")


@task
def update_packages(c):
    log("Upgrading system...")

    c.sudo("apt-get update -y", hide="out")
    c.sudo("apt-get upgrade -y", hide="out")
    c.sudo("apt-get dist-upgrade -y", hide="out")
    c.sudo("apt --fix-broken install -y", hide="out")

    ok("System upgrade complete!")


@task
def get_docker(c):
    if "docker" not in c.run("dpkg --list", hide="out").stdout:
        log("Installing docker...")
        c.sudo("apt-get install apt-transport-https ca-certificates curl gnupg-agent software-properties-common -y")
        c.run("curl -fsSL https://download.docker.com/linux/debian/gpg | sudo apt-key add -")
        c.sudo("add-apt-repository \"deb [arch=arm64] https://download.docker.com/linux/debian $(lsb_release -cs) stable\"")
        c.sudo("apt-get update -y", hide="out")
        c.sudo("apt-get install docker-ce docker-ce-cli containerd.io")
        c.sudo("usermod -aG docker pi")
        ok("Docker successfully installed!")
    else:
        warn("Skipping docker installation...")


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
def reboot(c):
    c.sudo("shutdown -r +0")


@task
def provision(c, file):
    with open(file, "r") as f:
        piconfig_toml = "".join(f.readlines())

    piconfig = toml.loads(piconfig_toml)
    piconfig_network = piconfig["pi"]["network"]
    piconfig_docker = piconfig["pi"]["docker"]

    set_network(c, piconfig_network["hostname"], piconfig_network["ip"], piconfig_network["gateway_ip"])
    set_timezone(c, piconfig["pi"].get("timezone", "Asia/Seoul"))
    set_cmdline_and_config(c)
    update_packages(c)
    get_docker(c)
    join_swarm(c, piconfig_docker["swarm_leader_ip"], piconfig_docker["role"])
    change_password(c, piconfig["pi"]["password"])

    reboot(c)


@task
def generate_profile(c, profile_name):
    print("[pi]")
    password = input("password = ")

    print()
    print("[pi.network]")
    hostname = input("hostname = ")
    ip = input("ip = ")
    gateway_ip = input("gateway_ip = ")

    print()
    print("[pi.docker]")
    swarm_leader_ip = input("swarm_leader_ip = ")
    role = input("role = ")

    profile_obj = {
        "pi": {
            "password": password,
            "network": {
                "hostname": hostname,
                "ip": ip,
                "gateway_ip": gateway_ip,
            },
            "docker": {
                "swarm_leader_ip": swarm_leader_ip,
                "role": role
            }
        }
    }

    profile = toml.dumps(profile_obj)

    c.run(f"echo '{profile}' > {profile_name}.toml ")