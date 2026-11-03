mock_provider "aws" { override_during = plan }
variables {
  environment       = "dev"
  aws_account_id    = "123456789012"
  state_bucket_name = "contoso-dev-offline-state-example"
}
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

run "test_state_target" {
  command = plan
  variables {
    environment       = "test"
    aws_account_id    = "234567890123"
    state_bucket_name = "contoso-test-offline-state-example"
  }
  assert {
    condition     = aws_s3_bucket.state.bucket == "contoso-test-offline-state-example" && output.environment == "test" && output.aws_account_id == "234567890123"
    error_message = "Test bootstrap state must use its explicitly selected target metadata."
  }
}
run "prod_state_target" {
  command = plan
  variables {
    environment       = "prod"
    aws_account_id    = "345678901234"
    state_bucket_name = "contoso-prod-offline-state-example"
  }
  assert {
    condition     = aws_s3_bucket.state.bucket == "contoso-prod-offline-state-example" && output.environment == "prod"
    error_message = "Prod bootstrap state must use its explicitly selected target metadata."
  }
}
run "reject_unknown_environment" {
  command = plan
  variables { environment = "staging" }
  expect_failures = [var.environment]
}
run "reject_invalid_account_id" {
  command = plan
  variables { aws_account_id = "not-an-account" }
  expect_failures = [var.aws_account_id]
}
