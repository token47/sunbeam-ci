# locals
locals {
  cloud_nodes = keys(var.cloud_nodes)
  cluster_nodes = (
    concat(
      local.cloud_nodes,
      [maas_vm_host_machine.juju_controller.id],
      [maas_vm_host_machine.sunbeam-infra.id]
    )
  )
}

# resources
resource "terraform_data" "maas_login" {
  input = {
        maas_url = var.maas_api_url
        maas_api_key = var.maas_api_key
        maas_admin_user = var.maas_admin_user
  }
  provisioner "local-exec" {
    command = "maas login $PROFILE $MAAS_URL $MAAS_API_KEY"
    environment = {
      MAAS_URL = self.input.maas_url
      MAAS_API_KEY = self.input.maas_api_key
      PROFILE = self.input.maas_admin_user
    }
  }
  provisioner "local-exec" {
    command = "maas logout $PROFILE"
    environment = {
      PROFILE = self.input.maas_admin_user
    }
    when = destroy
  }
}

resource "maas_vm_host" "infra_host" {
  type = "lxd"
  machine = var.infra_host
  cpu_over_commit_ratio = 10
  memory_over_commit_ratio = 10
}

resource "time_sleep" "wait_5_seconds" {
  depends_on = [resource.maas_vm_host.infra_host]
  create_duration = "5s"
}

resource "maas_vm_host_machine" "juju_controller" {
  depends_on = [resource.time_sleep.wait_5_seconds]
  vm_host = resource.maas_vm_host.infra_host.id
  hostname = "sunbeam-controller"
  cores   = 2
  memory  = 4096

  storage_disks {
    size_gigabytes = 25
  }
}

resource "maas_vm_host_machine" "sunbeam-client" {
  depends_on = [resource.time_sleep.wait_5_seconds]
  vm_host = resource.maas_vm_host.infra_host.id
  hostname = "sunbeam-client"
  cores   = 2
  memory  = 2048

  storage_disks {
    size_gigabytes = 25
  }
}

output "sunbeam_client" {
  description = "FQDN of sunbeam client"
  value       = resource.maas_instance.sunbeam-client.fqdn
}

resource "maas_vm_host_machine" "sunbeam-infra" {
  depends_on = [resource.time_sleep.wait_5_seconds]
  vm_host = resource.maas_vm_host.infra_host.id
  hostname = "sunbeam-infra"
  cores   = 2
  memory  = 4096

  storage_disks {
    size_gigabytes = 25
  }
}

resource "maas_instance" "sunbeam-client" {
  allocate_params {
    hostname = maas_vm_host_machine.sunbeam-client.hostname
  }
  deploy_params {
    distro_series = var.distro_series
  }
}

resource "maas_tag" "deployment_name" {
  name = "openstack-${var.deployment_name}"
  machines = local.cluster_nodes
}

resource "maas_tag" "juju-controller" {
  name = "juju-controller"
  machines = [
    maas_vm_host_machine.juju_controller.id,
  ]
}

resource "maas_tag" "sunbeam-infra" {
  name = "sunbeam"
  machines = [
    maas_vm_host_machine.sunbeam-infra.id,
  ]
}

resource "maas_tag" "storage" {
  name = "storage"
  machines = local.cloud_nodes
}

resource "maas_tag" "compute" {
  name = "compute"
  machines = local.cloud_nodes
}

resource "maas_tag" "control" {
  name = "control"
  machines = local.cloud_nodes
}

data "maas_machine" "machine" {
  for_each = var.cloud_nodes
  hostname = each.key
}

resource "terraform_data" "apply_block_device_tags" {
  depends_on = [terraform_data.maas_login]
  for_each = var.cloud_nodes

  input = {
    maas_profile = var.maas_admin_user
    tags         = "ceph"
    disk_name = each.value.ceph_disk_name
    hostname = each.key
  }

  provisioner "local-exec" {
    command = "system_id=$(maas $PROFILE machines read hostname=$HOSTNAME | jq -r '.[] | .system_id'); block_device=$(maas $PROFILE block-devices read $system_id | jq -r '.[] | select(.name == \"${self.input.disk_name}\") | .id'); maas $PROFILE block-device add-tag $system_id $block_device tag=$TAGS"
    environment = {
      HOSTNAME = self.input.hostname
      PROFILE   = self.input.maas_profile
      TAGS = self.input.tags
    }
  }

  provisioner "local-exec" {
    command = "system_id=$(maas $PROFILE machines read hostname=$HOSTNAME | jq -r '.[] | .system_id'); block_device=$(maas $PROFILE block-devices read $system_id | jq -r '.[] | select(.name == \"${self.input.disk_name}\") | .id'); maas $PROFILE block-device remove-tag $system_id $block_device tag=$TAGS"
    environment = {
      HOSTNAME = self.input.hostname
      PROFILE   = self.input.maas_profile
      TAGS = self.input.tags
    }
    when = destroy
  }
}

resource "terraform_data" "apply_network_tags" {
  depends_on = [terraform_data.maas_login]
  for_each = var.cloud_nodes

  input = {
    maas_profile = var.maas_admin_user
    tags         = "neutron:physnet1"
    nic = each.value.nic
    hostname = each.key
  }

  provisioner "local-exec" {
    command = "system_id=$(maas $PROFILE machines read hostname=$HOSTNAME | jq -r '.[] | .system_id'); nic=$(maas $PROFILE interfaces read $system_id | jq -r '.[] | select(.name == \"${self.input.nic}\") | .id'); maas $PROFILE interface add-tag $system_id $nic tag=$TAGS"
    environment = {
      HOSTNAME = self.input.hostname
      PROFILE   = self.input.maas_profile
      TAGS = self.input.tags
    }
  }

  provisioner "local-exec" {
    command = "system_id=$(maas $PROFILE machines read hostname=$HOSTNAME | jq -r '.[] | .system_id'); nic=$(maas $PROFILE interfaces read $system_id | jq -r '.[] | select(.name == \"${self.input.nic}\") | .id'); maas $PROFILE interface remove-tag $system_id $nic tag=$TAGS"
    environment = {
      HOSTNAME = self.input.hostname
      PROFILE   = self.input.maas_profile
      TAGS = self.input.tags
    }
    when = destroy
  }
}

resource "terraform_data" "create_api_ranges" {
  depends_on = [terraform_data.maas_login]
  for_each = var.api_ranges

  input = {
    maas_profile = var.maas_admin_user
    cidr = each.value.cidr
    name = "${var.deployment_name}-${each.key}-api"
    start = each.value.start
    end = each.value.end
  }

  provisioner "local-exec" {
    command = "subnet_id=$(maas root subnets read | jq -r '.[] | select(.cidr == \"${self.input.cidr}\") | .id'); maas $PROFILE ipranges create type=reserved subnet=$subnet_id start_ip=$START end_ip=$END comment=$NAME"
    environment = {
      CIDR = self.input.cidr
      PROFILE   = self.input.maas_profile
      START = self.input.start
      END = self.input.end
      NAME = self.input.name
    }
  }

  provisioner "local-exec" {
    command = "range_id=$(maas root ipranges read | jq -r '.[] | select(.comment == \"${self.input.name}\") | .id'); maas $PROFILE iprange delete $range_id"
    environment = {
      CIDR = self.input.cidr
      PROFILE   = self.input.maas_profile
      START = self.input.start
      END = self.input.end
      NAME = self.input.name
    }
    when = destroy
  }
}
