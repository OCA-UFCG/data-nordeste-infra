# -*- mode: ruby -*-
# vi: set ft=ruby :

SSH_KEY_PATH = '~/.ssh/id_rsa'

Vagrant.configure("2") do |config|
  config.vm.define "vagrant-datane" do |datane|
    datane.vm.box = "ubuntu/jammy64"
    datane.vm.hostname = "vagrant-datane" 
    datane.vm.network "private_network", ip: "192.168.56.200"

    datane.ssh.insert_key = false
    datane.ssh.private_key_path = ['~/.vagrant.d/insecure_private_key', SSH_KEY_PATH]
    datane.vm.provision "file", source: "#{SSH_KEY_PATH}.pub", destination: "~/.ssh/authorized_keys"
  end

  config.vm.define "vagrant-monitoring" do |datane|
    datane.vm.box = "ubuntu/jammy64"
    datane.vm.hostname = "vagrant-monitoring" 
    datane.vm.network "private_network", ip: "192.168.56.201"

    datane.ssh.insert_key = false
    datane.ssh.private_key_path = ['~/.vagrant.d/insecure_private_key', SSH_KEY_PATH]
    datane.vm.provision "file", source: "#{SSH_KEY_PATH}.pub", destination: "~/.ssh/authorized_keys"
  end

end
