terraform {
  required_version = ">= 0.14.0"
  required_providers {
    maas = {
      source  = "canonical/maas"
      version = "2.3.0"
    }
  }
}

provider "maas" {
  api_version = var.maas_api_version
  api_key     = var.maas_api_key
  api_url     = var.maas_api_url
}
