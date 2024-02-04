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

locals {
  maas_distro = "jammy"
}

# output variables

output "maas_hosts" {
  value       = resource.maas_instance.maas_hosts.*.fqdn
  description = "List of eployed hosts"
}

# sample output:
# maas_hosts = [
#   "ob76-node1.maas",
#   "ob76-node2.maas",
#   "ob76-node3.maas",
# ]

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