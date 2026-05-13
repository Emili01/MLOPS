resource "aws_sfn_state_machine" "mlops_pipeline" {
  name     = "${var.project_name}-pipeline"
  role_arn = aws_iam_role.step_functions_role.arn
  
  definition = templatefile("${path.module}/../scripts/step_functions/workflow.json", {
    glue_job_name  = "fase-a-preprocessing-job"
    sagemaker_role = aws_iam_role.sagemaker_role.arn
    curated_bucket = aws_s3_bucket.datalake.bucket
  })
}