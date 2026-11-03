mock_provider "aws" { override_during = plan }
variables { state_bucket_name = "contoso-offline-state-example" }
run "state_is_private_encrypted_and_versioned" {
  command = apply
  assert {
    condition     = aws_s3_bucket_public_access_block.state.block_public_acls && aws_s3_bucket_public_access_block.state.block_public_policy && aws_s3_bucket_public_access_block.state.ignore_public_acls && aws_s3_bucket_public_access_block.state.restrict_public_buckets
    error_message = "Terraform state must never be publicly accessible."
  }
  assert {
    condition     = aws_s3_bucket_versioning.state.versioning_configuration[0].status == "Enabled" && one(one(aws_s3_bucket_server_side_encryption_configuration.state.rule).apply_server_side_encryption_by_default).sse_algorithm == "AES256"
    error_message = "State needs encryption and recoverable object versions."
  }
  assert {
    condition     = !aws_s3_bucket.state.force_destroy && jsondecode(aws_s3_bucket_policy.state_tls.policy).Statement[0].Condition.Bool["aws:SecureTransport"] == "false"
    error_message = "Keep state during cleanup and deny unencrypted transport."
  }
}
