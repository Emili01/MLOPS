resource "aws_s3_bucket" "datalake" {
  bucket        = var.s3_bucket_name
  force_destroy = true 
}

resource "terraform_data" "create_s3_folders" {
  depends_on = [aws_s3_bucket.datalake]
  
  provisioner "local-exec" {
    command = <<-EOT
      awslocal s3api put-object --bucket ${var.s3_bucket_name} --key raw/
      awslocal s3api put-object --bucket ${var.s3_bucket_name} --key silver/
      awslocal s3api put-object --bucket ${var.s3_bucket_name} --key models/
    EOT
  }
}
