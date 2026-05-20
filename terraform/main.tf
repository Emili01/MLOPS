terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = "us-east-1"
  # ¡Cero credenciales y cero endpoints aquí! Terraform las buscará en tu computadora.
}