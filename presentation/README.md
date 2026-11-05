# Contoso IaC presentation

The English presentation uses 10 slides for the assignment's 10–15 minute stakeholder discussion. Its scope is delivery and ongoing change of Contoso's AWS landing zone through IaC by a central platform team. It compares Terraform, CloudFormation and AWS CDK for that same responsibility.

## Latest research and content

- [Editable Keynote presentation](output/contoso-iac-stakeholder.key)
- [Research and decision rationale](research.md)
- [Revised speaker notes and primary sources](researched-speaker-notes.md)

The recommendation is CloudFormation as the central team's primary IaC delivery tool. It configures supported Control Tower landing-zone resources and separately owned foundation stacks. Control Tower remains the managed governance service, rather than a replacement for IaC. Terraform and CDK are alternatives for the same team if its established skills or required integrations justify them. HCP Terraform offers managed state; the recommendation does not reject Terraform simply because it uses state.

The delivery workflow follows the benefits slide and makes resource ownership and access controls explicit. The architecture shows code delivering Control Tower configuration and additional foundation stacks. Applications are consumers of the landing zone; application deployment is outside this presentation. Further presentation edits should use the latest native Keynote document as their source.

## Earlier generated baseline

- [Original editable PowerPoint](output/contoso-iac-stakeholder.pptx)
- [Original speaker notes](speaker-notes.md)
- [Original JavaScript authoring source](build.mjs)

These files reflect the earlier baseline, including its Terraform-first recommendation and workload material. They predate the revised research and the user's native Keynote edits. The original PowerPoint contains editable architecture diagrams and a comparison table. Its enterprise landing zone is a proposal; it does not establish a completed AWS deployment.

The hands-on environment also has an [editable draw.io diagram](../docs/architecture.drawio) with AWS icons and separate network and identity pages.

## Separate implementation material

The repository's implementation and demonstration are separate from the landing-zone presentation. Their deployment, testing and teardown commands remain in the [root README](../README.md). The presentation does not claim that the enterprise landing zone has been deployed.

## Regeneration

**The commands below rebuild the earlier baseline. They do not preserve the user's native Keynote edits or apply the revised research and recommendation.**

The builder uses the supplied Codex presentation runtime's `@oai/artifact-tool`. It does not use `python-pptx` or PptxGenJS. Node.js, Python, presentation validators and the artifact package must be available.

The root mise configuration supplies Node.js for the builder. The bundled presentation runtime below remains an additional authoring dependency, including the Python validator environment; installing the project's mise tools alone does not provide the artifact package or validators. The checked-in PowerPoint can be used without regenerating it. After completing the root mise setup, run these commands on the authoring computer:

```bash
cd presentation
export PRESENTATION_RUNTIME_ROOT="$HOME/.cache/codex-runtimes/codex-primary-runtime"
export RUNTIME_NODE_MODULES="$PRESENTATION_RUNTIME_ROOT/dependencies/node/node_modules"
export RUNTIME_PYTHON="$PRESENTATION_RUNTIME_ROOT/dependencies/python/bin/python3"
export PRESENTATIONS_SKILL_DIR="$HOME/.codex/plugins/cache/openai-primary-runtime/presentations/26.1020.11618/skills/presentations"
ln -s "$RUNTIME_NODE_MODULES" node_modules  # only if the link does not already exist
PRESENTATION_OUTPUT_NAME=contoso-iac-baseline-rebuilt.pptx \
  mise exec -- node build.mjs
```

For another computer, set the runtime variables to its authoring-runtime paths. This authoring dependency is bundled with Codex and is not a dependency of the AWS application. Choose a new output filename on each revision because validation deliberately refuses to overwrite an existing final deck. The builder exports each slide to `.build/previews/`, exports a candidate deck and runs package, geometry, font, native-table and re-import checks before producing the final file. Inspect every rendered slide before accepting a revision.

Primary AWS and HashiCorp sources are cited in the deck's speaker notes and the Markdown notes. No source assignment PDF, email, account identifier or credential is included.
