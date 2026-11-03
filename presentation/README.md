# Contoso IaC presentation

The English deck contains 10 slides for the assignment's 10–15 minute stakeholder discussion. It compares Terraform, AWS CloudFormation and AWS CDK, recommends an ownership model, and connects the recommendation to this repository's EKS and PostgreSQL design.

- [Editable PowerPoint](output/contoso-iac-stakeholder.pptx)
- [Speaker notes and primary sources](speaker-notes.md)
- [JavaScript authoring source](build.mjs)

The architecture diagrams and comparison table are native editable PowerPoint objects. The deck does not claim the AWS implementation has been deployed or integration-tested. The multi-account landing zone is a recommendation, not an additional deployed part of the hands-on task.

## Regeneration

The builder uses the supplied Codex presentation runtime's `@oai/artifact-tool`. It does not use `python-pptx` or PptxGenJS. Node.js, Python, presentation validators and the artifact package must be available. On the authoring computer:

```bash
cd presentation
export PRESENTATION_RUNTIME_ROOT="$HOME/.cache/codex-runtimes/codex-primary-runtime"
export RUNTIME_NODE_MODULES="$PRESENTATION_RUNTIME_ROOT/dependencies/node/node_modules"
export RUNTIME_PYTHON="$PRESENTATION_RUNTIME_ROOT/dependencies/python/bin/python3"
export PRESENTATIONS_SKILL_DIR="$HOME/.codex/plugins/cache/openai-primary-runtime/presentations/26.1020.11618/skills/presentations"
ln -s "$RUNTIME_NODE_MODULES" node_modules  # only if the link does not already exist
PRESENTATION_OUTPUT_NAME=contoso-iac-recommendation-revised.pptx \
  "$PRESENTATION_RUNTIME_ROOT/dependencies/node/bin/node" build.mjs
```

For another computer, set the runtime variables and use its Node executable. This authoring dependency is bundled with Codex and is not a dependency of the AWS application. Choose a new output filename on each revision because validation deliberately refuses to overwrite an existing final deck. The builder exports each slide to `.build/previews/`, exports a candidate deck and runs package, geometry, font, native-table and re-import checks before producing the final file. Inspect every rendered slide before accepting a revision.

Primary AWS and HashiCorp sources are cited in the deck's speaker notes and the Markdown notes. No source assignment PDF, email, account identifier or credential is included.
