variable "maas_api_version" {
  type    = string
  default = "2.0"
}

variable "maas_api_key" {
  type      = string
  sensitive = true
  default = "abc123"
}

variable "maas_api_url" {
  type = string
  default = "http://ob76-node0.maas:5240/MAAS"
}

variable "maas_admin_user" {
  type = string
  default = "root"
}

variable "infra_host" {
  type = string
}

variable "distro_series" {
  type = string
}

variable "deployment_name" {
  type = string
}

variable "cloud_nodes" {
  type = map(object({
    nic  = string
    ceph_disk_name = string
  }))
}

variable "api_ranges" {
  type = map(object({
    start = string
    end = string
    cidr = string
  }))
}
