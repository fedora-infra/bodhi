# -*- mode: ruby -*-
# vi: set ft=ruby :

# On your host:
# git clone https://github.com/fedora-infra/bodhi.git
# cd bodhi
# cp devel/Vagrantfile.example Vagrantfile
# vagrant up

VAGRANTFILE_API_VERSION = "2"

Vagrant.configure(VAGRANTFILE_API_VERSION) do |config|
 config.vm.box_url = "https://download.fedoraproject.org/pub/fedora/linux/releases/29/Cloud/x86_64/images/Fedora-Cloud-Base-Vagrant-29-1.2.x86_64.vagrant-libvirt.box"
 config.vm.box = "f29-cloud-libvirt"
 config.vm.box_download_checksum = "30a58db024a5203fea0fee8fffcbc1998b3e6de787dbc504dc5c511b97c84777"
 config.vm.box_download_checksum_type = "sha256"

 # Forward traffic on the host to the development server on the guest.
 # You can change the host port that is forwarded to 5000 on the guest
 # if you have other services listening on your host's port 80.
 config.vm.network "forwarded_port", guest: 6543, host: 6543

 # Forward traffic on the host to the RabbitMQ management UI on the guest.
 # This allows developers to view message queues at http://localhost:15672/
 config.vm.network "forwarded_port", guest: 15672, host: 15672

 # This is an optional plugin that, if installed, updates the host's /etc/hosts
 # file with the hostname of the guest VM. In Fedora it is packaged as
 # ``vagrant-hostmanager``
 if Vagrant.has_plugin?("vagrant-hostmanager")
     config.hostmanager.enabled = true
     config.hostmanager.manage_host = true
 end

 # Vagrant can share the source directory using rsync, NFS, or SSHFS (with the vagrant-sshfs
 # plugin). Consult the Vagrant documentation if you do not want to use SSHFS.
 config.vm.synced_folder ".", "/vagrant", disabled: true
 config.vm.synced_folder ".", "/home/vagrant/bodhi", type: "sshfs"

 # To cache update packages (which is helpful if frequently doing `vagrant destroy && vagrant up`)
 # you can create a local directory and share it to the guest's DNF cache. Uncomment the lines below
 # to create and use a dnf cache directory
 #
 # Dir.mkdir('.dnf-cache') unless File.exists?('.dnf-cache')
 # config.vm.synced_folder ".dnf-cache", "/var/cache/dnf", type: "sshfs", sshfs_opts_append: "-o nonempty"

 # Comment this line if you would like to disable the automatic update during provisioning
 config.vm.provision "shell", inline: "sudo dnf upgrade -y"

 # bootstrap and run with ansible
 config.vm.provision "shell", inline: "sudo dnf -y install python2-dnf libselinux-python"
 config.vm.provision "ansible" do |ansible|
     ansible.playbook = "devel/ansible/playbook.yml"
 end


 # Create the bodhi dev box
 config.vm.define "bodhi" do |bodhi|
    bodhi.vm.host_name = "bodhi-dev.example.com"

    bodhi.vm.provider :libvirt do |domain|
        # Season to taste
        domain.cpus = 8
        domain.cpu_mode = "host-passthrough"
        domain.graphics_type = "spice"
        # The unit tests use a lot of RAM.
        domain.memory = 4096
        domain.video_type = "qxl"

        # Enable libvirt's unsafe cache
        # mode. It is called unsafe for a reason, as it causes the virtual host to ignore all
        # fsync() calls from the guest. Only do this if you are comfortable with the possibility of
        # your development guest becoming corrupted (in which case you should only need to do a
        # vagrant destroy and vagrant up to get a new one).
        domain.volume_cache = "unsafe"
    end
 end
end
