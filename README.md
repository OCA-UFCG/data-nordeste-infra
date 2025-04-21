# datane-infra

## Installation

### Always required
- Install [ansible](https://docs.ansible.com/ansible/latest/installation_guide/intro_installation.html#pipx-install)

### Test required
- Install [vagrant](https://developer.hashicorp.com/vagrant/install)
- Install [virtualbox](https://www.virtualbox.org/wiki/Downloads)

## Configuration

## Certs configuration
1. Add your SSL certs as `./certs/ssl.*` into `./certs`
```
## Example:
certs/
├── ssl.crt
├── ssl.key
└── ssl.pem
```

### Ansible Configuration
1. Configure Ansible inventory in `ansible/hosts.ini`:
```ini
[server]
<ip_vm1> ansible_user=ubuntu ansible_ssh_private_key_file=~/.ssh/id_rsa # aws datane-runner

[monitor]
<ip_vm3> ansible_user=ubuntu ansible_ssh_private_key_file=~/.ssh/id_rsa # aws monitor

[all:vars]
ansible_python_interpreter=/usr/bin/python3
```

2. Configure Ansible vars in `ansible/deploy/vars.yml` and `ansible/monitor/vars.yml`:
```
---
# vars file for roles/deploy
container_port: 3000
container_name: data-nordeste-frontend-beta-app
docker_image: ocaufcg/data-nordeste-frontend-beta
dns_name: <your_dns>

---
# vars file for roles/monitor
dns_name: <your_dns> 
ips_to_monitor: [<ip_vm1>, <ip_vm2>]
mail_app_user: 'mail_user' # emails sender 
mail_app_pass: 'mail_app_password' # password
mail_app_to: 'mail_receiver' # emails receiver
```

## Usage
### Running Ansible Playbooks
1. Run a playbook on the inventory:
```bash
cd ansible
ansible-playbook playbook.yml
```

2. Also, you can run using the Makefile:
```bash
# For initial setup
make ansible-setup

# For deployment
make ansible-deploy

# For monitoring configuration
make ansible-monitor

# To start Docker Compose services for deployment
make compose-deploy

# To start Docker Compose services for monitoring
make compose-monitor
```

## Testing with Vagrant

1. Start the Vagrant environment:
```bash
vagrant up
```

2. To connect to the machines:
```bash
vagrant ssh vagrant-datane
vagrant ssh vagrant-monitoring
```

3. To temporarily stop the machines:
```bash
vagrant halt
```

4. To destroy the environment when no longer needed:
```bash
vagrant destroy
```
