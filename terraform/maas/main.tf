terraform {
  required_providers {
    maas = {
      source  = "maas/maas"
      version = "~> 2.0.0"
    }
  }
}

provider "maas" {
  api_key = var.maas_api_key
  api_url = var.maas_api_url
  #api_version = "2.0"
  tls_insecure_skip_verify = true
}

# input variables

variable "maas_hosts_qty" {
  type        = number
  description = "Amount of nodes to deploy"
  default     = 1
}

variable "maas_api_url" {
  type        = string
  description = "URL of parent MAAS api (http://host:5240/MAAS)"
  #default     = ""
}

variable "maas_api_key" {
  type        = string
  description = "API key of parent MAAS"
  #default     = ""
  sensitive = true
}

# output variables

# beware maas returns a LIST of ips in ip_addresses (hence toset() in results)
output "maas_hosts" {
  description = "List of eployed hosts"
  value       = { for i in resource.maas_instance.maas_hosts: i.fqdn => i.ip_addresses }
}

### sample normal output:
#maas_hosts = {
#  "ob76-node6.maas" = toset([
#    "172.27.77.106",
#  ])
#  "ob76-node7.maas" = toset([
#    "172.27.77.107",
#  ])
#  "ob76-node8.maas" = toset([
#    "172.27.77.108",
#  ])
#}
### sample json output:
#{"ob76-node6.maas":["172.27.77.106"],"ob76-node7.maas":["172.27.77.107"],"ob76-node8.maas":["172.27.77.108"]}

# local variables

locals {
  maas_distro = "jammy"
}

# resources

resource "maas_instance" "maas_hosts" {
  count = var.maas_hosts_qty
  allocate_params {
    tags = [
      "jenkins",
    ]
  }
  deploy_params {
    distro_series = local.maas_distro
  }
}
