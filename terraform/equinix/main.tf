terraform {
  required_providers {
    equinix = {
      source  = "equinix/equinix"
      version = "~> 1.28"
    }
    random = {
      source  = "hashicorp/random"
      version = "3.6.0"
    }
  }
}

provider "equinix" {
  auth_token = var.equinix_api_key
}

# input variables

variable "equinix_hosts_qty" {
  type        = number
  description = "Amount of nodes to deploy"
  default     = 1
}

variable "equinix_project_id" {
  type        = string
  description = "ID of the project to create hosts in"
  #default     = ""
  sensitive = true
}

variable "equinix_api_key" {
  type        = string
  description = "API key of Equinix Metal"
  #default     = ""
  sensitive = true
}

# output variables

output "equinix_vlans" {
  description = "List of vlans created"
  value       = { "oam" : equinix_metal_vlan.oam_vlan.vxlan, "ovn" : equinix_metal_vlan.ovn_vlan.vxlan }
}

output "equinix_hosts" {
  description = "List of deployed hosts"
  value       = { for i in resource.equinix_metal_device.equinix_hosts : i.hostname => i.access_public_ipv4 }
}

# local variables

locals {
  metro  = "da"           # Dallas
  distro = "ubuntu_22_04" # jammy
  flavor = "c3.small.x86" # smallest = 8C/32GB/2x480G-SSD/2x10Gbps
}

# resources

resource "random_string" "random_suffix" {
  length  = 5
  special = false
  upper   = false
}

resource "equinix_metal_vlan" "oam_vlan" {
  metro       = local.metro
  project_id  = var.equinix_project_id
  description = "TF testing - OAM"
}

resource "equinix_metal_vlan" "ovn_vlan" {
  metro       = "da"
  project_id  = var.equinix_project_id
  description = "TF testing - OVN"
}

resource "equinix_metal_port_vlan_attachment" "oam_vlan_attachment" {
  count     = length(equinix_metal_device.equinix_hosts)
  device_id = equinix_metal_device.equinix_hosts[count.index].id
  port_name = "bond0"
  vlan_vnid = equinix_metal_vlan.oam_vlan.vxlan
}

resource "equinix_metal_port_vlan_attachment" "ovn_vlan_attachment" {
  count     = length(equinix_metal_device.equinix_hosts)
  device_id = equinix_metal_device.equinix_hosts[count.index].id
  port_name = "bond0"
  vlan_vnid = equinix_metal_vlan.ovn_vlan.vxlan
}

resource "equinix_metal_device" "equinix_hosts" {
  count            = var.equinix_hosts_qty
  hostname         = "tf-sunbeam-${random_string.random_suffix.id}-${count.index}"
  plan             = local.flavor
  metro            = local.metro
  operating_system = local.distro
  billing_cycle    = "hourly"
  project_id       = var.equinix_project_id
  #project_ssh_key_ids = "" # if both omited, all keys will be added
  #user_ssh_key_ids    = "" # if both omited, all keys will be added
  ip_address {
    type = "public_ipv4"
  }
  ip_address {
    type = "private_ipv4"
    cidr = 31
  }
}
